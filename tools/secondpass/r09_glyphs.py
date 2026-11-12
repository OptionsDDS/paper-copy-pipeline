"""Rule 9: characters whose drawn outline disagrees with the claimed character.

Each font/code pair the PDF uses for a Latin letter or for ; : ~ is measured
once from its embedded outline (tools/check_fonts.py outline_shape and the
same eight DejaVu reference silhouettes, upper and lower case, regular, bold
and italic). When a Greek letter (for a Latin claim) or a sign (for
punctuation: ∼ ± ≤ ≥ × − ° ≈ µ) matches the outline clearly better than the
claimed character (by .20, at least .55, the claim under .45) at places where
the glyph sits alone in its font (the letters beside it are in another face),
every such place is listed (an alpha shown as "a", a tilde shown as ";"), unless the
copy's uncertainty list already names that font and glyph. Private-use code
points left in the copy text (U+E000-U+F8FF, e.g. Symbol-font codes) are listed
by page unless the list mentions them.

Small faces (lane claims, rule R1): every code of a face of at most 5 used codes on
the paper, beside a body face of more, whose claim has its own reference silhouette
and whose glyph gives one character, takes the same sign decision with the Greek
letters competing (check_fonts.sign_outline_decision, small=True), with the glyph's place on
the line (its box: bottom and top in em) deciding which letters compete (check_fonts.placed).

Sign faces and quote marks in numbers (lane glyphsigns) use the copier's own
decision, check_fonts.sign_outline_decision, on every used code: a Pi, Symbol,
Math or Greek face, a symbolic built-in encoding whose glyph names are no Latin
names, or a quote mark touching a digit (the Wiley faces claim ” » ¿ „ . , for
± − × + # < >), read in the page text element as the first pass reads it (word
spaces and run ends count). A code the decision replaces or rejects is listed with its count
unless the uncertainty list already names that font and glyph (the first pass
lists every such code once per paper). A face named like a sign face whose codes form running text
(check_fonts.face_text_use / running_text, lane claims3) is no sign face by its name: a claim there is
listed only when a sign replaces it, never as a rejected claim.

Faces whose glyph names their outlines contradict (lane r3-glyphmap, check_fonts.names_contradicted: a code whose
glyph name gives a letter, ordinals included, draws a sign: a minus named /ordfeminine, an equals sign named /Omega,
a raised decimal point named /AE) are sign faces for every code, whatever the claimed character's class and whatever
touches it, as in the first pass. Every Unicode letter and ordinal is a letter claim here; a letter claim with no
reference silhouette, sitting alone in its face, is listed only when a sign of the sign set replaces it
(check_fonts.sign_outline_decision as for such a face), never as a rejected claim.
"""
import collections
import importlib.util
import json
import re
import sys
from pathlib import Path

from common import finding

NAME = 'characters'
GREEK = 'αβγδεκλμπσχω'
SIGNS = '∼±≤≥×−°≈µ'
CLAIMS = re.compile(r'[^\W\d_]|[;:~]')   # every Unicode letter (ordinals included) and ; : ~
_CF = None


def font_checks():
    global _CF
    if _CF is None:
        path = Path(__file__).resolve().parent.parent/'check_fonts.py'
        spec = importlib.util.spec_from_file_location('_secondpass_check_fonts', path)
        _CF = importlib.util.module_from_spec(spec); spec.loader.exec_module(_CF)
    return _CF


def private_use(paper):
    out = []
    pua = re.compile('[-]')
    listed = bool(re.search(r'private[- ]use|U\+F[0-9A-F]{3}', paper.notes_text, re.I))
    if listed: return out
    pages = collections.Counter(); first = {}
    for u in paper.content_units:
        hits = pua.findall(u['text'])
        if not hits: continue
        ls = paper.unit_lines(u) or [paper.lines[s['export_id']] for s in u.get('sources', []) if s.get('export_id') in paper.lines]
        pg = ls[0]['page'] if ls else None
        pages[pg] += len(hits); first.setdefault(pg, (u, hits[0]))
    for pg, n in sorted(pages.items(), key=lambda kv: (kv[0] or 0)):
        u, ch = first[pg]
        out.append(finding(9, f"page {pg}: {n} private-use code(s) such as U+{ord(ch):04X} left in the text, unflagged "
                              f"({u['text'][max(0, u['text'].find(ch)-20):u['text'].find(ch)+10]!r})",
                           page=pg, unit=u['id'], offset=u['span'][0] + u['text'].find(ch)))
    return out


def outlines(paper):
    cf = font_checks()
    refs = cf.outline_references()
    reader = None; doc = None; fonts = collections.defaultdict(list)
    measured = {}; places = collections.defaultdict(list); claims = collections.defaultdict(set); seen = collections.Counter()
    pages = []; located = {}
    for n in paper.page_numbers:
        page = paper.page(n)
        if not page: continue
        chars = cf.signs.copy.table_characters(dict(page, _table_pdf=paper.pdf))
        # the reader loads fonts page by page: refresh the map after each page
        reader = sys.modules['_copy_table_reader']; doc = reader.sc_doc(paper.pdf)
        for f in doc.fonts.values():
            if f not in fonts[f.basefont]: fonts[f.basefont].append(f)
        pages.append((n, chars)); located[n] = element_texts(cf, page, chars)
    small = small_faces(cf, pages)
    text = text_set = text_faces(cf, pages); small_keys = {}
    named = named_faces(cf, fonts, pages, text_set); unreferenced = {}
    for n, chars in pages:
        texts = located[n]
        for k, c in enumerate(chars):
            t = c.get('text', '')
            if len(t) != 1 or t.isspace() or not isinstance(c.get('source_code'), int): continue
            key = (c['font'], c['source_code'], t)
            in_small = (c['font'], c['source_code']) in small and t in refs and not cf.private_use(t) and t != '\ufffd'
            in_named = c['font'] in named and not cf.private_use(t) and t != '\ufffd'
            if in_small or in_named or sign_claim(cf, fonts, chars, k, c, t, texts.get(k)):
                claims[c['font'], c['source_code']].add(t); seen[key] += 1
                if key not in measured: measured[key] = sign_decision(cf, fonts, c, t, small=in_small,
                                                              text=c['font'] in text and bool(fonts.get(c['font']))
                                                              and cf.sign_face(fonts[c['font']][0]) == 'sign face',
                                                              named=in_named)
                if in_small: small_keys[key] = c
                m = measured[key]
                if m and m[0] in ('replaced', 'rejected'):
                    ctx = ''.join(x.get('text', '') for x in chars[max(0, k-12):k+12])
                    places[key].append((n, ctx, m[1], m[2], m[3]))
                continue
            if not CLAIMS.match(t): continue
            claims[c['font'], c['source_code']].add(t); seen[key] += 1
            # A Greek letter set from a symbol face sits alone in its face: the
            # letters beside it are in another font (a word's own letters share one).
            nb = [chars[j] for j in (k-1, k+1) if 0 <= j < len(chars) and chars[j].get('text', '').strip()]
            if any(x['font'] == c['font'] and x.get('text', '').isalpha() for x in nb): continue
            # A letter claim without a reference silhouette is decided against the sign set (lane r3-glyphmap):
            # listed only when a sign replaces it.
            if t not in refs and t.isalpha():
                if key not in unreferenced: unreferenced[key] = sign_decision(cf, fonts, c, t, named=True)
                m = unreferenced[key]
                if m and m[0] == 'replaced':
                    ctx = ''.join(x.get('text', '') for x in chars[max(0, k-12):k+12])
                    places[key].append((n, ctx, m[1], m[2], m[3]))
                continue
            if key not in measured:
                try:
                    shape = cf.outline_shape(fonts[c['font']][0], c['source_code'])
                except Exception:
                    measured[key] = None; continue
                native = max(cf.outline_similarity(shape, r) for r in refs[t]) if t in refs else None
                alts = GREEK if t.isalpha() else SIGNS
                best = max(((max(cf.outline_similarity(shape, r) for r in refs[a]), a) for a in alts if a in refs), default=(0, None))
                measured[key] = (native, best)
            m = measured[key]
            if not m or m[0] is None: continue
            native, (alt, ch) = m
            if alt >= .55 and native < .45 and alt - native >= .20:
                ctx = ''.join(x.get('text', '') for x in chars[max(0, k-12):k+12])
                places[key].append((n, ctx, ch, native, alt))
    # A small face whose outlines replace a Latin claim by a Greek letter draws Greek letters: its other
    # Latin claims are decided again with greek_face, as the first pass does (re-ladder of lane claims).
    greek_faces = {k[0] for k, m in measured.items() if k in small_keys and m and m[0] == 'replaced'
                   and cf.letter_script(k[2]) == 'latin' and cf.letter_script(m[1]) == 'greek'}
    again = {}
    for key, c in small_keys.items():
        m = measured.get(key)
        if key[0] not in greek_faces or not m or m[0] != 'confirmed' or cf.letter_script(key[2]) != 'latin': continue
        text = key[0] in text_set and bool(fonts.get(key[0])) and cf.sign_face(fonts[key[0]][0]) == 'sign face'
        m2 = sign_decision(cf, fonts, c, key[2], small=True, text=text, greek_face=True)
        if m2 and m2[0] in ('replaced', 'rejected'): again[key] = m2
    if again:
        for n, chars in pages:
            for k, c in enumerate(chars):
                key = (c.get('font'), c.get('source_code'), c.get('text', ''))
                if key in again:
                    m = again[key]; ctx = ''.join(x.get('text', '') for x in chars[max(0, k-12):k+12])
                    places[key].append((n, ctx, m[1], m[2], m[3]))
    # a code claimed as two letters is a ligature or a shared glyph: abstain
    return {k: v for k, v in places.items() if len(claims[k[0], k[1]]) == 1 and len(v) >= .5*seen[k]}


def named_faces(cf, fonts, pages, text_set):
    """Lane r3-glyphmap, as the first pass selects them: the faces (not setting running text) one of whose codes
    claims a letter its glyph name gives while its outline is a sign (check_fonts.names_contradicted)."""
    seen = set(); out = set()
    for n, chars in pages:
        for c in chars:
            t = c.get('text', ''); f = c.get('font')
            if len(t) != 1 or not t.isalpha() or not isinstance(c.get('source_code'), int) or not fonts.get(f): continue
            if f in out or f in text_set or (f, c['source_code'], t) in seen: continue
            seen.add((f, c['source_code'], t))
            if cf.names_contradicted(fonts[f][0], c['source_code'], t): out.add(f)
    return out


def small_faces(cf, pages):
    """Rule R1 (lane claims), as the first pass selects it: the (font, code) pairs of every face of at most
    check_fonts.SMALL_FACE_CODES used codes on the paper, beside a body face (most letters) of more, whose
    glyph gives one character (a ligature's characters share one box: exempt)."""
    codes = collections.defaultdict(set); letters = collections.Counter(); boxes = collections.defaultdict(list)
    for n, chars in pages:
        for c in chars:
            t = c.get('text', '')
            if not t or t.isspace() or not isinstance(c.get('source_code'), int): continue
            codes[c['font']].add(c['source_code'])
            if t.isalpha(): letters[c['font']] += 1
            boxes[c['font'], c['source_code']].append((n, tuple(c.get(k) for k in ('x0', 'y0', 'x1', 'y1'))))
    body = letters.most_common(1)[0][0] if letters else None
    if body is None or len(codes[body]) <= cf.SMALL_FACE_CODES: return set()
    return {key for key, bs in boxes.items() if key[0] != body and len(codes[key[0]]) <= cf.SMALL_FACE_CODES
            and len(set(bs)) == len(bs)}


def text_faces(cf, pages):
    """Lane claims3, as the first pass measures it: the faces whose used codes form running text
    (check_fonts.face_text_use over each page's characters in reading order; a character without text is a space)."""
    runs = []
    for n, chars in pages:
        text = []; faces = {}
        for c in chars:
            for ch in (c.get('text') or ' '):
                if c.get('font') and not ch.isspace(): faces[len(text)] = c['font']
                text.append(ch)
        runs.append((''.join(text), faces))
    return {face for face, use in cf.face_text_use(runs).items() if cf.running_text(use)}


def element_texts(cf, page, chars):
    """Character index -> (text, offset) in its page text element, as the first pass reads it.

    The character list holds no word spaces and runs on across elements, so a quote
    mark after "19 " or before a raised citation would touch a digit there; the
    element text keeps the spaces and ends where the run ends."""
    out = {}
    for e in page.get('elements', []):
        if e.get('kind') != 'text' or not e.get('text'): continue
        index = cf.indexed_run(e, chars)
        if index: out.update((cid, (e['text'], offset)) for offset, cid in index.items())
    return out


def sign_claim(cf, fonts, chars, k, c, t, located=None):
    """A sign-face glyph or a quote mark beside a digit: the first pass's own selection,
    on the element text when the character belongs to one."""
    if cf.private_use(t) or t == '\ufffd' or not fonts.get(c['font']): return False
    face = cf.sign_face(fonts[c['font']][0])
    if face == 'symbolic encoding' and t.isalnum(): face = None
    if located and located[0][located[1]] != t: located = None
    if face and t.isalpha():
        if located: inside = cf.inside_word(*located)
        else:
            text = ''.join(x.get('text', '') or ' ' for x in chars[max(0, k-12):k+13])
            inside = cf.inside_word(text, min(k, 12))
        if inside: face = None
    if face: return True
    if located: return cf.quote_in_number(*located)
    text = ''.join(x.get('text', '') or ' ' for x in chars[max(0, k-1):k+2])
    return cf.quote_in_number(text, min(k, 1))


def sign_decision(cf, fonts, c, t, small=False, text=False, greek_face=False, named=False):
    """(status, after, native, best) from check_fonts.sign_outline_decision, or None without an outline."""
    try:
        font = fonts[c['font']][0]; shape = cf.outline_shape(font, c['source_code'])
        references = cf.small_references() if small else cf.sign_references()
        scores = {ch: max(cf.outline_similarity(shape, r) for r in refs) for ch, refs in references.items()}
        geometry = None
        if shape[1] >= 4 or shape[2] >= .97 or named:   # bars, solid blocks and dots are sized by the font's bounds
            geometry = dict(bounds_em=[v/1000 for v in font.bbox(c['source_code'])], advance_em=font.width(c['source_code'])/1000)
        # a small face's glyph is also placed on the line by its box (re-ladder of lane claims)
        extent = cf.outline_extent(font.bbox(c['source_code'])) if small else None
        if greek_face: scores = cf.case_scores(shape, scores, extent)
        status, after = cf.sign_outline_decision(t, scores, shape=shape, geometry=geometry, small=small, text=text,
                                                 extent=extent, greek_face=greek_face, named=named)
    except Exception:
        return None
    return status, after, scores.get(t), max(scores.values(), default=0)


def check(paper):
    """Characters: a Latin letter claimed for a Greek or sign outline; a sign-face glyph or a
    quote mark in a number whose outline is a sign or no known character; private-use codes left in the text."""
    findings = private_use(paper)
    if not paper.pdf: return findings, dict(skipped_outlines='no PDF')
    places = outlines(paper)
    for (font, code, claim), ps in places.items():
        if re.search(re.escape(font) + r', glyph ' + str(code) + r'\b', paper.notes_text): continue
        pages = sorted({p for p, *_ in ps})
        n, ctx, ch, native, alt = ps[0]
        own = 'unmeasured' if native is None else f'{native:.2f}'
        what = (f"claimed {claim!r} but its outline is neither that nor a known sign (similarity {own}, best {alt:.2f})"
                if ch == '\ufffd' else f"claimed {claim!r} but its outline is {ch!r} (similarity {own} against {alt:.2f})")
        findings.append(finding(9, f"font {font}, glyph {code}: {what} in {len(ps)} place(s), e.g. {ctx!r}",
                                pages=pages, font=font, code=code, claimed=claim, outline=ch, places=len(ps)))
    return findings, dict(flagged_codes=len(places))
