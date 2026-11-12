#!/usr/bin/env python3
"""Measure Markdown table cells and structure against publisher JATS.

Usage: /usr/bin/python3 -I tools/score_tables.py COPIES_DIR TRUTH_DIR [ids...]
       /usr/bin/python3 -I tools/score_tables.py --self-test
Optional --json PATH saves the same counts and short diagnostic examples.
The default article list comes from TRUTH_DIR, so missing copies cannot improve
the score. No input file is changed. Only the standard library is used.

Captions are matched one to one by normalized text, never by number alone.
Exact cell equality (not token overlap or substring matching) earns credit.
Flagged line tables are matched as recovered-but-unstructured. Their cell text
recall counts non-overlapping complete phrases in the printed list lines;
they receive no row, column or whole-table credit. These two forms of recovery
are reported separately, so preserving text never implies recovered structure.
An explicitly empty recovered frame remains an unmatched flagged caption with
zero text and structure credit; following prose/list items cannot supply its cells.
Spans are expanded to rectangular slots, repeating text across both colspan
and rowspan. Empty slots/rows/columns have no weight. Cell recall is multiset
recall of those slots; duplicate values cannot earn unlimited credit. A row
or column passes if its nonempty cell multiset fits within one copy row or
column. Maximum order-preserving, one-to-one axis matching prevents one copy
row/column from satisfying several truth axes and penalizes reordering.
Unmatched, cell-scorable tables contribute zero to every metric. Overall
ratios are micro-averages, not averages of article percentages. Whole means
cell recall >= .95 and every truth row and column passes.

Multiple HTML tables inside one table-wrap are panels, stacked in XML order.
Markdown grids under one caption and explicitly labelled continuations are
stacked likewise. Image-only tables remain in the caption denominator but
are explicitly excluded from cell/row/column/whole denominators.

Diagnostics are evidence-based heuristics, may overlap, and do not change the
score. An additional 'cell text/placement differs' residual avoids pretending
that every OCR error or publisher/PDF discrepancy is a structural failure.
"""

import argparse
from collections import Counter
from dataclasses import dataclass, field
import difflib
import html
import json
from pathlib import Path
import re
import sys
import time
import unicodedata
import xml.etree.ElementTree as ET


CLASSES = ('header fused with row 1', 'rows merged', 'columns merged',
           'cells torn', 'caption text in the grid', 'rows split',
           'missing rows', 'table absent', 'structure not recovered', 'cell text/placement differs')
TRANSLATION = str.maketrans({**dict.fromkeys('‐‑‒–—―−﹘﹣－', '-'),
                           **dict.fromkeys('‘’‚‛′', "'"),
                           **dict.fromkeys('“”„‟″', '"'),
                           '\u00ad': '', '\u200b': '', '\ufeff': ''})
# Remove raised markers before NFKC flattens them into ordinary characters.
SUPERSCRIPTS = str.maketrans('', '', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱᵃᵇᶜᵈᵉᶠᵍʰʲᵏˡᵐᵒᵖʳˢᵗᵘᵛʷˣʸᶻ')


def normalise(text):
    """Typography only; retain numbers, signs, punctuation and word spacing."""
    text = html.unescape(text)
    text = re.sub(r'<sup\b[^>]*>.*?</sup>', '', text, flags=re.I | re.S)
    text = re.sub(r'<(?:br|/p|/div)\b[^>]*>', ' ', text, flags=re.I)
    text = re.sub(r'</?[a-z][a-z0-9-]*(?:\s[^<>]*?)?/?>', '', text, flags=re.I)
    text = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', text)
    text = re.sub(r'\[\^[^\]]+\]', '', text)
    text = re.sub(r'\*\*(.+?)\*\*|__(.+?)__', lambda m: m[1] or m[2], text)
    text = re.sub(r'(?<!\w)([*_])([^*_]+)\1(?!\w)', r'\2', text)
    text = re.sub(r'\\([\\|*_`])', r'\1', text)
    text = unicodedata.normalize('NFKC', text.translate(SUPERSCRIPTS))
    return ' '.join(text.translate(TRANSLATION).casefold().split())


def tag(element):
    return element.tag.rsplit('}', 1)[-1] if isinstance(element.tag, str) else ''


def child(element, name):
    return next((c for c in element if tag(c) == name), None)


def xml_text(element, markers=False):
    """Keep inline adjacency and tails; exclude only marked superscripts/notes."""
    if element is None:
        return ''
    pieces = [element.text or '']
    for c in element:
        skip = tag(c) == 'sup' or (tag(c) == 'xref' and c.get('ref-type') == 'table-fn')
        if not skip or markers:
            if tag(c) in ('p', 'break', 'br', 'div'):
                pieces.append(' ')
            pieces.append(xml_text(c, markers))
            if tag(c) in ('p', 'break', 'br', 'div'):
                pieces.append(' ')
        pieces.append(c.tail or '')
    return ''.join(pieces)


@dataclass
class Table:
    label: str
    caption: str
    grid: list = field(default_factory=list)
    headers: set = field(default_factory=set)
    aliases: dict = field(default_factory=dict)
    parts: int = 0
    printed_lines: list = field(default_factory=list)
    gated: bool = False


def rectangular(rows):
    width = max(map(len, rows), default=0)
    return [row + [''] * (width - len(row)) for row in rows]


def truth_tables(root):
    tables = []
    for ordinal, wrap in enumerate((e for e in root.iter() if tag(e) == 'table-wrap'), 1):
        table = Table(xml_text(child(wrap, 'label')).strip() or f'Table {ordinal}',
                      xml_text(child(wrap, 'caption')).strip())
        for part in (e for e in wrap.iter() if tag(e) == 'table'):
            # Nested tables are not independent panels; reject rather than
            # silently counting their cells twice.
            if any(tag(e) == 'table' for e in list(part.iter())[1:]):
                raise ValueError('nested HTML tables are unsupported')
            cells, headers = {}, set()
            rows = []
            for section in part:
                if tag(section) == 'tr':
                    rows.append((section, False, None))
                elif tag(section) in ('thead', 'tbody', 'tfoot'):
                    group = [r for r in section if tag(r) == 'tr']
                    end = len(rows) + len(group)
                    rows.extend((r, tag(section) == 'thead', end) for r in group)
            for r, (row, is_header, group_end) in enumerate(rows):
                c = 0
                if is_header or any(tag(e) == 'th' for e in row):
                    headers.add(r)
                for element in row:
                    if tag(element) not in ('td', 'th'):
                        continue
                    while (r, c) in cells:
                        c += 1
                    text = normalise(xml_text(element))
                    marked = normalise(xml_text(element, markers=True))
                    if marked != text and text:
                        table.aliases[marked] = text
                        # A flattened footnote may acquire a separating space.
                        if marked.startswith(text):
                            table.aliases[text + ' ' + marked[len(text):].lstrip()] = text
                    height, width = int(element.get('rowspan', '1')), int(element.get('colspan', '1'))
                    if height == 0:
                        height = (group_end or len(rows)) - r
                    if not 1 <= height <= (group_end or len(rows)) - r or not 1 <= width <= 1000:
                        raise ValueError('invalid rowspan/colspan')
                    for rr in range(r, r + height):
                        for cc in range(c, c + width):
                            if (rr, cc) in cells:
                                raise ValueError('overlapping JATS spans')
                            cells[rr, cc] = text
                    c += width
            width = max((c + 1 for r, c in cells), default=0)
            offset = len(table.grid)
            table.headers.update(offset + r for r in headers)
            table.grid.extend([[cells.get((r, c), '') for c in range(width)] for r in range(len(rows))])
            table.parts += 1
        table.grid = rectangular(table.grid)
        tables.append(table)
    return tables


def split_row(line):
    """Split unescaped pipes, including a pipe preceded by an escaped slash."""
    line = line.strip()
    if not line.startswith('|') or not line.endswith('|'):
        return None
    pieces, part, slashes = [], [], 0
    for char in line[1:-1]:
        if char == '|' and slashes % 2 == 0:
            pieces.append(''.join(part).strip())
            part = []
        else:
            part.append(char)
        slashes = slashes + 1 if char == '\\' else 0
    pieces.append(''.join(part).strip())
    return pieces


def caption_parts(caption):
    text = normalise(caption)
    match = re.match(r'^(?:(?:supplemental|supplementary)\s+)?table\s+(s?\d+[a-z]?)\b[. :;-]*', text)
    label = match[1] if match else ''
    body = text[match.end():] if match else re.sub(r'^table\b\s*', '', text)
    return label, ' '.join(re.findall(r'\w+', body))


def copy_tables(markdown):
    """Associate grids or explicit gated lists with their nearest bold float caption.

    Stop at body prose or a heading, so a distant orphan grid cannot rescue a
    caption-only table. Ignore blank lines and page comments between panels.
    """
    tables, active, accepting = [], None, False
    remaining=0
    for line in markdown.splitlines():
        caption = re.match(r'^\s*\*\*(.*?)\*\*\s*$', line)
        if caption:
            remaining=0
            text = caption[1]
            if re.match(r'(?:(?:Supplemental|Supplementary)\s+)?Table\b', text, re.I):
                label, _ = caption_parts(text)
                continued = bool(re.search(r'\bcontinued\b', text, re.I))
                previous = next((t for t in reversed(tables)
                                 if label and caption_parts(t.caption)[0] == label), None)
                if continued and previous is not None:
                    active = previous
                else:
                    active = Table('Table ' + label if label else 'Table (unlabelled)', text)
                    tables.append(active)
                accepting = True
            else:
                active, accepting = None, False
            continue
        flag=re.fullmatch(r'\[table structure not recovered: (\d+) printed lines follow as printed, left to right, top to bottom\]',line.strip())
        empty_flag=line.strip()=="[table structure not recovered: no printed lines located in the caption's recovered frame]"
        if (flag or empty_flag) and active is not None and accepting:
            active.gated=True; remaining=int(flag[1]) if flag else 0
            if empty_flag: accepting=False
            continue
        if remaining and active is not None and accepting and line.startswith('- '):
            raw=re.sub(r'\\([\\`*_\[\]<>|])',r'\1',line[2:])
            active.printed_lines.append(normalise(raw));remaining-=1
            if not remaining: accepting=False
            continue
        cells = split_row(line)
        if cells is not None and active is not None and accepting:
            if not all(re.fullmatch(r':?-{3,}:?', c.strip()) for c in cells):
                active.grid.append([normalise(c) for c in cells])
            continue
        if not line.strip() or re.fullmatch(r'\s*<!--.*?-->\s*', line):
            continue
        accepting = False
    for table in tables:
        table.grid = rectangular(table.grid)
    return tables


def caption_similarity(truth, copy):
    label, a = caption_parts(truth.label + '. ' + truth.caption)
    other, b = caption_parts(copy.caption)
    if not a or not b:
        return 0.0  # a table number is never caption evidence
    similarity = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    same = bool(label and label == other)
    # Recover a caption truncated at the start of its second line, while
    # requiring four words of actual caption evidence and its table label.
    prefix = (a.startswith(b) or b.startswith(a)) and min(len(a.split()), len(b.split())) >= 4
    if same and prefix and min(len(a), len(b)) / max(len(a), len(b)) >= .3:
        similarity = max(similarity, .85)
    threshold = .72 if same else .90
    if label and other and label != other:
        threshold = .97
    return similarity + (.02 if same else 0) if similarity >= threshold else 0.0


def assignment(weights):
    """Maximum-weight one-to-one assignment; dummy columns allow abstention.

    Hungarian algorithm, rectangular O(n^2 m). A positive edge receives a
    cardinality bonus, so an otherwise valid second match is not discarded.
    """
    n = len(weights)
    if not n:
        return {}
    actual = len(weights[0])
    costs = [[-(n + 1 + w) if w else 0 for w in row] + [0] * n for row in weights]
    m = actual + n
    u, v, p, way = [0.] * (n + 1), [0.] * (m + 1), [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0], j0 = i, 0
        minimum, used = [float('inf')] * (m + 1), [False] * (m + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], float('inf'), 0
            for j in range(1, m + 1):
                if not used[j]:
                    cur = costs[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minimum[j]:
                        minimum[j], way[j] = cur, j0
                    if minimum[j] < delta:
                        delta, j1 = minimum[j], j
            for j in range(m + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minimum[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    return {p[j] - 1: j - 1 for j in range(1, actual + 1)
            if p[j] and weights[p[j] - 1][j - 1] > 0}


def nonempty(values):
    return Counter(value for value in values if value)


def axes(grid, column=False):
    return [count for values in (zip(*grid) if column else grid) if (count := nonempty(values))]


def axis_hits(expected, actual):
    previous = [0] * (len(actual) + 1)
    for wanted in expected:
        current = [0]
        for j, found in enumerate(actual, 1):
            current.append(max(current[-1], previous[j],
                               previous[j - 1] + int(wanted <= found)))
        previous = current
    return previous[-1]


def short(text, words=12):
    return ' '.join(text.split()[:words])


def contains(container, needle):
    if not needle:
        return False
    return bool(re.search(r'(?<![\w.])' + re.escape(needle) + r'(?![\w.])', container))


def diagnose(truth, grid, result):
    """Classify only witnessed joins/splits; leave unexplained text differences."""
    failures = {}
    source = truth.grid
    cells = [(r, c, text) for r, row in enumerate(source) for c, text in enumerate(row) if text]
    found = [(r, c, text) for r, row in enumerate(grid) for c, text in enumerate(row) if text]
    exact = nonempty(t for r, c, t in found)
    haystack = '\n'.join(exact)
    actual_rows = [nonempty(row) for row in grid]
    expected_rows = [nonempty(row) for row in source]
    headers = truth.headers or ({0} if source else set())
    data_start = next((r for r in range(len(source)) if r not in headers), len(source))
    caption = caption_parts(truth.label + '. ' + truth.caption)[1].split()
    truth_text = ' '.join(t for r, c, t in cells)
    for _, _, text in found:
        tokens = ' '.join(re.findall(r'\w+', text))
        for start in range(max(0, len(caption) - 3)):
            fragment = ' '.join(caption[start:start + 4])
            if fragment in tokens and fragment not in truth_text:
                failures.setdefault('caption text in the grid', short(text))
                break
    if result['whole']:
        return [{'class': name, 'example': example} for name, example in failures.items()]
    # Adjacent truth cells concatenated into one copy cell. Require the whole
    # concatenation, not isolated repeated numeric values found by substring.
    for vertical in (False, True):
        lines = list(zip(*source)) if vertical else source
        for line in lines:
            for start in range(len(line)):
                for stop in range(start + 2, min(len(line), start + 5) + 1):
                    parts = [t for t in line[start:stop] if t]
                    if len(parts) < 2:
                        continue
                    joined = ' '.join(parts)
                    if joined in haystack and contains(haystack, joined):
                        kind = 'rows merged' if vertical else 'columns merged'
                        if vertical and start in headers and data_start in range(start, stop):
                            kind = 'header fused with row 1'
                        failures.setdefault(kind, short(joined))
    # A missing exact cell reconstructed from adjacent horizontal/vertical
    # fragments witnesses a torn cell or a wrapped row split, respectively.
    fragments = []
    for vertical in (False, True):
        joined = set()
        lines = list(zip(*grid)) if vertical and grid else grid
        for line in lines:
            for start in range(len(line)):
                for stop in range(start + 2, min(len(line), start + 5) + 1):
                    parts = [t for t in line[start:stop] if t]
                    if len(parts) > 1:
                        joined.update((' '.join(parts), ''.join(parts)))
        fragments.append(joined)
    for _, _, text in cells:
        if not exact[text]:
            for vertical, joined in enumerate(fragments):
                if text in joined:
                    failures.setdefault('rows split' if vertical else 'cells torn', short(text))
    for r, wanted in enumerate(expected_rows):
        if not wanted or any(wanted <= actual for actual in actual_rows):
            continue
        # Whole cells on adjacent rows, rather than a single torn text cell.
        for start in range(len(actual_rows)):
            combined = Counter()
            contributing = 0
            for stop in range(start, min(start + 3, len(actual_rows))):
                combined += actual_rows[stop]
                contributing += bool(wanted & actual_rows[stop])
                if contributing >= 2 and wanted <= combined:
                    failures.setdefault('rows split', short(' '.join(source[r])))
        if r not in headers and not any(contains(haystack, expected) or
                expected in fragments[0] or expected in fragments[1] for expected in wanted):
            failures.setdefault('missing rows', short(' '.join(source[r])))
    if not failures:
        missing = next(iter(nonempty(t for _, _, t in cells) - exact), '')
        failures['cell text/placement differs'] = short(missing or 'Cell texts survive, but row or column placement/order differs.')
    return [{'class': name, 'example': failures[name]} for name in CLASSES if name in failures]


def measure(truth, copy):
    grid = [[truth.aliases.get(t, t) for t in row] for row in copy.grid] if copy else []
    expected = nonempty(t for row in truth.grid for t in row)
    found = nonempty(t for row in grid for t in row)
    unstructured=bool(copy and copy.gated)
    if unstructured:
        # Consume each occurrence once, longest phrases first. A value inside a
        # larger number or a different signed/decimal value earns no credit.
        available='\n'.join(copy.printed_lines)
        occupied=set()
        for cell,count in sorted((expected-found).items(),key=lambda kv:(-len(kv[0]),kv[0])):
            variants=[cell]+[marked for marked,plain in truth.aliases.items() if plain==cell]
            hits=0
            for variant in variants:
                for match in re.finditer(r'(?<!\S)'+re.escape(variant)+r'(?!\S)',available):
                    span=set(range(match.start(),match.end()))
                    if span & occupied: continue
                    occupied.update(span);hits+=1
                    if hits==count: break
                if hits==count: break
            found[cell]+=hits
    rows, columns = axes(truth.grid), axes(truth.grid, column=True)
    result = dict(label=truth.label, caption=short(truth.caption), parts=truth.parts,
                  matched=copy is not None, scorable=bool(expected), unstructured=unstructured,
                  cells_found=sum((expected & found).values()), cells_truth=sum(expected.values()),
                  rows_found=axis_hits(rows, axes(grid)), rows_truth=len(rows),
                  columns_found=axis_hits(columns, axes(grid, column=True)), columns_truth=len(columns))
    result['whole'] = bool(expected and copy and
        not unstructured and
        result['cells_found'] / result['cells_truth'] >= .95 and
        result['rows_found'] == result['rows_truth'] and
        result['columns_found'] == result['columns_truth'])
    result['failures'] = []
    if not copy:
        result['failures'] = [{'class': 'table absent', 'example': short(truth.caption)}]
    elif unstructured:
        result['rows_found']=result['columns_found']=0
        result['failures']=[{'class':'structure not recovered','example':'Caption matched; printed lines retained without row or column assignments.'}]
    elif expected:
        result['failures'] = diagnose(truth, grid, result)
    return result


COUNT_KEYS = ('cells_found', 'cells_truth', 'rows_found', 'rows_truth',
              'columns_found', 'columns_truth')


def totals(tables):
    result = {key: sum(t[key] for t in tables) for key in COUNT_KEYS}
    result.update(tables_truth=len(tables), tables_matched=sum(t['matched'] for t in tables),
                  tables_unstructured=sum(t.get('unstructured',False) for t in tables),
                  tables_scorable=sum(t['scorable'] for t in tables),
                  whole=sum(t['whole'] for t in tables))
    return result


def score_paper(identifier, xml, markdown, missing_copy=False):
    expected = truth_tables(ET.fromstring(xml))
    copies = copy_tables(markdown)
    candidates = [c for c in copies if c.grid or c.printed_lines]
    matches = assignment([[caption_similarity(t, c) for c in candidates] for t in expected])
    tables = []
    for i, table in enumerate(expected):
        copy = candidates[matches[i]] if i in matches else None
        result = measure(table, copy)
        if copy is None:
            label = caption_parts(table.label)[0]
            same_label = [c for c in copies if label and caption_parts(c.caption)[0] == label]
            result['unmatched_reason'] = ('no copy table' if missing_copy or not candidates or
                (same_label and not any(c.grid or c.printed_lines for c in same_label)) else 'caption differs')
            result['unmatched_detail'] = ('copy.md missing' if missing_copy else
                'caption present without a grid or flagged lines' if same_label and not any(c.grid or c.printed_lines for c in same_label) else
                'no captioned grids' if not candidates else 'no unused grid passes caption matching')
        else:
            result['caption_similarity'] = round(caption_similarity(table, copy), 4)
        if not result['scorable']:
            result['truth_note'] = 'no nonempty HTML cells; excluded from cell/row/column/whole scores'
        tables.append(result)
    return dict(id=identifier, missing_copy=missing_copy, copy_tables=len(candidates),
                **totals(tables), tables=tables)


NOTES = """A perfect textual copy scores 100% cell recall, 100% rows, 100% columns,
and all cell-scorable tables whole. Scores include unmatched tables as zero;
image-only truth tables are excluded only from cell/row/column/whole denominators.
No-table papers have n/a ratios. Overall scores weight cells, rows and columns
by their counts. Headers count. Empty cells do not. Colspan and rowspan text is
repeated into every spanned slot; panels are stacked in source order.

Cells use exact normalized text with whitespace collapsed, case folded,
ligatures expanded, dashes/quotes unified, and superscript/footnote markers
removed. Flattened markers are removed only when the complete cell equals a
marked JATS cell. Numbers and ordinary punctuation remain significant. Rows
and columns require all their cells together, with duplicate counts respected;
axis matches are one to one and preserve order. Whole uses recall >=95% and
row=column=100%. Caption matching uses text similarity (>=0.72 with the same
label, >=0.90 otherwise); a same-label prefix of at least four words and 30%
of the caption also qualifies. Numbers alone never match.

An explicit structure-warning list counts as recovered but unstructured, not
absent. Complete normalized cell phrases are consumed once from the list's
printed lines, longest first, with whitespace boundaries (12 never matches
112, -12 or 12.5). Wrapped cells interrupted by other columns may remain
unmatched. List lines do not establish rows or columns and cannot earn whole
table credit; the unstructured count is reported separately. The declared
line count bounds the list, excluding subsequent notes and references.

This measures agreement with JATS, not a PDF visual audit. Publisher/PDF text
differences, formula encodings and flattened markers can lower the score.
Superscript content is ignored, including scientific exponents when marked
as superscript. Blank-cell placement, extra/duplicated content, and errors
hidden by repeated identical values can escape these recall-based metrics.
An added caption row can therefore be reported even on a whole table.
Separate row/column matches do not establish unique cell identities. Panels
with different column semantics and horizontal continuations need inspection.
Failure classes are heuristics, can overlap, and do not alter scores; the
residual class records failures without evidence for a named structural cause.
The table-absent class means no caption-matched grid, not proof that the PDF
table content is entirely missing from the copy.
Examples and unmatched captions are limited to twelve words.
"""


def ratio(row, key):
    denominator = row[key + '_truth']
    return f"{100 * row[key + '_found'] / denominator:.2f}%" if denominator else 'n/a'


def markdown_report(report):
    total = report['overall']
    lines = ['# PLOS table score', '',
             f"Articles: {len(report['papers'])}; missing copies: {report['missing_copies']}; "
             f"scoring time: {report['seconds']:.3f}s.", '',
             f"Recovered but unstructured: {total['tables_unstructured']} matched tables (included in cell text recall; zero structure credit).", '',
             '| Scope | Matched / truth | Cell recall | Row score | Column score | Whole / scorable |',
             '|---|---:|---:|---:|---:|---:|']
    for name, row in [('Overall', total)] + [(p['id'], p) for p in report['papers']]:
        lines.append(f"| {name} | {row['tables_matched']}/{row['tables_truth']} | "
                     f"{ratio(row, 'cells')} | {ratio(row, 'rows')} | {ratio(row, 'columns')} | "
                     f"{row['whole']}/{row['tables_scorable']} |")
    lines += ['', 'Overall count denominators: ' + '; '.join(
        f"{k} {total[k + '_found']}/{total[k + '_truth']}" for k in ('cells', 'rows', 'columns')) + '.',
        '', '## Failure classes, ranked', '',
        'Counts are tables with each diagnostic; one table may have several.', '',
        '| Class | Tables |', '|---|---:|']
    for name, count in sorted(report['failure_counts'].items(), key=lambda pair: (-pair[1], pair[0])):
        lines.append(f'| {name} | {count} |')
    lines += ['', '## Unmatched truth tables', '', '| Paper | Table | Caption (12 words) | Why |',
              '|---|---|---|---|']
    for paper in report['papers']:
        for table in paper['tables']:
            if not table['matched']:
                lines.append(f"| {paper['id']} | {table['label']} | {escape(table['caption'])} | "
                             f"{table['unmatched_reason']}: {table['unmatched_detail']} |")
    lines += ['', '## Tables without cell truth', '']
    for paper in report['papers']:
        for table in paper['tables']:
            if not table['scorable']:
                lines.append(f"- {paper['id']} {table['label']}: {table['truth_note']}.")
    lines += ['', '## Classified tables', '',
              '| Paper | Table | Class | Example (12 words maximum) |', '|---|---|---|---|']
    for paper in report['papers']:
        for table in paper['tables']:
            for failure in table['failures']:
                lines.append(f"| {paper['id']} | {table['label']} | {failure['class']} | {escape(failure['example'])} |")
    lines += ['', '## Reading the score', '', NOTES.strip(), '']
    return '\n'.join(lines)


def escape(text):
    return text.replace('|', '\\|').replace('\n', ' ')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('copies', nargs='?', type=Path)
    parser.add_argument('truth', nargs='?', type=Path)
    parser.add_argument('ids', nargs='*')
    parser.add_argument('--json', type=Path, help='write counts and short diagnostics as JSON')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.copies is None or args.truth is None:
        parser.error('COPIES_DIR and TRUTH_DIR are required')
    start = time.perf_counter()
    try:
        if not args.truth.is_dir() or not args.copies.is_dir():
            raise ValueError('copies and truth must be existing directories')
        ids = args.ids or sorted(p.name for p in args.truth.iterdir()
                                if p.is_dir() and list(p.glob('*.xml')))
        if not ids or len(set(ids)) != len(ids):
            raise ValueError('need a nonempty, nonduplicate article list')
        papers = []
        for identifier in ids:
            if Path(identifier).name != identifier or identifier in ('.', '..'):
                raise ValueError(f'invalid article id: {identifier}')
            paths = list((args.truth / identifier).glob('*.xml'))
            if len(paths) != 1:
                raise ValueError(f'{identifier}: expected one XML file, found {len(paths)}')
            copy = args.copies / identifier / 'copy.md'
            papers.append(score_paper(identifier, paths[0].read_text(encoding='utf-8'),
                copy.read_text(encoding='utf-8') if copy.is_file() else '', not copy.is_file()))
        tables = [t for p in papers for t in p['tables']]
        counts = Counter({name: 0 for name in CLASSES})
        counts.update(f['class'] for t in tables for f in t['failures'])
        report = dict(overall=totals(tables), papers=papers, failure_counts=dict(counts),
                      missing_copies=sum(p['missing_copy'] for p in papers),
                      seconds=round(time.perf_counter() - start, 6), notes=NOTES.strip())
        if args.json:
            args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(markdown_report(report))
    except (OSError, ValueError, ET.ParseError) as exc:
        parser.exit(2, f'score_tables: {exc}\n')
    return 0


def self_test():
    """Synthetic fixtures stay here to keep this job's two-file edit boundary."""
    import unittest

    caption = 'Measured outcomes for three experimental groups'
    base = [['Group', 'Value', 'Range'], ['Alpha group', '11', '21'],
            ['Beta group', '12', '22'], ['Gamma group', '13', '23']]

    def xml(rows=base, cap=caption):
        head = '<thead><tr>' + ''.join('<th>' + html.escape(t) + '</th>' for t in rows[0]) + '</tr></thead>'
        body = '<tbody>' + ''.join('<tr>' + ''.join('<td>' + html.escape(t) + '</td>' for t in row) + '</tr>'
                                  for row in rows[1:]) + '</tbody>'
        return '<article><table-wrap><label>Table 1</label><caption>' + cap + '</caption><table>' + head + body + '</table></table-wrap></article>'

    def md(rows=base, cap=caption):
        lines = ['**Table 1. ' + cap + '**', '']
        for i, row in enumerate(rows):
            lines.append('| ' + ' | '.join(row) + ' |')
            if i == 0:
                lines.append('| ' + ' | '.join(['---'] * len(row)) + ' |')
        return '\n'.join(lines)

    def score(rows=base, truth=None, cap=caption):
        return score_paper('synthetic', truth or xml(), md(rows, cap))['tables'][0]

    class Tests(unittest.TestCase):
        def test_gated_lines_match_without_structure_credit(self):
            lines=[' '.join(row) for row in base]
            text='**Table 1. '+caption+'**\n\n[table structure not recovered: 4 printed lines follow as printed, left to right, top to bottom]\n\n'+'\n'.join('- '+s for s in lines)
            result=score_paper('synthetic',xml(),text)['tables'][0]
            self.assertTrue(result['matched']);self.assertTrue(result['unstructured'])
            self.assertEqual(result['cells_found'],12)
            self.assertEqual(result['rows_found'],0);self.assertEqual(result['columns_found'],0)
            self.assertFalse(result['whole'])

        def test_gated_count_excludes_following_lists_and_substrings(self):
            text='**Table 1. '+caption+'**\n[table structure not recovered: 1 printed lines follow as printed, left to right, top to bottom]\n- 112 -12 12.5\n- 12\n'
            result=score_paper('synthetic',xml(),text)['tables'][0]
            self.assertTrue(result['matched']);self.assertEqual(result['cells_found'],0)

        def test_gated_repeated_values_are_consumed_once(self):
            text='**Table 1. '+caption+'**\n[table structure not recovered: 1 printed lines follow as printed, left to right, top to bottom]\n- 12\n'
            result=score_paper('synthetic',xml([['12','12'],['12','12']]),text)['tables'][0]
            self.assertEqual(result['cells_found'],1)

        def test_empty_recovered_frame_does_not_take_following_list(self):
            text='**Table 1. '+caption+"**\n[table structure not recovered: no printed lines located in the caption's recovered frame]\n- 12\n"
            result=score_paper('synthetic',xml(),text)['tables'][0]
            self.assertFalse(result['matched'])
            self.assertTrue(copy_tables(text)[0].gated)
            self.assertFalse(copy_tables(text)[0].printed_lines)
            self.assertEqual(result['cells_found'],0)
            self.assertFalse(result['whole'])

        def check(self, rows, kind, cells, row_hits, column_hits):
            result = score(rows)
            self.assertIn(kind, [f['class'] for f in result['failures']])
            self.assertEqual((result['cells_found'], result['rows_found'], result['columns_found']),
                             (cells, row_hits, column_hits))
            self.assertFalse(result['whole'])

        def test_perfect(self):
            result = score()
            self.assertTrue(result['whole'])
            self.assertEqual((result['cells_found'], result['rows_found'], result['columns_found']), (12, 4, 3))
            self.assertFalse(result['failures'])

        def test_header_fused(self):
            rows = [[' '.join(x) for x in zip(base[0], base[1])]] + base[2:]
            self.check(rows, 'header fused with row 1', 6, 2, 0)

        def test_rows_merged(self):
            rows = [base[0], [' '.join(x) for x in zip(base[1], base[2])], base[3]]
            self.check(rows, 'rows merged', 6, 2, 0)

        def test_columns_merged(self):
            self.check([[r[0], r[1] + ' ' + r[2]] for r in base], 'columns merged', 4, 0, 1)

        def test_cells_torn(self):
            rows = [base[0], ['Alpha', 'group', '11', '21']] + base[2:]
            self.check(rows, 'cells torn', 11, 3, 0)

        def test_caption_in_grid(self):
            rows = [[caption + ' Group', 'Value', 'Range']] + base[1:]
            self.check(rows, 'caption text in the grid', 11, 3, 2)

        def test_extra_caption_row_is_recall_blind_spot(self):
            result = score([[caption, '', '']] + base)
            self.assertTrue(result['whole'])
            self.assertIn('caption text in the grid', [f['class'] for f in result['failures']])

        def test_rows_split(self):
            rows = [base[0], ['Alpha', '11', '21'], ['group', '', '']] + base[2:]
            self.check(rows, 'rows split', 11, 3, 2)

        def test_missing_rows(self):
            self.check(base[:2] + base[3:], 'missing rows', 9, 3, 0)

        def test_absent(self):
            result = score_paper('synthetic', xml(), '')['tables'][0]
            self.assertFalse(result['matched'])
            self.assertEqual(result['unmatched_reason'], 'no copy table')
            self.assertEqual(result['cells_found'], 0)
            self.assertEqual(result['failures'][0]['class'], 'table absent')

        def test_caption_differs(self):
            result = score(cap='An entirely unrelated description')
            self.assertFalse(result['matched'])
            self.assertEqual(result['unmatched_reason'], 'caption differs')

        def test_spans_namespaces_and_panels(self):
            source = '''<article xmlns="urn:jats"><table-wrap><label>Table 1</label>
            <caption>Measured outcomes for three experimental groups</caption>
            <table xmlns="http://www.w3.org/1999/xhtml"><thead>
            <tr><th rowspan="2">Group</th><th colspan="2">Measures</th></tr>
            <tr><th>Value</th><th>Range</th></tr></thead><tbody>
            <tr><td>Alpha</td><td>1</td><td>2</td></tr></tbody></table>
            <table><tr><td>Beta</td><td>3</td><td>4</td></tr></table>
            </table-wrap></article>'''
            rows = [['Group', 'Measures', 'Measures'], ['Group', 'Value', 'Range'],
                    ['Alpha', '1', '2'], ['Beta', '3', '4']]
            result = score(rows, source)
            self.assertTrue(result['whole'])
            self.assertEqual(result['parts'], 2)
            self.assertEqual(result['cells_truth'], 12)
            rows[0][2] = ''
            result = score(rows, source)
            self.assertEqual(result['columns_found'], 2)
            self.assertFalse(result['whole'])

        def test_normalization_and_markers(self):
            self.assertEqual(normalise('  ﬁeld\u00a0 “A” — B¹ <sup>a</sup> '), 'field "a" - b')
            self.assertNotEqual(normalise('-1'), normalise('1'))
            self.assertNotEqual(normalise('0.1'), normalise('0.01'))
            source = xml().replace('Value</th>', 'Value<xref ref-type="table-fn">a</xref></th>')
            rows = [['Group', 'Valuea', 'Range']] + base[1:]
            self.assertTrue(score(rows, source)['whole'])
            self.assertEqual(normalise('**bold** and gene_id'), 'bold and gene_id')

        def test_escaped_pipe(self):
            self.assertEqual(split_row(r'| a\|b | c |'), [r'a\|b', 'c'])
            rows = [['Group', 'Value', 'Range'], ['Alpha|Beta', '1', '2']]
            text = md([rows[0], [r'Alpha\|Beta', '1', '2']])
            self.assertTrue(score_paper('s', xml(rows), text)['tables'][0]['whole'])

        def test_repeated_values_and_reordering(self):
            rows = [['Label', 'Value'], ['A', '1'], ['B', '1']]
            result = score_paper('s', xml(rows), md(rows[:2]))['tables'][0]
            self.assertEqual(result['cells_found'], 4)
            self.assertFalse(score([base[0], base[2], base[1], base[3]])['whole'])
            self.assertFalse(score([list(reversed(r)) for r in base])['whole'])

        def test_one_copy_cannot_match_two_truth_tables(self):
            first = ET.fromstring(xml()).find('table-wrap')
            second = ET.fromstring(xml()).find('table-wrap')
            second.find('label').text = 'Table 2'
            root = ET.Element('article')
            root.extend([first, second])
            result = score_paper('s', ET.tostring(root, encoding='unicode'), md())
            self.assertEqual(result['tables_matched'], 1)
            self.assertEqual(result['cells_found'], 12)
            self.assertEqual(result['cells_truth'], 24)

        def test_rowspan_zero_stops_at_row_group(self):
            source = xml().replace('<th>Group</th>', '<th rowspan="0">Group</th>')
            self.assertTrue(score(truth=source)['whole'])

        def test_cell_substrings_do_not_earn_credit(self):
            rows = [base[0], ['Alpha group extra', '110', '210']] + base[2:]
            result = score(rows)
            self.assertEqual(result['cells_found'], 9)
            self.assertFalse(result['whole'])

        def test_continuation_and_boundaries(self):
            text = md(base[:2]) + '\n\nBody paragraph.\n\n' + md(base[2:], '(continued)')
            self.assertTrue(score_paper('s', xml(), text)['tables'][0]['whole'])
            text = '**Table 1. ' + caption + '**\n\nBody paragraph.\n\n' + md().split('\n\n')[1]
            result = score_paper('s', xml(), text)['tables'][0]
            self.assertFalse(result['matched'])
            self.assertEqual(result['unmatched_reason'], 'no copy table')

        def test_empty_and_image_truth(self):
            self.assertEqual(score_paper('s', '<article/>', '')['tables_truth'], 0)
            source = '<article><table-wrap><label>Table 1</label><caption>' + caption + '</caption><graphic/></table-wrap></article>'
            result = score_paper('s', source, md())['tables'][0]
            self.assertTrue(result['matched'])
            self.assertFalse(result['scorable'])
            self.assertFalse(result['whole'])

        def test_assignment(self):
            self.assertEqual(assignment([[.95, .8], [.9, 0]]), {1: 0, 0: 1})
            self.assertEqual(assignment([[], []]), {})

        def test_missing_copy_counted(self):
            result = score_paper('s', xml(), '', missing_copy=True)
            self.assertTrue(result['missing_copy'])
            self.assertEqual(result['cells_truth'], 12)
            self.assertEqual(result['cells_found'], 0)

    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return int(not result.wasSuccessful())


if __name__ == '__main__':
    sys.exit(main())
