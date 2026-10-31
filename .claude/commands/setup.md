---
description: First-time setup — own copy, tools, GIU login, first sync, profile, courses, deadlines, first plan
---
Set this workspace up for a new student. Assume they have never used a terminal. Do every technical step yourself: they only answer questions, click Allow / Install, and type passwords into a box or a terminal, never into the chat. Keep every message short (CLAUDE.md "How to talk"). One question at a time. Skip any step that is already done.

1. **Their own copy.** First run only.
   - Downloaded with git from the template (`git remote -v` shows `cotcot09/giu-tutor`)? Delete that `.git` folder: it's the template's history, not theirs.
   - No `.git`: `git init -b main` (no git yet → step 2 first, then come back).
   - No git identity (`git config user.email` is empty): set one for this folder only: `git config user.name "GIU student"` and `git config user.email "student@giu-tutor.local"`.
   - `git add -A && git commit -qm "start from the GIU Tutor template"`.

2. **Tools.** Needed: `git`, `python3` (Windows: `python` or `py`), `curl`. For reading PDFs: `pdftotext` and `tesseract`. Install what's missing, one thing at a time; tell them what to click.
   - **Mac, no git or python3:** run `xcode-select --install`. Say: "Click Install in the box that pops up. It takes 5–10 minutes." Wait until `git --version` works.
   - **Mac, no pdftotext:** needs Homebrew, which asks for their Mac password, so it runs in a terminal they can type in (step 3 explains where). Command: `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"`. Say: "Type your Mac password there (nothing shows while you type), then press Return when it asks." Then `brew install poppler tesseract` (on Apple Silicon brew is at `/opt/homebrew/bin/brew` until a new terminal).
   - **Windows, no Python:** `winget install -e --id Python.Python.3.12`, then use `py`. No git: `winget install -e --id Git.Git`.
   - **Windows, no pdftotext:** in PowerShell: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned; irm get.scoop.sh | iex`, then `scoop install poppler tesseract`.
   - **Linux:** `sudo apt install git python3 curl poppler-utils tesseract-ocr` in their terminal.
   - Can't get the PDF tools? Go on. You can still read PDFs directly, and after installing later, `python3 scripts/pdf_text.py --scanned` lists the notes to fill with `--fill`.

3. **GIU login.** Say: "A box will pop up. Type your GIU username and password there, not here." Then run `python3 scripts/giu_login.py --dialog`. Never ask for the password in chat.
   - Cancelled, no box, or Linux: use the terminal instead: `python3 scripts/giu_login.py`. If you have a tool that runs a command in a terminal they can see and type in, run it there. If not, tell them exactly: Mac: open **Terminal** (Cmd+Space, type Terminal, Return). Windows: open **PowerShell** from the Start menu. Then paste `cd "<this folder's full path>"` and the command, and type the answers there.

4. **First sync, in the background.** Start `python3 scripts/cms_sync.py` in the background. The first run takes several minutes (it downloads every CMS file, creates a hub per course and fills data/courses.json, grades, exam seats and the timetable). Do step 5 while it runs.
   - Check its output after their first answer. "password rejected" → stop it, back to step 3.

5. **Profile.** Ask the questions in `me.md` one at a time (name, major and semester, how they learn best, ADHD or focus issues, their week, best study time, free time, a project to apply theory to, explanation language). Write the answers into `me.md` and set `setup: true`.

6. **Sync results.** When the sync ends: a 3-line summary: courses found, files downloaded, problems.

7. **Courses.** For each course in data/courses.json:
   - Set `short` to the plain name they use ("English", "Accounting"). Ask only if the title doesn't make it obvious.
   - Find the course outline / guidelines among its material notes (scans: `pdf-reader` skill). Fill the hub: Grading, Exam focus, How to study, with the source file after each line.
   - Every dated graded item → data/deadlines.json with scope + scope_source. Undated → data/unscheduled.json with who to ask.
   - Nothing in the files? Write "not in your material yet" in the hub. Never guess.

8. **Background sync (recommended).** Ask once, in one line. Yes → `python3 scripts/install_sync.py`. It syncs every 3 hours while the laptop is on (Mac LaunchAgent, Windows Task Scheduler, Linux cron).

9. **NotebookLM (optional).** Offer it in one line: audio/video overviews of each course. If yes: run `python3 scripts/notebooklm.py`, then they make one notebook per course on notebooklm.google.com named "<CODE> · <course title>" and add `notebooklm/<CODE>.md`. Browser tools available → offer to do it for them.

10. **Plan.** Run the /plan steps, then `python3 scripts/now.py`.

11. **Save.** `git add -A && git commit -m "setup: <name>"`. If there is a remote, push. Their copy lives in this folder on this laptop. Remind them once: if they ever put it on GitHub, it must be **private** (it holds their grades and GIU's files).

12. **Phone check-ins (optional, later).** Needs their copy on GitHub (private). Point them to README "Phone check-ins". Don't set it up unless they ask.

13. Tell them how to come back: open this folder in Claude Code and say "what now". Then give the one next action from NOW.md and offer to start a 20-minute block.
