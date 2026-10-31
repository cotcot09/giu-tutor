#!/usr/bin/env python3
"""Check a check-in / catch-up message before it is sent.

Usage: python3 scripts/checkin_lint.py [--quiz-course CODE] "<message>"
  --quiz-course: the course the MCQ was taken from (must match the message's course).
Exit 0 = OK to send. Exit 1 = fix the message (reasons printed).

Rules (added after a confusing check-in):
- ONE course per message. Never mix courses.
- Every course code is written with its short name from data/courses.json (e.g. "AS101 English").
- Max 6 lines. First line names the course.
- No choices for the student to make about WHAT to do ("want", "or", "which do you prefer").
- If there is a question, it has options 1-4.
- Ends with one directive: a time (12-hour) or "now".
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    with open(os.path.join(ROOT, "data", "courses.json"), encoding="utf-8") as f:
        NAMES = {code: (c.get("short") or c.get("title") or "").strip() for code, c in json.load(f).items()}
except (FileNotFoundError, json.JSONDecodeError, AttributeError):
    NAMES = {}

args = sys.argv[1:]
quiz_course = None
if args[:1] == ["--quiz-course"]:
    quiz_course, args = args[1], args[2:]
msg = args[0] if args else sys.stdin.read()
lines = [l for l in msg.strip().splitlines() if l.strip()]
errors = []

if len(lines) > 6:
    errors.append(f"{len(lines)} lines; max 6.")

codes = set(re.findall(r"\b([A-Z]{2,5}\d{3})\b", msg))
if len(codes) > 1:
    errors.append(f"Mixes courses {sorted(codes)}; use ONE course per message.")
if quiz_course and codes and quiz_course not in codes:
    errors.append(f"Question is from {quiz_course} but the message is about {sorted(codes)}; same course only.")
if "?" in msg and not quiz_course:
    errors.append("Pass --quiz-course CODE so the question's course is checked.")
if not codes:
    errors.append("No course code; name the course on line 1.")
for c in codes:
    if not NAMES.get(c):
        errors.append(f"{c} has no short name in data/courses.json; add one.")
    elif not re.search(rf"\b{c}\s+{re.escape(NAMES[c])}\b", msg):
        errors.append(f'Write "{c} {NAMES[c]}" so the student never has to guess the subject.')
if codes and lines and not any(c in lines[0] for c in codes):
    errors.append("First line must name the course.")

if re.search(r"\b(want|prefer|would you like|which (one|course)|or would)\b", msg, re.I):
    errors.append("Don't hand the student a choice of what to do; decide for them.")

if "?" in msg and not all(f"{i})" in msg for i in range(1, 5)):
    errors.append("Question needs options 1) 2) 3) 4).")

last = lines[-1] if lines else ""
if not re.search(r"\b(\d{1,2}(:\d{2})?\s?(AM|PM)|now)\b", last, re.I):
    errors.append('Last line must be one directive with a time ("12:00 PM: ...") or "now".')

if errors:
    print("NOT OK:\n- " + "\n- ".join(errors))
    sys.exit(1)
print("OK")
