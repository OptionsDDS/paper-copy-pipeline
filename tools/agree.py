#!/usr/bin/env python3
"""Apply auditable two-reader repairs, leaving every refusal unchanged.

Usage: /usr/bin/python3 -I tools/agree.py PAPER_COPY_DIR READERS_DIR PDF
       /usr/bin/python3 -I tools/agree.py --needed PAPER_COPY_DIR   (pages to read)
READERS_DIR contains model/pNNN.{md,json}; the trial's model/PAPER/pNNN
layout is also accepted. No inference, network or third-party imports here.

Tables must match cell by cell (including empty positions and span ownership),
with only NFKC, whitespace and dash normalization. Token multisets count words,
complete numbers and every punctuation/sign, preserving case and multiplicity.
Spanning cells contribute their printed text once to conservation, but repeat
in the Markdown slots. Source evidence is the copy's printed gate or its table
sidecar's printed_lines, never the proposed grid itself or a whole-page bag.
Caption/notes outside the replaced block are untouched. No approximate table
agreement is accepted. Matching is caption-number first, token overlap second;
ambiguous or truncated reads, stale evidence and scans abstain from auto edits.

Formula placeholders and explicit checker targets require equal reader LaTeX
and ordered PDF letter/digit conservation. Unknown TeX commands abstain. Scan
pages need an explicit page-specific interleaved/garbled flag and >=97% ordered
word agreement; they are offered only in copy.readers-page.json. A declaration
of an OCR scan alone is not a corruption flag. Checker input is optional
copy.readers-check.json: {"pages": [{"page": 1, "reason": "interleaved"}],
"formulas": [{"page": 2, "text": "exact flagged copy substring",
              "pdf_text": "exact text-layer formula", "reason": "garbled"}]}.
The checker cannot supply substitute text: pdf_text must occur in the PDF.

copy.agree.json records accepted and rejected candidates, hashes and evidence.
An unchanged rerun is a no-op. The original Markdown is retained in
copy.agree-before.md before the first applied edit. This is an evidence check,
not a proof against correlated model structure errors or a bad PDF text layer.
"""
import argparse
from collections import Counter
from dataclasses import dataclass, field
import difflib
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

MODELS = ('mineru2.5-pro-2605', 'ovisocr2')
DASH = str.maketrans(dict.fromkeys('‐‑‒–—―−﹘﹣－', '-'))
CAPTION = re.compile(r'^(?:Supplement(?:al|ary)\s+)?Table\s+(S?\d+[a-z]?)\b', re.I)


def normalise(text):
    return ' '.join(unicodedata.normalize('NFKC', text).translate(DASH).split())


def tokens(text):
    # Keep decimals and words whole: 11 cannot satisfy two copies of 1.
    return re.findall(r'[^\W\d_]+|\d+(?:[.,]\d+)*|[^\w\s]|_', normalise(text))


def bag(text):
    return Counter(tokens(text))


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, obj):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def label(text):
    m = CAPTION.match(text.strip('# *'))
    return m[1].lower() if m else ''


@dataclass
class Cell:
    row: int
    col: int
    text: str
    rowspan: int = 1
    colspan: int = 1
    header: bool = False


@dataclass
class Grid:
    cells: list
    rows: int
    cols: int
    headers: int = 1

    def expanded(self, texts=None):
        result = [[''] * self.cols for _ in range(self.rows)]
        for i, c in enumerate(self.cells):
            for r in range(c.row, c.row + c.rowspan):
                for k in range(c.col, c.col + c.colspan):
                    result[r][k] = normalise(c.text) if texts is None else texts[i]
        return result

    def signature(self):
        # A span and several duplicated literal cells are different evidence.
        return self.rows, self.cols, tuple((c.row, c.col, c.rowspan, c.colspan,
                                           normalise(c.text)) for c in self.cells)

    def text(self):
        return ' '.join(c.text for c in self.cells)

    def markdown(self, texts=None):
        result = []
        for i, row in enumerate(self.expanded(texts)):
            # The copy's own grids escape only the cell bar; printed '*', '_',
            # '<' and '&' stay as printed (e.g. a footnote star "CEP*").
            escaped = [c.replace('|', '\\|') for c in row]
            result.append('| ' + ' | '.join(escaped) + ' |')
            if i == max(1, self.headers) - 1:
                result.append('| ' + ' | '.join(['---'] * self.cols) + ' |')
        return '\n'.join(result)


def validate_grid(cells, rows, cols, headers=1):
    if not 1 <= rows <= 1000 or not 2 <= cols <= 128:
        raise ValueError('invalid grid size')
    occupied = set()
    for c in cells:
        if c.rowspan < 1 or c.colspan < 1 or c.row + c.rowspan > rows or c.col + c.colspan > cols:
            raise ValueError('span outside table')
        slots = {(r, k) for r in range(c.row, c.row + c.rowspan)
                 for k in range(c.col, c.col + c.colspan)}
        if slots & occupied:
            raise ValueError('overlapping spans')
        occupied |= slots
    if len(occupied) != rows * cols:
        raise ValueError('ragged grid')
    grid = Grid(sorted(cells, key=lambda c: (c.row, c.col)), rows, cols, headers)
    if any(not any(c.strip() for c in col) for col in zip(*grid.expanded())):
        raise ValueError('empty extra column')
    return grid


class TableHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.cells, self.occupied = [], set()
        self.row, self.col, self.current = -1, 0, None
        self.in_table = self.in_row = self.in_head = False
        self.closed, self.headers = False, 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table':
            if self.in_table or self.closed:
                raise ValueError('nested or multiple tables')
            self.in_table = True
        elif tag == 'thead':
            self.in_head = True
        elif tag == 'tr':
            if self.in_row or not self.in_table:
                raise ValueError('unclosed row')
            self.row += 1
            self.col, self.in_row = 0, True
            if self.in_head:
                self.headers = self.row + 1
        elif tag in ('td', 'th'):
            if self.current is not None or not self.in_row:
                raise ValueError('unclosed cell')
            while (self.row, self.col) in self.occupied:
                self.col += 1
            rs, cs = int(attrs.get('rowspan', 1)), int(attrs.get('colspan', 1))
            if not 1 <= rs <= 1000 or not 1 <= cs <= 128:
                raise ValueError('invalid span')
            self.current = Cell(self.row, self.col, '', rs, cs, tag == 'th' or self.in_head)
            if tag == 'th' and (self.in_head or self.row == 0):
                self.headers = self.row + 1
        elif tag in ('br', 'p', 'div') and self.current is not None:
            self.current.text += ' '
        elif tag not in ('tbody', 'tfoot', 'b', 'i', 'em', 'strong', 'span', 'sup', 'sub',
                          'u', 's', 'br', 'p', 'div'):
            raise ValueError('unsupported cell markup: ' + tag)

    def handle_endtag(self, tag):
        if tag in ('td', 'th'):
            c = self.current
            if c is None:
                raise ValueError('cell end without start')
            for r in range(c.row, c.row + c.rowspan):
                for k in range(c.col, c.col + c.colspan):
                    if (r, k) in self.occupied:
                        raise ValueError('overlapping spans')
                    self.occupied.add((r, k))
            self.cells.append(c)
            self.col += c.colspan
            self.current = None
        elif tag == 'tr':
            if self.current is not None or not self.in_row:
                raise ValueError('unclosed cell or row')
            self.in_row = False
        elif tag == 'thead':
            self.in_head = False
        elif tag == 'table':
            if self.in_row or not self.in_table:
                raise ValueError('unclosed row or table')
            self.in_table, self.closed = False, True

    def handle_data(self, data):
        if self.current is not None:
            self.current.text += data
        elif data.strip():
            raise ValueError('text outside cells')

    def grid(self):
        if not self.closed or self.in_table or not self.cells:
            raise ValueError('truncated table')
        return validate_grid(self.cells, self.row + 1,
                             max(k for _, k in self.occupied) + 1, self.headers or 1)


def parse_html(text):
    parser = TableHTML()
    parser.feed(text)
    parser.close()
    return parser.grid()


def plain_markup(text):
    text = re.sub(r'<br\s*/?>', ' ', text, flags=re.I)
    text = re.sub(r'</?(?:sup|sub|em|strong|b|i|span)\b[^>]*>', '', text, flags=re.I)
    text = re.sub(r'\\([\\|*_`\[\]<>])', r'\1', text)
    return html.unescape(text)


def split_row(line):
    line = line.strip()
    if not line.startswith('|') or not line.endswith('|'):
        raise ValueError('not a Markdown row')
    result, part, slashes = [], '', 0
    for char in line[1:-1]:
        if char == '|' and slashes % 2 == 0:
            result.append(part.strip())
            part = ''
        else:
            part += char
        slashes = slashes + 1 if char == '\\' else 0
    return result + [part.strip()]


def parse_markdown(text):
    rows, headers = [], 1
    for line in text.splitlines():
        if not line.strip():
            continue
        cells = split_row(line)
        if all(re.fullmatch(r':?-{3,}:?', c) for c in cells):
            headers = len(rows)
        else:
            rows.append([plain_markup(c) for c in cells])
    return validate_grid([Cell(r, k, t) for r, row in enumerate(rows) for k, t in enumerate(row)],
                         len(rows), max(map(len, rows), default=0), headers)


def parse_otsl(text):
    text = re.sub(r'</?otsl>', '', text.strip())
    pieces = re.split(r'(<(?:fcel|ecel|lcel|ucel|xcel|ched|rhed|srow|nl)>)', text)
    rows, current = [], []
    for piece in pieces:
        if re.fullmatch(r'<\w+>', piece):
            if piece == '<nl>':
                if not current:
                    raise ValueError('empty OTSL row')
                rows.append(current)
                current = []
            else:
                current.append([piece[1:-1], ''])
        elif piece.strip():
            if not current:
                raise ValueError('OTSL text outside cells')
            current[-1][1] += piece
    if current:
        rows.append(current)
    if not rows or any(len(r) != len(rows[0]) for r in rows):
        raise ValueError('ragged OTSL')
    owners, roots = {}, {}
    for r, row in enumerate(rows):
        for k, (kind, value) in enumerate(row):
            if kind in ('fcel', 'ecel', 'ched', 'rhed', 'srow'):
                root = (r, k)
                if kind == 'ecel' and value.strip():
                    raise ValueError('nonempty OTSL empty cell')
                roots[root] = Cell(r, k, html.unescape(value), header=kind == 'ched')
            else:
                if value.strip():
                    raise ValueError('text in OTSL span')
                left, up = owners.get((r, k - 1)), owners.get((r - 1, k))
                root = left if kind == 'lcel' else up
                if root is None or (kind == 'xcel' and left != up):
                    raise ValueError('orphan OTSL span')
            owners[r, k] = root
    for root, c in roots.items():
        positions = [p for p, o in owners.items() if o == root]
        c.rowspan = max(r for r, _ in positions) - c.row + 1
        c.colspan = max(k for _, k in positions) - c.col + 1
        if len(positions) != c.rowspan * c.colspan:
            raise ValueError('nonrectangular OTSL span')
    headers = max((c.row + 1 for c in roots.values() if c.header), default=1)
    return validate_grid(list(roots.values()), len(rows), len(rows[0]), headers)


@dataclass
class Candidate:
    grid: Grid
    caption: str = ''
    start: int = 0
    end: int = 0
    source: str = ''


def reader_tables(text):
    matches = [(m.start(), m.end(), m[0], parse_html)
               for m in re.finditer(r'<table\b[^>]*>.*?</table\s*>', text, re.I | re.S)]
    for m in re.finditer(r'(?m)^\s*\|[^\n]*\|\s*$(?:\n[ \t]*\|[^\n]*\|[ \t]*$)*', text):
        if not any(a <= m.start() < b for a, b, _, _ in matches):
            matches.append((m.start(), m.end(), m[0], parse_markdown))
    for m in re.finditer(r'<otsl>.*?</otsl>|(?:<(?:fcel|ecel|ched)>[^\n]*<nl>)+', text, re.S):
        if not any(a <= m.start() < b for a, b, _, _ in matches):
            matches.append((m.start(), m.end(), m[0], parse_otsl))
    captions = list(re.finditer(r'(?mi)^[ \t#*]*(?:supplement(?:al|ary)\s+)?table\s+(?:s?\d+[a-z]?)\b[^\n]*', text))
    result, errors = [], []
    for start, end, raw, parse in sorted(matches):
        near = [c for c in captions if c.end() <= start and
                not any(c.end() < b <= start for _, b, _, _ in matches)]
        cap = near[-1][0].strip('# *') if near else ''
        # Captions printed below tables: only an immediately adjacent paragraph.
        following = [c for c in captions if c.start() >= end and not text[end:c.start()].strip()]
        if not cap and following:
            cap = following[0][0].strip('# *')
        try:
            result.append(Candidate(parse(raw), cap, start, end, raw))
        except ValueError as error:
            errors.append(str(error))
    return result, errors


def select_candidate(candidates, caption, printed):
    numbered = [c for c in candidates if label(c.caption) and label(c.caption) == label(caption)]
    pool = numbered or [c for c in candidates if not label(c.caption) or not label(caption)]
    wanted = bag(' '.join(printed))
    ranked = sorted(((sum((wanted & bag(c.grid.text())).values()) /
                      max(1, sum((wanted | bag(c.grid.text())).values())), i, c)
                     for i, c in enumerate(pool)), key=lambda item: item[0], reverse=True)
    if not ranked or ranked[0][0] < (0.35 if numbered else 0.70):
        return None, 'no matching reader table'
    if len(ranked) > 1 and ranked[0][0] - ranked[1][0] < .10:
        return None, 'ambiguous reader table'
    return ranked[0][2], ''


def source_tokens(lines):
    """(normalised token, printed characters) for every token of the source.

    Each character is normalised alone, so every token keeps the exact printed
    characters it came from (an en dash, a minus sign, a superscript digit).
    None when that differs from normalising the whole text (composed accents).
    """
    text = '\n'.join(lines)
    chars, origin = [], []
    for i, c in enumerate(text):
        n = unicodedata.normalize('NFKC', c).translate(DASH)
        if n.isspace() or not n:
            n = ' ' if n else ''
        for x in n:
            chars.append(x)
            origin.append(i)
    flat = ''.join(chars)
    result = [(m[0], text[origin[m.start()]:origin[m.end() - 1] + 1])
              for m in re.finditer(r'[^\W\d_]+|\d+(?:[.,]\d+)*|[^\w\s]|_', flat)]
    return result if Counter(t for t, _ in result) == bag(' '.join(lines)) else None


def printed_cells(grid, lines):
    """Cell texts in the source's own characters, or None.

    Readers and the token check compare normalised text (NFKC, one dash), so a
    reader's grid could print a hyphen for the PDF's en dash or "2" for "²".
    Each cell token takes the printed form of an unused source token with the
    same normalised value, in source order; spacing follows the reader.
    """
    pairs = source_tokens(lines)
    if pairs is None:
        return None
    pool = {}
    for token, raw in pairs:
        pool.setdefault(token, []).append(raw)
    texts = []
    for c in grid.cells:
        cell = normalise(c.text)
        out, at = [], 0
        for m in re.finditer(r'[^\W\d_]+|\d+(?:[.,]\d+)*|[^\w\s]|_', cell):
            if not pool.get(m[0]):
                return None
            out.append(cell[at:m.start()] + pool[m[0]].pop(0))
            at = m.end()
        texts.append(''.join(out) + cell[at:])
    return texts if not any(pool.values()) else None


def accept_grid(a, b, printed):
    if a.signature() != b.signature():
        return False, {'reason': 'readers disagree on cells or spans'}
    if any(re.match(r'^(?:Supplement(?:al|ary)\s+)?Table\s+S?\d', normalise(c.text), re.I)
           for c in a.cells):
        return False, {'reason': 'table caption inside reader grid'}
    expected, found = bag(' '.join(printed)), bag(a.text())
    evidence = dict(source_tokens=dict(sorted(expected.items())),
                    grid_tokens=dict(sorted(found.items())),
                    missing=dict(expected - found), extra=dict(found - expected))
    evidence['reason'] = 'exact grid and printed-token agreement' if expected == found and expected else 'printed-token mismatch'
    return bool(expected and expected == found), evidence


def source_partition(grid, printed, candidates, reads):
    """Separate a complete grid prefix from a witnessed note suffix.

    Never trim arbitrary unmatched tokens to make conservation pass. The split
    is between entire source lines; the entire suffix must be the immediately
    following text in BOTH readers, or consist solely of DOI/continuation lines.
    The suffix is preserved below the replacement, including its exact spelling.
    This handles table notes that the copy's own gate included as printed lines.
    """
    wanted = bag(grid.text())
    prefix = Counter()
    for index, line in enumerate(printed, 1):
        prefix.update(tokens(line))
        if prefix != wanted:
            continue
        tail = printed[index:]
        if not tail:
            return printed, []
        if all(re.fullmatch(r'(?:https?://doi\.org/|doi\s*:)\S+|\(?[Cc]ontinued\)?',
                            line.strip(), re.I) for line in tail):
            return printed[:index], tail
        expected = tokens(' '.join(tail))
        witnessed = True
        for candidate, (text, _, _) in zip(candidates, reads):
            following = text[candidate.end:]
            following = re.sub(r'</?(?:b|i|strong|em)>|(?m:^#+ )', '', following)
            following = plain_markup(following)
            # Markdown emphasis is presentation only, but a literal footnote
            # star cannot be silently removed. First try the exact text.
            if tokens(following)[:len(expected)] != expected:
                witnessed = False
        if witnessed:
            return printed[:index], tail
    return printed, []


def page_at(text, offset):
    before = list(re.finditer(r'<!-- page (\d+) -->', text[:offset]))
    after = re.search(r'<!-- end of page (\d+) -->', text[offset:])
    return int(before[-1][1]) if before else int(after[1]) if after else None


def copy_blocks(text, sidecar):
    result, used = [], set()
    for cap in re.finditer(r'(?m)^\*\*((?:Supplement(?:al|ary)\s+)?Table\b[^\n]*)\*\*[ \t]*\n', text, re.I):
        start = cap.end()
        while start < len(text) and text[start].isspace():
            start += 1
        gate = re.match(r'\[table structure not recovered: (\d+) printed lines[^\n]*\]\n', text[start:])
        printed, end, kind = [], start, ''
        if gate:
            end = start + gate.end()
            while len(printed) < int(gate[1]):
                m = re.match(r'\s*^- ([^\n]*)\n?', text[end:], re.M)
                if not m:
                    break
                printed.append(plain_markup(m[1]))
                end += m.end()
            if len(printed) != int(gate[1]):
                continue
            kind = 'gate'
        elif text[start:start + 1] == '|':
            m = re.match(r'(?:\|[^\n]*\|[ \t]*(?:\n|$))+', text[start:])
            if m:
                end, kind = start + m.end(), 'grid'
        if not kind:
            continue
        candidates = [(i, t) for i, t in enumerate(sidecar) if i not in used and
                      (normalise(t.get('caption', '')) == normalise(cap[1]) or
                       label(cap[1]) and label(cap[1]) == label(t.get('caption', '')))]
        meta = {}
        if candidates:
            i, meta = candidates[0]
            used.add(i)
        result.append(dict(caption=cap[1], start=start, end=end, kind=kind,
                           page=meta.get('page') or page_at(text, start),
                           printed=printed if kind == 'gate' else meta.get('printed_lines', []),
                           meta=meta))
    return result


def read_page(root, paper, model, page, pdf_hash):
    paths = [root / model / f'p{page:03d}.md', root / model / paper / f'p{page:03d}.md']
    path = next((p for p in paths if p.is_file()), None)
    if path is None:
        return '', {}, 'missing reader page'
    try:
        info = json.loads(path.with_suffix('.json').read_text())
    except (OSError, ValueError):
        return '', {}, 'missing or invalid reader JSON'
    if info.get('input_sha256', pdf_hash) != pdf_hash:
        return '', info, 'reader PDF hash differs'
    if info.get('markdown_sha256', file_sha(path)) != file_sha(path):
        return '', info, 'reader Markdown hash differs'
    finishes = [info.get('finish_reason', 'stop'), info.get('layout_finish_reason', 'stop')]
    finishes += [b.get('finish_reason', 'stop') for b in info.get('blocks', [])]
    if any(f not in ('stop', 'eos', None) for f in finishes):
        return '', info, 'reader output truncated'
    return path.read_text(), info, ''


# Decode only known TeX presentation syntax; unknown commands cannot be deleted
# to manufacture matching characters. This decoder is for formulas, not tables.
GREEK = dict(zip('alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega'.split(),
                 'αβγδεζηθικλμνξοπρστυφχψω'))
GREEK.update({k.title(): v.upper() for k, v in list(GREEK.items())})
TEX_SYMBOLS = dict(GREEK, pm='±', times='×', cdot='·', le='≤', leq='≤', ge='≥', geq='≥',
                   approx='≈', neq='≠', infty='∞', partial='∂')
TEX_FORMAT = {'frac', 'dfrac', 'tfrac', 'sqrt', 'left', 'right', 'mathrm', 'mathit',
              'mathbf', 'text', 'operatorname', 'displaystyle', 'big', 'Big', 'bigg'}


def latex_characters(text):
    depth = 0
    for char in re.sub(r'\\[{}]', '', text):
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
        if depth < 0:
            raise ValueError('unbalanced LaTeX braces')
    if depth:
        raise ValueError('unbalanced LaTeX braces')
    def replace(m):
        name = m[1]
        if name in TEX_SYMBOLS:
            return TEX_SYMBOLS[name]
        if name in TEX_FORMAT:
            return ''
        raise ValueError('unknown LaTeX command: ' + name)
    plain = re.sub(r'\\([A-Za-z]+)', replace, text)
    return ''.join(c for c in normalise(plain) if c.isalnum())


def ordered_characters(source, latex):
    expected = ''.join(c for c in normalise(source) if c.isalnum())
    actual = latex_characters(latex)
    # Equality strengthens the requested subsequence rule: extra digits cannot
    # silently change a value while preserving all old characters in order.
    return bool(expected and expected == actual)


def formulas(text):
    return [(m.start(), m.end(), next(g for g in m.groups() if g is not None))
            for m in re.finditer(r'\$\$(.*?)\$\$|(?<![\\$])\$(?!\$)(.*?)(?<!\\)\$|\\\((.*?)\\\)|\\\[(.*?)\\\]', text, re.S)]


def formula_key(text):
    # TeX whitespace is presentation; do not equate different commands/operators.
    text = re.sub(r'\\(?:left|right)\b', '', normalise(text))
    text = re.sub(r'([_^])\{([A-Za-z0-9])\}', r'\1\2', text)
    return re.sub(r'\s+', '', text)


def scan_words(text):
    text = re.sub(r'!\[[^\]]*\]\([^)]*\)|<img\b[^>]*>', '', text, flags=re.I)
    text = re.sub(r'<[^>]+>', ' ', text)
    return normalise(html.unescape(text)).split()


def word_agreement(a, b):
    a, b = scan_words(a), scan_words(b)
    if not a or not b:
        return 0.0
    matches = sum(m.size for m in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return matches / max(len(a), len(b))


def full_page(text, info):
    """Restore MinerU's deliberately omitted furniture from its raw JSON.

    Ovis retains this material. Comparing both complete page transcriptions
    avoids treating an intentional Markdown export difference as OCR dissent.
    No words are discarded to increase agreement. Image placeholders survive in
    proposals; table spans are serialized once, as in the raw reader output.
    """
    if 'blocks' not in info:
        return text
    parts = []
    for block in info['blocks']:
        content = block.get('content', '')
        if not content and block.get('task') is None:
            parts.append('![%s](bbox=%s)' % (block.get('type', 'image'),
                         ','.join(map(str, block.get('bbox', [])))))
        elif content:
            if block.get('task') == 'table' and re.search(r'<(?:fcel|ecel|ched)>', content):
                grid = parse_otsl(content)
                rows = []
                for r in range(grid.rows):
                    cells = ['<td rowspan="%d" colspan="%d">%s</td>' %
                             (c.rowspan, c.colspan, html.escape(c.text))
                             for c in grid.cells if c.row == r]
                    rows.append('<tr>' + ''.join(cells) + '</tr>')
                content = '<table>' + ''.join(rows) + '</table>'
            parts.append(content)
    return '\n\n'.join(parts) + '\n'


UNCERTAINTY = '## Places the program is not sure of'
TABLE_DOUBT = re.compile(r'table structure not recovered|row boundaries are uncertain|its rows could not be read')


def resolve_uncertainty(text, tables, after):
    """Restate the uncertainty item of each replaced table, which is now a grid.

    Items "page N: <caption or Table X>: <not recovered/uncertain rows>" about a
    replaced table (the only one with that number on its page) become one
    restated item, only inside the list, which follows every replacement (so
    output offsets stay valid).
    """
    at = text.rfind(UNCERTAINTY)
    if at < after or not tables:
        return text
    head, tail = text[:at], text[at:]
    for event in tables:
        number = label(event['caption'])
        names = [re.escape(event['caption'].strip())] + ([r'(?:Supplement(?:al|ary)\s+)?Table %s' % re.escape(number)] if number else [])
        pattern = re.compile(r'(?m)^- page %d: (?:%s)\.?:[^\n]*$' % (event['page'], '|'.join(names)))
        items = [m for m in pattern.finditer(tail) if TABLE_DOUBT.search(m[0])]
        if not items or sum(label(e['caption']) == number and e['page'] == event['page'] for e in tables) != 1:
            continue
        event['uncertainty_items'] = [m[0] for m in items]
        statement = ('- page %d: %s: rows and columns read with two local page readers; they agree cell '
                     'by cell and every value matches the PDF text' % (event['page'], event['caption'].strip()))
        # The first item is restated; further items about the same table go.
        for i, m in reversed(list(enumerate(items))):
            tail = tail[:m.start()] + statement + tail[m.end():] if i == 0 else tail[:m.start()] + tail[m.end() + 1:]
    return head + tail


def process(copy_dir, readers, pdf):
    copy_path = copy_dir / 'copy.md'
    original = copy_path.read_text()
    pdf_hash = file_sha(pdf)
    log_path = copy_dir / 'copy.agree.json'
    if log_path.exists():
        previous = json.loads(log_path.read_text())
        if previous.get('applied_edits') and previous.get('output_sha256') == sha(original) and previous.get('pdf_sha256') == pdf_hash:
            return previous
        if (copy_dir / 'copy.agree-before.md').exists():
            raise ValueError('copy changed after agreement; use a fresh copy directory to preserve provenance')
    side_path = copy_dir / 'copy.tables.json'
    sidecar = json.loads(side_path.read_text()).get('tables', []) if side_path.exists() else []
    check_path = copy_dir / 'copy.readers-check.json'
    checker = json.loads(check_path.read_text()) if check_path.exists() else {}
    scan = bool(SCAN_KIND.search(original))
    log = dict(version=1, pdf=str(pdf.resolve()), pdf_sha256=pdf_hash,
               input_sha256=sha(original), readers=str(readers.resolve()),
               source_sidecar_sha256=file_sha(side_path) if side_path.exists() else None,
               checker_sha256=file_sha(check_path) if check_path.exists() else None,
               tables=[], formulas=[], pages=[])
    edits, cache = [], {}

    def page_reads(page):
        if page not in cache:
            cache[page] = [read_page(readers, copy_dir.name, m, page, pdf_hash) for m in MODELS]
        return cache[page]

    for block in copy_blocks(original, sidecar):
        event = {k: block[k] for k in ('caption', 'page', 'kind', 'start', 'end')}
        event.update(accepted=False)
        log['tables'].append(event)
        if not block['page'] or not block['printed']:
            event['reason'] = 'no page-local printed source lines'
            continue
        if scan:
            event['reason'] = 'OCR scan: page proposals only'
            continue
        reads = page_reads(block['page'])
        if any(error for _, _, error in reads):
            event['reason'] = '; '.join(error for _, _, error in reads if error)
            continue
        candidates = []
        for model, (text, info, _) in zip(MODELS, reads):
            tables, errors = reader_tables(text)
            candidate, error = select_candidate(tables, block['caption'], block['printed'])
            event.setdefault('readers', []).append(dict(model=model, text_sha256=sha(text),
                caption=candidate.caption if candidate else '', parse_errors=errors, match_error=error))
            candidates.append(candidate)
        if any(c is None for c in candidates):
            event['reason'] = 'reader table not matched unambiguously'
            continue
        a, b = candidates
        core, notes = source_partition(a.grid, block['printed'], candidates, reads)
        accepted, evidence = accept_grid(a.grid, b.grid, core)
        event.update(evidence)
        if not accepted:
            continue
        texts = printed_cells(a.grid, core)
        if texts is None:
            event.update(reason='printed characters of the cells cannot be restored')
            continue
        event.update(accepted=True, grid=a.grid.expanded(texts),
                     printed_lines=core, preserved_notes=notes, source='copy printed lines',
                     spans=[vars(c) for c in a.grid.cells if c.rowspan > 1 or c.colspan > 1])
        number = label(block['caption']) or '(unnumbered)'
        replacement = (a.grid.markdown(texts) + '\n\n' + f'Table {number} read with two local page readers; '
                       'every value checked against the PDF text\n')
        if notes:
            following = tokens(plain_markup(original[block['end']:]))
            note_tokens = tokens(' '.join(notes))
            if following[:len(note_tokens)] != note_tokens:
                replacement += '\n' + '\n\n'.join(notes) + '\n'  # each note its own paragraph
        edits.append((block['start'], block['end'], replacement, event))

    # PDF text is extracted only for explicitly targeted formula evidence.
    pdf_pages = {}

    def pdf_text(page):
        if page not in pdf_pages:
            pdf_pages[page] = subprocess.run(['pdftotext', '-f', str(page), '-l', str(page),
                '-raw', str(pdf), '-'], check=True, capture_output=True, text=True).stdout
        return pdf_pages[page]

    targets = list(checker.get('formulas', []))
    for m in re.finditer(r'\[formula:[^\]\n]+\]', original):
        targets.append(dict(page=page_at(original, m.start()), text=m[0], reason='copy placeholder'))
    for target in targets:
        event = dict(page=target.get('page'), text=target.get('text'), accepted=False)
        log['formulas'].append(event)
        page, old = event['page'], event['text']
        if not page or not old or original.count(old) != 1 or not target.get('reason'):
            event['reason'] = 'ambiguous or unflagged formula target'
            continue
        reads = page_reads(page)
        if any(error for _, _, error in reads):
            event['reason'] = 'missing or invalid reader page'
            continue
        first, second = ({formula_key(f): f for _, _, f in formulas(t)} for t, _, _ in reads)
        both = [first[k] for k in first.keys() & second.keys()]
        # Default placeholder evidence: keep only its printed operand expression.
        source = target.get('pdf_text')
        if source is None:
            source = re.sub(r'^\[formula:\s*|\s+inside an unread symbol.*|;.*', '', old).rstrip(']')
            try:
                source = latex_characters(source)
            except ValueError:
                source = ''
        layer_chars = ''.join(c for c in normalise(pdf_text(page)) if c.isalnum())
        source_chars = ''.join(c for c in normalise(source) if c.isalnum())
        old_expression = re.sub(r'^\[formula:\s*|\s+inside an unread symbol.*|;.*', '', old).rstrip(']')
        try:
            old_chars = latex_characters(old_expression)
        except ValueError:
            old_chars = ''
        if Counter(old_chars) != Counter(source_chars):
            event['reason'] = 'target and PDF formula have different letters/digits'
            continue
        if not source_chars or layer_chars.count(source_chars) != 1:
            event['reason'] = 'formula letters/digits not localized in PDF text'
            continue
        matches = []
        for latex in both:
            try:
                if ordered_characters(source, latex):
                    matches.append(latex)
            except ValueError:
                pass
        if len(matches) != 1:
            event['reason'] = 'no unique agreeing formula with PDF character order'
            continue
        event.update(accepted=True, reason='reader LaTeX agreement and PDF character order',
                     latex=matches[0], pdf_text=source, pdf_characters=source_chars,
                     source='unique formula sequence in pdftotext -raw on target page',
                     readers_sha256=[sha(t) for t, _, _ in reads])
        start = original.index(old)
        edits.append((start, start + len(old), '$' + matches[0] + '$', event))

    proposals = []
    flagged = {int(p['page']): p['reason'] for p in checker.get('pages', [])
               if 'page' in p and re.search(r'interleav|garbl', p.get('reason', ''), re.I)}
    for m in FLAGGED_PAGE.finditer(original):
        flagged.setdefault(int(m[1]), m[0])
    if scan:
        for page, reason in sorted(flagged.items()):
            reads = page_reads(page)
            try:
                texts = [full_page(t, info) for t, info, _ in reads]
                ratio = word_agreement(*texts) if not any(r[2] for r in reads) else 0.0
            except ValueError:
                texts, ratio = ['', ''], 0.0
            event = dict(page=page, flag=reason, agreement=ratio, accepted=ratio >= .97,
                         applied=False, evidence='complete reader page text, including JSON furniture',
                         reason='page proposal only' if ratio >= .97 else 'page agreement below 97%')
            log['pages'].append(event)
            if ratio >= .97:
                matcher = difflib.SequenceMatcher(None, scan_words(texts[0]), scan_words(texts[1]), autojunk=False)
                disagreements = [dict(kind=op, first=matcher.a[i:j], second=matcher.b[k:l])
                                  for op, i, j, k, l in matcher.get_opcodes() if op != 'equal']
                proposals.append(dict(event, text=texts[0], alternate_text=texts[1], differences=disagreements,
                    warning='page read from the image by two local readers',
                    reader_sha256=[sha(t) for t, _, _ in reads]))
    # Never partially apply overlapping repairs.
    edits.sort(key=lambda e: e[:2])
    if any(a[1] > b[0] for a, b in zip(edits, edits[1:])):
        raise ValueError('overlapping accepted repairs')
    result, delta = original, 0
    for start, end, replacement, event in edits:
        # Where the replacement sits in the output: the native trace (tools/
        # copy_trace.py) gives the replaced units this span, hash-bound to it.
        event.update(output_start=start + delta, output_end=start + delta + len(replacement))
        delta += len(replacement) - (end - start)
    for start, end, replacement, _ in reversed(edits):
        result = result[:start] + replacement + result[end:]
    result = resolve_uncertainty(result, [e for *_, e in edits if 'caption' in e],
                                 max((e['output_end'] for *_, e in edits), default=0))
    log.update(output_sha256=sha(result), applied_edits=len(edits))
    write_json(copy_dir / 'copy.readers-page.json', dict(version=1, pdf_sha256=pdf_hash,
        copy_sha256=sha(original), applied=False, proposals=proposals))
    if result != original:
        backup = copy_dir / 'copy.agree-before.md'
        if not backup.exists():
            backup.write_text(original)
        temp = copy_path.with_suffix('.md.tmp')
        temp.write_text(result)
        temp.replace(copy_path)
    write_json(log_path, log)
    return log


SCAN_KIND = re.compile(r'(?im)^Document kind:.*(?:scan|OCR)')
FLAGGED_PAGE = re.compile(r'(?im)^[-* ]*page (\d+):[^\n]*(?:interleav|garbl)[^\n]*')
FLOAT_CHECK = re.compile(r'\s*\[Float check: (?:Supplement(?:al|ary)\s+)?Table\b')


def needed_pages(copy_dir):
    """Pages whose copy content an accepted reader agreement could repair.

    Returns {page: [reasons]}, mirroring process(): on a born-digital copy, a
    table printed as gated lines, a grid table the copy itself marks uncertain
    (an uncertainty item "page N: Table X..." naming it, or a float-check note
    right below it), a formula placeholder or a checker formula target; on a
    scan, only a page the copy or checker flags as interleaved or garbled (scan
    pages are proposals, never applied). A confident grid table, an ordinary
    page or an unflagged scan page needs no reader: readers run only here.
    """
    copy_dir = Path(copy_dir)
    text = (copy_dir / 'copy.md').read_text()
    side_path = copy_dir / 'copy.tables.json'
    sidecar = json.loads(side_path.read_text()).get('tables', []) if side_path.exists() else []
    check_path = copy_dir / 'copy.readers-check.json'
    checker = json.loads(check_path.read_text()) if check_path.exists() else {}
    pages = {}

    def add(page, reason):
        if page:
            pages.setdefault(int(page), []).append(reason)

    if SCAN_KIND.search(text):
        for p in checker.get('pages', []):
            if 'page' in p and re.search(r'interleav|garbl', p.get('reason', ''), re.I):
                add(p['page'], 'checker: ' + p['reason'])
        for m in FLAGGED_PAGE.finditer(text):
            add(m[1], 'flagged scan page')
        return pages
    head, _, uncertain = text.rpartition('## Places the program is not sure of')
    uncertain = uncertain if head else ''
    for block in copy_blocks(text, sidecar):
        if not block['page'] or not block['printed']:
            continue
        if block['kind'] == 'gate':
            add(block['page'], 'gated table: ' + normalise(block['caption'])[:80])
            continue
        number = label(block['caption'])
        named = number and re.search(r'(?im)^- page %d: (?:Supplement(?:al|ary)\s+)?Table %s\b'
                                     % (block['page'], re.escape(number)), uncertain)
        if named or FLOAT_CHECK.match(text, block['end']):
            add(block['page'], 'uncertain grid table: ' + normalise(block['caption'])[:80])
    for target in checker.get('formulas', []):
        if target.get('reason'):
            add(target.get('page'), 'checker formula')
    for m in re.finditer(r'\[formula:[^\]\n]+\]', text):
        add(page_at(text, m.start()), 'formula placeholder')
    return pages


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('paper_copy_dir', type=Path)
    ap.add_argument('readers_dir', type=Path, nargs='?')
    ap.add_argument('pdf', type=Path, nargs='?')
    ap.add_argument('--needed', action='store_true',
                    help='only list the pages the readers should read: comma list on stdout, '
                         'reasons in PAPER_COPY_DIR/copy.readers-needed.json')
    args = ap.parse_args(argv)
    if args.needed:
        pages = needed_pages(args.paper_copy_dir)
        write_json(args.paper_copy_dir / 'copy.readers-needed.json',
                   dict(version=1, copy_sha256=sha((args.paper_copy_dir / 'copy.md').read_text()),
                        pages={str(p): r for p, r in sorted(pages.items())}))
        print(','.join(map(str, sorted(pages))))
        return 0
    if not args.readers_dir or not args.pdf:
        ap.error('READERS_DIR and PDF are required')
    if not args.readers_dir.is_dir():
        ap.error('READERS_DIR does not exist')
    log = process(args.paper_copy_dir, args.readers_dir, args.pdf)
    print(json.dumps(dict(applied=log['applied_edits'],
        tables=sum(t['accepted'] for t in log['tables']),
        formulas=sum(f['accepted'] for f in log['formulas']),
        page_proposals=sum(p['accepted'] for p in log['pages']))))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
