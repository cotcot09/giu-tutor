---
description: Sync new CMS files, grades, exam seats and the timetable from GIU
---
Sync the student's workspace.

1. `python3 scripts/cms_sync.py`. It pulls, downloads new CMS files into courses/<CODE>/files/ with material notes (scanned PDFs are OCR'd if tesseract is installed), creates hubs for new courses, merges portal grades into data/grades.json, exam seats into data/deadlines.json and classes into data/timetable.json, regenerates hubs and NOW.md, then commits and pushes. Never print or ask for their password.
   - "No GIU username/password saved" or "GIU password rejected": tell them to run `python3 scripts/giu_login.py` in their own terminal, then rerun.
   - Cloud session (no saved login): skip this step and say the sync runs on their laptop.
2. New course hubs or new outline/guideline files: fill the hub (grading, exam focus, how to study, with sources) and add dated assessments to data/deadlines.json with scope + scope_source; undated ones go to data/unscheduled.json. Set `short` names in data/courses.json if they're still the full title.
3. If step 2 changed anything: `python3 scripts/now.py`, then commit and push.
4. Reply with a 3-line summary: new deadlines, new grades, new files.
