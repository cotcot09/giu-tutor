#!/usr/bin/env python3
"""Build one NotebookLM upload file per course from courses/<CODE>/material/.

    python3 scripts/notebooklm.py [out_dir]   (default: notebooklm/)
"""
import glob, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'notebooklm')
os.makedirs(out, exist_ok=True)
for hub in sorted(glob.glob(os.path.join(ROOT, 'courses', '*', '*.md'))):
    code = os.path.basename(os.path.dirname(hub))
    if os.path.basename(hub) != code + '.md':
        continue
    files = sorted(glob.glob(os.path.join(ROOT, 'courses', code, 'material', '*.md')))
    if not files:
        continue
    hub_txt = open(hub, encoding='utf-8').read()
    hub_txt = re.sub(r'^---.*?---\n', '', hub_txt, flags=re.S)
    hub_txt = re.sub(r'## Material.*', '', hub_txt, flags=re.S).strip()
    parts = [hub_txt, '']
    for f in files:
        t = open(f, encoding='utf-8').read()
        m = re.match(r'^---\n(.*?)\n---\n', t, re.S)
        meta = {k: v.strip().strip('"') for k, v in re.findall(r'^(\w+):\s*(.*)$', m.group(1), re.M)} if m else {}
        body = t[m.end():] if m else t
        body = re.sub(r'^## ', '### ', body, flags=re.M)
        parts.append(f"\n---\n\n## {meta.get('title', os.path.basename(f))} ({meta.get('type', '')})\n{body.strip()}\n")
    path = os.path.join(out, f'{code}.md')
    open(path, 'w', encoding='utf-8').write('\n'.join(parts))
    print(f'{code}: {len(files)} files, {os.path.getsize(path)//1024} KB -> {path}')
