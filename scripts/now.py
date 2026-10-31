#!/usr/bin/env python3
"""Regenerate NOW.md, the one page the student looks at.

Reads data/*.json and writes NOW.md. Safe to run any time:
    python3 scripts/now.py
"""
import datetime as dt
import json
import os
import re
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    TZ = ZoneInfo("Africa/Cairo")
except Exception:  # Windows without the tzdata package: the laptop's own time zone (it's in Cairo)
    TZ = dt.datetime.now().astimezone().tzinfo


def load(name, default):
    path = os.path.join(ROOT, "data", name)
    try:
        if name.endswith(".jsonl"):
            with open(path, encoding="utf-8") as f:
                return [json.loads(l) for l in f if l.strip()]
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def t12(hhmm):
    if not hhmm:
        return ""
    h, m = map(int, hhmm.split(":"))
    return f"{(h + 11) % 12 + 1}:{m:02d} {'PM' if h >= 12 else 'AM'}"


def when(n):
    return "today" if n == 0 else "tomorrow" if n == 1 else f"in {n} days"


def flag(n):
    return "🔴" if n <= 3 else "🟠" if n <= 7 else "🟡" if n <= 14 else "⚪"


now = dt.datetime.now(TZ)
today = now.date()
deadlines = load("deadlines.json", [])
grades = load("grades.json", [])
weak = load("weak-spots.json", [])
nxt = load("next.json", [])
missed = load("missed.json", [])
log = load("log.jsonl", [])
checkins = load("checkins.json", [])
courses = load("courses.json", {})
try:
    with open(os.path.join(ROOT, "me.md"), encoding="utf-8") as f:
        set_up = "setup: false" not in f.read(500)
except FileNotFoundError:
    set_up = False

up = []
for d in deadlines:
    try:
        day = dt.date.fromisoformat(d["date"])
    except Exception:
        continue
    n = (day - today).days
    if n >= 0:
        up.append((n, d.get("time") or "", d, day))
up.sort(key=lambda x: (x[0], x[1]))

L = []
L.append(f"# Now: {today:%a} {today.day} {today:%b}")
L.append("")
L.append(f"_Updated {now.strftime('%I:%M %p').lstrip('0')} Cairo. Run `python3 scripts/now.py` to refresh._")
L.append("")

L.append("## Do this next")
L.append("")
if nxt:
    top = nxt[0]
    L.append(f"**{top['course']}: {top['task']}**")
    L.append(f"- {top.get('minutes', 20)} min · [[{top['course']}]] · {top.get('why', '')}")
    if top.get("file"):
        L.append(f"- Open: `{top['file']}`")
    L.append("")
    if len(nxt) > 1:
        L.append("Then:")
        for t in nxt[1:5]:
            L.append(f"- {t['course']}: {t['task']} ({t.get('minutes', 20)} min)")
        L.append("")
else:
    L.append("Ask the tutor: `/plan`" if set_up else "New here? Open this folder in Claude Code and run `/setup`.")
    L.append("")

due_reviews = [m for m in missed if m.get("next_review", "9999") <= today.isoformat()]
if due_reviews:
    L.append(f"**{len(due_reviews)} missed question(s) due for review** → `/quiz`")
    L.append("")

L.append("## Due soon")
L.append("")
soon = [u for u in up if u[0] <= 21]
if soon:
    L.append("| | When | What | Course | Weight | What it is |")
    L.append("|---|---|---|---|---|---|")
    for n, _, d, day in soon:
        w = f"{d['weight']:g}%" if d.get("weight") else ""
        tm = f", {t12(d.get('time'))}" if d.get("time") else ""
        title = re.sub(r'\s*\(\d+%\)', '', d['title'])
        seat = ", ".join(x for x in (d.get("hall") and f"hall {d['hall']}", d.get("seat") and f"seat {d['seat']}") if x)
        title += f" ({seat})" if seat else ""
        L.append(f"| {flag(n)} | {day:%a} {day.day} {day:%b}{tm} ({when(n)}) | {title} | [[{d['course']}]] | {w} | {d.get('scope') or '❓ not verified'} |")
else:
    L.append("Nothing graded in the next 3 weeks.")
L.append("")
later = [u for u in up if u[0] > 21][:5]
if later:
    L.append("Later: " + " · ".join(f"{d['course']} {d['title']} ({day.day} {day:%b})" for _, _, d, day in later))
    L.append("")

_up = os.path.join(ROOT, "data", "unscheduled.json")
_unsched = json.load(open(_up)) if os.path.exists(_up) else []
if _unsched:
    L.append("**No date yet (ask):** " + " · ".join(f"{u['course']} {u['title']} → {u['ask']}" for u in _unsched))
    L.append("")

L.append("## Weak spots")
L.append("")
ws = sorted([w for w in weak], key=lambda w: (w.get("recall") is not None, w.get("recall") or 0))
for w in ws[:6]:
    r = "?" if w.get("recall") is None else f"{round(w['recall'] * 100)}%"
    note = f" · {w['note']}" if w.get("note") else ""
    L.append(f"- [[{w['course']}]] {w['topic']}: recall {r}{note}")
L.append("")

L.append("## Grades so far")
L.append("")
if grades:
    for g in grades:
        pct = round(100 * g["score"] / g["out_of"]) if g.get("out_of") else None
        note = f" · {g['note']}" if g.get("note") else ""
        L.append(f"- [[{g['course']}]] {g['item']}: {g['score']:g}/{g['out_of']:g}" + (f" ({pct}%)" if pct is not None else "") + note)
else:
    L.append("None posted yet.")
L.append("")

L.append("## Last 7 days")
L.append("")
week_ago = now - dt.timedelta(days=7)
recent = []
for e in log:
    try:
        ts = dt.datetime.fromisoformat(e["ts"])
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=TZ)
    except Exception:
        continue
    if ts >= week_ago and e.get("type") in ("study", "quiz", "reply"):
        recent.append((ts, e))
mins = sum((e.get("minutes") or 0) for _, e in recent)
quiz = [e for _, e in recent if e.get("type") == "quiz" and e.get("score") is not None]
if recent:
    L.append(f"- {len({ts.date() for ts, _ in recent})} study day(s), {mins} min")
    if quiz:
        L.append(f"- Quiz: {sum(1 for e in quiz if e['score'])}/{len(quiz)} right")
    last = recent[-1][1]
    L.append(f"- Last: {last.get('course') or ''} {last.get('topic') or ''}".rstrip())
else:
    L.append("- Nothing logged yet. Start with the top item above.")
L.append("")

L.append("## Courses")
L.append("")
L.append(" · ".join(f"[[{c}]]" for c in sorted(courses)) or "None yet. They appear after the first `/sync`.")
L.append("")

with open(os.path.join(ROOT, "NOW.md"), "w", encoding="utf-8") as f:
    f.write("\n".join(L))
print("NOW.md updated")
