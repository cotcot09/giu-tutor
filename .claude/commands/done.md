---
description: Close the session — log, update tracker, regenerate NOW.md, commit, push
---
The student is done for now.

1. Append what they did this session to data/log.jsonl (one line per activity, with minutes).
2. Update data/weak-spots.json, data/missed.json and data/next.json.
3. `python3 scripts/now.py`
4. `git add -A && git commit -m "study: <short summary>"`, then `git push` if there is a remote
5. Reply in 2 lines max: what they did + the next action for next time. No praise speeches.
