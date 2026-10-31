---
description: Re-plan the next 7 days of study
---
Re-plan the student's next 7 days.

1. Dates: data/deadlines.json (exam seats arrive with /sync). Check the course files in courses/*/material/ for dated assessments that are missing, and add them with scope + scope_source. Classes: data/timetable.json. Their week, commitments and travel: me.md.
2. Using CLAUDE.md "Deciding what to study", write data/next.json: an ordered list of concrete tasks (course, task, file, minutes, why, due). 2–4 blocks per day max; light on busy or travel days from me.md.
3. `python3 scripts/now.py`, commit, push if there is a remote.
4. Reply with today's 1–3 blocks only.

Before describing any assessment, read its `scope` in data/deadlines.json (verified from a course file). Missing → verify from the course outline first, or say "not verified".
