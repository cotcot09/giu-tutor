#!/usr/bin/env python3
"""Read any PDF as text, scanned pages included (OCR).

    python3 scripts/pdf_text.py FILE.pdf                 # whole PDF to stdout
    python3 scripts/pdf_text.py FILE.pdf --pages 12-20   # some pages (also 3,5,9-11)
    python3 scripts/pdf_text.py --scanned                # material notes whose Full text is still empty
    python3 scripts/pdf_text.py --fill NOTE.md [...]     # write the PDF's text into a material note's "## Full text"

Pages with a text layer use pdftotext. Pages without one (scans, Canva exports) are OCR'd:
pdftoppm renders the page, tesseract reads it. Needs poppler + tesseract
(Mac: brew install poppler tesseract · Windows: scoop install poppler tesseract · Linux: apt install poppler-utils tesseract-ocr).
Each page starts with "--- Page N" (or "--- Page N (OCR)"), so answers can cite the page.
"""
import argparse
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIN_CHARS = 40    # a page with fewer non-space characters than this is treated as a scan
STUB_CHARS = 200  # a note whose Full text is shorter than this has no real text yet


def tool(name):
    return shutil.which(name) or next((p for p in (f"/opt/homebrew/bin/{name}", f"/usr/local/bin/{name}") if os.path.exists(p)), None)


def page_count(path):
    r = subprocess.run([tool("pdfinfo"), path], capture_output=True, text=True, timeout=60)
    m = re.search(r"^Pages:\s+(\d+)", r.stdout, re.M)
    return int(m.group(1)) if m else 0


def text_layer(path, n):
    r = subprocess.run([tool("pdftotext"), "-layout", "-enc", "UTF-8", "-f", str(n), "-l", str(n), path, "-"],
                       capture_output=True, timeout=120)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""


def ocr(path, n, lang, dpi=300):
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "page")
        subprocess.run([tool("pdftoppm"), "-r", str(dpi), "-png", "-singlefile", "-f", str(n), "-l", str(n), path, base],
                       capture_output=True, timeout=300, check=True)
        r = subprocess.run([tool("tesseract"), base + ".png", "-", "-l", lang], capture_output=True, timeout=300)
        return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""


def read_page(path, n, lang):
    t = text_layer(path, n)
    if len(re.sub(r"\s", "", t)) >= MIN_CHARS or not tool("tesseract"):
        return n, False, t
    return n, True, ocr(path, n, lang)


def clean(t):
    t = "\n".join(line.rstrip() for line in t.replace("\f", "\n").splitlines())
    return re.sub(r"\n{3,}", "\n\n", t).strip("\n")


def pdf_text(path, pages=None, lang="eng", workers=None):
    """The PDF's text with a '--- Page N' header per page; scanned pages are OCR'd. '' if nothing was read."""
    if not (tool("pdftotext") and tool("pdfinfo") and tool("pdftoppm")):
        raise RuntimeError("poppler missing (pdftotext, pdfinfo, pdftoppm): install poppler")
    total = page_count(path)
    nums = [n for n in (pages or range(1, total + 1)) if 1 <= n <= total]
    with ThreadPoolExecutor(workers or os.cpu_count() or 4) as pool:
        results = list(pool.map(lambda n: read_page(path, n, lang), nums))
    out = []
    for n, was_ocr, t in results:
        t = clean(t)
        if t:
            out.append(f"--- Page {n}{' (OCR)' if was_ocr else ''}\n\n{t}")
    return "\n\n".join(out)


# ---------- Material notes ----------

def note_pdf(note):
    head = open(note, encoding="utf-8").read(3000)
    m = re.search(r"^file:\s*[\"']?([^\"'\n]+?)[\"']?\s*$", head, re.M)
    if not m:
        return None
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(note))), m.group(1))
    return p if p.lower().endswith(".pdf") and os.path.exists(p) else None


def full_text(src):
    body = src.split("## Full text", 1)[1] if "## Full text" in src else ""
    return re.sub(r"\(Open the original:[^)]*\)", "", body)


def stub_notes():
    for note in sorted(glob.glob(os.path.join(ROOT, "courses", "*", "material", "*.md"))):
        if note_pdf(note) and len(re.sub(r"\s", "", full_text(open(note, encoding="utf-8").read()))) < STUB_CHARS:
            yield note


def fill(note, lang):
    pdf = note_pdf(note)
    if not pdf:
        print(f"skip, no PDF next to it: {note}", file=sys.stderr)
        return False
    body = pdf_text(pdf, lang=lang)
    if not body:
        print(f"skip, no text found: {note}", file=sys.stderr)
        return False
    src = open(note, encoding="utf-8").read()
    rel_pdf = os.path.relpath(pdf, os.path.dirname(os.path.dirname(os.path.abspath(note))))
    head = f"(Open the original: [[{rel_pdf}]])"
    if "(OCR)" in body:
        head += "\n\nPages marked (OCR) were read from a scan. OCR can misread words: check odd ones against the original page."
    src = src.split("## Full text", 1)[0].rstrip("\n") + "\n\n## Full text\n\n" + head + "\n\n" + body + "\n"
    with open(note, "w", encoding="utf-8") as f:
        f.write(src)
    print(f"filled: {os.path.relpath(note, ROOT)} ({body.count('--- Page')} pages)")
    return True


def parse_pages(s):
    out = []
    for part in s.split(","):
        a, _, b = part.strip().partition("-")
        out += range(int(a), int(b or a) + 1)
    return out


def main():
    ap = argparse.ArgumentParser(description="Read a PDF as text, OCR'ing scanned pages.")
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("--pages", help="e.g. 12-20 or 3,5,9-11")
    ap.add_argument("--lang", default="eng", help="tesseract language(s), e.g. eng or eng+ara")
    ap.add_argument("--fill", nargs="+", metavar="NOTE", help="material note(s) to fill with their PDF's text")
    ap.add_argument("--scanned", action="store_true", help="list material notes with no text yet")
    a = ap.parse_args()
    if a.scanned:
        for note in stub_notes():
            print(os.path.relpath(note, ROOT))
    elif a.fill:
        ok = [fill(n, a.lang) for n in a.fill]
        sys.exit(0 if all(ok) else 1)
    elif a.pdf:
        print(pdf_text(a.pdf, parse_pages(a.pages) if a.pages else None, a.lang))
    else:
        ap.error("give a PDF, --fill NOTE.md or --scanned")


if __name__ == "__main__":
    main()
