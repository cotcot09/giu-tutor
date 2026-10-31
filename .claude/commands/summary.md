---
description: Summarize a lecture/file into a note in the vault
argument-hint: <file, lecture or topic>
---
Summarize for the student: $ARGUMENTS

1. Find the file(s) in courses/<CODE>/material/.
2. Write courses/<CODE>/notes/<slug>.md with frontmatter (course, source, created) and sections:
   - Key ideas (max 8 bullets, ≤12 words each)
   - Terms (term: one-line meaning)
   - Formulas / rules (if any)
   - Exam traps (3 bullets)
   - Links: [[<CODE>]] and [[source file]]
3. In chat, show only the 5 most important bullets and the file path.
4. Offer a 3-question quiz on it.
