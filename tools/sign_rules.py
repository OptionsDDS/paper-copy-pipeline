"""sign_rules.py -- rules O22 and O28 (lane r5-signs): the doubtful places of a copy's signs, outside floats.

Called by copy_paper.py once the copy and its native trace are written; it changes neither.  Its places go to
copy.doubts.json through the shared doubts.py (tree root).

O22, two readings.  Each printed line outside floats is read twice: by the program's own reader (the element boxer's
characters of the line's runs, the reading the copy is made from) and by pdftotext (poppler), a reader of separate
code.  Both readings become tokens (NFKC; dash, quote, space and bullet forms folded; spaces dropped; any unreadable
code one unread token) and are aligned.  A token one reader holds more often than the other in the line is a
difference of the readings; each stretch of the alignment holding one is listed as doubtful at its place.  A token
both hold, only at other places, is an order difference of the two line assemblies (rules O20, O21), not a reading.
A line-end hyphen held by one reader only is a line-end mark, not a sign.

O28, never silent.  A sign still unsettled in the copy (the unread mark U+FFFD that the program prints for a
character it has no reading for) is listed with its page place, its glyph (face and code) and, for a later
picture question (O27, not built in this round), the fixed list of choices.

Scope: trace lines whose units are prose units (paragraphs, headings, list items, references, front matter, notes),
not table cells, captions or figure text.  Box units: the program's page pixels (the boxer's dpi).
"""
import collections
import html
import json
import os
import re
import subprocess
import sys
import unicodedata

SCOPE_UNITS = frozenset(('paragraph', 'reference', 'heading', 'list_item', 'author', 'article_information', 'footnote',
                         'affiliation', 'abstract_part', 'title', 'front_matter_printed', 'end_matter'))
UNREAD = '�'
# units the copy files away from their page position (author details with the front matter, end matter)
MOVED_UNITS = frozenset(('author', 'affiliation', 'article_information', 'front_matter_printed', 'end_matter', 'footnote'))
NOTSURE = '\n---\n## Places the program is not sure of'
PAGE_MIN_PLACES = 30      # a page check needs at least this many places
PAGE_SHARE = 0.2          # ... covering at least this share of the page's tokens of the second reader
# O27's fixed list (Greek letters, math signs and marks); "none of these" closes it
CHOICES = (list('αβγδεζηθικλμνξοπρστυφχψωςϑϕϵ') + list('ΓΔΘΛΞΠΣΥΦΨΩ') +
           list('±∓×÷−=≠≈≡∼≃≅<>≤≥≪≫∝∞∂∇∑∏∫√∈∉⊂⊃⊆⊇∩∪∧∨¬∀∃∅→←↑↓↔⇒⇐⇔°′″‰·•∗') +
           list('\'"‘’“”«»†‡§¶‖©®™–—…✓✗■□●○▲△♀♂') + ['none of these'])
FOLD = {'‐': '-', '‑': '-', '‒': '-', '–': '-', '—': '-', '−': '-', '\u00ad': '', '‘': "'", '’': "'", '‚': "'",
        '“': '"', '”': '"', '„': '"', 'ʼ': "'", '′': "'", '″': '"', '´': "'", '`': "'", '·': '.', '•': '.',
        '∗': '*', '∼': '~', '˜': '~', 'ϕ': 'φ', 'ϵ': 'ε', 'µ': 'μ'}
WRE = re.compile(r'<word xMin="([-\d.]+)" yMin="([-\d.]+)" xMax="([-\d.]+)" yMax="([-\d.]+)">(.*?)</word>')


def fold(s):
    """the comparison form: NFKC; dash, quote, space and bullet forms folded; a soft hyphen dropped; accents dropped (a
    spacing diaeresis after its letter and a combining one are one reading, and an accent is no sign)"""
    s = unicodedata.normalize('NFKD', ''.join(FOLD.get(c, c) for c in unicodedata.normalize('NFKC', s)))
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def unreadable(c):
    o = ord(c)
    return c == UNREAD or 0xE000 <= o <= 0xF8FF or o >= 0xF0000 or o < 32 or 0x7f <= o < 0xa0


def tokens(s):
    out = []
    for ch in fold(s):
        if unicodedata.category(ch) == 'Cf' or 0x2b0 <= ord(ch) <= 0x2ff:
            continue                      # a format code prints nothing; a spacing accent is an accent, not a sign
        if unreadable(ch):
            out.append(UNREAD)
        elif ch.strip():
            out.append(ch)
    return out


def differences(a, abox, b, bbox):
    """O22: the places where two token readings of one line differ: [(box, reason)]"""
    if len(a) > 1 and len(b) > 1:
        # a line-end hyphen one reader has and the other has not (the other ends on the hyphen's left neighbour)
        if b[-1] == '-' and a[-1] != '-' and a[-1] == b[-2]:
            b, bbox = b[:-1], bbox[:-1]
        elif a[-1] == '-' and b[-1] != '-' and b[-1] == a[-2]:
            a, abox = a[:-1], abox[:-1]
    ra = collections.Counter(a) - collections.Counter(b)
    rb = collections.Counter(b) - collections.Counter(a)
    if not ra and not rb:
        return []
    import difflib
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag == 'equal':
            continue
        if not any(t in ra for t in a[i1:i2]) and not any(t in rb for t in b[j1:j2]):
            continue
        bx = abox[i1:i2] or bbox[j1:j2]
        box = [min(q[0] for q in bx), min(q[1] for q in bx), max(q[2] for q in bx), max(q[3] for q in bx)]
        out.append((box, {'replace': 'readers_differ', 'delete': 'second_reader_none',
                          'insert': 'program_reader_none'}[tag], (i1, i2, j1, j2)))
    return out


def joined(toks):
    return ''.join(toks)


def unmark(s):
    """the copy's Markdown marks (emphasis, escapes, headings, quotes) are no reading of the page"""
    return re.sub(r'[*_`\\#>]', '', s)


def poppler_words(pdf):
    try:
        out = subprocess.run(['pdftotext', '-bbox', pdf, '-'], capture_output=True, text=True, errors='replace',
                             timeout=300).stdout
    except Exception:  # noqa: BLE001
        return None
    res = {}
    for k, pg in enumerate(out.split('<page ')[1:], 1):
        res[k] = [(float(a), float(b), float(c), float(d), html.unescape(t)) for a, b, c, d, t in WRE.findall(pg)]
    return res


def run(paper_dir, pages, pdf, table_characters, doubts):
    """add the O22 and O28 places of the written copy to the doubt list"""
    try:
        with open(os.path.join(paper_dir, 'copy.trace.json'), encoding='utf-8') as f:
            trace = json.load(f)
        with open(os.path.join(paper_dir, 'copy.md'), encoding='utf-8') as f:
            text = f.read()
    except (OSError, ValueError):
        return
    starts = [0] + [m.end() for m in re.finditer('\n', text)]
    import bisect
    units = {u['id']: u for u in trace.get('units', [])}
    media = {p['page']: p['media_box_pdf_points'] for p in trace.get('pdf', {}).get('pages', [])}
    bypage = {p['page']: p for p in pages}
    tlines = collections.defaultdict(list)
    for l in trace.get('lines', []):
        if l.get('box_pdf_points') and l.get('page') in media:
            tlines[l['page']].append(l)

    def copy_lines(l):
        """the copy lines of a trace line's prose units (a byline is printed in the authors list and as front matter)"""
        out = []
        for u in l.get('units') or []:
            unit = units.get(u.get('unit_id'))
            if unit and unit.get('kind') in SCOPE_UNITS and u.get('copy_span'):
                n = bisect.bisect_right(starts, u['copy_span'][0])
                if n not in out:
                    out.append(n)
        return out

    words = poppler_words(pdf) if pdf else None
    o22 = collections.defaultdict(list)
    page_tokens = collections.Counter()
    not_compared = set()
    body_end = text.find(NOTSURE)
    body_end = body_end if body_end >= 0 else len(text)
    tok_cache = {}

    def copy_tokens(n):
        """the copy's tokens joined: of copy line n, or of the whole copy above the list of unsure places (None)"""
        if n not in tok_cache:
            if n is None:
                tok_cache[n] = unmark(joined(tokens(text[:body_end])))
            else:
                z = starts[n] if n < len(starts) else len(text)
                tok_cache[n] = unmark(joined(tokens(text[starts[n - 1]:min(z, body_end)])))
        return tok_cache[n]
    o28 = collections.defaultdict(list)
    seen = set()
    for pg in sorted(tlines):
        p = bypage.get(pg)
        if p is None or (p.get('scan_evidence') or {}).get('ocr_layer'):
            continue
        k = (p.get('params') or {}).get('dpi', 150) / 72.0
        mb = media[pg]
        els = {e['id']: e for e in p.get('elements', [])}
        chars = table_characters(p)
        ls = []
        for l in tlines[pg]:
            a, b, c, d = l['box_pdf_points']
            ls.append((l, (a - mb[0], mb[3] - d, c - mb[0], mb[3] - b)))
        # poppler reads hidden text layers too (an unpainted link or OCR layer); the program's reader knows them: a
        # word over the program's hidden characters is no reading of the printed page
        # the page's offset from poppler's points to the program's pixels, from the lines' own boxes (median)
        dxs, dys = [], []
        for l, bb in ls:
            rb = [els[r]['box_px'] for r in l.get('runs') or [] if r in els and els[r].get('box_px')]
            if rb:
                dxs.append(min(q[0] for q in rb) / k - bb[0])
                dys.append(min(q[1] for q in rb) / k - bb[1])
        dx = sorted(dxs)[len(dxs) // 2] if dxs else 0.0
        dy = sorted(dys)[len(dys) // 2] if dys else 0.0
        hid = []
        reader = sys.modules.get('_copy_table_reader')
        if reader is not None and pdf:
            try:
                hid = [((c['x0'] + c['x1']) / 2 / k - dx, (c['y0'] + c['y1']) / 2 / k - dy) for c in reader.sc_read_page(pdf, pg)[0] if c.get('hidden')]
            except Exception:  # noqa: BLE001
                hid = []
        # the band each line's own characters occupy (points), where it has characters: a word is read with a line
        # only where it stands in that band, so the words of a row that no line holds (a row the copy files elsewhere,
        # a row of a smaller type between) are never given to a neighbour
        band = {}
        for i, (l, bb) in enumerate(ls):
            cb = [chars[j] for r in l.get('runs') or [] if r in els
                  for j in els[r].get('char_ids') or [] if 0 <= j < len(chars) and chars[j].get('text', '').strip()]
            if cb:
                band[i] = (min(c['y0'] for c in cb) / k - dy, max(c['y1'] for c in cb) / k - dy,
                           min(c['x0'] for c in cb) / k - dx, max(c['x1'] for c in cb) / k - dx,
                           [((c['x0'] + c['x1']) / 2 / k - dx, (c['y0'] + c['y1']) / 2 / k - dy, c.get('text', '')) for c in cb])
        # each poppler word to every line whose own characters it covers, else to the nearest line it lies across
        wl = collections.defaultdict(list)
        # poppler reads hidden layers too: a word over hidden characters is a reading of the printed page only if the
        # printed characters under it spell it; then a word drawn twice at nearly one place is one reading
        pw = []
        for w in (words or {}).get(pg, []):
            if hid and any(w[0] <= x <= w[2] and w[1] <= y <= w[3] for x, y in hid):
                under = sorted((x, t) for bd_ in band.values() for x, y, t in bd_[4] if w[0] <= x <= w[2] and w[1] <= y <= w[3])
                if tokens(''.join(t for _, t in under)) != tokens(w[4]):
                    continue
            if any(v[4] == w[4] and abs((v[0] + v[2]) - (w[0] + w[2])) / 2 < 3 and abs((v[1] + v[3]) - (w[1] + w[3])) / 2 < 3
                   for v in pw):
                continue
            pw.append(w)
        hs = sorted(w[3] - w[1] for w in pw)
        wh = hs[len(hs) // 2] if hs else 10.0
        for w in pw:
            cx, cy = (w[0] + w[2]) / 2, (w[1] + w[3]) / 2
            best, bd, holders = None, None, []
            wt = set(tokens(w[4]))
            for i, (l, bb) in enumerate(ls):
                h = max(1.0, bb[3] - bb[1])
                x0, x1 = (min(bb[0], band[i][2]), max(bb[2], band[i][3])) if i in band else (bb[0], bb[2])
                if x0 - 1 <= cx <= x1 + 1:   # across the line's box or its own characters, whichever is wider
                    if i in band:
                        y0, y1 = band[i][:2]
                        if min(w[3], y1) - max(w[1], y0) < 0.5 * min(w[3] - w[1], y1 - y0):
                            continue
                    dd = abs(cy - (bb[1] + bb[3]) / 2)
                    # the line's own characters under the word that are characters of the word
                    ov = sum(w[0] <= x <= w[2] and w[1] <= y <= w[3] and bool(set(tokens(t)) & wt) for x, y, t in band[i][4]) \
                        if i in band else 0
                    if ov:
                        holders.append(i)   # a line printed twice in the trace holds the same characters
                    if dd <= 0.85 * h and (bd is None or dd < bd):
                        best, bd = i, dd
            if not holders and w[3] - w[1] > 2.5 * wh:
                continue   # a word far taller than the page's words that no line's characters hold (a drop cap the
                #            program sets apart) is set across lines, not in the nearest one
            for i in holders or ([best] if best is not None else []):
                wl[i].append(w)
        for i, (l, bb) in enumerate(ls):
            ns = copy_lines(l)
            if not ns:
                continue
            cs = []      # (character record, its final text in the run)
            certain = True   # the program's first reading of the line is had: every run's characters match its text
            for r in l.get('runs') or []:
                e = els.get(r)
                if not e or e.get('kind') != 'text':
                    continue
                allids = e.get('char_ids') or []
                ids = [j for j in allids if 0 <= j < len(chars)]
                fin = [ch for ch in e.get('text', '') if ch.strip()]
                rec = [chars[j] for j in ids if chars[j].get('text', '').strip()]
                eb = e.get('box_px') or [0, 0, 0, 0]
                inside = sum(eb[0] - 3 <= (c['x0'] + c['x1']) / 2 <= eb[2] + 3 and eb[1] - 3 <= (c['y0'] + c['y1']) / 2 <= eb[3] + 3
                             for c in rec)
                if len(ids) != len(allids) or inside < 0.8 * len(rec):
                    certain = False   # the run's character records are not where the run is printed: not its reading
                for q, c in enumerate(rec):
                    cs.append((c, fin[q] if len(fin) == len(rec) else c.get('text', '')))
            # the records, in run order, must spell the line much as the trace recorded it (a sign check changes a few
            # characters; a foreign set of records shares little with it)
            said = [ch for ch in (l.get('text') or '') if ch.strip()]
            got = [ch for c, _ in cs for ch in c.get('text', '') if ch.strip()]
            if said and got:
                import difflib
                if difflib.SequenceMatcher(None, said, got, autojunk=False).ratio() < 0.5:
                    certain = False
            cs.sort(key=lambda x: x[0]['x0'])
            # O28: every unread mark of the line's runs, with its glyph
            for c, t in cs:
                for n in ns:
                    if t != UNREAD or (id(c), n) in seen:
                        continue
                    seen.add((id(c), n))
                    face = re.sub(r'^[A-Z]{6}\+', '', str(c.get('font') or 'unknown'))
                    o28[n].append((pg, [c['x0'], c['y0'], c['x1'], c['y1']], 'unread_sign:%s:%s' % (face, c.get('source_code'))))
            if words is None:
                continue
            # O22: the program's reading against poppler's
            lbox = [(bb[0] + dx) * k, (bb[1] + dy) * k, (bb[2] + dx) * k, (bb[3] + dy) * k]
            a, abox, kept = [], [], []
            for c, _ in cs:
                # a character drawn twice at nearly one place (a doubled layer) is one reading, as on the second side
                if any(v['text'] == c['text'] and abs((v['x0'] + v['x1']) - (c['x0'] + c['x1'])) / 2 < 0.3 * (c['x1'] - c['x0']) and
                       abs((v['y0'] + v['y1']) - (c['y0'] + c['y1'])) / 2 < 0.3 * (c['y1'] - c['y0']) for v in kept[-12:]):
                    continue
                kept.append(c)
                for t in tokens(c['text']):
                    a.append(t)
                    abox.append((c['x0'], c['y0'], c['x1'], c['y1']))
            b, bbox = [], []
            for w in sorted(wl.get(i, []), key=lambda w: w[0]):
                box = ((w[0] + dx) * k, (w[1] + dy) * k, (w[2] + dx) * k, (w[3] + dy) * k)
                for t in tokens(w[4]):
                    b.append(t)
                    bbox.append(box)
            page_tokens[pg] += len(b)
            if not b:
                continue
            if not a or not certain:
                # the first reading of the line cannot be had: one entry for the line, never one per word
                if (pg, ns[0]) not in not_compared:
                    not_compared.add((pg, ns[0]))
                    o22[pg].append((lbox, 'not_compared:no_first_reading', ns[0], len(b)))
                continue
            places = differences(a, abox, b, bbox)
            span = max(len(a), len(b))
            covered = sum(max(i2 - i1, j2 - j1) for _, _, (i1, i2, j1, j2) in places)
            if span >= 8 and covered >= 0.5 * span:
                # the readings share less than half the line: not two readings of one line (a doubled or moved layer,
                # a line assembled elsewhere); one entry for the line
                if (pg, ns[0]) not in not_compared:
                    not_compared.add((pg, ns[0]))
                    o22[pg].append((lbox, 'not_compared:readings_apart', ns[0], covered))
                continue
            moved = any((units.get(u.get('unit_id')) or {}).get('kind') in MOVED_UNITS for u in l.get('units') or [])
            for box, why, (i1, i2, j1, j2) in places:
                if why == 'program_reader_none':
                    # output check: the program lacks the token only if the copy does not print it there (the copy
                    # line, with its neighbours; for a unit the copy files elsewhere, anywhere in the copy)
                    # a word-long stretch is looked for alone (a doubled word has a twin for neighbour); a sign with
                    # its neighbours
                    probe = unmark(joined(b[j1:j2] if j2 - j1 >= 3 else b[max(0, j1 - 1):j2 + 1]))
                    if probe and (any(probe in copy_tokens(m) for m in ns) or (moved and probe in copy_tokens(None))):
                        continue
                o22[pg].append((box, why, ns[0], max(i2 - i1, j2 - j1)))
    # output check on the listing: a page where the places cover a large share of the page's words is a reading failure
    # of the listing, not of the paper: the page is listed once, as not compared
    for pg in sorted(o22):
        entries = o22[pg]
        covered = sum(e[3] for e in entries)
        if len(entries) >= PAGE_MIN_PLACES and covered >= PAGE_SHARE * max(1, page_tokens[pg]):
            mb = media[pg]
            k = (bypage[pg].get('params') or {}).get('dpi', 150) / 72.0
            doubts.add('O22', pg, [0, 0, (mb[2] - mb[0]) * k, (mb[3] - mb[1]) * k], 'not_compared:page', line=entries[0][2])
            continue
        for box, why, n, _ in entries:
            doubts.add('O22', pg, box, why, line=n)
    # O28: as many places per copy line as the copy prints unread marks there (a mark another rule settled later is
    # not printed, so not listed)
    for n, cands in o28.items():
        a = starts[n - 1]
        z = starts[n] if n < len(starts) else len(text)
        for pg, box, why in cands[:text[a:z].count(UNREAD)]:
            doubts.add('O28', pg, box, why, options=CHOICES, line=n)
