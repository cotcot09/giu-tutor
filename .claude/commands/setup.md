---
description: First-time setup — profile, GIU login, first sync, courses, deadlines, first plan
---
Set this workspace up for a new student. Keep every message short (CLAUDE.md "How to talk"). One question at a time. Skip any step that is already done.

1. **Profile.** Ask the questions in `me.md` one at a time (name, major and semester, how they learn best, ADHD or focus issues, their week, best study time, free time, a project to apply theory to, explanation language). Write the answers into `me.md` and set `setup: true`.

2. **Tools.** Check `git --version`, `python3 --version` (Windows: `python` or `py`) and `curl --version`.
   - Missing one: give the one install command for their system and wait.
   - Optional, for scanned PDFs: `pdftotext` and `tesseract`. Mac: `brew install poppler tesseract`. Windows: `scoop install poppler tesseract`. Linux: `sudo apt install poppler-utils tesseract-ocr`. Offer to run it; fine to skip.

3. **GIU login.** Tell them: "Open a terminal in this folder and run `python3 scripts/giu_login.py`. Type your GIU username and password there, not here." Never ask for the password in chat. Wait until they say it's done.

4. **First sync.** Run `python3 scripts/cms_sync.py` (it can take a few minutes the first time). It downloads every CMS file, creates a hub per course and fills data/courses.json, grades, exam seats and the timetable.
   - "password rejected" → back to step 3.
   - Show a 3-line summary: courses found, files downloaded, problems.

5. **Courses.** For each course in data/courses.json:
   - Set `short` to the plain name they use ("English", "Accounting"). Ask only if the title doesn't make it obvious.
   - Find the course outline / guidelines among its material notes (scans: `pdf-reader` skill). Fill the hub: Grading, Exam focus, How to study, with the source file after each line.
   - Every dated graded item → data/deadlines.json with scope + scope_source. Undated → data/unscheduled.json with who to ask.
   - Nothing in the files? Write "not in your material yet" in the hub. Never guess.

6. **Background sync (recommended).** Run `python3 scripts/install_sync.py`. It syncs every 3 hours while the laptop is on (Mac LaunchAgent, Windows Task Scheduler, Linux cron).

7. **NotebookLM (optional).** Offer it in one line: audio/video overviews of each course. If yes: run `python3 scripts/notebooklm.py`, then they make one notebook per course on notebooklm.google.com named "<CODE> · <course title>" and add `notebooklm/<CODE>.md`. Browser tools available → offer to do it for them.

8. **Plan.** Run the /plan steps, then `python3 scripts/now.py`.

9. **Save.** `git add -A && git commit -m "setup: <name>"`. If there is a remote, push. Remind them once: their repo must stay **private** (it holds their grades and GIU's files).

10. **Phone check-ins (optional, later).** Needs their repo on GitHub (private). Point them to README "Phone check-ins". Don't set it up unless they ask.

11. End with the one next action from NOW.md and offer to start a 20-minute block.
