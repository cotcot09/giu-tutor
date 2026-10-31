#!/usr/bin/env python3
"""Refresh the Material and Notes lists inside each course hub (courses/<CODE>/<CODE>.md)."""
import glob, json, os, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ORDER = {'lecture slides': 0, 'lecture notes': 0, 'tutorial notes': 1, 'supplementary notes': 2, 'exercise': 2,
         'assignment': 3, 'assignment solution': 3, 'project': 4, 'other': 5, 'vod': 6}


def meta(path):
    head = open(path, encoding='utf-8').read(1500)
    t = re.search(r'^title:\s*(.+)$', head, re.M)
    k = re.search(r'^type:\s*(.+)$', head, re.M)
    return (unquote(t.group(1)) if t else os.path.splitext(os.path.basename(path))[0],
            unquote(k.group(1)) if k else 'Other')


def unquote(v):
    v = v.strip()
    return json.loads(v) if len(v) >= 2 and v[0] == v[-1] == '"' else v


def block(text, name, lines):
    start, end = f'<!-- {name}:start -->', f'<!-- {name}:end -->'
    if start not in text:
        return text
    pre, rest = text.split(start, 1)
    _, post = rest.split(end, 1)
    return pre + start + '\n' + '\n'.join(lines) + ('\n' if lines else '') + end + post


for hub in glob.glob(os.path.join(ROOT, 'courses', '*', '*.md')):
    code = os.path.basename(os.path.dirname(hub))
    if os.path.basename(hub) != code + '.md':
        continue
    mats = []
    for p in glob.glob(os.path.join(ROOT, 'courses', code, 'material', '*')):
        name = os.path.basename(p)
        if name.endswith('.md'):
            title, kind = meta(p)
            # Full path: lecture-3 exists in four courses, a bare [[lecture-3]] would open the wrong one.
            mats.append((ORDER.get(kind.lower(), 5), kind, title, f'- [[courses/{code}/material/{os.path.splitext(name)[0]}|{title}]] · {kind}'))
        else:
            mats.append((7, 'Original', name, f'- [[courses/{code}/material/{name}|{name}]] · original file'))
    mats.sort(key=lambda x: (x[0], x[2].lower()))
    notes = [f'- [[courses/{code}/notes/{os.path.splitext(os.path.basename(p))[0]}|{os.path.splitext(os.path.basename(p))[0]}]]' for p in sorted(glob.glob(os.path.join(ROOT, 'courses', code, 'notes', '*.md')))]
    text = open(hub, encoding='utf-8').read()
    text = block(text, 'material', [m[3] for m in mats] or ['_Nothing yet. Run `/sync`._'])
    text = block(text, 'notes', notes or ['_No notes yet._'])
    if 'Open in NotebookLM:' not in text:
        t = re.search(r'^title:\s*(.+)$', text[:1500], re.M)
        name = f"{code} · {unquote(t.group(1))}" if t else code
        text = text.rstrip('\n') + f"\n\nOpen in NotebookLM: one notebook per course named '{name}'\n"
    open(hub, 'w', encoding='utf-8').write(text)
print('hubs updated')
