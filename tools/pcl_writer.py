#!/usr/bin/env python3
"""Write PCL 1.2 from the copy's own emitted units and their decoded glyphs.

COPY_PDF_PCL=1 enables the copy_paper hook. The writer reads the finished
copy.md and copy.trace.json, where the copier records each unit's source rows
when it writes the unit, so a decoded source line (export_lines rows of the
copier's verified snapshot) is allocated to its own copy unit rather than to
the first similar text. Short numeric rows and OCR rows keep the earlier
matching fallback; split and partial claims are placed by exact text inside
their recorded destinations. The copy's units (one Markdown line each) then
decide reading order inside a page, paragraph and heading boundaries, float
membership, line-end hyphen joins and word spaces; the source glyphs decide
what is printed and how it is styled.
So the reading view carries the copy's words in the copy's order. Remaining
differences are where the copy is not the printed page (generated labels,
repeated cells, lost or duplicated lines, case changes) or where the rulebook
fixes an order (pages are consecutive; float blocks follow their page's
prose). They are measured, never assumed away: copy.pcl.audit.json lists
each one with its cause.

Rules. Explicit font names, descriptor flags/weight/italic angle establish
bold/italic. Smaller glyphs displaced from a local ordinary baseline establish
sup/sub (classify_notation's .88/.12 thresholds); size alone never does. No
species, formula, citation or statistical vocabulary is used. Small capitals
have no command in the approved grammar: their letters stay plain and the
evidence is recorded. OCR cannot establish style.

PCL contains printed text only: copy text with no source glyph (labels,
Markdown, warnings) is never printed, and a printed glyph is never dropped.
Copy spaces become printed spaces, ⟦gap⟧ (no glyph printed) or, for a
printed space the copy does not read, glyph U+0020 as=none with its measured
gap. Source lines no copy unit used keep their printed text: the copier's
furniture exclusions as furniture, figure lettering (catalog or containment
in a figure region) as float kind=figure, any other line as body text that
the copy lost (listed). Tables use 1.2 float spans; the 2.0 cell proposal is
not implemented by the approved parser.
"""
import bisect
import collections
import copy
import difflib
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import statistics
import sys
import unicodedata

# Port: paper-copy-language/pcl.py, parse/analyse/printed; inventory C3 and
# JOB-pcl Revision (1). The vendored parser and fixtures are byte-identical
# to the approved project; UPSTREAM.json records their source hashes.
DEFAULT_VALIDATOR = Path(__file__).with_name('pcl')/'pcl.py'
KINDS = ('bold', 'italic', 'sup', 'sub')
# Port: convert_page.py, classify_notation's notatable/SUP_BRIDGE test
# (inventory C7). Bridge punctuation also needs its own size/offset witness;
# the prototype's semantic growth and small-digit fallbacks are not used.
NOTATION_MARKS = ('*', '\u2020', '\u2021', '\u00ae', '\u2122', '\u00a9', '#', '&')
SUP_BRIDGE = (',', '\u2013', '\u2014')
# Adaptation: retain the earlier writer's individually witnessed mathematical
# signs and citation punctuation. The prototype's smaller alphabet would
# flatten signed exponents, charges and bracketed citations. These receive
# no semantic growth: every character must pass Revision (2)'s .88/.12 test.
# Vertical divider bars remain ineligible, as in the ported classifier.
NOTATION_PUNCTUATION = ('-', '+', '\u2212', '/', '[', ']', '\u2217')


def notation_character(text):
    return len(text) == 1 and (unicodedata.category(text)[0] in ('L', 'N') or
                              text in NOTATION_MARKS + SUP_BRIDGE + NOTATION_PUNCTUATION)


# Port: paper-mapper/mapper/stage3_markers.py, heading_number/parse_marker;
# D-555 and D-561. Syntax establishes depth only for an existing heading;
# it cannot promote a body/list/reference line to a heading.
BULLETS = '•◦▪–-∙·⋅‣⁃●○◉‧'


def parse_marker(text):
    leading = len(text)-len(text.lstrip())
    text = text.lstrip()
    if not text:
        return None
    if text[0] in BULLETS:
        return {'marker':text[0], 'syntax':'bullet', 'span':[leading,leading+1], 'ordinal':None}
    hit = re.match(r'(\d+|[ivxlcdmIVXLCDM]+|[a-z])([.)])\s+', text)
    if not hit:
        return None
    if re.match(r'(?:https?\b|doi\b|\d)',text[hit.end():],re.I):
        return None
    token = hit.group(1)
    syntax = 'decimal' if token.isdigit() else 'roman' if re.fullmatch('[ivxlcdm]+',token,re.I) else 'alphabetic'
    ordinal = int(token) if token.isdigit() else None
    return {'marker':hit.group(1)+hit.group(2), 'syntax':syntax,
            'span':[leading,leading+len(hit.group(1)+hit.group(2))], 'ordinal':ordinal}


def heading_number(text):
    match = re.match(r'^\s*(\d+(?:\.\d+)*\.?)(?=\s)', text)
    return tuple(int(value) for value in match[1].rstrip('.').split('.')) if match else None


def heading_level(text):
    number = heading_number(text)
    if number and all(n > 0 for n in number):
        return len(number)
    marker = parse_marker(text)
    if marker and marker['syntax'] == 'decimal' and marker['ordinal'] > 0:
        return 1
    return '?'


def classify_notation(ratio, offset_em):
    """Port the witnessed size/offset test, without semantic fallbacks.

    Source: paper-copy-language/converter/convert_page.py,
    classify_notation; inventory C7 (R-004), JOB-pcl Revision (2).
    The revision explicitly specifies .88 and +/- .12 for BOTH kinds;
    it takes precedence over the old converter's .85 subscript constant.
    Native baselines in the copier's reading frame replace glyph bottoms.
    """
    if ratio <= .88 and offset_em >= .12:
        return 'sup'
    if ratio <= .88 and offset_em <= -.12:
        return 'sub'
    return None


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    # The approved language project is read-only, including its bytecode cache.
    exec(compile(Path(path).read_bytes(), str(path), 'exec'), result.__dict__)
    return result


def snapshot(pages):
    """Capture decoded, verified sources before ownership creates fragments."""
    return copy.deepcopy(pages)


def font_style(name, metadata=None):
    """Only explicit font evidence; an opaque face name does not mean regular."""
    meta = metadata or {}
    face = re.sub(r'^[A-Z]{6}\+', '', name)
    flags = int(meta.get('flags') or 0)
    result = []
    if (re.search(r'bold|demi|semibold|(?:^|[.,_-])(?:b|bd|bi)(?:$|[.,_-])', face, re.I)
            or (meta.get('weight') or 0) >= 600 or flags & 262144):
        result.append('bold')
    if (re.search(r'italic|oblique|(?:^|[.,_-])(?:i|it|bi)(?:$|[.,_-])', face, re.I)
            or abs(meta.get('italic_angle') or 0) >= 2 or flags & 64):
        result.append('italic')
    small = bool(flags & 131072 or re.search(r'small.?cap|(?:^|[.,_-])sc\d*(?:$|[.,_-])', face, re.I))
    known = bool(result or small or meta or re.search(r'regular|roman|book|normal|(?:^|[.,_-])r$', face, re.I))
    return tuple(result), ('small capitals unsupported in PCL 1.2' if small else
                           None if known else 'font style not established')


def classify(chars, fonts):
    """Classify a physical baseline using coordinates in its reading frame.

    The largest repeated size needs two glyphs and one fifth of the line;
    this also handles formulas with more indices than ordinary letters. A script is
    at most .88 of that size and at least .12 em above/below their median
    baseline. Unverified or incomplete native witnesses
    abstain. A shifted whole line cannot turn itself into a superscript.
    """
    valid = [c for c in chars if not c.get('_mark_unverified') and
             isinstance(c.get('size'), (int, float)) and c['size'] > 0 and
             isinstance(c.get('origin'), (tuple, list)) and len(c['origin']) == 2 and
             all(isinstance(v, (int, float)) and math.isfinite(v) for v in c['origin'])]
    counts = collections.Counter(round(c['size'], 1) for c in valid if not c['text'].isspace())
    candidates = [size for size, count in counts.items() if count >= max(2, .2*counts.total())]
    em = max(candidates) if candidates else 0
    ordinary = [c for c in valid if .95*em <= c['size'] <= 1.05*em]
    baseline = statistics.median(c['origin'][1] for c in ordinary) if ordinary else None
    result = []
    for c in chars:
        style, issue = font_style(c.get('font', ''), fonts.get(c.get('font', '')))
        evidence = dict(font=c.get('font', ''), metadata=fonts.get(c.get('font', ''), {}))
        if c.get('_mark_unverified'):
            result.append(((), 'native glyph not verified', evidence)); continue
        if c in valid and len(ordinary) >= 2:
            ratio = c['size']/em
            delta = (baseline-c['origin'][1])/em
            evidence.update(size=c['size'], baseline=c['origin'][1], ordinary_size=em,
                            ordinary_baseline=baseline, ratio=round(ratio, 5), offset_em=round(delta, 5))
            notation = classify_notation(ratio, delta)
            if notation and notation_character(c['text']):
                style += (notation,)
            elif notation:
                issue = 'displaced character outside the ported notation alphabet'
            elif ratio <= .88 and abs(delta) > .05:
                issue = 'baseline displacement below notation threshold'
        result.append((style, issue, evidence))
    return result


def escape(ch):
    """Preserve delimiters and controls in the printed view; expand ligatures."""
    cp = f'U+{ord(ch):04X}'
    if ch in '⟦⟧': return f'⟦char {cp}⟧'
    if unicodedata.category(ch) == 'Cs':
        raise ValueError('a surrogate has no PCL code point')
    if ch == '\x08':
        return f'⟦glyph {cp} as=U+0020 rule=control-space/1.0⟧'
    if unicodedata.category(ch) == 'Cc':
        raise ValueError(f'no measured reading substitution for control {cp}')
    if '\ufb00' <= ch <= '\ufb06':
        seq = ','.join(f'U+{ord(c):04X}' for c in unicodedata.normalize('NFKC', ch))
        return f'⟦glyph {cp} as={seq} rule=ligature/1.0⟧'
    return ch




def styled_text(atoms, line, spans, uncertain):
    """Nest style transitions without changing any source character."""
    out, active, starts = [], (), {}
    content = [i for i, a in enumerate(atoms) if a['text']]
    edges = {content[0], content[-1]} if content else set()
    for i, atom in enumerate(atoms + [dict(text='', style=())]):
        wanted = tuple(k for k in KINDS if k in atom.get('style', ()))
        common = 0
        while common < min(len(active), len(wanted)) and active[common] == wanted[common]: common += 1
        for kind in reversed(active[common:]):
            out.append(f'⟦/{kind}⟧')
            a = starts.pop(kind)
            witness = [x for x in atoms[a:i] if x.get('evidence')]
            spans.append(dict(kind=kind, line=line['line'], page=line['page'], columns=[a, i],
                              text=''.join(x['text'] for x in atoms[a:i]),
                              box=line['box'], witnesses=[x['evidence'] for x in witness]))
        for kind in wanted[common:]:
            out.append(f'⟦{kind}⟧'); starts[kind] = i
        active = wanted
        if atom['text']:
            if atom.get('gap'): out.append('⟦gap⟧')
            elif atom.get('hidden'):
                # A printed space the copy does not read: kept in the printed
                # view, omitted from reading, with its measured spacing.
                measured = 'edge' if i in edges else atom.get('gap_em', 0.0)
                out.append(f'⟦glyph U+{ord(atom["text"]):04X} as=none rule=copy-joins/1.0 gap={measured}⟧')
            else: out.append(''.join(escape(ch) for ch in atom['text']))
            if atom.get('issue'):
                # Adjacent identical abstentions are one inspectable record.
                if (uncertain and uncertain[-1].get('line') == line['line'] and
                        uncertain[-1].get('reason') == atom['issue'] and uncertain[-1]['columns'][1] == i):
                    uncertain[-1]['text'] += atom['text']; uncertain[-1]['columns'][1] = i+1
                else:
                    uncertain.append(dict(page=line['page'], line=line['line'], columns=[i, i+1],
                                          text=atom['text'], reason=atom['issue'], box=line['box']))
    return ''.join(out)


FLOAT_ROLES = ('table', 'caption', 'figure', 'note')


def serialize(lines, digest):
    """Serialize source lines with explicit roles, joins and provenance.

    A line may state its own `para` decision (the copy's unit boundaries);
    otherwise a body line opening a new group starts a paragraph. Neither is
    written where the rulebook forbids it (next to a heading, on a float).
    """
    header = (f'⟦paper-copy 1.2 source={digest} uses=pcl/1.2,font-evidence/1.0,'
              'baseline-evidence/1.0,copy-joins/1.0,ligature/1.0,control-space/1.0⟧')
    out, spans, uncertain, last_page = [], [], [], 0
    for i, original in enumerate(lines, 1):
        line = dict(original, line=i)
        page = line['page']
        if page != last_page and page != last_page+1:
            raise ValueError('PCL pages must be consecutive from 1')
        prefix = (header if i == 1 else '') + (f'⟦page {page}⟧' if page != last_page else '') + f'⟦line {i}⟧'
        role, group = line.get('role', 'body'), line.get('group', f'line-{i}')
        previous = lines[i-2] if i > 1 else {}
        following = lines[i] if i < len(lines) else {}
        same_prev = previous.get('group') == group and previous.get('role') == role
        same_next = following.get('group') == group and following.get('role') == role
        wrap = line.get('wrap')
        after_heading = previous.get('role') == 'heading' and not same_prev
        if wrap:
            origin = f'from={wrap["from"]} ' if wrap.get('from', i-1) < i-1 else ''
            prefix += f'⟦wrap {i} {origin}hyphen={wrap["hyphen"]} basis=rule ref=copy-joins/1.0⟧'
        elif role == 'body' and i > 1 and not after_heading and (
                line['para'] if 'para' in line else not same_prev):
            prefix += '⟦para⟧'
        if role == 'heading' and not same_prev:
            parts = []
            for member in lines[i-1:]:
                if member.get('group') != group or member.get('role') != role: break
                parts.append(''.join(a['text'] for a in member['atoms']))
            heading = ' '.join(parts)
            # Adapt the port to the copier's line map: a bare table digit can
            # match a numbered Markdown heading. Require its mapped title
            # in the same group before treating the number as a section.
            # A separate first physical number line remains supported.
            level = heading_level(heading + ' ')
            if level != '?' and not any(ch.isalpha() for ch in heading):
                level = '?'
                uncertain.append(dict(page=page, line=i, text=heading, box=line['box'],
                    reason='numbered heading has no mapped title; level left unknown'))
            prefix += f'⟦heading level={level} basis=map ref={line.get("ref", group)}⟧'
        elif role in FLOAT_ROLES and not same_prev:
            prefix += (f'⟦float id={line.get("float_id", group)} kind={role} basis=map '
                       f'ref={line.get("ref", group)}⟧')
        elif role == 'furniture': prefix += '⟦furniture⟧'
        body = styled_text(line['atoms'], line, spans, uncertain)
        if role == 'heading' and not same_next: body += '⟦/heading⟧'
        elif role in FLOAT_ROLES and not same_next: body += '⟦/float⟧'
        elif role == 'furniture': body += '⟦/furniture⟧'
        out.append(prefix+body); last_page = page
    return '\n'.join(out or [header])+'\n', spans, uncertain


def font_metadata(pdf):
    """Read descriptors already loaded by the copy's native PDF reader."""
    reader = sys.modules.get('_copy_table_reader')
    if not reader or not pdf: return {}
    result = {}
    for font in reader.sc_doc(pdf).fonts.values():
        data = {}
        for key, field in [('Flags', 'flags'), ('FontWeight', 'weight'), ('ItalicAngle', 'italic_angle')]:
            value = reader.resolve1(font.desc.get(key))
            if isinstance(value, (int, float)) and math.isfinite(value): data[field] = value
        program = font.prog
        if program:
            if program.kind == 'truetype':
                if 'OS/2' in program.tt: data.setdefault('weight', program.tt['OS/2'].usWeightClass)
                if 'post' in program.tt: data.setdefault('italic_angle', program.tt['post'].italicAngle)
            elif hasattr(program, 'top'):
                value = getattr(program.top, 'ItalicAngle', None)
                if isinstance(value, (int, float)): data.setdefault('italic_angle', value)
        if data:
            # Duplicate PDF font names with conflicting descriptors cannot
            # safely share evidence. Font names themselves remain available.
            if font.basefont in result and result[font.basefont] != data: result[font.basefont] = {}
            else: result[font.basefont] = data
    return result


def row_atoms(row, page, fonts, engine):
    """Keep source characters; use exact native witnesses for style and order."""
    chars = []
    if '_pcl_space_chars' not in page:
        page['_pcl_space_chars'] = [x for x in page.get('_table_chars', [])
                                    if x.get('text', '').isspace() and isinstance(x.get('origin'), (list, tuple))]
    for run in row:
        native = run.get('_chars', [])
        raw = ''.join(c['text'] for c in native)
        if not native or raw != re.sub(r'\s', '', run['text']):
            text = ' '.join(e['text'].strip() for e in row)
            return [dict(text=ch, style=(), issue='source/native text mismatch; style left plain') for ch in text]
        framed = engine.mark_reading_frame(native, run.get('angle', 0))
        if not framed or any(not isinstance(c.get('origin'), (list, tuple)) for c in framed):
            text = ' '.join(e['text'].strip() for e in row)
            return [dict(text=ch, style=(), issue='native reading frame unavailable; style left plain') for ch in text]
        cursor = 0
        for j, c in enumerate(framed):
            while cursor < len(run['text']) and run['text'][cursor].isspace(): cursor += 1
            cursor += len(c['text'])
            chars.append(dict(c, _run=run['id'], _index=j,
                              _space=cursor < len(run['text']) and run['text'][cursor].isspace()))
    chars.sort(key=lambda c: (c['origin'][0], c['origin'][1]))
    for run in row:
        indices = [c['_index'] for c in chars if c['_run'] == run['id']]
        if indices != sorted(indices):
            text = ' '.join(e['text'].strip() for e in row)
            return [dict(text=ch, style=(), issue='native positions contradict source order; left plain') for ch in text]
    styles = classify(chars, fonts)
    result = []
    for i, (c, (style, issue, evidence)) in enumerate(zip(chars, styles)):
        if i:
            prev = chars[i-1]
            same_run = prev['_run'] == c['_run'] and prev['_index']+1 == c['_index']
            gap = c['origin'][0]-(prev.get('adv_x1') or prev['x1'])
            space = prev['_space'] if same_run else gap > .18*min(prev['size'], c['size'])
            if space:
                # The source run's spaces may be inferred by the boxer. Only
                # a native space glyph proves that the separator was printed.
                native_space = any(prev['origin'][0] < x['origin'][0] < c['origin'][0] and
                    abs(x['origin'][1]-c['origin'][1]) < .4*c['size']
                    for x in page['_pcl_space_chars'] if not round(row[0].get('angle', 0))%360)
                between = tuple(k for k in KINDS if k in style and k in styles[i-1][0])
                result.append(dict(text=' ', style=between, gap=not native_space))
        evidence = dict(evidence, run=c['_run'], origin=c['origin'],
                        box=[c['x0'], c['y0'], c['x1'], c['y1']])
        result.append(dict(text=c['text'], style=style, issue=issue, evidence=evidence))
    return result




# ---------------------------------------------------------------- the copy
UNCERTAINTY = '\n## Places the program is not sure of'
# Text that copy_paper.py and its float pass generate, never print: labels,
# notices, file lines, OCR tags and Markdown fences. A closed list taken from
# the copier's emitting code; anything else in the copy counts as copy words.
GENERATED = re.compile('|'.join([
    r'<!--.*?-->',
    r'^Document kind: [^\n]*$',
    r'^> (?:NO COPY|INCOMPLETE COPY):[^\n]*$',
    r'^Image file: \S+ \(page \d+\)$',
    r'^\[(?:Image unavailable|Float check|table structure not recovered|'
    r'Author list or affiliation links not verified|Author information printed separately from the byline|'
    r'No byline or affiliation lines identified|Figure text as printed; publisher OCR is unverified|'
    r'Author list not verified; publisher OCR lines follow as printed|Publisher OCR is unverified|'
    r'Page image: no OCR text recovered|Figure label incomplete in the OCR layer|'
    r'page \d+ is an image; not read)\b[^\n]*\]$',
    r'^\*\*(?:Front matter as printed|Footnote as printed|Separate text block as printed|'
    r'Article information(?: — references belonging to the previous article)?|'
    r'Author details \(page \d+\):)\*\*$',
    r'^\*\*Authors:\*\*(?= )',
    r'^Page \d+:$',
    r'^```(?:text)?$',
    r'^## Article information$',
    r'\*\*(?:Table|Figure) \(no caption(?: on page \d+)?\)\*\*',
    r' — the (?:figure|table) is an image; not read$',
    r'\\?\[unreadable:[^\]\n]*\\?\]',
    r' ?\\?\[ocr\\?\]',
    r'^\*\*Unlabelled (?:figure|table) p\d+-\d+\*\*(?: \(page \d+\))?$',
    r'^- Unconfirmed page header \(pages [^\n]*$',
    r'^---$',
    r'^## Unpaired floats$',
    r'(?<=\*\*) \(page \d+\)$',
    r'<br\s*/?>',
]), re.M | re.S)
CAPTION_UNIT = re.compile(r'^\*\*(?:(?:Supplementa(?:l|ry)\s+)?(?:Table|Figure|Fig\.?|Scheme|Box|Chart|Plate|'
                          r'Graph|Panel|Unlabelled)\b|(?:TABLE|FIGURE|FIG\.?)\b)', re.I)


def nkey(ch):
    """The copier's lexical key (conserve.normalise) for one character."""
    return ''.join(c for c in unicodedata.normalize('NFKD', ch).casefold() if c.isalnum())


def copy_index(text):
    """Copy body characters, their Markdown line units and float groups.

    Generated labels and comments are masked: they can neither anchor a
    source line nor count as printed words.
    """
    cut = text.rfind(UNCERTAINTY)
    body = text[:cut] if cut >= 0 else text
    masked = bytearray(len(body))
    for m in GENERATED.finditer(body):
        masked[m.start():m.end()] = b'\1'*(m.end()-m.start())
    units, unit_of, pos = [], [None]*len(body), 0
    group, groups, table_lines, fence = None, 0, False, False
    for raw in body.split('\n'):
        start, end = pos, pos+len(raw); pos = end+1
        visible = ''.join(ch for i, ch in zip(range(start, end), raw) if not masked[i])
        if raw.startswith('```'):
            fence = not fence
            continue
        if not raw.strip():
            continue
        if not any(ch.isalnum() for ch in visible):
            # A generated notice or a separator row: it ends no float group,
            # except the notice announcing printed table lines.
            if raw.startswith('[table structure not recovered'): table_lines = True
            if raw.startswith('[Figure text as printed'):
                # OCR figure lettering follows in a fence: a float without caption.
                groups += 1; group = groups; table_lines = False
            continue
        kind = ('fenced' if fence else 'title' if raw.startswith('# ') else 'heading' if re.match(r'#{2,6} ', raw) else
                'table_row' if raw.startswith('| ') else 'list' if re.match(r'\s*- ', raw) else
                'quote' if raw.startswith('> ') else 'caption' if CAPTION_UNIT.match(raw) else
                'printed_line' if raw.endswith('  ') else 'paragraph')
        if kind == 'caption':
            groups += 1; group = groups; table_lines = False
        elif group is not None and not (kind in ('table_row', 'printed_line', 'fenced') or
                                        kind == 'list' and table_lines):
            group = None; table_lines = False
        units.append(dict(index=len(units), start=start, end=end, kind=kind, group=group, text=raw))
        for i in range(start, end): unit_of[i] = len(units)-1
    key, kpos = [], []
    for i, ch in enumerate(body):
        if masked[i]: continue
        for c in nkey(ch):
            key.append(c); kpos.append(i)
    return dict(body=body, masked=masked, units=units, unit_of=unit_of, key=''.join(key), kpos=kpos)


# ---------------------------------------------------------------- the source
def group_records(index, catalog):
    """Copy float group -> catalog record id, by the caption's lexical key."""
    captions = []
    for record in catalog.get('floats', []):
        for value in [record.get('caption') or ''] + [p.get('caption') or '' for p in record.get('parts', [])]:
            value = ''.join(nkey(ch) for ch in value)
            if len(value) >= 4: captions.append((value, record['id']))
    result = {}
    for u in index['units']:
        if u['kind'] != 'caption' or u['group'] is None: continue
        value = ''.join(nkey(ch) for ch in u['text'])
        hits = {rid for cap, rid in captions if value.startswith(cap[:40]) or cap.startswith(value[:40])}
        if len(hits) == 1: result[u['group']] = hits.pop()
    return result


def catalog_roles(catalog):
    """The copier's float ownership: (page, run id) -> (float id, kind, role)."""
    roles, regions = {}, []
    for record in catalog.get('floats', []):
        for part in record.get('parts', []):
            for o in part.get('objects', []):
                role = (o.get('assignment') or {}).get('role')
                if o.get('source_id') and role:
                    # Unassigned objects lie in the float region without an owner.
                    roles[part['page'], o['source_id']] = (record['id'], record.get('kind'), role)
            box = part.get('graphic_box') or part.get('box')
            if record.get('kind') == 'figure' and box:
                regions.append((part['page'], record['id'], box))
    return roles, regions


def source_lines(sources, pages, state, catalog, fonts, engine, helper):
    """Decoded physical rows, as the export_lines port cuts them, plus OCR text.

    Every text run is owned by exactly one row. Text drawn as glyph outlines
    and read by the copier's OCR step is its own row; it is unverified.
    """
    owner, regions = catalog_roles(catalog)
    result = []
    for page in sorted(sources, key=lambda p: p['page']):
        number = page['page']
        roles = helper.source_roles(page, state)
        for (pg, sid), (_, kind, role) in owner.items():
            if pg == number and role in ('caption', 'structure', 'note'):
                roles[sid] = {'caption': 'caption', 'note': 'note'}.get(role, 'table' if kind == 'table' else 'figure_text')
        block_of = {m: b['id'] for b in page.get('blocks', []) for m in b.get('members', [])}
        expected = collections.Counter(e['id'] for e in page['elements']
                                       if e.get('kind') == 'text' and e.get('text', '').strip())
        seen = collections.Counter()
        rows = []
        for row in helper.source_rows(page, roles):
            original = [s for e in row for s in e.get('_subscript_sources', [e])]
            seen.update(e['id'] for e in original)
            if page.get('_pcl_ocr'):
                atoms = []
                for e in row:
                    if not e['text'].strip(): continue
                    if atoms: atoms.append(dict(text=' ', style=(), issue='publisher OCR unverified; no printed font evidence'))
                    atoms += [dict(text=ch, style=(), issue='publisher OCR unverified; no printed font evidence',
                                   evidence=dict(run=e['id'])) for ch in e['text'].strip()]
            else: atoms = row_atoms(row, page, fonts, engine)
            rows.append((atoms, original, row[0].get('angle', 0)))
        if expected != seen:
            raise ValueError(f'page {number}: source ownership differs: missing={expected-seen}, extra={seen-expected}')
        for e in page['elements']:
            if e.get('kind') == 'outline' and (e.get('ocr_text') or '').strip():
                value = ' '.join(e['ocr_text'].split())
                rows.append(([dict(text=ch, style=(), issue='text drawn as outlines; copier OCR unverified')
                              for ch in value], [e], 0))
        for number_line, (atoms, original, angle) in enumerate(rows, 1):
            box = engine.hull(e['box_px'] for e in original)
            votes = collections.Counter(owner.get((number, e['id'])) for e in original)
            float_owner = votes.most_common(1)[0][0]
            if float_owner and float_owner[2] not in ('caption', 'structure', 'note'):
                member, float_owner = float_owner, None
            else: member = float_owner
            role = collections.Counter(roles.get(e['id'], 'body') for e in original).most_common(1)[0][0]
            if role not in ('furniture', 'figure_text') and float_owner is None:
                cx, cy = (box[0]+box[2])/2, (box[1]+box[3])/2
                inside = [fid for pg, fid, b in regions if pg == number and b[0] <= cx <= b[2] and b[1] <= cy <= b[3]]
                if inside: member = float_owner = (inside[0], 'figure', 'lettering')
            key, kat, run_spans = row_key(atoms)
            result.append(dict(page=number, page_line=number_line, atoms=atoms, run_spans=run_spans,
                               runs=[e['id'] for e in original], box=box, angle=angle,
                               role=role, float_owner=float_owner, member=member, key=''.join(key), kat=kat,
                               block=collections.Counter(block_of.get(e['id']) for e in original).most_common(1)[0][0],
                               ocr=bool(page.get('_pcl_ocr')), pieces=[]))
    return result


def row_key(atoms):
    """The row's lexical key, key-to-atom map and allocation pieces.

    A piece is one source run, cut again at a gap clearly wider than the
    row's own word spaces (the boxer can join two table cells in one run).
    """
    # Word spaces of this row: a cell gutter is clearly wider.
    spacing, last_box, spaced = [], None, False
    for a in atoms:
        glyph_box = (a.get('evidence') or {}).get('box')
        if a['text'].isspace(): spaced = True; continue
        if glyph_box and last_box and spaced: spacing.append(glyph_box[0]-last_box[2])
        if glyph_box: last_box, spaced = glyph_box, False
    word_space = statistics.median(spacing) if spacing else 0
    key, kat, run_spans, previous = [], [], [], None
    for j, a in enumerate(atoms):
        if a.get('gap'): continue
        evidence = a.get('evidence') or {}
        run = evidence.get('run')
        # A piece is one source run, cut again at a gutter-wide gap
        # inside it (the boxer can join two table cells in one run).
        wide = False
        if previous is not None and evidence.get('box') and previous.get('box') and not a['text'].isspace():
            size = evidence.get('size') or previous.get('size') or 0
            wide = size and evidence['box'][0]-previous['box'][2] > max(.6*size, 1.6*word_space)
        for c in nkey(a['text']):
            if run is not None and (not run_spans or run_spans[-1][0] != run or wide):
                run_spans.append([run, len(key), len(key)]); wide = False
            key.append(c); kat.append(j)
            if run_spans and run_spans[-1][0] == run: run_spans[-1][2] = len(key)
        if not a['text'].isspace() and evidence.get('box'): previous = evidence
    return ''.join(key), kat, [(a, b) for _, a, b in run_spans if b > a]


def trace_windows(trace, rows):
    """Copy spans each printed source row was recorded into, from copy.trace.json.

    The copier records a unit's source rows when it writes the unit, so the
    writer no longer has to guess which repeated occurrence of a row belongs
    to which copy unit. A trace line's destination units give the copy spans;
    spans close together (the separators of one byline or table row) are one
    region. Beyond short numeric rows and OCR rows (which keep the earlier
    matching fallback), a line the trace marks furniture, uncertainty or lost
    has no copy destination and must not be matched to copy text by
    similarity. Lines shared by a split or partial claim keep every recorded
    destination and are placed by exact text inside those regions.
    """
    if not trace or trace.get('schema') != 'copy-trace/2 (native)':
        return {}
    by_line = {}
    for record in trace.get('lines', []):
        by_line.setdefault((record.get('page'), record.get('page_line')), []).append(record)
    by_runs = {}
    for record in trace.get('lines', []):
        by_runs.setdefault((record.get('page'), tuple(str(x) for x in record.get('runs', []))), []).append(record)
    kinds = {unit['id']: unit.get('kind') for unit in trace.get('units', [])}
    windows = {}
    for i, row in enumerate(rows):
        # Short numeric rows repeat too freely for a line-level group to
        # identify their exact place; the copy's neighbours decide them.
        # OCR rows have no native glyph identity to corroborate the trace.
        if row.get('ocr') or len(row.get('key', '')) < 8: continue
        page = row['page']
        page_line = row.get('page_line') or i+1
        found = by_line.get((page, page_line), [])
        if len(found) != 1 or tuple(str(x) for x in found[0].get('runs', [])) != tuple(str(x) for x in row['runs']):
            found = by_runs.get((page, tuple(str(x) for x in row['runs'])), [])
        if len(found) != 1:
            continue
        record = found[0]
        status = record.get('status')
        if status in ('furniture', 'uncertainty', 'lost'):
            windows[i] = dict(regions=[], primary=[])
            continue
        def spans_of(skip_flagged):
            return sorted((tuple(u['copy_span']) for u in record.get('units', [])
                           if u.get('copy_span') and u['copy_span'][0] is not None
                           and not (skip_flagged and status == 'flagged_repeat' and
                                    kinds.get(u['unit_id']) == 'front_matter_printed')))

        def merge(spans):
            regions = []
            for a, b in spans:
                if regions and a <= regions[-1][1]+64:
                    regions[-1] = (regions[-1][0], max(regions[-1][1], b))
                else:
                    regions.append((a, b))
            return regions
        regions = merge(spans_of(False))
        # The flagged "Front matter as printed" block deliberately repeats the
        # parsed byline and addresses: their source rows belong to the parsed
        # units when the text is found there, and only fall back to the repeat.
        primary = merge(spans_of(True)) if status == 'flagged_repeat' else regions
        windows[i] = dict(regions=regions, primary=primary or regions)
    return windows



# ---------------------------------------------------------------- allocation
def neighbours(lines, engine):
    """Block reading neighbours and same-baseline neighbours of each row."""
    links = collections.defaultdict(lambda: dict(prev=[], next=[]))
    by_block, by_page = collections.defaultdict(list), collections.defaultdict(list)
    for i, line in enumerate(lines):
        if not line['key']: continue   # a sign-only row is nobody's text neighbour
        if line['block'] is not None: by_block[line['page'], line['block']].append(i)
        by_page[line['page'], round(line['angle']) % 360].append(i)
    def framed(i): return engine.frame(lines[i]['angle'])(lines[i]['box'])
    for members in by_block.values():
        members.sort(key=lambda i: (framed(i)[1], framed(i)[0]))
        for a, b in zip(members, members[1:]):
            links[b]['prev'].append(a); links[a]['next'].append(b)
    for members in by_page.values():
        boxes = {i: framed(i) for i in members}
        for i in members:
            bi, best = boxes[i], None
            for j in members:
                bj = boxes[j]
                if j == i or bj[0] < bi[2]-1: continue
                if min(bi[3], bj[3])-max(bi[1], bj[1]) < .5*min(bi[3]-bi[1], bj[3]-bj[1]): continue
                if best is None or bj[0] < boxes[best][0]: best = j
            if best is not None:
                links[i]['next'].append(best); links[best]['prev'].append(i)
    return links, by_block


def allocate(lines, index, engine):
    """Give each row the copy characters made from it, each character once.

    Exact key occurrences only: unique long rows anchor; rows continue a
    placed block or baseline neighbour; remaining candidates are chosen by
    the copier's own records first (a table cell or figure lettering only
    inside a copy float; a row near its page's part of the copy, between the
    copy's page marks), then by how much of their neighbours' text surrounds
    them, then by position. A row without an exact occurrence takes the
    matching pieces of the copy between its placed neighbours. Furniture is
    only taken by a unique or neighbour-continued occurrence. Unmatched text
    stays unallocated and is reported.
    """
    key, kpos, units, unit_of = index['key'], index['kpos'], index['units'], index['unit_of']
    records = index.get('records', {})
    used = bytearray(len(key))
    owner_of = index['owner'] = [-1]*len(key)
    links, by_block = neighbours(lines, engine)
    by_float = collections.defaultdict(list)
    for i, line in enumerate(lines):
        if line['float_owner']: by_float[line['page'], line['float_owner'][0]].append(i)
    cache = {}
    trace_regions = index.get('trace_windows') or {}
    marks = [(m.start(), int(m[1])) for m in re.finditer(r'<!-- end of page (\d+) -->', index['body'])]
    starts = [m[0] for m in marks]

    def recorded(i, at):
        """The place is inside a copy span the trace recorded for this row.

        Rows without a trace mapping keep the earlier matching behaviour;
        rows the trace marks as furniture, uncertainty or lost have no region
        and are never matched to a repeated copy occurrence by similarity.
        """
        if i not in trace_regions: return True
        position = kpos[at] if 0 <= at < len(kpos) else None
        return position is not None and any(start <= position < end
                                            for start, end in trace_regions[i]['regions'])

    def recorded_rank(i, at):
        """0 inside the trace's preferred destination, 1 in a listed fallback."""
        if i not in trace_regions: return 0
        position = kpos[at] if 0 <= at < len(kpos) else None
        if position is None: return 2
        entry = trace_regions[i]
        if any(start <= position < end for start, end in entry['primary']): return 0
        return 1

    def near_page(at, page):
        """Within one page of the pages the copy's marks put around this place.

        Marks are not monotone when the copy moves a float; use both sides.
        """
        if not marks: return True
        k = bisect.bisect_left(starts, kpos[at])
        before = marks[k-1][1]+1 if k else 1
        after = marks[k][1] if k < len(marks) else before
        low, high = min(before, after), max(before, after)
        return low-1 <= page <= high+1

    def group_at(at):
        u = unit_of[kpos[at]]
        return units[u]['group'] if u is not None else None

    def kind(i):
        owner, role = lines[i]['float_owner'], lines[i]['role']
        if role == 'furniture': return 'furniture'
        if role == 'figure_text' or owner and owner[1] == 'figure' and owner[2] in ('structure', 'lettering'):
            return 'inside'
        if owner and owner[2] == 'structure': return 'inside'
        return 'float' if owner else 'text'

    def allowed(i, at, strict=True):
        if kind(i) != 'inside': return True
        group = group_at(at)
        owner = lines[i]['float_owner']
        near = near_page(at, lines[i]['page'])
        # Lettering and cells belong to their own float, near their page. Only
        # a unique or neighbour-continued occurrence may put them in prose
        # (a text box the catalog took for a figure).
        if group is None: return not strict and near
        if owner and owner[2] == 'lettering':
            # Containment in a catalog figure region, not an owned object:
            # the copier may print that region as another float's lines.
            return near
        return records.get(group, owner and owner[0]) == (owner and owner[0]) and near

    def preference(i, at):
        near = near_page(at, lines[i]['page'])
        grouped = group_at(at) is not None
        return (-recorded_rank(i, at), near, kind(i) in ('inside', 'float') or not grouped)

    def occurrences(value):
        if value not in cache:
            found, start = [], 0
            while True:
                at = key.find(value, start)
                if at < 0: break
                found.append(at); start = at+1
            cache[value] = found
        return cache[value]

    def free(at, n): return not any(used[at:at+n])

    def bounded(i, at, n=None):
        """A short row's text is a whole copy word run, not part of a longer word.

        ('Grade I' is not the start of 'Grade II'.) A row ending in a hyphen
        may continue into the next word; longer rows need no check.
        """
        n = len(lines[i]['key']) if n is None else n
        if n >= 16: return True
        start = at == 0 or kpos[at]-kpos[at-1] > 1
        tail = [a['text'] for a in lines[i]['atoms'] if not a['text'].isspace()]
        end = at+n >= len(key) or kpos[at+n]-kpos[at+n-1] > 1 or bool(tail) and tail[-1] in '-‐'
        return start and end

    def claim(i, at):
        n = len(lines[i]['key']); used[at:at+n] = b'\1'*n
        owner_of[at:at+n] = [i]*n
        lines[i]['pieces'] = [(0, at, n)]

    def span(i):
        pieces = lines[i]['pieces']
        return (pieces[0][1], pieces[-1][1]+pieces[-1][2]) if pieces else None

    def context(i, at):
        n = len(lines[i]['key'])
        left = right = 0
        for p in links[i]['prev']:
            k = lines[p]['key'][-20:]; s = 0
            while s < len(k) and at-1-s >= 0 and key[at-1-s] == k[-1-s]: s += 1
            left = max(left, s)
        for q in links[i]['next']:
            k = lines[q]['key'][:20]; s = 0
            while s < len(k) and at+n+s < len(key) and key[at+n+s] == k[s]: s += 1
            right = max(right, s)
        return left+right

    def expected(i):
        line = lines[i]
        mates = [j for j in by_block.get((line['page'], line['block']), []) if lines[j]['pieces']] \
            if line['block'] is not None else []
        if line['float_owner']:
            # A table cell's mates are the rows of its own float on its page.
            mates = [j for j in by_float.get((line['page'], line['float_owner'][0]), []) if lines[j]['pieces']] or mates
        same = mates or [j for j, m in enumerate(lines) if m['page'] == line['page'] and m['pieces']]
        before = [span(j)[1] for j in same if (lines[j]['box'][1], lines[j]['box'][0]) <= (line['box'][1], line['box'][0])]
        return (max(before) if before else min((span(j)[0] for j in same), default=0)), mates

    order = sorted((i for i, l in enumerate(lines) if l['key']), key=lambda i: -len(lines[i]['key']))
    for i in order:
        n = len(lines[i]['key'])
        if n < 8: break
        # Unique in the whole copy, not merely among free occurrences: the
        # last free occurrence is often the text of a row not yet placed.
        every = [at for at in occurrences(lines[i]['key']) if bounded(i, at)]
        if len(every) == 1 and free(every[0], n) and allowed(i, every[0], strict=False) and recorded(i, every[0]): claim(i, every[0])
    changed = True
    while changed:
        changed = False
        for i in order:
            line = lines[i]; n = len(line['key'])
            if line['pieces']: continue
            found = []
            for p in links[i]['prev']:
                if lines[p]['pieces']:
                    end = span(p)[1]
                    found += [t for t in range(end, end+(7 if n >= 4 else 1)) if key.startswith(line['key'], t) and free(t, n)]
            for q in links[i]['next']:
                if lines[q]['pieces']:
                    start = span(q)[0]
                    found += [start-n-t for t in range(7 if n >= 4 else 1) if start-n-t >= 0 and
                              key.startswith(line['key'], start-n-t) and free(start-n-t, n)]
            found = [at for at in found if allowed(i, at, strict=False) and recorded(i, at)]
            if i in trace_regions:
                # A source row whose trace names a parsed destination is not
                # pulled into the flagged repeat beside a placed neighbour;
                # leave it for the scored allocation if no primary place is near.
                preferred = [at for at in found if recorded_rank(i, at) == 0]
                found = preferred or ([] if trace_regions[i]['primary'] != trace_regions[i]['regions'] else found)
            if found:
                claim(i, min(found, key=lambda at: (recorded_rank(i, at), at))); changed = True
    for final in (False, False, False, True):
        for i in order:
            line = lines[i]; n = len(line['key'])
            if line['pieces'] or kind(i) == 'furniture': continue
            exp, mates = expected(i)
            found = [at for at in occurrences(line['key']) if free(at, n) and allowed(i, at) and bounded(i, at)
                     and recorded(i, at)]
            if n < 4 or len(found) > 150:
                # A short or common row is only allocated inside its block's copy span.
                if not mates: continue
                low = min(span(j)[0] for j in mates)-80; high = max(span(j)[1] for j in mates)+80
                found = [at for at in found if low <= at <= high]
            if not found: continue
            scored = sorted(((preference(i, at), context(i, at), -abs(at-exp), at) for at in found), reverse=True)
            rivals = [s for s in scored[1:] if s[0] == scored[0][0]]
            margin = scored[0][1]-(rivals[0][1] if rivals else -1)
            if final or len(scored) == 1 and n >= 4 or scored[0][1] >= 3 and margin >= 2:
                claim(i, scored[0][3])
    def rarity(i):
        counts = [sum(1 for at in occurrences(lines[i]['key'][a:b]) if free(at, b-a))
                  for a, b in lines[i].get('run_spans', []) if b-a >= 4]
        return min([c for c in counts if c] or [10**9])
    # A row whose whole text has no occurrence can join two cells or two
    # columns: allocate its pieces separately (each exact, near the row's
    # expected place; rows with the rarest piece first), before any inexact piece.
    for i in sorted((i for i in order if not lines[i]['pieces'] and len(lines[i].get('run_spans', [])) >= 2),
                    key=rarity):
        line = lines[i]
        spans_ = line.get('run_spans', [])
        if line['pieces'] or kind(i) in ('furniture',) or len(spans_) < 2: continue
        exp, _ = expected(i)
        pieces = []
        options = []
        for a, b in spans_:
            value = line['key'][a:b]
            if len(value) < 4: continue
            found = [at for at in occurrences(value) if free(at, len(value)) and allowed(i, at)
                     and recorded(i, at)]
            found = [at for at in found if bounded(i, at, len(value))] or found
            found = [at for at in found if preference(i, at)[1]] or found
            if found: options.append((len(found), a, value, found))
        # The rarest piece first; the row's other pieces stay near it.
        for _, a, value, found in sorted(options):
            found = [at for at in found if free(at, len(value))]
            if not found: continue
            near = [at for _, at, _ in pieces] or [exp]
            at = min(found, key=lambda at: (recorded_rank(i, at), min(abs(at-x) for x in near)))
            used[at:at+len(value)] = b'\1'*len(value); owner_of[at:at+len(value)] = [i]*len(value)
            pieces.append((a, at, len(value)))
        line['pieces'] = sorted(pieces)
    def physical(i):
        box = engine.frame(lines[i]['angle'])(lines[i]['box'])
        return (lines[i]['page'], box[1], box[0])
    for i in sorted(order, key=physical):
        line = lines[i]; n = len(line['key'])
        # Inexact pieces are never taken for furniture, lettering or a cell:
        # a near-identical neighbouring cell would receive the wrong value.
        if line['pieces'] or kind(i) in ('furniture', 'inside'):
            continue
        starts_ = [span(p)[1] for p in links[i]['prev'] if lines[p]['pieces']]
        ends = [span(q)[0] for q in links[i]['next'] if lines[q]['pieces']]
        if not starts_ and not ends:
            # No placed neighbour: the copy between the placed rows printed
            # just before and just after it on the page, if that is close.
            here = sorted((j for j, m in enumerate(lines) if m['page'] == line['page'] and m['pieces']), key=physical)
            before = [j for j in here if physical(j) < physical(i)]
            after = [j for j in here if physical(j) > physical(i)]
            if not before or not after: continue
            low, high = span(before[-1])[1], span(after[0])[0]
            if not 0 < high-low <= 4*n+300: continue
        else:
            low = max(starts_) if starts_ else max(0, min(ends)-2*n-40)
            high = min([e for e in ends if e > low] or [low+2*n+40])
        window = key[low:high]
        blocks = difflib.SequenceMatcher(None, line['key'], window, autojunk=False).get_matching_blocks()
        pieces = [(a, low+b, size) for a, b, size in blocks if size >= min(3, n) and free(low+b, size)
                  and recorded(i, low+b) and all(allowed(i, low+b+t) for t in range(size))]
        for a, at, size in pieces:
            used[at:at+size] = b'\1'*size; owner_of[at:at+size] = [i]*size
        line['pieces'] = pieces
    return used


# ---------------------------------------------------------------- realization
SIGNS = str.maketrans({**{c: '-' for c in '‐‑‒–—−•●◦▪\u00ad'}, **{c: "'" for c in '‘’‚‛′'},
                       **{c: '"' for c in '“”„‟″'}})


def same_sign(a, b):
    """Signs the copy may write differently: dashes, bullets, quotes, NFKC forms."""
    return unicodedata.normalize('NFKC', a).translate(SIGNS) == unicodedata.normalize('NFKC', b).translate(SIGNS)


def atom_offsets(line, index):
    """Copy offsets of each atom: alphanumerics by key, signs by local order."""
    body, kpos, atoms = index['body'], index['kpos'], line['atoms']
    first, last = [None]*len(atoms), [None]*len(atoms)
    for a, at, size in line['pieces']:
        for t in range(size):
            j, c = line['kat'][a+t], kpos[at+t]
            first[j] = c if first[j] is None else min(first[j], c)
            last[j] = c if last[j] is None else max(last[j], c)
    anchors = [j for j in range(len(atoms)) if first[j] is not None]
    taken = set()
    for ja, jb in zip(anchors, anchors[1:]):
        if last[ja] >= first[jb]: continue
        signs = [j for j in range(ja+1, jb) if not atoms[j]['text'].isspace() and not atoms[j].get('gap')]
        chars = [c for c in range(last[ja]+1, first[jb]) if not body[c].isspace() and not index['masked'][c]]
        s = 0
        for j in signs:
            want = atoms[j]['text']
            for k in range(s, len(chars)):
                got = body[chars[k]]
                if same_sign(got, want):
                    first[j] = last[j] = chars[k]; taken.add(chars[k]); s = k+1; break
    if anchors:
        # Trailing signs (a line-end hyphen, closing punctuation) follow the
        # last alphanumeric directly in the copy when the copy kept them.
        c = last[anchors[-1]]+1
        for j in range(anchors[-1]+1, len(atoms)):
            if atoms[j]['text'].isspace() or atoms[j].get('gap'): break
            while c < len(body) and body[c] == '\\': c += 1
            if c < len(body) and same_sign(body[c], atoms[j]['text']):
                first[j] = last[j] = c; c += 1
            else: break
        c = first[anchors[0]]-1
        for j in range(anchors[0]-1, -1, -1):
            if atoms[j]['text'].isspace() or atoms[j].get('gap'): break
            while c >= 0 and body[c] == '\\': c -= 1
            if c >= 0 and same_sign(body[c], atoms[j]['text']):
                first[j] = last[j] = c; c -= 1
            else: break
    return first, last


def spaced_atoms(atoms, first, last, body):
    """Follow the copy's word spaces with printed spaces, gaps or hidden spaces."""
    def whitespace(a, b):
        return any(ch.isspace() for ch in body[a+1:b]) if a is not None and b is not None and a < b else None

    def em(a, b):
        try:
            left, right = a['evidence'], b['evidence']
            size = left.get('size') or right.get('size')
            return round((right['box'][0]-left['box'][2])/size, 3) if size else 0.0
        except (KeyError, TypeError, IndexError):
            return 0.0
    printed = [j for j, a in enumerate(atoms) if not a['text'].isspace() and not a.get('gap')]
    result = []
    for p, q in zip(printed, printed[1:]+[None]):
        result.append(dict(atoms[p], _src=p))
        if q is None: break
        between = range(p+1, q)
        wanted = whitespace(last[p], first[q])
        if wanted is None:
            result.extend(dict(atoms[j], _src=j) for j in between)
        elif wanted:
            if between: result.extend(dict(atoms[j], _src=j) for j in between)
            else: result.append(dict(text=' ', style=(), gap=True, _src=None))
        else:
            for j in between:
                if not atoms[j].get('gap'):
                    result.append(dict(atoms[j], hidden=True, gap_em=em(atoms[p], atoms[q]), _src=j))
    leading = [dict(atoms[j], _src=j) for j in range(printed[0])] if printed else \
        [dict(a, _src=j) for j, a in enumerate(atoms)]
    trailing = [dict(atoms[j], _src=j) for j in range(printed[-1]+1, len(atoms))] if printed else []
    return [a for a in leading+result+trailing]


def tidy_edges(atoms):
    """A gap cannot open or close a line; a printed edge space stays printed."""
    while atoms and atoms[0].get('gap'): atoms = atoms[1:]
    while atoms and atoms[-1].get('gap'): atoms = atoms[:-1]
    return atoms


def identifier(value):
    value = re.sub(r'[^A-Za-z0-9._:/-]+', '-', str(value)).strip('-._:/')
    return value if value and value[0].isalnum() else 'x' + value


def segments(lines, index):
    """Cut each row where its copy characters change unit; keep all glyphs."""
    result, owners, kpos = [], index['owner'], index['kpos']
    for n, line in enumerate(lines):
        first, last = atom_offsets(line, index)
        atoms = spaced_atoms(line['atoms'], first, last, index['body'])
        parts, current, end = [[]], None, None
        for a in atoms:
            j = a.get('_src')
            printed = j is not None and not a['text'].isspace() and not a.get('gap') and not a.get('hidden')
            unit = index['unit_of'][first[j]] if printed and first[j] is not None else None
            if unit is not None:
                # Cut where the copy changes unit, or puts another row's text
                # between two neighbouring glyphs of this row (merged cells).
                foreign = end is not None and any(
                    owners[k] not in (-1, n) for k in range(bisect.bisect_right(kpos, end), bisect.bisect_left(kpos, first[j])))
                if current is not None and (unit != current or foreign) and any(
                        not x['text'].isspace() and not x.get('gap') for x in parts[-1]):
                    parts.append([])
                current, end = unit, last[j]
            parts[-1].append(a)
        for part, atoms in enumerate(parts):
            atoms = tidy_edges(atoms)
            if not atoms: continue
            offsets = [c for a in atoms if a.get('_src') is not None
                       for c in (first[a['_src']], last[a['_src']]) if c is not None]
            units = [index['unit_of'][c] for c in offsets if index['unit_of'][c] is not None]
            result.append(dict(line, atoms=atoms, source=n, part=part, unit=units[0] if units else None,
                               offsets=sorted(set(offsets)),
                               cfirst=min(offsets) if offsets else None, clast=max(offsets) if offsets else None,
                               aligned=[a.get('_src') is not None and first[a['_src']] is not None for a in atoms],
                               text=''.join(' ' if a.get('gap') else a['text'] for a in atoms)))
    return result


def assign_roles(segs, index):
    """Roles follow the copy unit; unused rows follow the copier's own records."""
    units = index['units']
    notes = collections.defaultdict(list)
    for s in segs:
        if s['unit'] is not None: notes[s['unit']].append((s['float_owner'] or (None, None, None))[2])
    for u in units:
        # A table's note paragraph follows its float in the copy: same block.
        if (u['group'] is None and u['kind'] == 'paragraph' and u['index'] and units[u['index']-1]['group']
                and notes.get(u['index']) and all(r == 'note' for r in notes[u['index']])):
            u['group'] = units[u['index']-1]['group']
    group_kind, group_ref = {}, {}
    for u in units:
        if u['kind'] == 'caption' and u['group'] is not None:
            group_kind[u['group']] = 'figure' if re.match(r'\*\*(?:Fig|Unlabelled figure|Scheme|Plate)', u['text'], re.I) else 'table'
    for s in segs:
        u = units[s['unit']] if s['unit'] is not None else None
        owner = s['float_owner']
        if u is not None and u['group'] is not None and owner and u['group'] not in group_ref:
            group_ref[u['group']] = identifier(owner[0])
    for s in segs:
        u = units[s['unit']] if s['unit'] is not None else None
        owner = s['float_owner']
        if u is not None:
            if u['kind'] in ('title', 'heading'):
                s.update(role='heading', group=f'u{u["index"]}', ref=f'copy-line-{u["index"]+1}')
            elif u['group'] is not None:
                kind = ('caption' if u['kind'] == 'caption' else 'note' if owner and owner[2] == 'note' else
                        'figure' if owner and owner[1] == 'figure' else group_kind.get(u['group'], 'table'))
                s.update(role=kind, group=f'float-{u["group"]}', float_id=f'float-{u["group"]}',
                         ref=group_ref.get(u['group'], f'float-{u["group"]}'))
            else: s.update(role='body', group=f'u{u["index"]}')
        elif s['role'] == 'furniture':
            s.update(role='furniture', group=f'furniture-{s["source"]}', unused=True, reason='copier furniture')
        elif s['member'] or s['role'] == 'figure_text':
            fid, kind, role = s['member'] or ('figure-text', 'figure', 'lettering')
            name = identifier(f'{fid}-p{s["page"]}')
            s.update(role={'caption': 'caption', 'note': 'note'}.get(role, 'table' if kind == 'table' else 'figure'),
                     group=name, float_id=name, ref=identifier(fid), unused=True)
        elif not s['key']:
            # Signs alone (a divider bar, a stray bullet) that the copy omits
            # are page decoration, not paper text.
            s.update(role='furniture', group=f'furniture-{s["source"]}', unused=True,
                     reason='sign-only row the copy omits')
        else:
            s.update(role='body', group=f'lost-{s["page"]}-{s["block"]}', unused=True)
    return segs


def arrange(segs, engine):
    """Pages stay consecutive; inside a page, the copy's order decides.

    An unused row follows its nearest physically preceding used row.
    """
    result = []
    for page in sorted({s['page'] for s in segs}):
        here = [s for s in segs if s['page'] == page]
        physical = lambda s: (engine.frame(s['angle'])(s['box'])[1], engine.frame(s['angle'])(s['box'])[0], s['source'])
        used = sorted((s for s in here if s['cfirst'] is not None), key=physical)
        reading = sorted(used, key=lambda s: s['cfirst'])
        for s in here:
            if s['cfirst'] is not None: s['_order'] = (s['cfirst'], 0, physical(s))
            else:
                mine = [u for u in used if s['member'] and u['member'] and u['member'][0] == s['member'][0]]
                before = [u for u in (mine or used) if physical(u) < physical(s)] or mine[:1]
                anchor = before[-1] if before else None
                if anchor is not None:
                    # Unused text never splits a copy unit (a paragraph, a
                    # caption): it follows the unit's last row on this page.
                    k = reading.index(anchor)
                    while k+1 < len(reading) and reading[k+1]['unit'] == anchor['unit']: k += 1
                    anchor = reading[k]
                s['_order'] = ((anchor['clast'] if anchor else -1), 1, physical(s))
        result.extend(sorted(here, key=lambda s: s['_order']))
    return result


def join_kind(a, b, body):
    """The copy's join of two consecutive rows of one unit, or None for a space."""
    if a['clast'] is None or b['cfirst'] is None or a['clast'] >= b['cfirst']: return None
    if any(ch.isspace() for ch in body[a['clast']+1:b['cfirst']]): return None
    tail = [(atom, ok) for atom, ok in zip(a['atoms'], a['aligned']) if not atom.get('hidden')]
    if not tail: return None
    atom, aligned = tail[-1]
    if atom['text'] in ('-', '‐'):
        # A raised or lowered hyphen is not the line's last reading character
        # (its notation span closes after it): the rulebook cannot join there.
        if {'sup', 'sub'} & set(atom.get('style', ())): return None
        return 'keep' if aligned else 'remove'
    if atom['text'].isspace(): return None
    return 'none'


def joins(lines, index):
    """Paragraphs and word joins exactly where the copy has them."""
    body, previous = index['body'], None
    for i, line in enumerate(lines):
        role = line['role']
        if role == 'furniture': continue
        if role in FLOAT_ROLES:
            prev = lines[i-1] if i and lines[i-1].get('group') == line['group'] and lines[i-1]['role'] == role else None
            if prev and prev['unit'] is not None and prev['unit'] == line['unit']:
                kind = join_kind(prev, line, body)
                if kind: line['wrap'] = dict(hyphen=kind)
            continue
        p = lines[previous] if previous is not None else None
        same = p is not None and (p['unit'] is not None and p['unit'] == line['unit'] and p['clast'] < line['cfirst']
                                  or p['unit'] is None and line['unit'] is None and p['group'] == line['group']
                                  and previous == i-1)
        line['para'] = not same
        if same and line['unit'] is not None:
            kind = join_kind(p, line, body)
            if kind: line['wrap'] = dict(hyphen=kind, **({'from': previous+1} if previous < i-1 else {}))
        previous = i
    return lines


def build_lines(sources, pages, text, conservation, catalog, fonts, engine, scan_audit=None, trace=None):
    """Return PCL lines in the copy's order, with the copy index and source rows."""
    helper = module('_pcl_line_helpers', Path(__file__).with_name('export_lines.py'))
    index = copy_index(text)
    index['records'] = group_records(index, catalog)
    state = dict(pages=pages, saved_conservation=conservation, scan_audit=scan_audit or {})
    rows = source_lines(sources, pages, state, catalog, fonts, engine, helper)
    return place_lines(rows, index, engine, [p['page'] for p in sources], trace), index, rows


def place_lines(rows, index, engine, page_numbers, trace=None):
    """Allocate rows to the copy, cut, give roles, order by page and copy, join."""
    index['trace_windows'] = trace_windows(trace, rows)
    index['used'] = allocate(rows, index, engine)
    segs = arrange(assign_roles(segments(rows, index), index), engine)
    present = {s['page'] for s in segs}
    for page in sorted(page_numbers):
        if page not in present:
            segs.append(dict(page=page, role='body', group=f'p{page}-empty', atoms=[], text='', runs=[],
                             box=[0, 0, 0, 0], unit=None, cfirst=None, clast=None, aligned=[], source=None,
                             _order=(-1, 0, ())))
    segs.sort(key=lambda s: (s['page'], s['_order']))
    index['printed'] = {c for s in segs for c in s.get('offsets', ())}
    # A row is displaced when page grouping, not the copy, decides its place:
    # copy text of an earlier page follows it, or of a later page precedes it.
    pages_ = sorted({s['page'] for s in segs})
    last = {p: max((s['cfirst'] for s in segs if s['page'] == p and s['cfirst'] is not None), default=None) for p in pages_}
    first = {p: min((s['cfirst'] for s in segs if s['page'] == p and s['cfirst'] is not None), default=None) for p in pages_}
    for s in segs:
        if s['cfirst'] is None: continue
        before = [last[p] for p in pages_ if p < s['page'] and last[p] is not None]
        after = [first[p] for p in pages_ if p > s['page'] and first[p] is not None]
        s['displaced'] = bool(before and s['cfirst'] < max(before) or after and s['cfirst'] > min(after))
    return joins(segs, index)


# ---------------------------------------------------------------- measurement
WORD = re.compile(r'[^\W\d_]+|\d+')


def tokens(value):
    """Case-sensitive NFKC letter runs and digit runs."""
    return WORD.findall(unicodedata.normalize('NFKC', value))


def located_tokens(value, positions):
    """Tokens with the position of their first character (NFKC per character)."""
    chars, where = [], []
    for ch, at in zip(value, positions):
        for c in unicodedata.normalize('NFKC', ch):
            chars.append(c); where.append(at)
    text = ''.join(chars)
    return [(m[0], where[m.start()]) for m in WORD.finditer(text)]


def copy_words(index):
    """Copy words; the copy's own notation signs (^, and [ ] around raised marks) join.

    A sign aligned to a printed glyph is printed text and stays a boundary.
    """
    body, printed = index['body'], index.get('printed', set())
    keep = [i for i, ch in enumerate(body) if index['masked'][i] or ch not in '^[]' or i in printed]
    return located_tokens(''.join('\n' if index['masked'][i] else body[i] for i in keep), keep)


def pcl_words(analysis, skip_lines):
    """Reading-view words (with reading offsets) and file-order words (with lines).

    File order reads every line where the file has it, so float blocks stand
    where the copy puts them; the reading view places them by rulebook 7.12.
    """
    notation = {e['offset'] for e in analysis.annotations['reading_map']
                if e.get('derived') in ('sup-open', 'sup-close', 'sub-open', 'sub-close')}
    text, owner = analysis.text, {}
    for record in analysis.annotations['lines']:
        for i in range(record['reading_start'], record['reading_end']): owner[i] = record['line']
    # Derived notation markers join, as the copy's ^ and [n] do (copy_words).
    keep = [i for i in range(len(text)) if i not in notation and owner.get(i) not in skip_lines]
    reading = located_tokens(''.join(text[i] for i in keep), [owner.get(i, 0) for i in keep])
    chars, where, end = [], [], None
    for record in analysis.annotations['lines']:
        if record['line'] in skip_lines: continue
        # Contiguous reading ranges are a word join; others meet at a break.
        if end is not None and record['reading_start'] != end:
            chars.append('\n'); where.append(record['line'])
        for i in range(record['reading_start'], record['reading_end']):
            if i not in notation: chars.append(text[i]); where.append(record['line'])
        end = record['reading_end']
    return reading, located_tokens(''.join(chars), where)


CAUSES = {
    'case': 'the copy rewrites the letter case of printed words (caption labels)',
    'rewritten': 'the copy writes printed glyphs differently (overprint read once, accents composed, spacing)',
    'moved_locally': 'the copy writes a printed word a few words from its printed place (e.g. author markers)',
    'lost': 'printed text the copy does not carry (lost or excluded by the copier)',
    'repeat': 'the copy repeats printed text (spanning cells, front matter as printed, duplicates)',
    'copy_text': 'copy words with no printed glyphs (generated or rewritten by the copier)',
    'page_order': 'the copy puts text of one page among text of another; PCL pages are consecutive',
    'float_place': 'float blocks read after their page prose (rulebook 7.12)',
    'order': 'order within a page differs (allocation of repeated text)',
}


def compare(expected, actual, index, lines, rows, view):
    """Order-sensitive token differences, each with a measured cause.

    Positions are copy offsets (copy side) and PCL line numbers (PCL side).
    """
    a, b = [t for t, _ in expected], [t for t, _ in actual]
    fold_a, fold_b = [t.casefold() for t in a], [t.casefold() for t in b]
    matcher = difflib.SequenceMatcher(None, fold_a, fold_b, autojunk=False)
    used, kpos, owner = index['used'], index['kpos'], index['owner']
    where = {kpos[k]: owner[k] for k in range(len(used)) if used[k]}
    line_at = {c: n for n, l in enumerate(lines, 1) for c in l.get('offsets', ())}
    marks = [(m.start(), int(m[1])) for m in re.finditer(r'<!-- end of page (\d+) -->', index['body'])]
    starts = [m[0] for m in marks]

    def copy_page(offset):
        k = bisect.bisect_left(starts, offset)
        return marks[k][1] if k < len(marks) else None

    def floating(offset):
        unit = index['unit_of'][offset]
        return unit is not None and index['units'][unit]['group'] is not None

    counts_a, counts_b = collections.Counter(a), collections.Counter(b)
    result = []
    for op, a0, a1, b0, b1 in matcher.get_opcodes():
        if op == 'equal':
            # Equal ignoring case: list each token whose printed case the copy changed.
            for k in range(a1-a0):
                if a[a0+k] != b[b0+k]:
                    result.append(dict(op='replace', copy=[a[a0+k]], pcl=[b[b0+k]], copy_offset=expected[a0+k][1],
                                       pcl_lines=[actual[b0+k][1]], causes=['case'],
                                       context=' '.join(a[max(0, a0+k-6):a0+k]) + ' | ' + ' '.join(a[a0+k+1:a0+k+7])))
            continue
        copy_part, pcl_part = expected[a0:a1], actual[b0:b1]
        anchor = expected[min(a0, len(expected)-1)][1] if expected else 0
        record = dict(op=op, copy=[t for t, _ in copy_part], pcl=[t for t, _ in pcl_part],
                      copy_offset=anchor, pcl_lines=sorted({l for _, l in pcl_part}),
                      context=' '.join(a[max(0, a0-6):a0]) + ' | ' + ' '.join(a[a1:a1+6]))
        causes = set()
        rewritten = False
        if copy_part and pcl_part:
            low, high = min(o for _, o in copy_part), max(o+len(t) for t, o in copy_part)
            here = any(l.get('cfirst') is not None and l['cfirst'] < high and low <= l['clast']
                       for l in (lines[n-1] for n in record['pcl_lines']))
            similar = difflib.SequenceMatcher(None, ''.join(record['copy']).casefold(),
                                              ''.join(record['pcl']).casefold(), autojunk=False).ratio() >= .5
            rewritten = here and similar
        if rewritten:
            # The same copy characters were made from these printed glyphs.
            record['causes'] = ['rewritten']
            result.append(record)
            continue

        def carried(token, line):
            if line.get('cfirst') is None: return False
            covered = index['body'][line['cfirst']:line['clast']+1]
            return token.casefold() in {t.casefold() for t in tokens(covered)}

        def pcl_cause(token, n):
            line = lines[n-1]
            if line.get('unused') or not carried(token, line) or counts_b[token] > counts_a[token]: return 'lost'
            if line.get('displaced'): return 'page_order'
            if view == 'reading' and line['role'] in FLOAT_ROLES: return 'float_place'
            return 'order'

        def copy_cause(token, offset):
            characters = [offset+k for k in range(len(token)) if offset+k < len(index['body'])]
            if counts_a[token] > counts_b[token] or not any(c in where for c in characters):
                return 'repeat' if counts_a[token] > counts_b[token] and counts_b[token] else 'copy_text'
            held = [lines[line_at[c]-1] for c in characters if c in line_at]
            if any(l.get('displaced') for l in held): return 'page_order'
            if view == 'reading' and floating(offset): return 'float_place'
            return 'order'
        # One record per run of tokens with one cause, on each side.
        for side, part, cause_of in (('copy', copy_part, copy_cause), ('pcl', pcl_part, pcl_cause)):
            k = 0
            while k < len(part):
                cause = cause_of(*part[k]); j = k
                while j < len(part) and cause_of(*part[j]) == cause: j += 1
                piece = part[k:j]
                result.append(dict(op='delete' if side == 'copy' else 'insert',
                                   copy=[t for t, _ in piece] if side == 'copy' else [],
                                   pcl=[t for t, _ in piece] if side == 'pcl' else [],
                                   copy_offset=piece[0][1] if side == 'copy' else anchor,
                                   pcl_lines=sorted({n for _, n in piece}) if side == 'pcl' else [],
                                   context=record['context'], causes=[cause]))
                k = j
    # A word the copy writes a few words away from its printed place (author
    # markers after degrees) shows as a nearby delete/insert pair.
    for k, r in enumerate(result):
        if (r['op'] not in ('insert', 'delete') or len(r['copy'])+len(r['pcl']) > 3 or
                not set(r['causes']) <= {'order', 'copy_text', 'lost'}): continue
        mine = collections.Counter(t.casefold() for t in r['copy']+r['pcl'])
        for q in result[max(0, k-4):k+5]:
            if q is not r and q['op'] in ('insert', 'delete') and q['op'] != r['op'] and \
                    set(q['causes']) <= {'order', 'copy_text', 'lost'} and \
                    collections.Counter(t.casefold() for t in q['copy']+q['pcl']) == mine and \
                    abs((q['copy_offset'] or 0)-(r['copy_offset'] or 0)) < 300:
                r['causes'] = q['causes'] = ['moved_locally']
                break
    return dict(equal=a == b, multiset_equal=counts_a == counts_b, equal_ignoring_case=fold_a == fold_b,
                copy_words=len(a), pcl_words=len(b),
                copy_only=sum((counts_a-counts_b).values()), pcl_only=sum((counts_b-counts_a).values()),
                cause_counts=dict(collections.Counter(c for r in result for c in r['causes'])),
                cause_words=dict(collections.Counter(r['causes'][0] for r in result
                                                     for _ in range(max(len(r['copy']), len(r['pcl']))))),
                differences=result)


def write(paper_dir, pdf, sources, pages, engine=None):
    """Publish a validated sidecar; never modify copy.md or boxer evidence.

    Without the PDF, verified sources or offline validator, fail explicitly.
    A stale previous PCL is removed on failure so it cannot masquerade as the
    result of this copy. The Markdown result remains usable.
    """
    folder = Path(paper_dir)
    audit_path = folder/'copy.pcl.audit.json'
    destination = folder/'copy.pcl'
    temporary = folder/'copy.pcl.tmp'
    audit = dict(version=2, format='PCL 1.2', status='failed')
    try:
        if not pdf: raise ValueError('the source PDF is required for its digest and font evidence')
        validator_path = Path(os.environ.get('COPY_PDF_PCL_VALIDATOR') or DEFAULT_VALIDATOR)
        if not validator_path.is_file(): raise ValueError(f'offline reference validator unavailable: {validator_path}')
        validator = module('_copy_pcl_reference', validator_path)
        if engine is None:
            engine = module('_pcl_copy_engine', Path(__file__).resolve().parents[1]/'copy_paper.py')
        if sources is None: sources = snapshot(pages)
        for i, page in enumerate(sources):
            if (page.get('scan_evidence') or {}).get('ocr_layer'):
                actual = next(p for p in pages if p['page'] == page['page'])
                sources[i] = dict(page, _pcl_ocr=True, elements=[dict(r, id=f'ocr:{r["_scan_id"]}',
                    kind='text', angle=r.get('angle', 0)) for r in engine.scan_source_runs(actual)])
        text = (folder/'copy.md').read_text(encoding='utf-8')
        trace = None
        trace_path = folder/'copy.trace.json'
        if trace_path.is_file():
            candidate = json.loads(trace_path.read_text(encoding='utf-8'))
            if candidate.get('copy', {}).get('sha256') == hashlib.sha256(text.encode('utf-8')).hexdigest():
                trace = candidate
        conservation = json.loads((folder/'copy.conservation.json').read_text(encoding='utf-8'))
        catalog_path = folder/'copy.floats.json'
        catalog = json.loads(catalog_path.read_text(encoding='utf-8')) if catalog_path.is_file() else {}
        scan_path = folder/'copy.scan.json'
        scan_audit = json.loads(scan_path.read_text()) if scan_path.is_file() else {}
        lines, index, rows = build_lines(sources, pages, text, conservation, catalog,
                                         font_metadata(pdf), engine, scan_audit, trace)
        with open(pdf, 'rb') as stream: digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        encoded, spans, uncertain = serialize(lines, digest)
        document = validator.parse(encoded)
        analysis = validator.analyse(document)
        printed = validator.printed(document)
        if printed != ''.join(l['text']+'\n' for l in lines):
            raise ValueError('PCL printed view differs from the emitted source glyphs')
        # Every decoded glyph, including printed spaces, is printed exactly once.
        emitted = collections.defaultdict(list)
        for line in lines:
            if line.get('source') is not None: emitted[line['source']].append(line)
        for n, row in enumerate(rows):
            want = ''.join(a['text'] for a in row['atoms'] if not a.get('gap'))
            got = ''.join(a['text'] for s in sorted(emitted[n], key=lambda s: s['part'])
                          for a in s['atoms'] if not a.get('gap'))
            if want != got:
                raise ValueError(f'page {row["page"]}: printed glyphs of a source row changed: {want!r} -> {got!r}')
        lettering = {i for i, l in enumerate(lines, 1) if l.get('unused') and l['role'] == 'figure'}
        expected_words = copy_words(index)
        reading_words, file_words = pcl_words(analysis, lettering)
        used = index['used']
        uncovered, i = [], 0
        while i < len(used):
            if used[i]: i += 1; continue
            j = i
            while j < len(used) and not used[j]: j += 1
            start, end = index['kpos'][i], index['kpos'][j-1]+1
            uncovered.append(dict(start=start, end=end, text=index['body'][start:end]))
            i = j
        unused = [dict(page=l['page'], role=l['role'], runs=l['runs'], text=l['text'], line=i)
                  for i, l in enumerate(lines, 1) if l.get('unused')]
        audit.update(status='validated', source_sha256=digest,
                     trace=dict(used=bool(trace), copy_sha256=(trace or {}).get('copy', {}).get('sha256'),
                                lines=len((trace or {}).get('lines', [])), units=len((trace or {}).get('units', []))),
                     validator=dict(path=str(validator_path), sha256=hashlib.sha256(validator_path.read_bytes()).hexdigest()),
                     spans=spans, spans_per_kind=dict(collections.Counter(s['kind'] for s in spans)),
                     uncertain=uncertain,
                     lines=[dict(line=i, page=l['page'], role=l['role'], runs=l['runs'], text=l['text'],
                                 copy_unit=l.get('unit'), copy_span=[l.get('cfirst'), l.get('clast')],
                                 **({'wrap': l['wrap']} if l.get('wrap') else {}))
                            for i, l in enumerate(lines, 1)],
                     headings=analysis.annotations.get('headings', []),
                     printed_glyphs_exact=True,
                     copy_key_characters=len(index['key']), copy_key_allocated=sum(used),
                     copy_text_without_source=uncovered,
                     source_lines_not_in_copy=unused,
                     words_against_markdown=dict(
                         reading_view=compare(expected_words, reading_words, index, lines, rows, 'reading'),
                         file_order=compare(expected_words, file_words, index, lines, rows, 'file'),
                         figure_lettering_words=sum(len(tokens(lines[i-1]['text'])) for i in lettering),
                         causes=CAUSES,
                         scope=('Case-sensitive NFKC letter runs and digit runs. Copy: copy.md before the uncertainty '
                                'list, without the closed GENERATED label list and Markdown signs. PCL: the reading '
                                'view without derived notation markers (the copy\'s ^, [ and ] are dropped likewise), '
                                'without figure lettering the copy does not carry '
                                '(counted separately); file_order reads each line in file order, i.e. float blocks '
                                'where the copy puts them.')),
                     limitations=['Small capitals have no PCL 1.2 command.',
                                  'Publisher and outline OCR stay plain and unverified.',
                                  'Table cells remain in copy.tables.json; PCL 2.0 is an unimplemented proposal.',
                                  'Float blocks read after their page prose (rulebook 7.12); pages stay consecutive.'])
        temporary.write_text(encoded, encoding='utf-8')
        os.replace(temporary, destination)
    except Exception as exc:
        destination.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)
        audit['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        audit_path.write_text(json.dumps(audit, ensure_ascii=True, indent=1)+'\n', encoding='utf-8')
    return destination
