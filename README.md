# GIU Tutor

A private study tutor for GIU students that runs in Claude Code. It downloads your CMS files, grades, exam seats and timetable, then teaches you from your own course material: what to study next, quizzes, explanations, revision sheets and a plan for your week.

Every course fact it tells you comes from your files, with the file and page. If something isn't in your material, it says so instead of guessing.

## What you need

- A Claude subscription with Claude Code (Pro or Max).
- A laptop: Mac, Windows or Linux. Windows and Linux are untested so far: report what breaks.
- Your GIU portal / CMS login.
- Git and Python 3. curl is built into macOS and Windows 10+. `/setup` checks all of this.
- Optional: [Obsidian](https://obsidian.md) to browse your notes; poppler + tesseract to read scanned PDFs.

## Start

1. **Make your own private copy.**
   - With GitHub: on this repo, **Use this template → Create a new repository → Private**, then clone your copy.
   - Without GitHub: **Code → Download ZIP** and unzip it. Everything works except phone check-ins.
2. **Open the folder in Claude Code** (desktop app: open the folder; terminal: `cd` into it and run `claude`).
3. **Type `/setup`.** It asks a few questions about you, then asks you to run one command in your own terminal to save your GIU login:

   ```bash
   python3 scripts/giu_login.py
   ```

   On Windows use `python` instead of `python3`. Your password goes into your system's secure store (macOS Keychain, Windows DPAPI, Linux secret-tool). It never goes into the chat or the repo.
4. **Wait for the first sync.** It downloads all your CMS files, makes a page per course, reads the course outlines for deadlines and plans your week.

Then ask "what now".

## Keep your copy private

Your copy fills up with your grades and GIU's course files. Never make it public and don't share it. Share this template instead.

## Daily use

Open the folder in Claude Code and say what you want, or use a command:

| Say | Command | What happens |
|---|---|---|
| "what now" | `/now` | The one thing to do next, then a 20-minute block |
| "study AS101" | `/study AS101` | What to study for it, how, and step 1 right away |
| "quiz me" | `/quiz` | Exam-style questions, one at a time, from your weak spots |
| "explain X" | `/explain X` | Taught from your material, then one check question |
| "summarize lecture 3" | `/summary` | A short note in the course folder |
| "build X" | `/build X` | Learn by coding a tiny program |
| "cheat sheet X" | `/revise X pdf` | Revision slides or a 1-page PDF |
| "video on X" | `/revise X video` | A NotebookLM video or audio overview (see below) |
| "plan" | `/plan` | Next 7 days, around your week |
| "sync" | `/sync` | New CMS files, grades, exam seats now |
| "done" | `/done` | Logs the session and saves |

`NOW.md` is the one page to look at: next task, deadlines, weak spots, grades.

## What runs by itself

- **Background sync** every 3 hours while you're logged in: `python3 scripts/install_sync.py` (`/setup` offers it). Status and log: `python3 scripts/install_sync.py --status`. Remove: `--remove`.
- **Scanned PDFs** are read with OCR during the sync if poppler and tesseract are installed.

## NotebookLM (optional)

Turn a course into audio overviews, video overviews and mind maps with [NotebookLM](https://notebooklm.google.com) (free with a Google account), built from the same material.

1. Ask the tutor "make my NotebookLM packs", or run `python3 scripts/notebooklm.py`. It writes one file per course to `notebooklm/` (kept out of git).
2. In NotebookLM, make one notebook per course named `<CODE> · <course title>` and add that course's file as a source.
3. Then say "video on X" or "audio on X". The tutor rebuilds the pack. If Claude can use your browser (Claude in Chrome), it updates the notebook and starts the overview for you; if not, it tells you which file to add and which button to press.

Rebuild the packs after a lot of new material arrives.

## Phone check-ins (optional)

An evening check-in and an afternoon catch-up arrive as notifications from Claude. They need your copy on GitHub (private).

1. In `.claude/routines/checkin.md` and `catchup.md`, replace `<your-github-username>/<your-repo>` with your repo.
2. In Claude Code, run `/schedule` and give it each file. It creates a cloud routine with that schedule and prompt.

Ignoring them is fine. They get shorter when you're busy and only ping when a deadline is close.

## Troubleshooting

- **"GIU password rejected"**: your password changed. Run `python3 scripts/giu_login.py` again.
- **`python3` not found on Windows**: use `python` or `py`.
- **Scanned PDFs have no text**: install poppler + tesseract (Mac `brew install poppler tesseract`, Windows `scoop install poppler tesseract`, Linux `sudo apt install poppler-utils tesseract-ocr`), then run `python3 scripts/pdf_text.py --scanned` and fill each note it lists with `--fill`.

## Layout

```
NOW.md                     the one page (generated by scripts/now.py)
me.md                      about you: filled by /setup, edit any time
CLAUDE.md / AGENTS.md      how the tutor works (Claude Code, Codex)
courses/<CODE>/<CODE>.md   course page: grading, exam focus, how to study, links
courses/<CODE>/material/   every CMS file as text + summary
courses/<CODE>/files/      the CMS originals
courses/<CODE>/notes/      notes and cheat sheets made while studying
labs/<CODE>/               code-to-learn mini projects
data/                      courses, deadlines, grades, timetable, weak spots, plan, log
scripts/                   cms_sync, giu_login, install_sync, now, index, pdf_text, ...
.claude/                   commands (/setup, /now, ...), skills, phone routines
```

## Privacy

- Your GIU login stays on your laptop, in the system's secure store.
- Files and grades come from your own GIU account, into your own copy.
- The scripts only talk to GIU's portal and CMS, and to GitHub if your copy has a remote.
