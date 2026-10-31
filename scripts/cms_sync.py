#!/usr/bin/env python3
"""
GIU CMS + portal -> this repo. Runs every 3 hours on your laptop (scripts/install_sync.py), or by hand:

    python3 scripts/cms_sync.py             # sync, then commit + push if anything changed
    python3 scripts/cms_sync.py --dry-run   # list what it would download; writes nothing
    python3 scripts/cms_sync.py --debug     # also save fetched pages to a cache folder (giu-sync)
    python3 scripts/cms_sync.py --log FILE  # append all output to FILE (used by the background job)

Logs into the GIU portal and CMS with Windows (NTLM) auth via curl. Credentials stay on this
laptop: the username in ~/.config/giu/username, the password in the system's secure store
(macOS Keychain, Windows DPAPI, Linux secret-tool). Set or change both with: python3 scripts/giu_login.py

CMS     -> courses/<CODE>/files/<original>, courses/<CODE>/material/<slug>.md, data/cms_index.json
Portal  -> data/grades.json (posted scores), data/deadlines.json (exam seats), data/timetable.json (class times)
Needs only Python 3 (stdlib) and curl. PDF text uses pdftotext (brew install poppler) if present;
scanned PDFs are OCR'd by scripts/pdf_text.py (brew install tesseract).
"""
import argparse
import datetime as dt
import hashlib
import html
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.parse
import zipfile
from html.parser import HTMLParser

try:
    import fcntl
except ImportError:  # Windows
    fcntl = None
    import msvcrt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTAL = "https://portal.giu-uni.de/GIUb/EXTStudent/"
CMS = "https://cms.giu-uni.de"
BIG_FILE = 50 * 1024 * 1024  # originals over this stay out of git (.gitignore)
PERIODS = ["08:30-10:00", "10:15-11:45", "12:00-13:30", "13:45-15:15", "15:45-17:15", "17:45-19:15", "19:45-21:15"]
DAYS = {"sunday": 0, "monday": 1, "tuesday": 2, "wednesday": 3, "thursday": 4, "friday": 5, "saturday": 6}
LOGIN_HINT = "run python3 scripts/giu_login.py in your terminal"


def _short_names():
    """Course code -> plain name, from data/courses.json (the sync adds new courses there)."""
    try:
        with open(os.path.join(ROOT, "data", "courses.json"), encoding="utf-8") as f:
            return {k: v.get("short") or v.get("title") or k for k, v in json.load(f).items()}
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        return {}


SHORT = _short_names()

NETRC = JAR = None   # temp files, set in session()
DEBUG_DIR = None


class AuthError(Exception):
    pass


class SetupError(Exception):
    pass


# ---------- Credentials (saved by scripts/giu_login.py) ----------

def get_credentials():
    from giu_login import load_username, load_password
    user = load_username()
    if not user:
        raise SetupError(f"No GIU username saved: {LOGIN_HINT}")
    password = load_password(user)
    if not password:
        raise SetupError(f"No GIU password saved: {LOGIN_HINT}")
    return user, password


def netrc_token(s):
    # curl 7.84+ understands quoted netrc tokens.
    if re.search(r'[\s"\\]', s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


class session:
    """Writes the netrc (0600) and cookie jar to temp files; always deletes them."""

    def __enter__(self):
        global NETRC, JAR
        user, password = get_credentials()
        fd, NETRC = tempfile.mkstemp(prefix="giu-netrc-")
        if hasattr(os, "fchmod"):  # Windows temp files are already private to the user
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as f:
            for host in ("portal.giu-uni.de", "cms.giu-uni.de"):
                f.write(f"machine {host} login {netrc_token(user)} password {netrc_token(password)}\n")
        fd, JAR = tempfile.mkstemp(prefix="giu-cookies-")
        os.close(fd)
        return self

    def __exit__(self, *exc):
        global NETRC, JAR
        for p in (NETRC, JAR):
            if p:
                try:
                    os.unlink(p)
                except OSError:
                    pass
        NETRC = JAR = None
        return False


# ---------- GIU over curl (NTLM) ----------

def curl(url, data=None, binary=False):
    cmd = ["curl", "-sS", "-L", "--ntlm", "--netrc-file", NETRC, "-b", JAR, "-c", JAR,
           "--max-time", "900" if binary else "90", "-w", "\n__STATUS__%{http_code}", url]
    if data is not None:
        cmd[1:1] = ["--data-raw", data]
    res = subprocess.run(cmd, capture_output=True, check=False)
    body, _, status = res.stdout.rpartition(b"\n__STATUS__")
    status = status.strip().decode() or "error"
    if status == "401":
        raise AuthError(f"GIU password rejected: {LOGIN_HINT}")
    if status != "200":
        why = res.stderr.decode("utf-8", "replace").strip().splitlines()
        raise RuntimeError(f"GET {url.split('?')[0]} -> HTTP {status}" + (f" ({why[-1]})" if why and status == "000" else ""))
    if DEBUG_DIR and not binary:
        name = re.sub(r"[^\w.-]+", "_", url.split("://", 1)[-1])[:120] + (".post" if data else "") + ".html"
        with open(os.path.join(DEBUG_DIR, name), "wb") as f:
            f.write(body)
    return body if binary else body.decode("utf-8", "replace")


def text(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


class Cells(HTMLParser):
    """Collects rows of the table with the given id: [[cell text, ...], ...] (top-level cells only)."""

    def __init__(self, table_id):
        super().__init__()
        self.table_id, self.depth, self.inside, self.rows, self.buf, self.cell_depth = table_id, 0, False, [], None, None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            if not self.inside and a.get("id") == self.table_id:
                self.inside, self.depth = True, 0
            if self.inside:
                self.depth += 1
        if not self.inside:
            return
        if tag == "tr" and self.depth == 1:
            self.rows.append([])
        if tag in ("td", "th") and self.depth == 1:
            self.buf = []
        if tag == "br" and self.buf is not None:
            self.buf.append(" ")

    def handle_endtag(self, tag):
        if not self.inside:
            return
        if tag in ("td", "th") and self.depth == 1 and self.buf is not None:
            self.rows[-1].append(re.sub(r"\s+", " ", "".join(self.buf)).strip())
            self.buf = None
        if tag == "table":
            self.depth -= 1
            if self.depth == 0:
                self.inside = False

    def handle_data(self, d):
        if self.inside and self.buf is not None:
            self.buf.append(d + " ")


def table(html_s, table_id):
    p = Cells(table_id)
    p.feed(html_s)
    return [r for r in p.rows if r]


# ---------- Portal ----------

def courses_from_grades(page):
    out = []
    for value, label in re.findall(r'<option[^>]*value="(\d+)"[^>]*>([^<]+)</option>', page):
        m = re.search(r"-\s*([A-Z]{2,5}\d{3})\s+(.+)$", html.unescape(label).strip())
        if m:
            out.append({"value": value, "code": m.group(1), "title": m.group(2).strip()})
    return out


def parse_schedule(page, courses):
    """Portal timetable parser. Feeds data/timetable.json (see timetable_from_schedule)."""
    rows = table(page, "Table1")
    by_title = sorted(courses, key=lambda c: -len(c["title"]))
    sessions = []
    for row in rows[1:]:
        if not row or row[0].strip().lower() not in DAYS:
            continue
        wd = DAYS[row[0].strip().lower()]
        for i, cell in enumerate(row[1:8]):
            if not cell or cell.lower() == "free":
                continue
            course = next((c for c in by_title if cell.startswith(c["title"])), None)
            rest = cell[len(course["title"]):].strip() if course else cell
            room = re.match(r"([A-Z]\d?\.\d{2,4})", rest)
            kind = "Lecture" if rest.endswith("Lecture") else "Lab" if rest.endswith("Lab") else "Tutorial" if rest.endswith("Tut") else (rest.split() or ["Tutorial"])[-1]
            code = course["code"] if course else None
            name = SHORT.get(code, course["title"] if course else cell.split("  ")[0])
            start, end = PERIODS[i].split("-")
            sessions.append({
                "portalId": f"sched:{wd}:{i + 1}", "courseCode": code,
                "title": f"{name} · {kind}" + (f" ({room.group(1)})" if room else ""),
                "weekday": wd, "start": start.zfill(5), "end": end.zfill(5), "room": room.group(1) if room else None,
                "kind": kind,
            })
    for s in sessions:
        if s["room"] is None:
            del s["room"]
    return sessions


TT_DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]  # index = DAYS value
TT_ORDER = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu", "Fri"]  # GIU week


def schedule_urls(home):
    """Schedule page links on the portal home page first, then the usual names."""
    found = [urllib.parse.urljoin(PORTAL, html.unescape(h)) for h in re.findall(r'href="([^"]*Schedul[^"]*)"', home or "", re.I)]
    guesses = [PORTAL + p for p in ("GroupSchedule_m.aspx", "Scheduling/GroupSchedule_m.aspx", "Scheduling/GroupSchedule.aspx", "GroupSchedule.aspx")]
    return list(dict.fromkeys(u for u in found + guesses if "exam" not in u.lower() and u.startswith(PORTAL)))


def timetable_from_schedule(sessions, courses=()):
    """parse_schedule() output -> data/timetable.json sessions."""
    out, ids = [], set()
    for s in sessions:
        code = s.get("courseCode")
        if not code:
            m = re.search(r"\b([A-Z]{2,5})\s?(\d{3})\b", s.get("title", ""))
            code = m[1] + m[2] if m else None
        k = (s.get("kind") or "").lower()
        kind = "Lecture" if k.startswith("lec") else "Lab" if k.startswith("lab") else "Tutorial"
        if not code:
            continue
        day = TT_DAYS[s["weekday"]]
        sid = f"{day.lower()}-{s['start'].replace(':', '')}"
        n = 2
        while sid in ids:
            sid, n = f"{day.lower()}-{s['start'].replace(':', '')}-{n}", n + 1
        ids.add(sid)
        out.append({"id": sid, "weekday": day, "start": s["start"], "end": s["end"], "course": code, "kind": kind,
                    "room": s.get("room") or "", "title": f"{SHORT.get(code) or next((c['title'] for c in courses if c['code'] == code), code)} · {kind}"})
    out.sort(key=lambda x: (TT_ORDER.index(x["weekday"]), x["start"]))
    return out


MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def norm_date(s):
    s = s.strip()
    if m := re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", s):
        return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}"
    if m := re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s):  # US style m/d/yyyy as used by the CMS
        return f"{int(m[3]):04d}-{int(m[1]):02d}-{int(m[2]):02d}"
    if m := re.search(r"(\d{1,2})\s*[- ]\s*([A-Za-z]{3})[a-z]*\s*[- ]\s*(\d{4})", s):
        return f"{int(m[3]):04d}-{MONTHS[m[2].lower()]:02d}-{int(m[1]):02d}"
    return None


def norm_time(s):
    m = re.search(r"(\d{1,2}):(\d{2})\s*([AaPp][Mm])?", s or "")
    if not m:
        return None
    h = int(m[1]) % 12 + (12 if (m[3] or "").lower() == "pm" else 0) if m[3] else int(m[1])
    return f"{h:02d}:{m[2]}"


def parse_exams(page, courses):
    exams = []
    for t in re.findall(r'<table[^>]*id="([^"]+)"', page):
        rows = table(page, t)
        if not rows or not any("Hall" in c for c in rows[0]):
            continue
        head = [c.lower() for c in rows[0]]
        col = lambda name: next((i for i, h in enumerate(head) if name in h), None)
        for r in rows[1:]:
            if len(r) < len(head):
                continue
            course_txt = r[col("course") or 0]
            date = norm_date(r[col("date")]) if col("date") is not None else None
            if not date:
                continue
            course = next((c for c in courses if c["code"] in course_txt or c["title"].lower() in course_txt.lower()), None)
            kind = r[col("type")] if col("type") is not None else "Exam"
            exams.append({
                "portalId": f"exam:{course['code'] if course else course_txt}:{kind}:{date}",
                "courseCode": course["code"] if course else None,
                "courseText": course_txt, "kind": kind,
                "title": f"{SHORT.get(course['code'], course['title']) if course else course_txt} · {kind}",
                "date": date,
                **({"start": norm_time(r[col("start")])} if col("start") is not None and norm_time(r[col("start")]) else {}),
                **({"hall": r[col("hall")]} if col("hall") is not None else {}),
                **({"seat": r[col("seat")]} if col("seat") is not None else {}),
            })
    return exams


def hidden_fields(page):
    return {n: html.unescape(v) for n, v in re.findall(r'<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"', page)}


def grades(page, courses):
    """Select each course in the Check Grade dropdown and return its grade page."""
    out = []
    select = re.search(r'<select[^>]*name="([^"]*smCrsLst[^"]*)"', page)
    if not select:
        return out
    for c in courses:
        fields = hidden_fields(page)
        fields.update({"__EVENTTARGET": select.group(1), "__EVENTARGUMENT": "", select.group(1): c["value"]})
        res = curl(PORTAL + "CheckGrade_m.aspx", data=urllib.parse.urlencode(fields))
        body = text(res)
        i = body.find("Check Grade")
        chunk = body[i:i + 4000] if i >= 0 else body[:4000]
        # Strip the dropdown's own option list so only grade content remains.
        for cc in courses:
            chunk = chunk.replace(cc["title"], "")
        out.append({"courseCode": c["code"], "text": chunk, "html": res})
    return out


SCORE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:/|out of)\s*(\d+(?:\.\d+)?)\s*$", re.I)


def num(s):
    f = float(s)
    return int(f) if f.is_integer() else f


def _tables_without_id(page):
    """Fallback for grade tables that have no id: rows of every innermost <table>."""
    out = []
    for tb in re.findall(r"<table\b[^>]*>((?:(?!<table\b).)*?)</table>", page, re.S | re.I):
        rows = []
        for tr in re.findall(r"<tr\b[^>]*>(.*?)</tr>", tb, re.S | re.I):
            cells = [text(c) for c in re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", tr, re.S | re.I)]
            if cells:
                rows.append(cells)
        if rows:
            out.append(rows)
    return out


def parse_grade_items(page):
    """Rows like  Quiz 1 | Quiz 1 | 8 / 10 | TA  ->  [{item, score, out_of}]. Only numeric 'x / y' scores."""
    def from_rows(rows):
        found = []
        head = [c.lower() for c in rows[0]] if rows else []
        is_head = not any(SCORE.match(c) for c in rows[0]) if rows else False
        pick = lambda *names: next((i for i, h in enumerate(head) for n in names if n in h), None) if is_head else None
        score_col = pick("grade", "score", "mark")
        item_col = pick("element", "item", "name")
        type_col = pick("quiz", "assignment", "type")
        for r in (rows[1:] if is_head else rows):
            si = score_col if score_col is not None and score_col < len(r) and SCORE.match(r[score_col]) else \
                next((i for i, c in enumerate(r) if SCORE.match(c)), None)
            if si is None:
                continue
            m = SCORE.match(r[si])
            names = [r[i] for i in (item_col, type_col) if i is not None and i < len(r) and i != si and r[i].strip()]
            names += [c for i, c in enumerate(r) if i != si and c.strip() and not re.fullmatch(r"[\d.\s/%-]+", c)]
            if not names or float(m[2]) <= 0:
                continue
            found.append({"item": re.sub(r"\s+", " ", names[0]).strip(" :"), "score": num(m[1]), "out_of": num(m[2])})
        return found

    items = []
    for t in re.findall(r'<table[^>]*id="([^"]+)"', page):
        items += from_rows(table(page, t))
    if not items:
        for rows in _tables_without_id(page):
            items += from_rows(rows)
    seen, out = set(), []
    for it in items:
        k = it["item"].lower()
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out


# ---------- CMS ----------

def cms_courses(home):
    out = []
    for href, label in re.findall(r'href="([^"]*CourseViewStn\.aspx\?id=\d+&(?:amp;)?sid=\d+)"[^>]*>(.*?)</a>', home, re.S):
        t = text(label)
        m = re.search(r"\(\|([A-Z]{2,5}\d{3})\|", t)  # labels are truncated: "(|CTRL101|..."
        if m and not any(o["code"] == m[1] for o in out):
            out.append({"code": m[1], "url": CMS + "/apps/student/" + html.unescape(href).split("/")[-1]})
    return out


def cms_contents(page):
    items = []
    for week in re.split(r'class="card mb-5 weeksdata"', page)[1:]:
        wk = re.search(r"Week:\s*(\d{4}-\d{1,2}-\d{1,2})", text(week[:600]))
        for card in re.split(r'class="card mb-4"', week)[1:]:
            href = re.search(r"""href=['"](/Uploads/[^'"]+)['"]""", card)
            if not href:
                continue
            title = re.search(r'<div id="content\d+">(.*?)</div>', card, re.S) or re.search(r"<strong[^>]*>(.*?)</strong>", card, re.S)
            cid = re.search(r'data-contentid="(\d+)"', card)
            path = html.unescape(href.group(1))
            key = cid.group(1) if cid else hashlib.sha1(path.encode()).hexdigest()[:12]
            items.append({"sourceId": f"cms:{key}", "path": path, "title": text(title.group(1)) if title else path.split("/")[-1], "week": wk.group(1) if wk else None})
    return items


# ---------- Repo: JSON data ----------

def rel(p):
    return os.path.relpath(p, ROOT)


def load_json(name, default):
    try:
        with open(os.path.join(ROOT, "data", name), encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(name, obj):
    path = os.path.join(ROOT, "data", name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, path)


def slug(s, n=60):
    s = re.sub(r"[^a-z0-9]+", "-", s.lower().replace("&", " ")).strip("-")
    return s[:n].rstrip("-") or "item"


def merge_grades(existing, posted, today):
    """posted: [{course, item, score, out_of}]. Keeps every existing entry; matches by course + item."""
    key = lambda c, i: (c, re.sub(r"\s+", " ", i).strip().lower())
    by_key = {key(g.get("course", ""), g.get("item", "")): g for g in existing}
    changes = []
    for p in posted:
        g = by_key.get(key(p["course"], p["item"]))
        if g is None:
            g = {"course": p["course"], "item": p["item"], "score": p["score"], "out_of": p["out_of"],
                 "date": today, "note": "", "source": "portal"}
            existing.append(g)
            by_key[key(p["course"], p["item"])] = g
            changes.append(f"{p['course']} {p['item']}: {p['score']:g}/{p['out_of']:g} (new)")
        elif (g.get("score"), g.get("out_of")) != (p["score"], p["out_of"]):
            old = f"{g.get('score')}/{g.get('out_of')}"
            g["score"], g["out_of"] = p["score"], p["out_of"]
            changes.append(f"{p['course']} {p['item']}: {old} -> {p['score']:g}/{p['out_of']:g}")
    return changes


def merge_exams(deadlines, exams):
    """Exam seats -> deadlines (kind exam, source portal). Same course + date + kind exam = same entry."""
    changes = []
    for e in exams:
        code = e.get("courseCode")
        if not code:
            m = re.search(r"[A-Z]{2,5}\s?\d{3}", e.get("courseText", ""))
            code = m.group(0).replace(" ", "") if m else None
        if not code:
            continue
        title = e.get("kind") or "Exam"
        new = {"id": f"{e['date']}-{code}-{slug(title)}", "course": code, "title": title, "date": e["date"],
               "time": e.get("start"), "weight": None, "kind": "exam", "source": "portal"}
        extra = {k: e[k] for k in ("hall", "seat") if e.get(k)}
        d = next((d for d in deadlines if d.get("id") == new["id"]), None) or \
            next((d for d in deadlines if d.get("course") == code and d.get("date") == e["date"] and d.get("kind") == "exam"), None)
        if d is None:
            new.update(extra)
            deadlines.append(new)
            changes.append(f"{code} {title} {e['date']} (new)")
            continue
        upd = dict(extra)
        if e.get("start"):
            upd["time"] = e["start"]
        upd = {k: v for k, v in upd.items() if d.get(k) != v}
        if upd:
            d.update(upd)
            changes.append(f"{code} {d.get('title', title)} {e['date']}: " + ", ".join(f"{k} {v}" for k, v in upd.items()))
    if changes:
        deadlines.sort(key=lambda d: (d.get("date") or "", d.get("time") or ""))
    return changes


# ---------- Repo: material notes ----------

TYPES = {"lecture slides": "Lecture slides", "lecture notes": "Lecture notes", "lecture": "Lecture slides",
         "tutorial notes": "Tutorial notes", "tutorial slides": "Tutorial notes", "tutorial": "Tutorial notes",
         "supplementary notes": "Supplementary notes", "exercise": "Exercise", "assignment": "Assignment",
         "assignment solution": "Assignment solution", "project": "Project", "other": "Other", "vod": "VoD"}
TYPE_PAREN = re.compile(r"\s*\(\s*((?:lecture|tutorial|tut|lab|supplementary|assignment|exercise|project|other|vod|video|"
                        r"sheet|slides|notes)s?(?:\s+(?:slides|notes|solution|sheet|material)s?)?)\s*\)\s*$", re.I)


def clean_title(t):
    """'3 - Lecture 3 (Lecture Slides)' -> 'Lecture 3'. Only strips a trailing (Type), not '(Carpooling)'."""
    t = re.sub(r"^\s*\d+\s*-\s*", "", t or "")
    t = TYPE_PAREN.sub("", t)
    return re.sub(r"\s+", " ", t).strip()


def title_key(t):
    return clean_title(t).lower()


def infer_type(raw):
    m = TYPE_PAREN.search(raw or "")
    if m and m.group(1).strip().lower() in TYPES:
        return TYPES[m.group(1).strip().lower()]
    t = (raw or "").lower()
    has = lambda *ws: any(re.search(rf"\b{w}s?\b", t) for w in ws)
    if has("solution", "model answer") and has("assignment", "sheet", "practice", "quiz", "exercise"):
        return "Assignment solution"
    if has("tutorial", "tut", "lab", "section"):
        return "Tutorial notes"
    if has("lecture", "slides", "chapter", "ppt"):
        return "Lecture notes" if has("sheet", "notes", "handout") else "Lecture slides"
    if has("assignment", "practice", "quiz", "homework", "sheet", "exercise"):
        return "Assignment"
    if has("project"):
        return "Project"
    if has("vod", "video", "recording"):
        return "VoD"
    return "Other"


def yaml_str(s):
    s = str(s)
    if not s or re.search(r"""^[\s\-?:,\[\]{}#&*!|>'"%@`]|: | #|\s$""", s):
        return json.dumps(s, ensure_ascii=False)
    return s


def read_frontmatter(path):
    with open(path, encoding="utf-8") as f:
        t = f.read()
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    meta = {}
    if m:
        for k, v in re.findall(r"^(\w+):\s*(.*)$", m.group(1), re.M):
            v = v.strip()
            if len(v) >= 2 and v[0] == v[-1] == '"':
                try:
                    v = json.loads(v)
                except ValueError:
                    pass
            meta[k] = v
    return meta, t, m


def course_notes(code):
    """{title key: path} and {cms_id: path} for courses/<code>/material/*.md."""
    by_title, by_id = {}, {}
    folder = os.path.join(ROOT, "courses", code, "material")
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.endswith(".md"):
            continue
        p = os.path.join(folder, name)
        meta, _, _ = read_frontmatter(p)
        by_title.setdefault(title_key(meta.get("title") or name[:-3]), p)
        if meta.get("cms_id"):
            by_id[meta["cms_id"]] = p
    return by_title, by_id


def add_frontmatter(path, fields):
    """Adds the fields that are missing from the note's frontmatter. Returns True if the file changed."""
    meta, t, m = read_frontmatter(path)
    missing = [(k, v) for k, v in fields.items() if not meta.get(k)]
    if not missing:
        return False
    lines = "".join(f"{k}: {yaml_str(v)}\n" for k, v in missing)
    t = (t[:m.end(1)] + "\n" + lines.rstrip("\n") + t[m.end(1):]) if m else f"---\n{lines}---\n\n{t}"
    with open(path, "w", encoding="utf-8") as f:
        f.write(t)
    return True


def safe_filename(cms_path):
    name = urllib.parse.unquote(cms_path.split("/")[-1]).strip()
    name = re.sub(r"[^\w.()\- ]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip(" ._") or "file"
    stem, ext = os.path.splitext(name)
    if len(name) > 120:
        name = stem[:120 - len(ext)].rstrip() + ext
    return name


def pick_file_path(code, name, key, data_sha):
    folder = os.path.join(ROOT, "courses", code, "files")
    p = os.path.join(folder, name)
    if os.path.exists(p) and sha256_file(p) != data_sha:
        stem, ext = os.path.splitext(name)
        p = os.path.join(folder, f"{stem}-{key}{ext}")
    return p


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# ---------- Text extraction ----------

def find_pdftotext():
    return shutil.which("pdftotext") or next((p for p in ("/opt/homebrew/bin/pdftotext", "/usr/local/bin/pdftotext") if os.path.exists(p)), None)


def _xml_text(xml, para, run, extra):
    xml = re.sub(rf"<{para}\b[^>]*/>", "\n", xml)
    out = []
    for p in re.findall(rf"<{para}\b[^>]*>(.*?)</{para}>", xml, re.S):
        for tag, rep in extra.items():
            p = re.sub(rf"<{tag}\b[^>]*/>", rep, p)
        bits = re.findall(rf"<{run}(?:\s[^>]*)?>(.*?)</{run}>|(\n|\t)", p, re.S)
        out.append(html.unescape("".join(a or b for a, b in bits)).rstrip())
    return "\n".join(out).strip()


def _zip_read(z, name, limit=100 * 1024 * 1024):
    if z.getinfo(name).file_size > limit:
        return ""
    return z.read(name).decode("utf-8", "replace")


def pptx_text(path):
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        slides = []
        try:  # presentation order, from presentation.xml + its rels
            rels = dict(re.findall(r'<Relationship\b[^>]*Id="([^"]+)"[^>]*Target="([^"]+)"', _zip_read(z, "ppt/_rels/presentation.xml.rels")))
            rels.update({k: v for v, k in re.findall(r'<Relationship\b[^>]*Target="([^"]+)"[^>]*Id="([^"]+)"', _zip_read(z, "ppt/_rels/presentation.xml.rels"))})
            for rid in re.findall(r'<p:sldId\b[^>]*r:id="([^"]+)"', _zip_read(z, "ppt/presentation.xml")):
                tgt = rels.get(rid, "")
                tgt = tgt.lstrip("/") if tgt.startswith("/") else os.path.normpath("ppt/" + tgt).replace(os.sep, "/")
                if tgt in names:
                    slides.append(tgt)
        except KeyError:
            slides = []
        if not slides:
            slides = sorted((n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)),
                            key=lambda n: int(re.search(r"(\d+)\.xml$", n).group(1)))
        parts = []
        for i, n in enumerate(slides, 1):
            body = _xml_text(_zip_read(z, n), "a:p", "a:t", {"a:br": "\n", "a:tab": "\t"})
            parts.append(f"--- Slide {i}\n\n{body}".rstrip())
        return "\n\n".join(parts) if any(re.sub(r"--- Slide \d+", "", p).strip() for p in parts) else ""


def docx_text(path):
    with zipfile.ZipFile(path) as z:
        return _xml_text(_zip_read(z, "word/document.xml"), "w:p", "w:t", {"w:br": "\n", "w:tab": "\t", "w:cr": "\n"})


def extract_text(path):
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".pdf":
            exe = find_pdftotext()
            if not exe:
                return None
            r = subprocess.run([exe, "-layout", "-enc", "UTF-8", path, "-"], capture_output=True, timeout=300)
            t = r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""
            if len(re.sub(r"\s", "", t)) < 200:  # scanned PDF (no text layer): OCR it
                try:
                    from pdf_text import pdf_text
                    t = pdf_text(path) or t
                except Exception:
                    pass
        elif ext == ".pptx":
            t = pptx_text(path)
        elif ext == ".docx":
            t = docx_text(path)
        else:
            return None
    except Exception:
        return None
    t = "\n".join(line.rstrip() for line in t.replace("\f", "\n\n").splitlines())
    t = re.sub(r"\n{4,}", "\n\n\n", t).strip("\n")
    return t if t.strip() else None


HUB = """---
course: {code}
title: {title}
tags: [course]
---
# {code} · {name}

**Grading:** not filled in yet. The tutor reads it from the course outline (`/setup` or `/sync`).

## Exam focus
- Not filled in yet.

## How to study
- 

## Professor notes
- 

## Open questions
- 

## Material
<!-- material:start -->
<!-- material:end -->

## Notes
<!-- notes:start -->
<!-- notes:end -->
"""


def ensure_course(code, title=None):
    """New course -> data/courses.json entry + courses/<CODE>/<CODE>.md hub. True if anything was added."""
    courses = load_json("courses.json", {})
    added = False
    entry = courses.get(code)
    if entry is None:
        courses[code] = {"title": title or code, "short": title or code}
        added = True
    elif title and entry.get("title") in (None, "", code):
        entry["title"] = title
        if entry.get("short") in (None, "", code):
            entry["short"] = title
        added = True
    if added:
        save_json("courses.json", courses)
        SHORT[code] = courses[code]["short"]
    hub = os.path.join(ROOT, "courses", code, f"{code}.md")
    name = courses[code]["title"]
    if not os.path.exists(hub):
        os.makedirs(os.path.dirname(hub), exist_ok=True)
        with open(hub, "w", encoding="utf-8") as f:
            f.write(HUB.format(code=code, title=yaml_str(name), name=name))
        added = True
    elif name != code:  # hub made before the portal named the course: fill the name in
        with open(hub, encoding="utf-8") as f:
            text = f.read()
        placeholder = f"title: {code}\n"
        if placeholder in text and f"# {code} · {code}\n" in text:
            text = text.replace(placeholder, f"title: {yaml_str(name)}\n", 1).replace(f"# {code} · {code}\n", f"# {code} · {name}\n", 1)
            with open(hub, "w", encoding="utf-8") as f:
                f.write(text)
            added = True
    return added


def write_note(code, item, file_rel_course, text_body):
    title = clean_title(item["title"]) or item["title"]
    folder = os.path.join(ROOT, "courses", code, "material")
    os.makedirs(folder, exist_ok=True)
    base = slug(title)
    p, n = os.path.join(folder, base + ".md"), 2
    while os.path.exists(p):
        p, n = os.path.join(folder, f"{base}-{n}.md"), n + 1
    fm = [("title", title), ("course", code), ("type", infer_type(item["title"])), ("source", "cms"),
          ("cms_id", item["sourceId"]), ("file", file_rel_course)]
    if item.get("week"):
        fm.append(("week", item["week"]))
    body = text_body if text_body else f"(Open the original: [[{file_rel_course}]])"
    with open(p, "w", encoding="utf-8") as f:
        f.write("---\n" + "".join(f"{k}: {yaml_str(v)}\n" for k, v in fm) + "---\n\n"
                "## Summary\n\n(none yet)\n\n## Full text\n\n" + body + "\n")
    return p


def gitignore_big(path):
    line = "/" + rel(path).replace(os.sep, "/")
    gi = os.path.join(ROOT, ".gitignore")
    cur = open(gi, encoding="utf-8").read() if os.path.exists(gi) else ""
    if line not in cur.splitlines():
        with open(gi, "a", encoding="utf-8") as f:
            f.write(("" if cur.endswith("\n") or not cur else "\n") + line + "\n")


# ---------- Git ----------

def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def git_start():
    git("checkout", "--", "NOW.md")  # generated file; regenerated at the end
    if not git("remote").stdout.strip():
        return True  # local-only copy: nothing to pull
    r = git("pull", "--rebase", "--autostash", "-q")
    if r.returncode != 0 and any(os.path.isdir(os.path.join(ROOT, ".git", d)) for d in ("rebase-merge", "rebase-apply")):
        git("rebase", "--abort")  # never leave the repo mid-rebase
    return r.returncode == 0


def git_finish(changed, n_new):
    status = "nothing changed"
    if changed:
        git("add", "-A")
        if git("diff", "--cached", "--quiet").returncode != 0:
            r = git("commit", "-q", "-m", f"sync: CMS/portal ({n_new} new file{'' if n_new == 1 else 's'})")
            if r.returncode != 0:
                return "commit failed: " + ((r.stderr or r.stdout).strip().splitlines() or ["?"])[-1]
            status = "committed"
    ahead = git("rev-list", "--count", "@{u}..HEAD")  # also retries a push that failed last time
    if ahead.returncode == 0 and ahead.stdout.strip() not in ("", "0"):
        r = git("push", "-q")
        status = "pushed" if r.returncode == 0 else f"{status}; push failed (retries next run)"
    return status


# ---------- Run ----------

def now_cairo():
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("Africa/Cairo"))
    except Exception:
        return dt.datetime.now()


def t12(d):
    return d.strftime("%I:%M %p").lstrip("0")


class Run:
    def __init__(self, dry):
        self.dry = dry
        self.errors, self.new_files, self.notes_new, self.notes_linked = [], [], [], []
        self.grade_changes, self.exam_changes, self.big, self.cms_counts = [], [], [], {}
        self.timetable_change = ""
        self.changed = False

    def step(self, name, fn):
        try:
            return fn()
        except AuthError:
            raise
        except Exception as e:  # keep going; report at the end
            self.errors.append(f"{name}: {e}")
            return None

    # -- portal --
    def portal(self):
        today = now_cairo().date().isoformat()
        home = self.step("portal home", lambda: curl(PORTAL + "Home.aspx"))
        home_ok = home is not None
        grade_page = self.step("grades page", lambda: curl(PORTAL + "CheckGrade_m.aspx")) or ""
        courses = courses_from_grades(grade_page)
        if not self.dry:
            for c in courses:
                self.changed |= ensure_course(c["code"], c["title"])
        self.step("timetable", lambda: self.timetable(home, courses, today))
        exams = self.step("exam seats", lambda: parse_exams(curl(PORTAL + "ViewExamSeat_m.aspx"), courses)) or []
        g = self.step("grades", lambda: grades(grade_page, courses)) or []
        posted = []
        for page in g:
            items = parse_grade_items(page["html"])
            if not items and re.search(r"\d\s*/\s*\d", page["text"]):
                self.errors.append(f"grades {page['courseCode']}: scores on the page but not parsed (run with --debug)")
            posted += [dict(it, course=page["courseCode"]) for it in items]
        grades_data = load_json("grades.json", [])
        self.grade_changes = merge_grades(grades_data, posted, today)
        deadlines = load_json("deadlines.json", [])
        self.exam_changes = merge_exams(deadlines, exams)
        if not self.dry:
            if self.grade_changes:
                save_json("grades.json", grades_data)
            if self.exam_changes:
                save_json("deadlines.json", deadlines)
        self.changed |= bool(self.grade_changes or self.exam_changes)
        return home_ok or bool(grade_page)

    def timetable(self, home, courses, today):
        """Portal schedule -> data/timetable.json. Written only when the sessions changed; never emptied."""
        if home is None:
            return
        sessions = []
        for url in schedule_urls(home):
            try:
                sessions = timetable_from_schedule(parse_schedule(curl(url), courses), courses)
            except (AuthError, RuntimeError):  # page missing or not ours: try the next one
                continue
            if sessions:
                break
        if not sessions:
            self.errors.append("timetable: no schedule found on the portal (kept data/timetable.json; run with --debug)")
            return
        old = load_json("timetable.json", {})
        if isinstance(old, dict) and old.get("source") == "portal" and old.get("sessions") == sessions:
            return
        self.timetable_change = f"{len(sessions)} sessions" + (" (would update)" if self.dry else " (updated)")
        if not self.dry:
            save_json("timetable.json", {"updated": today, "source": "portal", "timezone": "Africa/Cairo", "sessions": sessions})
            self.changed = True

    # -- CMS --
    def cms(self):
        index = load_json("cms_index.json", {})
        home = self.step("cms home", lambda: curl(CMS + "/apps/student/HomePageStn.aspx"))
        if home is None:
            return False
        courses = cms_courses(home)
        if not courses:
            self.errors.append("cms home: no courses found on the page")
        for c in courses:
            code = c["code"]
            if not self.dry:
                self.changed |= ensure_course(code)
            page = self.step(f"cms {code}", lambda: curl(c["url"])) or ""
            items = cms_contents(page)
            self.cms_counts[code] = len(items)
            by_title, by_id = course_notes(code)
            for item in items:
                if item["sourceId"] in index:
                    continue
                name = safe_filename(item["path"])
                existing = by_id.get(item["sourceId"]) or by_title.get(title_key(item["title"]))
                if self.dry:
                    where = f"links to {rel(existing)}" if existing else "new note"
                    self.new_files.append(f"{code}: {item['title']} -> courses/{code}/files/{name} ({where})")
                    continue
                data = self.step(f"download {code} {item['title']}", lambda: curl(CMS + item["path"].replace(" ", "%20"), binary=True))
                if not data:
                    continue
                sha = hashlib.sha256(data).hexdigest()
                key = item["sourceId"].split(":", 1)[-1]
                fpath = pick_file_path(code, name, key, sha)
                os.makedirs(os.path.dirname(fpath), exist_ok=True)
                with open(fpath, "wb") as f:
                    f.write(data)
                if len(data) > BIG_FILE:
                    gitignore_big(fpath)
                    self.big.append(rel(fpath))
                file_ref = "files/" + os.path.basename(fpath)
                if existing:
                    if add_frontmatter(existing, {"file": file_ref, "cms_id": item["sourceId"]}):
                        self.notes_linked.append(rel(existing))
                    note = existing
                else:
                    note = write_note(code, item, file_ref, extract_text(fpath))
                    self.notes_new.append(rel(note))
                    by_title.setdefault(title_key(item["title"]), note)
                by_id[item["sourceId"]] = note
                index[item["sourceId"]] = {
                    "sourceId": item["sourceId"], "course": code, "title": item["title"], "week": item["week"],
                    "path": rel(fpath), "note": rel(note), "downloaded_at": now_cairo().isoformat(timespec="seconds"),
                    "sha256": sha,
                }
                save_json("cms_index.json", index)  # after every file, so a cut-off run keeps its progress
                self.new_files.append(f"{code}: {clean_title(item['title']) or item['title']}")
                self.changed = True
        return True

    def report(self, git_status):
        L = [f"GIU sync · {now_cairo():%a} {now_cairo().day} {now_cairo():%b} {t12(now_cairo())}" + (" · DRY RUN" if self.dry else "")]
        if self.cms_counts:
            L.append("- CMS: " + ", ".join(f"{k} {v}" for k, v in self.cms_counts.items()) + " items")
        verb = "would download" if self.dry else "new files"
        L.append(f"- {len(self.new_files)} {verb}" + (":" if self.new_files else ""))
        L += [f"  - {x}" for x in self.new_files[:40]]
        if len(self.new_files) > 40:
            L.append(f"  - … and {len(self.new_files) - 40} more")
        if self.notes_new or self.notes_linked:
            L.append(f"- Notes: {len(self.notes_new)} new, {len(self.notes_linked)} existing linked to originals")
        if self.grade_changes:
            L.append("- Grades: " + "; ".join(self.grade_changes))
        if self.exam_changes:
            L.append("- Exams: " + "; ".join(self.exam_changes))
        if self.timetable_change:
            L.append("- Timetable: " + self.timetable_change)
        if self.big:
            L.append("- Over 50 MB, kept out of git: " + ", ".join(self.big))
        for e in self.errors:
            L.append(f"- Problem: {e}")
        if git_status:
            L.append(f"- Git: {git_status}")
        print("\n".join(L), flush=True)


def lock():
    d = os.path.join(ROOT, ".git") if os.path.isdir(os.path.join(ROOT, ".git")) else tempfile.gettempdir()
    f = open(os.path.join(d, "giu-sync.lock"), "w")
    waited = False
    for _ in range(180):  # wait up to 15 min for another run (e.g. the background job) to finish
        try:
            if fcntl:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            else:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return f, waited
        except OSError:  # held by another run (BlockingIOError on Mac/Linux)
            if not waited:
                print("Another GIU sync is running; waiting for it to finish…", flush=True)
            waited = True
            time.sleep(5)
    raise SetupError("Another GIU sync is still running; try again later")


def main(argv=None):
    global DEBUG_DIR
    ap = argparse.ArgumentParser(description="Sync GIU CMS files and portal grades/exams into this repo.")
    ap.add_argument("--dry-run", action="store_true", help="list what would be downloaded; write nothing")
    ap.add_argument("--debug", action="store_true", help="save fetched pages to a cache folder (giu-sync)")
    ap.add_argument("--log", metavar="FILE", help="append all output to FILE (the background job uses this)")
    ap.add_argument("--no-git", action="store_true", help="skip git pull/commit/push")
    args = ap.parse_args(argv)
    if args.log:
        sys.stdout = sys.stderr = open(args.log, "a", encoding="utf-8", buffering=1)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))  # so temp credentials are always cleaned up

    if args.debug:
        base = "~/Library/Caches" if os.path.isdir(os.path.expanduser("~/Library")) else "~/.cache"
        DEBUG_DIR = os.path.expanduser(os.path.join(base, "giu-sync"))
        os.makedirs(DEBUG_DIR, mode=0o700, exist_ok=True)

    use_git = not args.dry_run and not args.no_git
    run = Run(args.dry_run)
    try:
        lk, waited = lock()
        if waited:
            print("(Another sync just finished; its result is in the background sync log.)", flush=True)
        if use_git and not git_start():
            run.errors.append("git pull failed (offline?); syncing anyway")
        with session():
            portal_ok = run.portal()
            cms_ok = run.cms()
    except AuthError as e:
        print(str(e), file=sys.stderr, flush=True)
        return 2
    except SetupError as e:
        print(str(e), file=sys.stderr, flush=True)
        return 1

    status = ""
    if not args.dry_run:
        for script in ("index.py", "now.py"):
            r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", script)], cwd=ROOT, capture_output=True, text=True)
            if r.returncode != 0:
                run.errors.append(f"{script} failed: " + ((r.stderr or "").strip().splitlines() or ["?"])[-1])
        if use_git:
            status = git_finish(run.changed, len(run.new_files))
    run.report(status)
    lk.close()
    return 0 if (portal_ok or cms_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
