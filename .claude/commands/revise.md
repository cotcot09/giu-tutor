---
description: Revision slideshow or 1-page cheat-sheet PDF for a course/topic, built from the material and their weak spots
argument-hint: <course or topic> [slides|pdf|video]
---
Make the student a revision pack for: $ARGUMENTS

Default format: slides. "pdf" / "cheat sheet" = one A4 page. "video" / "audio" = NotebookLM (step 6).

1. **Scope**: the course + topic, and the next graded item it serves (data/deadlines.json: name, date, weight). Truly unclear → ask ONE question, else pick the nearest graded item.
2. **Sources** (read before writing):
   - courses/<CODE>/material/: slides, sheets, solutions.
   - courses/<CODE>/notes/ and the course hub's exam focus.
   - data/weak-spots.json + data/missed.json for this course: every weak spot gets its own slide/box.
3. **Write it** (one idea per slide, max 5 bullets of ≤10 words, bold the key term, every rule cited):
   - **slides**: Marp markdown, 8–15 slides. Slide 1 = what the assessment tests + date. Worked example for math/accounting, code for programming, rubric checklist for writing, theory applied to their project (me.md) for management. Second-last slide = 5 self-test questions, last slide = answers + source files.
     Header: `marp: true`, `theme: default`, `paginate: true`, `size: 16:9`.
   - **pdf**: one A4 cheat sheet as a self-contained HTML file (print CSS: `@page { size: A4; margin: 12mm }`, 2 columns, 9–10 pt), same content rules, weak spots boxed.
   - Save as courses/<CODE>/notes/revision/<YYYY-MM-DD>-<topic-slug>.md (or .html) with frontmatter: title, course, type: Revision, for: <deadline id>, sources: [[file]] links.
4. **Render the PDF** next to it:
   - slides: `npx -y @marp-team/marp-cli@latest <file>.md --pdf --allow-local-files -o <file>.pdf` (needs Node + Chrome or Edge; no `node` → install Node.js, then retry).
   - pdf: Chrome or Edge headless: `<chrome or msedge> --headless=new --no-pdf-header-footer --print-to-pdf=<file>.pdf <file>.html`. Mac Chrome path: `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"`.
   - Check the PDF (page count, nothing cut off); fix and re-render if not. Then open it.
   - Can't render here (cloud session)? Commit the .md/.html and say it renders on their laptop.
5. **Reply** in 2 lines: what's in it + "Quiz on it now?" (yes → run /quiz on the same topic). Commit .md/.html + .pdf with `study: revision <CODE> <topic>`.
6. **NotebookLM** (video/audio, or when they say "notebook"):
   - `python3 scripts/notebooklm.py` rebuilds notebooklm/<CODE>.md from the latest material.
   - Browser tools available → open notebooklm.google.com, the notebook "<CODE> · …", replace the old pack source with the new one (plus the revision .md), then Studio → Video Overview or Audio Overview, focused on the topic.
   - No browser tools → tell them the one file to add and the one button to press.
