#!/usr/bin/env python3
"""Native copy trace and code checks, written by copy_paper.py with its copy.

copy_paper.py records provenance at the moment it writes each unit: the unit's
source rows (page, run ids, read text, character range) and runs, as carried
by its own strings and float/front records. This module never matches copy
text against the PDF. It only:

- builds the printed-line universe exactly as tools/export_lines.py does
  (source_rows/source_roles on the decoded pages; line ids pN.lNNN), with
  D-020 addresses pdf:<sha256>:p<page>:c<first boxer character index>;
- resolves each unit's claims to runs and lines, and each line to exactly one
  destination: one unit (or one unit group: the cells of a table, the authors
  of a byline, parts cut from one joined text), a furniture reason, or a run
  named in the copy's uncertainty list;
- locates each unit's span in the final copy.md from the sentinel offsets the
  writer recorded (later float-file lines are located in their inserted lines);
- runs the code checks (copy.checks.json): (a) PDF text-layer characters
  outside every box of the sort, (b) pages/columns/boxes skipped by the body
  order, (c) floats without captions and captions without floats, (d) lines
  in no unit or duplicated in two units, (e) printed body lines that lose
  characters to furniture or to no box at all (excluded_body_characters).

Line statuses: unit, furniture, uncertainty, split (disjoint parts of one row
in different units, or a row partly furniture: accounted, listed), lost (in no
unit, no furniture reason, not in the uncertainty list: fails), duplicate (the
same source characters in two units: fails), partly_excluded (a body line,
otherwise accounted, whose own characters on its baseline were taken as
furniture or left in no rule-1 box: fails, with the characters listed). A claim
that kept an unknown part of a row ("partial") cannot prove a duplicate; such
shares are split_unverified.
"""
import collections
import difflib
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import statistics
import sys
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
UNCERTAINTY = '## Places the program is not sure of'
SCHEMA = 'copy-trace/2 (native)'


def module(name, path):
    if name in sys.modules: return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


def sha_bytes(data): return hashlib.sha256(data).hexdigest()


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


# ------------------------------------------------------------------ lines
def scan_source_pages(source_pages, scan_pages, copy):
    """export_lines.snapshot: a scan page's OCR runs replace its native layer."""
    scans = {p['page']: p for p in scan_pages}
    result = []
    for page in sorted(source_pages, key=lambda p: p['page']):
        if page['page'] in scans:
            source = scans[page['page']]
            page = dict(source, elements=[dict(run, id=f'ocr:{run["_scan_id"]}', kind='text', angle=run.get('angle', 0))
                                          for run in copy.scan_source_runs(source)])
        result.append(page)
    return result


def source_lines(pages, state, pdf_digest, geometry, exporter, accounting):
    """The exporter's printed lines, ids and roles; furniture evidence per run."""
    lines, run_reason, run_line = [], {}, {}
    ordinal = 0
    for page in pages:
        n = page['page']
        dpi = page.get('params', {}).get('dpi', 150)
        roles = exporter.source_roles(page, state)
        final = next((p for p in state['saved_conservation'].get('pages', []) if p['page'] == n), page)
        exclusions = {str(e['id']): e.get('reason', 'unspecified exclusion')
                      for e in final.get('copy_conservation', {}).get('excluded', [])}
        for e in final.get('copy_conservation', {}).get('excluded', []):
            for m in e.get('source_run_ids', []): exclusions.setdefault(str(m), e.get('reason', 'unspecified exclusion'))
        source_offset = 0
        geo = geometry.get(n)
        for i, row in enumerate(exporter.source_rows(page, roles), 1):
            sources = [s for e in row for s in e.get('_subscript_sources', [e])]
            decoded = [dict(e, text=exporter.copy.glyph_spacing(e)) for e in row]
            value = str(exporter.copy.compose_accents(exporter.copy.prose_row(decoded, page)[0]))
            native = exporter.copy.hull(e['box_px'] for e in sources)
            box = points = None
            if geo:
                size = [geo['media'][2]-geo['media'][0], geo['media'][3]-geo['media'][1]]
                if geo['rotation'] in (90, 270): size.reverse()
                dimensions = [math.ceil(v*110/72) for v in size]
                raw = exporter.image_box(native, dpi, geo)
                box = [round(max(0, min(v, dimensions[j % 2])), 4) for j, v in enumerate(raw)]
                points = [round(v, 5) for v in (native[0]*72/dpi, geo['height']-native[3]*72/dpi,
                                                 native[2]*72/dpi, geo['height']-native[1]*72/dpi)]
            indices = list(dict.fromkeys(c for e in sources for c in e.get('char_ids', []) if isinstance(c, int) and c >= 0))
            basis = 'boxer visible-character index' if indices else 'OCR decoded-character offset; not native PDF glyph identity'
            index = min(indices) if indices else source_offset
            source_offset += max(1, len(value))
            ordinal += 1
            export_id = f'p{n}.l{i:03}'
            lid = accounting.source_id(pdf_digest, n, index) if pdf_digest else export_id
            runs = [str(e['id']) for e in sources]
            reasons = []
            for m in runs:
                why = exclusions.get(m.removeprefix('ocr:'))
                if not why and roles.get(m) in ('furniture', 'figure_text'):
                    why = 'program figure lettering classification' if roles[m] == 'figure_text' else 'program furniture classification'
                if why: run_reason[n, m] = why; reasons.append(why)
                run_line[n, m] = len(lines)
            lines.append(dict(id=lid, export_id=export_id, number=ordinal, page=n, page_line=i,
                              source_id_basis=basis, first_character_index=index if indices else None,
                              source_characters=len(indices), text=value,
                              box_110dpi=box, box_pdf_points=points, runs=runs,
                              source_role=collections.Counter(roles.get(m, 'body') for m in runs).most_common(1)[0][0]))
    ids = collections.Counter(l['id'] for l in lines)
    for line in lines:
        if ids[line['id']] > 1: line['id'] = f"{line['id']}#{line['export_id']}"
    return lines, run_reason, run_line


# ------------------------------------------------------------------ claims
def claims_of(units, rows):
    """(page, run) -> [(group, unit index, kind, row, start, end, partial)]."""
    claims = collections.defaultdict(list)
    for k, unit in enumerate(units):
        group = unit['group']
        for row, a, b in unit['segs']:
            record = rows[row]
            for m in record['runs']:
                claims[record['page'], str(m)].append((group, k, 'row', row, a, b, a < 0))
        for page, m, partial in unit['runs']:
            claims[page, str(m)].append((group, k, 'run', None, None, None, bool(partial)))
    return claims


FRONT_PARSED = ('title', 'author', 'affiliation')
LINE_FAIL = ('lost', 'partly_lost', 'duplicate', 'partly_excluded')


def run_status(entries, kinds=None):
    """unit / split / split_unverified / flagged_repeat / duplicate, from one run's claims.

    The flagged "Front matter as printed" block deliberately repeats the
    source rows of a parsed byline/affiliation that rule 8 did not verify;
    that repeat is listed (flagged_repeat). Any other repeat is a duplicate.
    """
    groups = {e[0] for e in entries}
    if len(groups) == 1: return 'unit'
    status = 'split'
    rank = {'split': 0, 'split_unverified': 1, 'flagged_repeat': 2}
    by_group = collections.defaultdict(list)
    for e in entries: by_group[e[0]].append(e)
    keys = sorted(by_group)
    for i, g in enumerate(keys):
        for h in keys[i+1:]:
            for x in by_group[g]:
                for y in by_group[h]:
                    pair = {kinds[x[1]], kinds[y[1]]} if kinds else set()
                    if 'front_matter_printed' in pair and pair - {'front_matter_printed'} <= set(FRONT_PARSED):
                        found = 'flagged_repeat'
                    elif x[6] or y[6]: found = 'split_unverified'
                    elif x[2] == y[2] == 'row' and x[3] == y[3] and (x[5] <= y[4] or y[5] <= x[4]): found = 'split'
                    else: return 'duplicate'
                    if rank[found] > rank[status]: status = found
    return status


def account(lines, claims, run_reason, uncertain, run_line, kinds=None):
    records = []
    known = set(run_line)
    for line in lines:
        n = line['page']
        per_run = []
        for m in line['runs']:
            entries = claims.get((n, m), [])
            if entries:
                per_run.append((m, run_status(entries, kinds), sorted({e[0] for e in entries})))
            elif (n, m) in run_reason: per_run.append((m, 'furniture', [run_reason[n, m]]))
            elif (n, m) in uncertain or (n, 'scan:'+m.removeprefix('ocr:')) in uncertain:
                per_run.append((m, 'uncertainty', [uncertain.get((n, m)) or uncertain.get((n, 'scan:'+m.removeprefix('ocr:')))]))
            else: per_run.append((m, 'lost', []))
        statuses = {s for _, s, _ in per_run}
        groups = sorted({g for _, s, gs in per_run if s not in ('furniture', 'uncertainty', 'lost') for g in gs})
        sinks = {('unit' if s in ('unit', 'split', 'split_unverified', 'flagged_repeat', 'duplicate') else s) for _, s, _ in per_run}
        if 'duplicate' in statuses: status = 'duplicate'
        elif 'lost' in statuses: status = 'lost' if statuses == {'lost'} else 'partly_lost'
        elif 'flagged_repeat' in statuses: status = 'flagged_repeat'
        elif len(groups) > 1 or len(sinks) > 1:
            status = 'split_unverified' if 'split_unverified' in statuses else 'split'
        else: status = next(iter(sinks))
        furniture = sorted({gs[0] for _, s, gs in per_run if s == 'furniture'})
        noted = sorted({gs[0] for _, s, gs in per_run if s == 'uncertainty'})
        records.append(dict(status=status, groups=groups, furniture=furniture, uncertainty=noted,
                            runs=[dict(run=m, status=s) for m, s, _ in per_run]))
    unknown = sorted({f'p{n}:{m}' for (n, m) in claims if (n, m) not in known})
    return records, unknown


# ------------------------------------------------------------------ spans
def map_spans(pre, spans, final):
    """Map writer offsets in the pre-final copy to the final copy.md.

    Only later float-file insertions, notices and the uncertainty list change
    the copy after writing; unchanged lines keep their offsets exactly.
    """
    a = pre.splitlines(keepends=True); b = final.splitlines(keepends=True)
    starts_a = [0]
    for line in a: starts_a.append(starts_a[-1]+len(line))
    starts_b = [0]
    for line in b: starts_b.append(starts_b[-1]+len(line))
    mapping = {}
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for k in range(i2-i1): mapping[i1+k] = j1+k
    import bisect
    def where(offset, end=False):
        i = bisect.bisect_right(starts_a, offset - (1 if end and offset else 0)) - 1
        i = max(0, min(i, len(a)-1)) if a else 0
        if i not in mapping: return None
        return starts_b[mapping[i]] + offset - starts_a[i]
    result, inserted = {}, set(range(len(b))) - set(mapping.values())
    for uid, (s, e) in spans.items():
        if s is None or e is None: result[uid] = None; continue
        x, y = where(s), where(e, end=True)
        if x is not None and y is not None and final[x:y] == pre[s:e]:
            result[uid] = [x, y]; continue
        value = pre[s:e]
        hits = [m.start() for m in re.finditer(re.escape(value), final)] if value else []
        result[uid] = [hits[0], hits[0]+len(value)] if len(hits) == 1 else None
    return result, inserted, starts_b


def locate_late(late, final, inserted, starts_b, taken):
    import bisect
    spans = []
    for unit in late:
        value = unit['text']; found = None
        for m in re.finditer(re.escape(value), final) if value else []:
            line = bisect.bisect_right(starts_b, m.start()) - 1
            span = (m.start(), m.end())
            # A generated line or bold label stands alone: never inside another inserted line.
            bounded = (span[0] == 0 or final[span[0]-1] in '\n*') and (span[1] == len(final) or final[span[1]] in '\n*')
            if bounded and line in inserted and not any(a < span[1] and span[0] < b for a, b in taken):
                found = span; break
        if found: taken.append(found)
        spans.append(list(found) if found else None)
    return spans


def reader_replacements(folder, final, body, spans, unit_spans):
    """Give the units that tools/agree.py replaced the span of their replacement.

    An accepted reader agreement replaces a table's printed lines (and its
    notice) with a grid whose tokens equal theirs exactly; their source lines
    stay claimed by the same units. copy.agree.json must name this exact copy
    as its output and copy.agree-before.md as its input (SHA-256), else nothing
    changes. Units whose span in the pre-agreement copy lies inside an accepted
    block are its members: the first owns the replacement span, the others an
    empty span at its end, so spans never overlap. Returns {unit: caption}.
    """
    folder = Path(folder)
    log_path, before_path = folder/'copy.agree.json', folder/'copy.agree-before.md'
    if not log_path.is_file() or not before_path.is_file(): return {}
    try: log = json.loads(log_path.read_text(encoding='utf-8'))
    except ValueError: return {}
    before = before_path.read_text(encoding='utf-8')
    if log.get('output_sha256') != sha_bytes(final.encode()) or log.get('input_sha256') != sha_bytes(before.encode()):
        return {}
    in_before, _, _ = map_spans(body, spans, before)
    members = {}
    for event in log.get('tables', []):
        if not event.get('accepted') or 'output_start' not in event: continue
        inside = sorted((v[0], k) for k, v in in_before.items()
                        if v and event['start'] <= v[0] <= v[1] <= event['end'] and v[0] < event['end'])
        for i, (_, k) in enumerate(inside):
            start = event['output_start'] if i == 0 else event['output_end']
            unit_spans[k] = [start, event['output_end']]
            members[k] = event['caption']
    return members


# ------------------------------------------------------------------ checks
def check_outside_boxes(pdf, pages, conserve, geometry):
    """(a) Text-layer words whose centre lies outside every text box of the sort."""
    by_page = {p['page']: p for p in pages}
    result = collections.defaultdict(lambda: dict(characters=0, words=[]))
    for n, width, height, ws in conserve.pdf_lines(pdf):
        page = by_page.get(n)
        if not page: continue
        region = page.get('region_box_px', [0, 0, width, height])
        g = geometry.get(n)
        sx = (region[2]-region[0])/(g['width'] if g else width); sy = (region[3]-region[1])/(g['height'] if g else height)
        boxes = [e['box_px'] for e in page.get('elements', []) if e.get('kind') == 'text']
        boxes += [r['box_px'] for r in ((page.get('scan_evidence') or {}).get('ocr_runs') or []) if r.get('box_px')]
        for w in ws:
            # Invisible format characters and trailing tab/space advances can
            # widen Poppler's word box far beyond its printed glyphs.
            text = ''.join(c for c in w['text'] if not c.isspace() and unicodedata.category(c) != 'Cf')
            if not text: continue
            box = conserve.native_box(w['box'], g, sx, sy) if g else [w['box'][0]*sx, w['box'][1]*sy, w['box'][2]*sx, w['box'][3]*sy]
            cx, cy = (box[0]+box[2])/2, (box[1]+box[3])/2
            dx, dy = .35*(box[2]-box[0]), .35*(box[3]-box[1])
            points = [(cx, cy), (cx-dx, cy), (cx+dx, cy), (cx, cy-dy), (cx, cy+dy)]
            if any(b[0]-2 <= x <= b[2]+2 and b[1]-2 <= y <= b[3]+2 for x, y in points for b in boxes): continue
            record = result[n]; record['characters'] += len(text); record['words'].append(text)
    out = []
    for n in sorted(result):
        counts = by_page[n].get('counts') or {}
        out.append(dict(page=n, characters=result[n]['characters'], words=result[n]['words'],
                        unpainted_characters_on_page=counts.get('characters_unpainted', 0)))
    return out


BODY_STATUSES = ('unit', 'split', 'split_unverified', 'flagged_repeat')
CUT = dict(baseline_em=.25, size_low=.8, size_high=1.25, reach_em=1.0, overprint_em=.3, word_em=.3)


def page_reader():
    """The rule-1 reading layer the copier already loaded (same characters, same cache)."""
    reader = sys.modules.get('_copy_table_reader')
    if reader is None: reader = module('_copy_table_reader', ROOT/'standalone/element_boxer_sc.py')
    return reader


def excluded_body_characters(pdf, pages, lines, records, run_reason, reader=None, omitted=None):
    """(e) Printed body lines that lose their own characters: {line index: [evidence]}.

    Furniture removal and the page region never take body characters. A body
    line is a printed line with a run claimed by a unit. Its own characters are
    the upright reading-layer characters on its baseline (within baseline_em of
    its median origin) at its size (size_low..size_high of its median letter),
    reaching the line within reach_em, chained along the baseline, and inside
    the line's extent. Of these, a character fails the line when it is in no
    rule-1 text element (outside the page region, or never boxed) or belongs
    to a run the copy leaves out as furniture. Glyph identity decides: rotated or
    oblique watermark letters, superscripts, letters on another baseline and
    free-standing accents (composed into their letters) and small ink over one
    of the line's letters (an accent or dot glyph) are not the line's own
    characters, and an unboxed copy of a letter printed on an assigned letter
    (overprint) is not lost. A furniture run that is a bare number set off from
    the line by a word gap (word_em) is margin numbering or a folio, not part of
    the line (measured: W07, proof line numbers within an em of the text). Letters the copier omitted on their own paint or
    glyph evidence (copy_omitted: unpainted, white, an empty spacer glyph, a
    diagonal watermark letter) were never printed body text. Measured: AI03 (CropBox from
    43.2 pt) lost "de-", "38%" -> "3", "analy[sis]" at the right column edge and
    the trace counted every such line accounted."""
    reader = reader or page_reader()
    by_page = collections.defaultdict(list); furniture = set()
    for i, (line, rec) in enumerate(zip(lines, records)):
        if rec['status'] in BODY_STATUSES: by_page[line['page']].append(i)
        furniture.update((line['page'], r['run']) for r in rec['runs'] if r['status'] == 'furniture')
    found = {}
    for page in pages:
        n = page['page']
        if not by_page.get(n) or (page.get('scan_evidence') or {}).get('ocr_layer'): continue
        region = page.get('region_box_px')
        if not region: continue
        scale = page.get('params', {}).get('dpi', reader.PARAMS['dpi']) / reader.PARAMS['dpi']
        chars = [c for c in reader.sc_read_page(pdf, n)[0] if not c['hidden']]
        if scale != 1:
            chars = [dict(c, **{k: c[k]*scale for k in ('x0', 'y0', 'x1', 'y1')},
                          origin=(c['origin'][0]*scale, c['origin'][1]*scale), size=c['size']*scale) for c in chars]
        inside = lambda c: region[0] <= (c['x0']+c['x1'])/2 <= region[2] and region[1] <= (c['y0']+c['y1'])/2 <= region[3]
        indexed = [c for c in chars if inside(c)]
        texts = {str(e['id']): e for e in page.get('elements', []) if e.get('kind') == 'text'}
        def own(e):
            return [indexed[k] for k in e.get('char_ids', []) if isinstance(k, int) and 0 <= k < len(indexed)]
        # The ids must name this reader's characters (old outputs or another reader: no evidence).
        checked = [e for e in texts.values() if e.get('char_ids')]
        agree = sum(''.join(c['text'] for c in own(e)).replace(' ', '')[:3] == ''.join(e.get('text', '').split())[:3] for e in checked)
        if not checked or agree < .9 * len(checked): continue
        assigned = set()
        for e in texts.values(): assigned.update(k for k in e.get('char_ids', []) if isinstance(k, int))
        unprinted = set((omitted or {}).get(n, ()))
        for o in page.get('copy_omitted', []): unprinted.update(o.get('char_ids', []))
        excluded = [(c, 'in no rule-1 text element (outside the page region)') for c in chars if not inside(c)]
        excluded += [(c, 'in no rule-1 text element') for k, c in enumerate(indexed) if k not in assigned and k not in unprinted]
        numbers = {}   # letter -> its run's letters, for furniture runs that are a bare number
        for m, e in texts.items():   # a run the copy left out as furniture (a claimed run is in the copy)
            if (n, m) in furniture:
                letters = own(e)
                excluded += [(c, 'counted as furniture: ' + run_reason.get((n, m), 'furniture')) for c in letters]
                if re.fullmatch(r'\d+', ''.join(c['text'] for c in letters)): numbers.update((id(c), letters) for c in letters)
        # A free-standing accent or modifier belongs to its letter (rule 1 composes it), not a letter of its own.
        excluded = [(c, why) for c, why in excluded if c['angle'] % 360 == 0 and c['text'].strip()
                    and not all(unicodedata.category(ch) in ('Sk', 'Mn', 'Lm') for ch in c['text'])]
        if not excluded: continue
        printed = collections.defaultdict(list)
        for k in assigned:
            if 0 <= k < len(indexed): printed[indexed[k]['text']].append(indexed[k])
        def overprint(c):
            return any(abs((a['x0']+a['x1'])/2-(c['x0']+c['x1'])/2) < CUT['overprint_em']*c['size'] and
                       abs(a['origin'][1]-c['origin'][1]) < CUT['overprint_em']*c['size'] and a is not c
                       for a in printed.get(c['text'], ()))
        def mark_on_letter(c, letters, em):
            # small ink over one of the line's letters (an accent or dot glyph, mapped or not)
            mid = (c['x0']+c['x1'])/2
            return c['y1']-c['y0'] < .4*em and any(a['x0'] <= mid <= a['x1'] for a in letters)
        for i in by_page[n]:
            body = [r['run'] for r in records[i]['runs'] if r['status'] not in ('furniture', 'uncertainty', 'lost')]
            cs = [c for m in body if m in texts for c in own(texts[m]) if c['angle'] % 360 == 0]
            if not cs: continue
            size = statistics.median(c['size'] for c in cs); base = statistics.median(c['origin'][1] for c in cs)
            left, right = min(c['x0'] for c in cs), max(c['x1'] for c in cs)
            def apart(letters):   # set off from the line by at least a word gap
                return max(min(c['x0'] for c in letters) - right, left - max(c['x1'] for c in letters)) >= CUT['word_em']*size
            pool = [(c, why) for c, why in excluded if abs(c['origin'][1]-base) <= CUT['baseline_em']*size
                    and CUT['size_low']*size <= c['size'] <= CUT['size_high']*size
                    and not (id(c) in numbers and apart(numbers[id(c)]))]
            taken, grown = [], True
            while grown and pool:
                grown = False
                for item in list(pool):
                    c = item[0]
                    if c['x0'] <= right + CUT['reach_em']*size and c['x1'] >= left - CUT['reach_em']*size:
                        pool.remove(item); grown = True
                        if overprint(c) or mark_on_letter(c, cs, size): continue
                        taken.append(item); left, right = min(left, c['x0']), max(right, c['x1'])
            if taken:
                taken.sort(key=lambda item: item[0]['x0'])
                groups = collections.OrderedDict()
                for c, why in taken: groups.setdefault(why, []).append(c)
                found[i] = [dict(reason=why, characters=len(cs_), text=''.join(c['text'] for c in cs_),
                                 box_px=[round(min(c['x0'] for c in cs_), 2), round(min(c['y0'] for c in cs_), 2),
                                         round(max(c['x1'] for c in cs_), 2), round(max(c['y1'] for c in cs_), 2)])
                            for why, cs_ in groups.items()]
    return found


def check_body_order(folder, pages):
    """(b) Rule-6 main boxes, pages and columns absent from rule 9's body order."""
    path = Path(folder)/'body-order.json'
    if not path.is_file(): return dict(evaluated=False, reason='no body-order.json', findings=[])
    order = json.loads(path.read_text())
    # Rule 9 orders rule 6's boxes: compare with the boxer's saved main text,
    # not with blocks the copier added or reclassified in memory.
    saved = {}
    for f in Path(folder).glob('page-[0-9]*.json'):
        try: data = json.loads(f.read_text()); saved[data.get('page')] = data.get('main_text')
        except (OSError, ValueError): pass
    pages = [dict(p, main_text=saved[p['page']]) if saved.get(p['page']) is not None else p for p in pages]
    placed = {(b['page'], b['id']) for b in order.get('blocks', [])}
    unplaced = {(u.get('page'), u.get('id')) for u in order.get('unplaced', [])}
    findings = []
    for u in order.get('unplaced', []):
        findings.append(dict(kind='unplaced_box', page=u.get('page'), id=u.get('id'),
                             reason=u.get('reason') or u.get('flag') or 'listed as unplaced by rule 9'))
    for page in pages:
        if (page.get('scan_evidence') or {}).get('ocr_layer'): continue
        mt = page.get('main_text') or {}
        main = [b for b in mt.get('blocks', []) if b.get('cls') == 'main' and b.get('order') is not None]
        if not main: continue
        missing = [b for b in main if (page['page'], b['id']) not in placed and (page['page'], b['id']) not in unplaced]
        if len(missing) == len(main):
            findings.append(dict(kind='page_skipped', page=page['page'], boxes=[b['id'] for b in missing]))
            continue
        columns = mt.get('columns', [])
        for c, (left, right) in enumerate(columns):
            inside = [b for b in main if left-1 <= b['box_px'][0] and b['box_px'][2] <= right+1]
            gone = [b for b in inside if b in missing]
            if inside and len(gone) == len(inside):
                findings.append(dict(kind='column_skipped', page=page['page'], column=c+1, boxes=[b['id'] for b in gone]))
                missing = [b for b in missing if b not in gone]
        for b in missing:
            findings.append(dict(kind='box_skipped', page=page['page'], id=b['id'],
                                 first_words=' '.join(str(b.get('text', '')).split()[:8])))
    return dict(evaluated=True, findings=findings)


def check_floats(folder):
    """(c) Float records without a caption or captions without a float."""
    path = Path(folder)/'copy.floats.json'
    if not path.is_file(): return dict(evaluated=False, reason='no copy.floats.json', findings=[])
    catalog = json.loads(path.read_text())
    findings = []
    for record in catalog.get('floats', []):
        status = (record.get('check') or {}).get('status')
        if status in (None, 'paired'): continue
        findings.append(dict(kind=status, id=record['id'], pages=sorted({p['page'] for p in record.get('parts', [])})))
    return dict(evaluated=True, findings=findings)


SLOT_BODY = {'paragraph', 'list_item', 'abstract_part'}
SLOT_NOTES = {'article_information', 'footnote', 'front_matter_printed'}


def check_sentence_slots(units, witness):
    """(d) The R1 invariant (lane f5stream): a float, caption, note, side block, heading or
    front-matter row stands only at a witnessed boundary. A finding is a body unit whose end
    can only be inside a sentence (a lowercase letter, comma, semicolon or hyphen, eight words
    or more) followed, after one or more other units, by a body unit that resumes with an
    ordinary lowercase word the shared boundary witness confirms ('between'); or a note or
    front-matter row of six words or more ending so before such a resume ('torn')."""
    if witness is None: return dict(evaluated=False, reason='no boundary witness', findings=[])
    findings = []
    content = [u for u in units if u['text'].strip() and (u['status'] != 'generated' or u['kind'] == 'heading')]
    open_end, resume = witness.open_end, witness.resumes
    def page(u, last=False):
        s = u.get('sources') or []
        return s[-1 if last else 0].get('page') if s else None
    for k, u in enumerate(content):
        body = u['kind'] in SLOT_BODY
        if not (body and len(u['text'].split()) >= 8 or u['kind'] in SLOT_NOTES and len(u['text'].split()) >= 6): continue
        if not open_end(u['text']): continue
        j = k+1
        while j < len(content) and content[j]['kind'] not in SLOT_BODY: j += 1
        if j >= len(content) or j == k+1 and body: continue
        w = content[j]
        if not resume(w['text']) or witness(u['text'], w['text'])['verdict'] != 'continuation': continue
        between = content[k+1:j]
        findings.append(dict(kind='between' if body else 'torn', page=page(u, True), resume_page=page(w),
                             kinds=sorted({v['kind'] for v in between} | ({u['kind']} if not body else set())),
                             unit=u['id'], resume_unit=w['id'], end=u['text'][-40:], resume=w['text'][:40]))
    return dict(evaluated=True, findings=findings)


def quote(text, n=80):
    text = ' '.join(str(text).split())
    return json.dumps(text if len(text) <= n else text[:n-1]+'…', ensure_ascii=False)


# ------------------------------------------------------------------ build
def build(folder, pdf, trace, source_pages, scan_pages, main_pages, scan_document=False):
    """Write copy.trace.json and copy.checks.json; return (failed, notices)."""
    folder = Path(folder)
    exporter = module('_copy_trace_export', ROOT/'tools/export_lines.py')
    accounting = module('_copy_trace_accounting', ROOT/'tools/trace_port/accounting.py')
    conserve = exporter.conserve
    copy_path = folder/'copy.md'
    final = copy_path.read_text(encoding='utf-8')
    pdf_digest = sha(pdf) if pdf else None
    geometry = {}
    if pdf:
        try: geometry = conserve.page_geometry(pdf)
        except Exception: geometry = {}
    saved = json.loads((folder/'copy.conservation.json').read_text()) if (folder/'copy.conservation.json').is_file() else {}
    scan_audit = json.loads((folder/'copy.scan.json').read_text()) if (folder/'copy.scan.json').is_file() else {}
    pages = scan_source_pages(source_pages, scan_pages, exporter.copy)
    state = dict(pages=main_pages, scan_audit=scan_audit, saved_conservation=saved)
    lines, run_reason, run_line = source_lines(pages, state, pdf_digest, geometry, exporter, accounting)

    rows = trace['rows']
    units = [dict(u, group=u.get('group') or f'#{k}') for k, u in enumerate(trace['units'])]
    late = []
    for value in trace.get('late', []):
        late.append(dict(kind=value['kind'], group=None, segs=[], runs=[list(r) for r in value.get('runs', [])],
                         generated=value.get('generated'), text=value['text']))
    for k, u in enumerate(late, len(units)): u['group'] = f'#{k}'
    spans, inserted, starts_b = map_spans(trace.get('body_text', ''), trace.get('body_spans', {}), final)
    taken = [tuple(v) for v in spans.values() if v]
    late_spans = locate_late(late, final, inserted, starts_b, taken)
    all_units = units + late
    unit_spans = [spans.get(k) for k in range(len(units))] + late_spans
    replaced = reader_replacements(folder, final, trace.get('body_text', ''), trace.get('body_spans', {}), unit_spans)
    claims = claims_of(all_units, rows)
    uncertain = {(p, str(m)): why for (p, m), why in trace['uncertain'].items()}
    records, unknown = account(lines, claims, run_reason, uncertain, run_line, [u['kind'] for u in all_units])
    cut_check = dict(evaluated=bool(pdf), findings=[])
    if pdf:
        omitted = collections.defaultdict(set)
        for p in list(pages) + list(main_pages):
            for o in p.get('copy_omitted', []): omitted[p['page']].update(o.get('char_ids', []))
        try: cut = excluded_body_characters(pdf, pages, lines, records, run_reason, omitted=omitted)
        except Exception as exc: cut = {}; cut_check = dict(evaluated=False, reason=f'{type(exc).__name__}: {exc}', findings=[])
        for i, evidence in sorted(cut.items()):
            records[i].update(status='partly_excluded', excluded=evidence)

    # Unit ids follow reading order in the final copy.
    order = sorted(range(len(all_units)), key=lambda k: (unit_spans[k] is None, unit_spans[k] or [0, 0], k))
    uid = {k: f'u{i+1:05}' for i, k in enumerate(order)}
    group_units = collections.defaultdict(list)
    for k in order: group_units[all_units[k]['group']].append(uid[k])
    line_by_run = collections.defaultdict(set)
    for (n, m), entries in claims.items():
        if (n, m) in run_line:
            for e in entries: line_by_run[e[1]].add(run_line[n, m])
    unit_records = []
    for k in order:
        u = all_units[k]; span = unit_spans[k]
        sources = [dict(line_id=lines[i]['id'], export_id=lines[i]['export_id'], page=lines[i]['page'],
                        box_110dpi=lines[i]['box_110dpi']) for i in sorted(line_by_run[k])]
        has_claims = bool(u['segs'] or u['runs'])
        group_claims = any(all_units[j]['segs'] or all_units[j]['runs'] for j in range(len(all_units))
                           if all_units[j]['group'] == u['group']) if not has_claims else True
        group_sources = sources or [s for j in range(len(all_units)) if all_units[j]['group'] == u['group']
                                    for s in [dict(line_id=lines[i]['id'], export_id=lines[i]['export_id'], page=lines[i]['page'],
                                                   box_110dpi=lines[i]['box_110dpi']) for i in sorted(line_by_run[j])]]
        if span is None: status = 'span_unresolved'
        elif u.get('generated'): status = 'generated'
        elif group_sources: status = 'traced'
        elif group_claims: status = 'claims_without_lines'
        else: status = 'untraced'
        extra = {key: u[key] for key in ('row', 'column') if key in u}
        if k in replaced: extra['reader_replaced'] = replaced[k]
        unit_records.append(dict(id=uid[k], kind=u['kind'], group=u['group'], group_units=group_units[u['group']],
            span=span or [0, 0], text=final[span[0]:span[1]] if span else u.get('_source_text', u.get('text', '')),
            status=status, generated_reason=u.get('generated'),
            sources=sources if sources else group_sources,
            source_basis='own claims' if sources else ('group claims' if group_sources else None),
            claims=dict(rows=[[r, a, b] for r, a, b in u['segs']],
                        runs=[[p, m, bool(q)] for p, m, q in u['runs']]),
            unmatched=[] if status in ('traced', 'generated') else [dict(reason=status)], **extra))
    by_group = collections.defaultdict(list)
    for r in unit_records: by_group[r['group']].append(r)
    line_records = []
    for line, rec in zip(lines, records):
        destinations = [dict(unit_id=r['id'], copy_span=r['span']) for g in rec['groups'] for r in by_group.get(g, [])]
        line_records.append(dict(line, status=rec['status'], units=destinations,
            groups=rec['groups'], furniture_reason='; '.join(rec['furniture']) or None,
            uncertainty=rec['uncertainty'] or None,
            **({'run_statuses': rec['runs']} if rec['status'] not in ('unit', 'furniture', 'uncertainty') else {}),
            **({'excluded_body_characters': rec['excluded']} if rec.get('excluded') else {}),
            unmatched=[] if rec['status'] not in LINE_FAIL else [dict(reason=rec['status'])]))
    counts = collections.Counter(r['status'] for r in line_records)
    total = len(line_records)
    failing = [r for r in line_records if r['status'] in LINE_FAIL]
    unit_counts = collections.Counter(r['status'] for r in unit_records)
    content = [r for r in unit_records if r['status'] != 'generated']
    accounting_report = dict(
        lost_lines=[dict(line_id=r['id'], export_id=r['export_id'], page=r['page'], text=r['text'], status=r['status'],
                         runs=[x for x in r['run_statuses'] if x['status'] == 'lost']) for r in line_records if r['status'] in ('lost', 'partly_lost')],
        duplicate_lines=[dict(line_id=r['id'], export_id=r['export_id'], page=r['page'], text=r['text'],
                              units=[d['unit_id'] for d in r['units']], groups=r['groups']) for r in line_records if r['status'] == 'duplicate'],
        partly_excluded_lines=[dict(line_id=r['id'], export_id=r['export_id'], page=r['page'], text=r['text'],
                                    excluded_body_characters=r['excluded_body_characters'])
                               for r in line_records if r['status'] == 'partly_excluded'],
        split_lines=[dict(line_id=r['id'], export_id=r['export_id'], page=r['page'], text=r['text'], status=r['status'],
                          groups=r['groups'], furniture=r['furniture_reason'], uncertainty=r['uncertainty'])
                     for r in line_records if r['status'] in ('split', 'split_unverified', 'flagged_repeat')],
        untraced_units=[dict(unit_id=r['id'], kind=r['kind'], text=r['text'][:200], status=r['status'])
                        for r in unit_records if r['status'] in ('untraced', 'claims_without_lines', 'span_unresolved')],
        unknown_source_runs=unknown)
    statistics = dict(lines=total, line_status=dict(sorted(counts.items())),
        lines_accounted=total-len(failing), lines_accounted_share=round((total-len(failing))/total, 4) if total else 1.0,
        lines_exactly_one_destination=counts['unit']+counts['furniture']+counts['uncertainty'],
        units=len(unit_records), unit_status=dict(sorted(unit_counts.items())),
        units_traced=unit_counts['traced'], content_units=len(content),
        units_traced_share=round(unit_counts['traced']/len(content), 4) if content else 1.0)
    failed = bool(failing or accounting_report['untraced_units'])

    # Code checks
    checks = dict(schema='copy-checks/1', copy_sha256=None)
    try: checks['text_outside_sort_boxes'] = dict(evaluated=bool(pdf), findings=check_outside_boxes(pdf, main_pages, conserve, geometry) if pdf else [])
    except Exception as exc: checks['text_outside_sort_boxes'] = dict(evaluated=False, reason=f'{type(exc).__name__}: {exc}', findings=[])
    checks['body_order_skips'] = check_body_order(folder, main_pages)
    checks['float_pairing'] = check_floats(folder)
    checks['sentence_slots'] = check_sentence_slots(unit_records, trace.get('boundary_witness'))
    # C5 (mapper D-377): an emitted main-text line assembled across the paper's majority gutter is a finding;
    # copy_paper.gutter_cut cut the block into its columns ('cut') or, beside a spanning line, left it in page
    # order and reports it ('spans'); never interleaved
    checks['lines_across_gutter'] = dict(evaluated=bool(trace.get('gutters_evaluated')), findings=list(trace.get('gutter_findings', [])))
    cut_check['findings'] = [dict(page=r['page'], line_id=r['id'], export_id=r['export_id'], text=r['text'],
                                  excluded_body_characters=r['excluded_body_characters'])
                             for r in line_records if r['status'] == 'partly_excluded']
    checks['body_lines_partly_excluded'] = cut_check
    checks['line_accounting'] = dict(evaluated=True, findings=
        [dict(kind={'duplicate': 'line_in_two_units', 'partly_excluded': 'body_line_partly_excluded'}.get(r['status'], 'line_in_no_unit'),
              page=r['page'], line_id=r['id'], export_id=r['export_id'], text=r['text'], units=[d['unit_id'] for d in r['units']])
         for r in failing] + [dict(kind='unit_without_source', unit_id=u['unit_id'], text=u['text'], status=u['status'])
                              for u in accounting_report['untraced_units']])
    notices = []
    for f in checks['text_outside_sort_boxes']['findings']:
        words = ' '.join(f['words']); hidden = f' ({f["unpainted_characters_on_page"]} unpainted characters on the page)' if f['unpainted_characters_on_page'] else ''
        notices.append(f"page {f['page']}: check: {f['characters']} PDF text-layer character(s) outside every box of the sort{hidden}: {quote(words, 120)}")
    for f in checks['body_order_skips']['findings']:
        if f['kind'] == 'unplaced_box': notices.append(f"page {f['page']}: check: body order leaves main box {f['id']} unplaced ({f['reason']})")
        elif f['kind'] == 'page_skipped': notices.append(f"page {f['page']}: check: body order skips the page ({len(f['boxes'])} main boxes)")
        elif f['kind'] == 'column_skipped': notices.append(f"page {f['page']}: check: body order skips column {f['column']} ({len(f['boxes'])} main boxes)")
        else: notices.append(f"page {f['page']}: check: body order skips main box {f['id']} {quote(f['first_words'], 60)}")
    for f in checks['lines_across_gutter']['findings']:
        if f['kind'] == 'cut': notices.append(f"page {f['page']}: check: {f['rows']} line(s) assembled across the column gutter (x {f['gutter'][0]}-{f['gutter'][1]}) were cut into their columns: {quote(f['text'], 70)}")
        else: notices.append(f"page {f['page']}: check: {f['rows']} line(s) span the column gutter (x {f['gutter'][0]}-{f['gutter'][1]}) beside {f['crossing']} line(s) crossing it; kept in page order, not cut: {quote(f['text'], 70)}")
    for f in checks['float_pairing']['findings']:
        what = 'caption without a float' if f['kind'] == 'caption_without_float' else 'float without a caption'
        notices.append(f"page {', '.join(map(str, f['pages']))}: check: {f['id']}: {what}")
    for f in checks['sentence_slots']['findings']:
        what = (', '.join(f['kinds']) + ' printed between the halves of a sentence' if f['kind'] == 'between' else
                f"{', '.join(f['kinds'])} ends inside a sentence that resumes in the body")
        notices.append(f"page {f['page']}: check: {what}: {quote('…' + f['end'], 45)} … {quote(f['resume'] + '…', 45)}")
    by_page = collections.defaultdict(lambda: collections.defaultdict(list))
    for r in failing: by_page[r['page']][r['status']].append(r)
    for n in sorted(by_page):
        for status, rs in sorted(by_page[n].items()):
            what = {'lost': 'printed line(s) in no unit of the copy', 'partly_lost': 'printed line(s) partly in no unit of the copy',
                    'duplicate': 'printed line(s) in two units of the copy',
                    'partly_excluded': 'printed body line(s) missing their own characters, taken as furniture or in no box'}[status]
            def lost_part(r):
                cut = ' + '.join(quote(e['text'], 30) for e in r.get('excluded_body_characters', []))
                return f" missing {cut}" if cut else ''
            notices.append(f"page {n}: check: {len(rs)} {what} (copy.trace.json): " + '; '.join(
                f"{r['export_id']} {quote(r['text'], 70)}{lost_part(r)}" for r in rs))
    for u in accounting_report['untraced_units']:
        notices.append(f"check: copy unit {u['unit_id']} ({u['kind']}) has no source line: {quote(u['text'], 70)}")

    report = dict(schema=SCHEMA,
        method='native: units and their source rows/runs are recorded by copy_paper.py when each unit is written; no text matching',
        pdf=dict(path=str(Path(pdf).resolve()) if pdf else None, sha256=pdf_digest,
                 pages=[dict(page=n, media_box_pdf_points=g['media'], rotation=g['rotation']) for n, g in sorted(geometry.items())]),
        copy=dict(path='copy.md', sha256=None, characters=None),
        line_ids='D-020 pdf:<sha256>:p<page>:c<first boxer character index>; export_id is tools/export_lines.py pN.lNNN',
        statistics=statistics, accounting=accounting_report, failed=failed,
        units=unit_records, lines=line_records,
        rows=[dict(row=i, page=r['page'], runs=r['runs'], text=r['text']) for i, r in enumerate(rows)],
        furniture_runs=[dict(page=n, run=m, reason=why) for (n, m), why in sorted(run_reason.items(), key=lambda kv: (kv[0][0], kv[0][1]))],
        uncertainty_runs=[dict(page=p, run=m, statement=s) for (p, m), s in sorted(trace['uncertain'].items(), key=lambda kv: (kv[0][0], str(kv[0][1])))])
    return report, checks, notices, failed


def write(folder, report, checks, notices):
    """Append fired checks to the uncertainty list, then bind both sidecars to the copy hash."""
    folder = Path(folder); copy_path = folder/'copy.md'
    text = copy_path.read_text(encoding='utf-8')
    if notices:
        body, mark, rest = text.partition(UNCERTAINTY)
        if mark:
            rest = re.sub(r'\n- none\s*$', '\n', rest)
            text = body + mark + rest.rstrip('\n') + '\n' + '\n'.join('- '+n for n in notices) + '\n'
        else:
            text = text.rstrip('\n') + '\n\n---\n' + UNCERTAINTY + '\n' + '\n'.join('- '+n for n in notices) + '\n'
        copy_path.write_text(text, encoding='utf-8')
    digest = sha_bytes(text.encode('utf-8'))
    report['copy'].update(sha256=digest, characters=len(text))
    checks['copy_sha256'] = digest
    for unit in report['units']:
        if unit['status'] != 'span_unresolved' and text[slice(*unit['span'])] != unit['text']:
            unit['status'] = 'span_unresolved'
    for name, value in (('copy.trace.json', report), ('copy.checks.json', checks)):
        temporary = folder/(name+'.tmp')
        temporary.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':'))+'\n', encoding='utf-8')
        temporary.replace(folder/name)
