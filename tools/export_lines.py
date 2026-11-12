#!/usr/bin/env python3
"""Export decoded source lines and 110-dpi page images, without editing a copy.

Usage: /usr/bin/python3 -I tools/export_lines.py COPY_DIR PDF OUT

The existing copy program runs on disposable copies of its JSON inputs. A
profile hook observes its decoded runs, final roles and order; it never changes
the program's code, inputs or return values. Additional outputs are an explicit
source/completeness audit, the current program's copy, and a proposed ID-only
map for round-trip testing. See tools/LINEMAP.md for limitations and decisions.
"""
import argparse
from collections import Counter, defaultdict
import contextlib
import copy as deepcopy_module
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unicodedata


ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


copy = module('_export_lines_copy', ROOT / 'copy_paper.py')
conserve = module('_export_lines_conserve', ROOT / 'tools/conserve.py')


def words(text):
    """Case-sensitive Unicode words, retaining accents, digits and multiplicity."""
    return Counter(re.findall(r'[^\W_]+', unicodedata.normalize('NFKC', text)))


def difference(expected, actual):
    missing, extra = expected - actual, actual - expected
    return dict(equal=not missing and not extra, expected_words=expected.total(),
                actual_words=actual.total(), missing=dict(sorted(missing.items())), extra=dict(sorted(extra.items())))


def snapshot(folder, pdf, scratch_parent):
    """Observe the real pipeline in an isolated directory, restoring process hooks."""
    captured = {}
    main_code = copy.main.__code__
    decode_code = copy.restore_prose_glyphs.__code__
    scan_code = copy.copy_ocr_scan.__code__

    def observe(frame, event, arg):
        if event != 'return':
            return
        if frame.f_code == main_code:
            captured['pages'] = frame.f_locals.get('pages', [])
        elif frame.f_code == decode_code:
            # Later ownership passes may add synthetic table fragments. The
            # decoded source before those passes is the conservation universe.
            captured['source_pages'] = deepcopy_module.deepcopy(frame.f_locals['pages'])
        elif frame.f_code == scan_code:
            captured.setdefault('scan_pages', []).extend(frame.f_locals['pages'])

    with tempfile.TemporaryDirectory(prefix='.linemap-', dir=scratch_parent) as tmp:
        work = Path(tmp) / folder.name
        work.mkdir()
        for source in sorted(folder.glob('*.json')):
            shutil.copyfile(source, work / source.name)
        (work / 'paper.pdf').symlink_to(pdf)
        previous = sys.getprofile()
        env = {key: os.environ.pop(key, None) for key in ('COPY_PAPER_PDF', 'COPY_PAPER_PDF_MAP')}
        try:
            sys.setprofile(observe)
            with contextlib.redirect_stdout(sys.stderr):
                copy.main(str(work))
        finally:
            sys.setprofile(previous)
            for key, value in env.items():
                if value is not None:
                    os.environ[key] = value
        captured['copy_text'] = (work / 'copy.md').read_text(encoding='utf-8')
        captured['saved_conservation'] = json.loads((work / 'copy.conservation.json').read_text())
        captured['scan_audit'] = json.loads((work / 'copy.scan.json').read_text()) if (work / 'copy.scan.json').exists() else {}
    if 'source_pages' not in captured:
        if not captured.get('scan_pages'):
            raise ValueError('copy program did not expose decoded source pages')
        captured['source_pages'] = captured['scan_pages']
    # A hybrid scan uses the OCR source once, not its native hidden layer too.
    scans = {p['page']: p for p in captured.get('scan_pages', [])}
    for i, page in enumerate(captured['source_pages']):
        if page['page'] in scans:
            source = scans[page['page']]
            captured['source_pages'][i] = dict(source, elements=[
                dict(run, id=f'ocr:{run["_scan_id"]}', kind='text', angle=run.get('angle', 0))
                for run in copy.scan_source_runs(source)])
    return captured


def png_size(path):
    with Path(path).open('rb') as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b'\x89PNG\r\n\x1a\n' or header[12:16] != b'IHDR':
        raise ValueError(f'invalid PNG: {path}')
    return struct.unpack('>II', header[16:24])


def render_page(pdf, number, output):
    prefix = output / f'p{number:02}'
    subprocess.run(['pdftoppm', '-r', '110', '-f', str(number), '-l', str(number),
                    '-singlefile', '-png', str(pdf), str(prefix)], check=True, capture_output=True, timeout=120)
    path = prefix.with_suffix('.png')
    return path, png_size(path)


def image_box(box, dpi, geometry):
    """Inverse of conserve.native_box: native unrotated PDF to Poppler pixels.

    The boxer retains MediaBox offsets and native text angles, even on rotated
    pages. Scaling region_box alone is wrong for those documents. Use the same
    transform as the existing PDF audit, inverted at each corner.
    """
    scale = dpi / 72
    x0, y0, x1, y1 = geometry['media']
    height, rotation = geometry['height'], geometry['rotation']
    points = []
    for u, v in ((box[0], box[1]), (box[0], box[3]), (box[2], box[1]), (box[2], box[3])):
        u, v = u / scale, height - v / scale
        if rotation == 90: x, y = v - y0, u - x0
        elif rotation == 180: x, y = x1 - u, v - y0
        elif rotation == 270: x, y = y1 - v, x1 - u
        else: x, y = u - x0, y1 - v
        points.append((x * 110 / 72, y * 110 / 72))
    return [min(x for x, y in points), min(y for x, y in points),
            max(x for x, y in points), max(y for x, y in points)]


def style(row, pattern):
    votes = Counter()
    for run in row:
        spans = run.get('font_spans') or [dict(font=run.get('font', ''), start=0, end=len(run['text']))]
        for span in spans:
            face = re.sub(r'^[A-Z]{6}\+', '', span.get('font') or '')
            votes[bool(re.search(pattern, face, re.I))] += max(1, span['end'] - span['start'])
    return votes[True] > votes[False]


def markdown_chunks(text):
    """Keep current output paragraph boundaries and offsets for automatic maps."""
    body = text.split(conserve.UNCERTAINTY, 1)[0]
    chunks = []
    table_lines_next = False
    section = None
    for match in re.finditer(r'\S(?:.*?\S)?(?=\n\s*\n|\Z)', body, re.S):
        value = match[0]
        if value.startswith('<!--') or value.strip() == '---':
            continue
        kind = 'paragraph'
        if value.startswith('# '): kind = 'title'
        elif re.match(r'#{2,3} ', value):
            kind = 'heading'
            section = 'references' if copy.REF_HEAD.match(value.lstrip('# ')) else (
                'article_info' if value.lstrip('# ') == 'Article information' else None)
        elif value.startswith('**Authors:'): kind = 'authors'
        elif value.startswith('**') and re.match(r'\*\*(?:Table|Fig)', value, re.I): kind = 'caption'
        elif value.startswith('| '): kind = 'table'
        elif value.startswith('> '): kind = 'footnote'
        if table_lines_next and value.startswith('- '): kind = 'table_lines'
        table_lines_next = value.startswith('[table structure not recovered:')
        cuts = [0]
        if kind == 'authors' or value.startswith('- ') and kind != 'table_lines':
            cuts += [m.end() for m in re.finditer(r'\n(?=- )', value)]
        for begin, end in zip(cuts, cuts[1:] + [len(value)]):
            part = value[begin:end].rstrip()
            part_kind = 'affiliation' if kind == 'authors' and begin else kind
            if kind == 'paragraph' and part.startswith('- '):
                part_kind = {'references': 'reference', 'article_info': 'article_info'}.get(section, 'list_item')
            key, case_key, positions = [], [], []
            for j, ch in enumerate(part):
                for c in conserve.normalise(ch):
                    key.append(c); case_key.append(c.upper() if ch.isupper() else c)
                    positions.append(match.start()+begin+j)
            chunks.append(dict(start=match.start()+begin, end=match.start()+begin+len(part), text=part, kind=part_kind,
                               key=''.join(key), case_key=''.join(case_key), positions=positions))
    return chunks


def locate_line(text, offsets, chunks):
    """Prefer a contiguous full-line witness over separately allocated words.

    The copy's occurrence ledger can allocate an isolated common word earlier
    than its surrounding line. Such an offset must not reorder the whole line.
    """
    votes = Counter(i for offset in offsets for i, chunk in enumerate(chunks)
                    if chunk['start'] <= offset < chunk['end'])
    key = conserve.normalise(text)
    matches = [(votes[i], i, chunk['key'].find(key)) for i, chunk in enumerate(chunks)
               if len(key) >= 8 and key in chunk['key']]
    if matches:
        _, i, start = max(matches, key=lambda value: (value[0], -value[1]))
        return i, chunks[i]['positions'][start]
    if votes:
        i = votes.most_common(1)[0][0]
        own = sorted(offset for offset in offsets if chunks[i]['start'] <= offset < chunks[i]['end'])
        return i, own[len(own)//2]
    return None, None


def line_locations(text, chunks):
    key = conserve.normalise(text)
    if len(key) < 8:
        return []
    result = []
    case_matches = []
    case_key = ''.join(conserve.normalise(ch).upper() if ch.isupper() else conserve.normalise(ch) for ch in text)
    for i, chunk in enumerate(chunks):
        chunk_case = chunk['case_key']
        at = chunk['key'].find(key)
        while at >= 0:
            result.append((i, chunk['positions'][at]))
            if chunk_case[at:at+len(key)] == case_key:
                case_matches.append(result[-1])
            at = chunk['key'].find(key, at+1)
    return case_matches or result


def source_roles(page, state):
    roles = {}
    actual = next((p for p in state.get('pages', []) if p['page'] == page['page']), page)
    blocks = {b['id']: b for b in page.get('blocks', [])}
    for block in (page.get('main_text') or {}).get('blocks', []):
        cls = block.get('cls')
        role = {'main': 'body', 'title': 'front', 'authors': 'front', 'furniture': 'furniture',
                'heading': 'heading', 'reference': 'reference'}.get(cls, 'body')
        if block.get('in_refs'): role = 'reference'
        for mid in blocks.get(block['id'], {}).get('members', []): roles[mid] = role
    scan = next((p for p in state.get('scan_audit', {}).get('pages', []) if p['page'] == page['page']), {})
    for mid, role in scan.get('destinations', {}).items():
        roles[f'ocr:{mid}'] = {'text': 'body', 'title': 'front', 'figure': 'figure_text'}.get(role, role)
    final = next((p for p in state.get('saved_conservation', {}).get('pages', []) if p['page'] == page['page']), actual)
    for entry in final.get('copy_conservation', {}).get('excluded', []):
        mid = f'ocr:{entry["id"]}' if scan else entry['id']
        roles[mid] = 'figure_text' if 'figure' in entry.get('reason', '') else 'furniture'
    return roles


def source_rows(page, roles):
    """Retain a physical baseline, cutting wide gutters and role boundaries.

    A table cell can contain several lines, but one exported line is never
    divided to fit a guessed table grid. Distinct angles are grouped separately.
    Every original run has exactly one source-row owner.
    """
    angles = defaultdict(list)
    for run in page['elements']:
        if run.get('kind', 'text') == 'text' and run.get('text', '').strip():
            angles[round(run.get('angle', 0)) % 360].append(dict(run, angle=run.get('angle', 0)))
    result = []
    columns = (page.get('main_text') or {}).get('columns', [])

    def column(run):
        if round(run.get('angle', 0)) % 360:
            return None
        box = run['box_px']
        matches = [i for i, (left, right) in enumerate(columns) if left-1 <= box[0] and box[2] <= right+1]
        return matches[0] if len(matches) == 1 else None

    for angle, runs in sorted(angles.items()):
        fr = copy.frame(angle)
        for row in (copy.scan_rows(runs) if any('_scan_id' in run for run in runs) else copy.text_rows(runs)):
            groups = []
            for run in row:
                previous = groups[-1][-1] if groups else None
                em = max(run.get('run_size_px') or run.get('size_px') or 10,
                         (previous or {}).get('run_size_px') or 10)
                gap = fr(run['box_px'])[0] - fr(previous['box_px'])[2] if previous else 0
                distinct_columns = previous and column(run) is not None and column(previous) is not None and column(run) != column(previous)
                distinct_regions = previous and run.get('region') and previous.get('region') and run['region'] != previous['region']
                separate = previous and (gap > em or distinct_columns or distinct_regions and gap > .5 * em or
                    roles.get(run['id'], 'body') != roles.get(previous['id'], 'body'))
                if not groups or separate: groups.append([])
                groups[-1].append(run)
            result.extend(groups)
    return sorted(result, key=lambda row: (*copy.hull(e['box_px'] for e in row)[1::-1],
                                          tuple(e['id'] for e in row)))


def automatic_map(document, provenance, chunks, state):
    """Use current placements, never synthesize or copy source text into a map."""
    mapping = dict(paper=document['paper'], front={}, body=[], references=[], end_matter=[],
                   furniture={key: [] for key in ['running_head', 'page_number', 'figure_text', 'watermark', 'licence', 'other']},
                   split_lines=[], notes=[])
    by_chunk = defaultdict(list)
    remaining = []
    for page in document['pages']:
        for line in page['lines']:
            record = provenance[line['id']]
            if line['program_role'] in ('furniture', 'figure_text'):
                key = 'figure_text' if line['program_role'] == 'figure_text' else 'other'
                if key == 'other' and line['text'].strip().isdigit(): key = 'page_number'
                mapping['furniture'][key].append(line['id'])
            elif record['chunk'] is not None:
                by_chunk[record['chunk']].append(line)
            else:
                remaining.append(line)
    in_refs = False
    in_info = False
    for i, chunk in enumerate(chunks):
        lines = sorted(by_chunk[i], key=lambda line: (provenance[line['id']]['order'], line['id']))
        ids = [line['id'] for line in lines]
        kind, text = chunk['kind'], chunk['text']
        if kind == 'heading':
            in_info = bool(re.match(r'## Article information', text))
            in_refs = bool(re.match(r'## (?:References|Bibliography)', text, re.I))
        if not ids: continue
        publisher = re.match(r'^[>\s]*(How to cite this article)\s*:', text, re.I)
        if publisher and mapping['references']:
            mapping['end_matter'].append(dict(label=publisher[1], lines=ids))
            continue
        if kind in ('title', 'authors'):
            mapping['front'].setdefault(kind, []).extend(ids)
            continue
        if kind in ('affiliation', 'article_info'):
            mapping['front'].setdefault('affiliations' if kind == 'affiliation' else 'article_info', []).append(ids)
            continue
        if kind == 'heading':
            mapping['body'].append(dict(kind='heading', level=3 if text.startswith('### ') else 2, lines=ids))
        elif kind in ('table', 'table_lines'):
            # Output cells can split a source line. Only a mapper with page
            # evidence may choose splits; the automatic map stays conservative.
            # Preserve source baseline order inside a table, in its reading
            # frame, rather than sorting by the first recovered cell token.
            lines.sort(key=lambda line: (provenance[line['id']]['page'],
                copy.frame(provenance[line['id']]['angle'])(provenance[line['id']]['source_box'])[1],
                copy.frame(provenance[line['id']]['angle'])(provenance[line['id']]['source_box'])[0]))
            mapping['body'].append(dict(kind='table_lines', caption=[], lines=[line['id'] for line in lines],
                reason='Current program table layout has not been verified as whole-line cells.'))
        elif kind == 'caption':
            label = re.search(r'(Table|Figure|Fig\.?)\s*(\S+)', text, re.I)
            number = label[2].strip('.*') if label else '?'
            of = ('Table' if label and label[1].lower() == 'table' else 'Figure') + ' ' + (number or '?')
            mapping['body'].append(dict(kind='caption', of=of, lines=ids))
        elif in_refs or kind == 'reference':
            # Existing output references may share a list block. Split at its
            # individual output lines, using provenance offsets only.
            groups = defaultdict(list)
            for line in lines:
                offset = provenance[line['id']]['order']
                groups[state['copy_text'].count('\n', chunk['start'], offset)].append(line['id'])
            mapping['references'].extend(groups.values())
        elif in_info:
            mapping['front'].setdefault('article_info', []).append(ids)
        else:
            mapping['body'].append(dict(kind=kind if kind in ('footnote', 'paragraph', 'list_item') else 'paragraph', lines=ids))
    for line in remaining:
        mapping['body'].append(dict(kind='paragraph', lines=[line['id']]))
    if remaining:
        mapping['notes'].append('Current placement could not be located for line ids: ' + ', '.join(line['id'] for line in remaining))
    uncertainty = state['copy_text'].partition(conserve.UNCERTAINTY)[2]
    mapping['notes'].extend(line[2:] for line in uncertainty.splitlines() if line.startswith('- ') and line != '- none')
    return mapping


def refresh_program_map(document, audit, text):
    """Rebuild only roles/order from saved source provenance and the current copy.

    This is also used by round-trip tests. No source text, boxes or line IDs
    are inferred from Markdown, and no copy of the PDF needs to be rendered.
    """
    chunks = markdown_chunks(text)
    candidates = {}
    all_lines = [line for page in document['pages'] for line in page['lines']]
    for line in all_lines:
        candidates[line['id']] = line_locations(line['text'], chunks)
    for page in document['pages']:
        for line in page['lines']:
            record = audit['lines'][line['id']]
            line['program_role'] = record.get('source_role', line['program_role'])
            chunk, order = locate_line(line['text'], [record['order']], chunks)
            options = candidates[line['id']]
            if len(options) == 1:
                chunk, order = options[0]
            if len(options) > 1 and line['program_role'] not in ('furniture', 'figure_text', 'table'):
                # Repeated journal tails must follow their local reference,
                # not the first identical tail elsewhere in the bibliography.
                fr = copy.frame(record['angle']); box = fr(record['source_box'])
                neighbors = []
                for other in page['lines']:
                    options2 = candidates[other['id']]
                    other_record = audit['lines'][other['id']]
                    if other is line or len(options2) != 1 or other_record['angle'] != record['angle']:
                        continue
                    b = fr(other_record['source_box'])
                    overlap = min(box[2], b[2]) - max(box[0], b[0])
                    distance = abs((box[1]+box[3]-b[1]-b[3])/2)
                    if overlap > .6 * min(box[2]-box[0], b[2]-b[0]) and 0 < distance < 3 * max(box[3]-box[1], b[3]-b[1]):
                        neighbors.append((distance, options2[0][1], box[1]+box[3] > b[1]+b[3]))
                if neighbors:
                    _, anchor, after = min(neighbors)
                    directional = [option for option in options if option[1] > anchor] if after else [
                        option for option in options if option[1] < anchor]
                    chunk, order = min(directional or options, key=lambda option: abs(option[1]-anchor))
            record.update(chunk=chunk, order=order if order is not None else len(text))
            # The copy explicitly recovers article information (notably DOI
            # records) from first-page furniture. Its actual front placement
            # outranks the earlier exclusion record when the complete line
            # has a unique witness there.
            if (page['page'] == min(p['page'] for p in document['pages']) and len(options) == 1 and
                    re.fullmatch(r'(?:DOI\s*:\s*)?10\.\d{4,9}/\S+', line['text'].strip(), re.I) and
                    chunks[options[0][0]]['kind'] == 'article_info'):
                line['program_role'] = 'front'
            if line['program_role'] not in ('furniture', 'figure_text') and chunk is not None:
                line['program_role'] = {'title': 'front', 'authors': 'front', 'affiliation': 'front',
                    'article_info': 'front', 'paragraph': 'body', 'list_item': 'body', 'table_lines': 'table'}.get(
                        chunks[chunk]['kind'], chunks[chunk]['kind'])
    mapping = automatic_map(document, audit['lines'], chunks, dict(copy_text=text))
    # The legacy author formatter substitutes semicolons for a byline's
    # conjunction. Represent that omission explicitly, using legal splits,
    # only when its entire author output contains no such printed word.
    if not any(re.search(r'\band\b', chunk['text'], re.I) for chunk in chunks if chunk['kind'] == 'authors'):
        by_id = {line['id']: line for line in all_lines}
        authors = []
        for mid in mapping['front'].get('authors', []):
            value = by_id[mid]['text']
            matches = list(re.finditer(r'(?<!\S)and(?=\s)', value))
            if len(matches) != 1:
                authors.append(mid); continue
            match = matches[0]; left = value[:match.start()].rstrip(); right = value[match.end():].lstrip()
            if not left or not right:
                authors.append(mid); continue
            tail = value[match.start():]
            if value.count(tail) != 1 or tail.count(right) != 1:
                authors.append(mid); continue
            mapping['split_lines'].extend([
                dict(id=mid, at=tail, new_ids=[mid+'a', mid+'b']),
                dict(id=mid+'b', at=right, new_ids=[mid+'ba', mid+'bb'])])
            authors.extend([mid+'a', mid+'bb'])
            mapping['furniture']['other'].append(mid+'ba')
            mapping['notes'].append(f'Current author formatter omits the byline conjunction at {mid} (retained as furniture after splitting).')
        if authors: mapping['front']['authors'] = authors
    return mapping


def export(folder, pdf, output):
    folder, pdf, output = Path(folder).resolve(), Path(pdf).resolve(), Path(output).resolve()
    if folder == output or folder in output.parents or output in folder.parents:
        raise ValueError('OUT must be outside COPY_DIR with neither directory containing the other; source runs are read-only')
    if not pdf.is_file() or not (folder / 'main-text.json').is_file():
        raise ValueError('PDF or copy main-text.json is missing')
    output.mkdir(parents=True, exist_ok=True)
    state = snapshot(folder, pdf, output)
    geometry = conserve.page_geometry(pdf)
    pages = sorted(state['source_pages'], key=lambda page: page['page'])
    if [p['page'] for p in pages] != sorted(geometry):
        raise ValueError('copy page records do not cover every PDF page exactly once')
    chunks = markdown_chunks(state['copy_text'])
    placed = defaultdict(list)
    ledger = state['saved_conservation'].get('token_ledger')
    if ledger is None:
        source = [dict(page=p['page'], id=e['id'], text=e['text'], box=e['box_px'])
                  for p in pages for e in p['elements'] if e.get('text', '').strip() and
                  source_roles(p, state).get(e['id']) not in ('furniture', 'figure_text')]
        ledger = conserve.token_ledger(state['copy_text'].split(conserve.UNCERTAINTY)[0], source)
    for token in ledger.get('tokens', []):
        if token.get('output'):
            placed[token['page'], token['run']].append(token['output'][0])
    image_dir = output / 'pages'
    image_dir.mkdir(exist_ok=True)
    document = dict(paper=folder.name, pages=[])
    provenance = {}
    source_words, line_words = Counter(), Counter()
    raw_characters, export_characters = Counter(), Counter()
    for page in pages:
        n = page['page']
        print(f'{folder.name}: exporting page {n}/{len(pages)}', file=sys.stderr, flush=True)
        _, (width, height) = render_page(pdf, n, image_dir)
        dpi = page.get('params', {}).get('dpi', 150)
        if not isinstance(dpi, (int, float)) or not math.isfinite(dpi) or dpi <= 0:
            raise ValueError(f'page {n}: invalid source dpi')
        records = dict(page=n, width_px=width, height_px=height, image=f'pages/p{n:02}.png', lines=[])
        roles = source_roles(page, state)
        seen = Counter()
        expected = Counter(e['id'] for e in page['elements'] if e.get('kind', 'text') == 'text' and e.get('text', '').strip())
        if any(count != 1 for count in expected.values()): raise ValueError(f'page {n}: duplicate source run ids')
        for k, row in enumerate(source_rows(page, roles), 1):
            mid = f'p{n}.l{k:03}'
            sources = [source for e in row for source in e.get('_subscript_sources', [e])]
            seen.update(e['id'] for e in sources)
            # Font runs are decoded by the copy, then its native row reader
            # handles attached marks, spacing and position-based ordering.
            decoded = [dict(e, text=copy.glyph_spacing(e)) for e in row]
            text = copy.compose_accents(copy.prose_row(decoded, page)[0])
            source_text = ' '.join(e['text'].strip() for e in sources)
            source_words.update(words(source_text)); line_words.update(words(text))
            raw_characters.update(c for c in unicodedata.normalize('NFKC', source_text) if c.isalnum())
            export_characters.update(c for c in unicodedata.normalize('NFKC', text) if c.isalnum())
            box = image_box(copy.hull(e['box_px'] for e in sources), dpi, geometry[n])
            unclipped = list(box)
            box = [round(max(0, min(value, width if j % 2 == 0 else height)), 4) for j, value in enumerate(box)]
            if box[0] >= box[2] or box[1] >= box[3]:
                raise ValueError(f'{mid}: source box outside page image: {unclipped}')
            offsets = [offset for e in sources for offset in placed[n, e['id']]]
            chunk, order = locate_line(text, offsets, chunks)
            source_role = role = Counter(roles.get(e['id'], 'body') for e in sources).most_common(1)[0][0]
            if role not in ('furniture', 'figure_text') and chunk is not None:
                role = {'title': 'front', 'authors': 'front', 'affiliation': 'front', 'article_info': 'front',
                        'paragraph': 'body', 'list_item': 'body', 'table_lines': 'table'}.get(chunks[chunk]['kind'], chunks[chunk]['kind'])
                if role == 'body' and all(roles.get(e['id']) == 'reference' for e in sources): role = 'reference'
            size = max(e.get('run_size_px') or e.get('size_px') or e['box_px'][3]-e['box_px'][1] for e in sources) * 110 / dpi
            records['lines'].append(dict(id=mid, text=text, box=box, size=round(size, 4),
                bold=style(sources, r'bold|(?:^|[.,_-])(?:b|bd)(?:$|[.,_-])'),
                italic=style(sources, r'italic|oblique|(?:^|[.,_-])(?:i|it)(?:$|[.,_-])'), program_role=role))
            provenance[mid] = dict(page=n, runs=[e['id'] for e in sources], source_text=source_text,
                source_box=copy.hull(e['box_px'] for e in sources), angle=row[0].get('angle', 0), source_role=source_role,
                chunk=chunk, order=order if order is not None else len(state['copy_text']),
                word_difference=difference(words(source_text), words(text)),
                clipped=any(abs(a-b) > .001 for a, b in zip(box, unclipped)))
        if seen != expected:
            raise ValueError(f'page {n}: source run conservation failed: missing={expected-seen}, extra={seen-expected}')
        document['pages'].append(records)
    pdf_text = subprocess.run(['pdftotext', '-layout', str(pdf), '-'], check=True, capture_output=True,
                              text=True, timeout=120).stdout
    audit = dict(paper=folder.name, copy_code_sha256=copy.COPY_CODE_SHA256,
        normalization='case-sensitive NFKC Unicode alphanumeric words; multiplicity retained',
        source_run_ownership='every nonempty decoded source run appears exactly once',
        decoded_source_words=difference(source_words, line_words),
        decoded_source_characters=difference(raw_characters, export_characters),
        pdf_text_layer_words=difference(words(pdf_text), line_words),
        lines=provenance)
    mapping = refresh_program_map(document, audit, state['copy_text'])
    assembler = module('_export_lines_assembler', ROOT / 'tools/assemble_map.py')
    assembler.validate(document, mapping)
    for name, value in [('lines.json', document), ('lines.audit.json', audit), ('program.map.json', mapping)]:
        (output / name).write_text(json.dumps(value, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    (output / 'program.copy.md').write_text(state['copy_text'], encoding='utf-8')
    print(json.dumps(dict(paper=folder.name, pages=len(pages), lines=len(provenance),
                         decoded_source_words=audit['decoded_source_words'])))
    return document, audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('copy_dir')
    parser.add_argument('pdf')
    parser.add_argument('out')
    args = parser.parse_args()
    try:
        export(args.copy_dir, args.pdf, args.out)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.exit(2, f'export_lines: {exc}\n')


if __name__ == '__main__':
    main()
