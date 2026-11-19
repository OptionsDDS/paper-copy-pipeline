"""doubts.py -- the one list of doubtful places of a copy (round 5, shared by every lane; do not change this file).

A rule that says "listed as doubtful" calls add(); the copy program calls write() once at the end of a paper.
The list goes to copy.doubts.json beside copy.md. It never changes copy.md."""
import json
import os

_ITEMS = []


def reset():
    del _ITEMS[:]


def add(rule, page, box, reason, options=None, line=None):
    """rule: 'O30', 'F31', ...; page: 1-based; box: [x0, y0, x1, y1] in the program's page units; reason: a short code,
    no paper text; options: for a place a later stage may ask about, the fixed choices; line: copy.md line number or None."""
    item = {'rule': str(rule), 'page': int(page), 'box': [round(float(v), 1) for v in box], 'reason': str(reason)}
    if options:
        item['options'] = [str(o) for o in options]
    if line is not None:
        item['line'] = int(line)
    _ITEMS.append(item)


def items():
    return list(_ITEMS)


def write(outdir):
    out = sorted(_ITEMS, key=lambda d: (d['page'], d['box'][1], d['box'][0], d['rule'], d['reason']))
    with open(os.path.join(outdir, 'copy.doubts.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
