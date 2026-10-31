---
description: Active-recall quiz, one question at a time, logged
argument-hint: [course code or topic; empty = weakest spots + due reviews]
---
Quiz the student on: $ARGUMENTS

- If empty: first any data/missed.json items with next_review <= today, then their weakest topics in data/weak-spots.json, mixed across courses.
- Build questions from courses/<CODE>/material/ (and the course hub's exam focus). Match the real assessment format.
- MCQ: 4 options, same length, one clearly right. Number the options 1–4 so they can answer with a digit.
- ONE question at a time. After each answer: ✅/❌ + one-line why. Then the next.
- Default 5 questions, then a one-line score.
- After every answer append to data/log.jsonl ({ts, type:"quiz", course, topic, score: 1|0, note}).
- Wrong → add to data/missed.json (next_review tomorrow). Right on a missed item → push next_review out (1 → 3 → 7 days) and bump streak; streak 3 = remove.
- Update recall in data/weak-spots.json. At the end, regenerate NOW.md and commit + push quietly.
