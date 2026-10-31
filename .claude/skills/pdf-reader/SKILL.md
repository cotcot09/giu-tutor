---
name: pdf-reader
description: Read any course PDF in this repo as text, including scanned or Canva PDFs with no text layer (OCR). Use before teaching, quizzing or citing from a PDF, when a material note's "Full text" is empty or says "(none yet)", or when a page needs checking by number.
---

# pdf-reader

Every course claim must come from the material (CLAUDE.md). Some PDFs are scans, so plain `pdftotext` returns nothing. This skill reads them anyway.

## Read a PDF

```bash
python3 scripts/pdf_text.py courses/<CODE>/files/<file>.pdf --pages 171-200
```

- Each page starts with `--- Page N`. Scanned pages say `--- Page N (OCR)`.
- Cite the page: "Student Book p.196".
- Leave out `--pages` to read the whole file. Large files: pick the pages from the contents page first.

## Fill a material note that has no text

```bash
python3 scripts/pdf_text.py --scanned          # notes whose Full text is still empty
python3 scripts/pdf_text.py --fill courses/<CODE>/material/<note>.md
```

This writes the text into the note's `## Full text`, keeping the link to the original. New CMS files are OCR'd automatically by `scripts/cms_sync.py`. Commit after filling.

## OCR can misread

- Dotted contents lines and tables often come out garbled.
- An odd word, a number that matters, or a table or diagram: look at the page itself with the Read tool (`pages: "196"`, up to 20 pages per call).
- Never teach a rule from a line that looks garbled. Check the page first, or say it's unreadable.

## Needs

poppler (pdftotext, pdftoppm) and tesseract. Mac: `brew install poppler tesseract`. Windows: `scoop install poppler tesseract`. Linux: `sudo apt install poppler-utils tesseract-ocr`. Other languages: `--lang eng+ara` once that tesseract language is installed.
