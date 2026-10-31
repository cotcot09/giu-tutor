---
description: What to study for a course or deadline, how, then start teaching
argument-hint: <course code, deadline or topic>
---
The student wants to study: $ARGUMENTS

1. Find the target in data/deadlines.json and the course hub courses/<CODE>/<CODE>.md. Read the relevant files in courses/<CODE>/material/ (cite them).
2. Tell them exactly what to study: up to 5 bullets, most important first, each with file and 20-minute blocks needed. Weigh exam focus, weight, days left and data/weak-spots.json.
3. Tell them how, in one line per item (method that fits the subject; see CLAUDE.md "How to teach").
4. Update data/next.json with these tasks.
5. Start block 1 right away: open with a retrieval question, not an explanation.

Before describing any assessment, read its `scope` in data/deadlines.json (verified from a course file). Missing → verify from the course outline first, or say "not verified".
