#!/usr/bin/env python3
"""Scan copies for body words cut at a line edge and for body-font text counted as furniture.

Usage: /usr/bin/python3 -I tools/cut_scan.py COPIES_DIR PDFMAP.json [--json OUT] [names...]

Each copy folder needs copy.trace.json (copy-trace/2) and its page-NN.json files.
The scan is independent of the copier's own checks: it reads Poppler's words
(pdftotext -bbox-layout, mapped to the boxer frame as tools/conserve.py does)
and the trace's printed lines, and counts per copy:

- cut: a body line (a line with a run in a unit) whose last token is a strict
  prefix of the Poppler word at its right end, or whose first token is a strict
  suffix of the Poppler word at its left end, the missing part holding a letter
  or digit ("analy" for "analysis."; a sign read differently is no cut);
- edge_words: Poppler words on a body line's band, within one em beyond its
  left or right end, whose centre lies in no text element of the page (whole
  words dropped at a column edge: "de-" after "were");
- furniture_body_lines / furniture_body_characters: lines the trace counted as
  furniture (or furniture runs of split lines) whose runs are upright, in the
  paper's body font and within 15% of its body size;
- furniture_body_adjacent: of those runs, the ones on a body line's band within
  one em of its ends (body characters partly taken as furniture).

Body font: the font with most characters over upright runs of body lines;
body size: the character-weighted median run size of that font's runs.
Normalisation: NFKC without spaces, case and punctuation kept. Only the standard library.
"""
import collections
import importlib.util
import json
from pathlib import Path
import re
import statistics
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
BODY = ('unit', 'split', 'split_unverified', 'flagged_repeat', 'partly_excluded')


def module(name, path):
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); sys.modules[name] = result; spec.loader.exec_module(result)
    return result


conserve = module('_cut_scan_conserve', ROOT/'tools/conserve.py')


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFKC', text) if c.isalnum())


def plain(text):
    """NFKC without spaces; punctuation kept, so a differently read sign is never a cut."""
    return ''.join(unicodedata.normalize('NFKC', text).split())


def dominant_font(e):
    spans = e.get('font_spans') or []
    if spans:
        count = collections.Counter()
        for s in spans: count[s['font']] += s['end'] - s['start']
        return count.most_common(1)[0][0]
    f = e.get('font')
    return f[0] if isinstance(f, list) and f else f


def size(e): return e.get('run_size_px') or e.get('size_px') or 0


def hull(boxes):
    boxes = list(boxes)
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)] if boxes else None


def band(a, b):
    """Vertical overlap of two boxes as a share of the smaller height."""
    overlap = min(a[3], b[3]) - max(a[1], b[1])
    return overlap / max(.01, min(a[3]-a[1], b[3]-b[1]))


def scan(folder, pdf):
    folder = Path(folder)
    trace = json.loads((folder/'copy.trace.json').read_text(encoding='utf-8'))
    pages = {}
    for f in sorted(folder.glob('page-[0-9]*.json')):
        p = json.loads(f.read_text(encoding='utf-8')); pages[p['page']] = p
    elements = {(n, str(e['id'])): e for n, p in pages.items() for e in p.get('elements', []) if e.get('kind') == 'text'}
    def runs_of(line, wanted=None):
        statuses = {r['run']: r['status'] for r in line.get('run_statuses', [])}
        out = []
        for m in line['runs']:
            e = elements.get((line['page'], str(m)))
            if e is None: continue
            status = statuses.get(m, line['status'])
            if wanted is None or status in wanted: out.append(e)
        return out
    fonts = collections.Counter(); sizes = collections.defaultdict(list)
    for line in trace['lines']:
        if line['status'] not in BODY: continue
        for e in runs_of(line, BODY):
            if round(e.get('angle', 0)) % 360: continue
            n = len(''.join(e.get('text', '').split())); f = dominant_font(e)
            fonts[f] += n; sizes[f].extend([size(e)] * n)
    body_font = fonts.most_common(1)[0][0] if fonts else None
    body_size = statistics.median(sizes[body_font]) if body_font and sizes[body_font] else 0
    geometry = conserve.page_geometry(pdf)
    words = collections.defaultdict(list)
    for n, width, height, ws in conserve.pdf_lines(pdf):
        p = pages.get(n); g = geometry.get(n)
        if not p or not g: continue
        region = p.get('region_box_px', [0, 0, width, height])
        sx = (region[2]-region[0])/g['width']; sy = (region[3]-region[1])/g['height']
        for w in ws:
            text = ''.join(c for c in w['text'] if not c.isspace() and unicodedata.category(c) != 'Cf')
            if text: words[n].append(dict(text=text, box=conserve.native_box(w['box'], g, sx, sy)))
    text_boxes = collections.defaultdict(list)
    for (n, _), e in elements.items(): text_boxes[n].append(e['box_px'])
    def in_text(n, box):
        cx, cy = (box[0]+box[2])/2, (box[1]+box[3])/2
        return any(b[0]-2 <= cx <= b[2]+2 and b[1]-2 <= cy <= b[3]+2 for b in text_boxes[n])
    body_lines = collections.defaultdict(list)
    result = dict(body_font=body_font, body_size_px=round(body_size, 2), cut=[], edge_words=[],
                  furniture_body=[], furniture_body_adjacent=[])
    for line in trace['lines']:
        if line['status'] not in BODY: continue
        rs = [e for e in runs_of(line, BODY) if not round(e.get('angle', 0)) % 360]
        box = hull(e['box_px'] for e in rs)
        if not box: continue
        em = statistics.median(size(e) for e in rs) or (box[3]-box[1])
        body_lines[line['page']].append((line, box, em))
        tokens = line['text'].split()
        if not tokens: continue
        n = line['page']
        same = [w for w in words[n] if band(w['box'], box) >= .5 and (w['box'][3]-w['box'][1]) <= 2*(box[3]-box[1])]
        # the word holding the line's right end, and the one holding its left end
        right = [w for w in same if w['box'][0] < box[2] - .1*em and w['box'][2] > box[2] - .1*em]
        left = [w for w in same if w['box'][0] < box[0] + .1*em and w['box'][2] > box[0] + .1*em]
        last, first = plain(tokens[-1]), plain(tokens[0])
        for w in right:
            full = plain(w['text'])
            if norm(last) and full.startswith(last) and norm(full[len(last):]):
                result['cut'].append(dict(page=n, line=line['export_id'], copy=tokens[-1], pdf=w['text'], edge='right')); break
        for w in left:
            full = plain(w['text'])
            if norm(first) and full.endswith(first) and norm(full[:len(full)-len(first)]):
                result['cut'].append(dict(page=n, line=line['export_id'], copy=tokens[0], pdf=w['text'], edge='left')); break
        for w in same:
            b = w['box']
            beyond = 0 <= b[0] - box[2] <= em or 0 <= box[0] - b[2] <= em
            if beyond and norm(w['text']) and not in_text(n, b):
                result['edge_words'].append(dict(page=n, line=line['export_id'], pdf=w['text']))
    for line in trace['lines']:
        if line['status'] not in ('furniture', 'split', 'split_unverified'): continue
        for e in runs_of(line, ('furniture',)):
            if round(e.get('angle', 0)) % 360 or dominant_font(e) != body_font: continue
            if not body_size or abs(size(e)/body_size - 1) > .15: continue
            text = ''.join(e.get('text', '').split())
            if not text: continue
            record = dict(page=line['page'], line=line['export_id'], run=e['id'], text=e['text'][:80],
                          characters=len(text), reason=line.get('furniture_reason'))
            result['furniture_body'].append(record)
            b = e['box_px']
            for other, box, em in body_lines[line['page']]:
                if band(b, box) >= .5 and (0 <= b[0]-box[2] <= em or 0 <= box[0]-b[2] <= em or
                                           (b[0] < box[2] and b[2] > box[0])):
                    result['furniture_body_adjacent'].append(dict(record, body_line=other['export_id'])); break
    result['counts'] = dict(cut=len(result['cut']), edge_words=len(result['edge_words']),
                            furniture_body_lines=len({(r['page'], r['line']) for r in result['furniture_body']}),
                            furniture_body_characters=sum(r['characters'] for r in result['furniture_body']),
                            furniture_body_adjacent=len(result['furniture_body_adjacent']),
                            trace_status=trace['statistics']['line_status'])
    return result


def main():
    args = sys.argv[1:]
    out = None
    if '--json' in args:
        i = args.index('--json'); out = args[i+1]; del args[i:i+2]
    if len(args) < 2: print(__doc__); sys.exit(2)
    root, pdfs = Path(args[0]), json.loads(Path(args[1]).read_text())
    names = args[2:] or sorted(pdfs)
    report = {}
    for name in names:
        folder = root/name
        if not (folder/'copy.trace.json').is_file():
            report[name] = dict(error='no copy.trace.json'); continue
        try: report[name] = scan(folder, pdfs[name])
        except Exception as exc: report[name] = dict(error=f'{type(exc).__name__}: {exc}')
        c = report[name].get('counts')
        print(name, json.dumps({k: v for k, v in c.items() if k != 'trace_status'}) if c else report[name]['error'], flush=True)
    if out: Path(out).write_text(json.dumps(report, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
