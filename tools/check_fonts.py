#!/usr/bin/env python3
"""Verify suspect text-layer glyph claims against 300-dpi page rasters.

An additional embedded-outline pass screens every used, supported font/code,
including URL/DOI/e-mail characters and duplicate letter/digit claims. It
compares 32-pixel silhouettes with precomputed versions of the same eight
DejaVu references, without rasterizing pages or calling OCR. Measurements
are cached per font/code and shared only for identical silhouettes. A native
score below .40, alternative >=.80, native margin >=.30 and runner-up margin
>=.10 are required for replacement. Weaker separated mismatches (alternative
>=.72 and margin >=.20) retain the text and receive a page/run/glyph notice,
except digit claims contradicted by a non-digit outline: these become U+FFFD.
Digit claims always compete with the other reference shapes. A separated
plus-minus match (>=.70, margin >=.18) with two wide bars and a central
crossing stem also rejects a digit, even above the ordinary .40 native floor.
This weaker structural evidence flags U+FFFD; it never guesses a replacement.
A uniquely matched prime uses the same strong replacement thresholds as other signs.
An independently verified non-digit reading takes precedence over this weaker
rejection; discarded digit readings cannot be restored by earlier OCR.
Number-unit prefixes l/m/u also receive a warning when the mu/micro-sign family scores
>=.60, beats the native claim by .20 and all other shapes by .10. This weaker evidence
never substitutes text. Ordinary words and honest unit prefixes remain unchanged.
Letter claims drawing one solid midline bar use the embedded bounds and
advance in em units to distinguish en/em dashes; ordinary letter outlines,
short strokes, low underscores and intermediate lengths abstain. Baseline and
length evidence survives the copy handoff and is revalidated with the silhouette.
Symbol-font arrows may instead use a straight central shaft and two symmetric,
converging wings, with a direction-template score >=.45 and native margin >=.20.
Arrow-like symbol claims that fail the structural or template check are flagged
even below the generic mismatch threshold. Weak native similarity alone does
not flag punctuation: thin but honest hashes must not acquire spurious warnings. CMSY/CMEX faces participate in this outline pass. These structural
checks do not infer a reading from surrounding words or numbers.
Absent/ambiguous outlines and unsupported claims abstain. Lookalikes compete
separately, so a tilde versus a mathematical wave may safely remain flagged.
Source codes and character IDs are revalidated when applying both prose and
table edits. Saved native text is unchanged. fonts-ocr.json records coverage,
timing, scores, silhouettes and every affected place.

The verification pass selects every non-space glyph in a named sign/Pi face,
or numbers, short alphabetic tokens and operators in a face used for less than
3% of the page. Latin letters touching chemical punctuation, digits or a
statistical operator are selected regardless of font share. Inspect full runs
as well as font spans, so surrounding parentheses and exponents are visible.
Unicode operators, currencies, dashes, fractions and typographic signs are
also selected whenever their font differs from the paper's most-used text font or
they touch a number or unit. Selection never determines a glyph's reading.
Random subset prefixes are not font names. Full subset names and source codes
remain distinct; all assigned occurrences of a selected font/code are measured.

Render isolated glyphs at 300 dpi with two pixels of white margin, excluding
neighbours. A separate process uses the existing Pillow raster backend (the
reader installs its own PIL shim). Compare DejaVu Sans/Serif regular, bold and
italic templates using centred 32-pixel silhouettes and nine translations.
The score is binary correlation * (0.5 + 0.25*aspect_match + 0.25*ink_match).
Integer bit masks preserve the original set-intersection metric; identical
crops may share measurements, never font/code decisions.

For Latin claims, also compare α β γ δ ε κ λ μ π σ χ ω and common signs;
marker faces additionally compare ‖ ¶ † ‡ § *. Claimed signs compete with
± ≤ ≥ × ‖ − · ′ ° ∼ ≈ ≠ → ← ↑ ↓ ∞ ∑ √ ∫ and the older OCR signs.
A single alternative must score at least 0.60 (0.55 for sign claims/marker
faces) and beat the native claim by 0.20 on EVERY measurable occurrence.
Separated evidence overrides native confirmation. A sign correction to
±/≤/≥/× needs a 0.30 margin and independent stroke geometry on every crop;
a marker needs a 0.25 margin, a sign face, separation of 0.10 from every other
template and matching strokes (or similarity >=0.70). Otherwise use accepted
independent OCR or emit U+FFFD. Simple solid sign strokes are not mistaken for
reversed figure backgrounds. Correct signs with no separated competitor keep
their original reading; newly selected signs never fail by the old floor alone.
Two-part punctuation (; : ! ?) is selected like a sign only when it is set in
another face than the body text AND touches a number or unit (a sign face's
text layer may claim ';' for a tilde before a number). It competes with the
sign templates, but is rejected only when every crop contradicts the claim's
own structure: not exactly two separate ink parts and a claim score below
0.35. The drawn sign is then named only when the stroke check finds exactly
that one sign on every crop and it is also the best template, beating the
claim by 0.20; otherwise the glyph becomes U+FFFD. A tilde's stroke check is
one flat wave above the baseline with a crest left of a trough and both ends
turned back; a named tilde is written as the ASCII '~' (its shape cannot tell
the operator from the ASCII tilde, and '~' also keeps a URL valid).
Spacing accents beside letters retain the native accent when only a competing
template disagrees. Two wide horizontal stroke bands veto a simpler +/−/</>/dot
competitor for a claimed ±/=/≤/≥/≠, including plus/minus designs whose lower bar touches the stem.
Other Latin-to-common-sign rejections and replacements inside alphabetic words
remain diagnostic only unless a marker is decisively named. Small asterisk
styles still need independent OCR: their silhouettes overlap dots. The copy
formatter classifies headings, equations and hyphens
after replacement, so these edits can change order or delete a real hyphen.
The previous decision policy still applies to those cases; deferred_alternative
records the rejected claim and why the new edit was withheld. Contradictory
occurrences veto a font-wide alternative. Scores, minimum margins and isolated
crops remain for calibration. Above native similarity 0.80, the score's upper
bound of 1 proves that no alternative can clear the 0.20 margin.

Without separated alternative evidence, the original calibration policy stays:
one occurrence at 0.35 (0.45 for '5') confirms its font/code. A newly selected
context-only letter cannot be rejected by that old floor alone. In the original
population, a/b/c/d/e/l/p/v/* need agreeing OCR after failure; U+FFFD inside an
alphabetic word remains diagnostic only because it can change table layout.
Mixed claims, absent raw codes, overlaps, empty crops and coloured/reversed
backgrounds abstain. Unknown evidence is never a confirmation.

A raised ring mapped as U+25E6 between a number and C/F is occurrence-flagged
as U+FFFD: compare its box with the adjacent unit, not its superscript baseline.
This prevents a temperature mark from being consumed as a list bullet. The
copy hook revalidates context, geometry, character IDs and source code before
updating both prose and private table characters. Original JSON text is never
edited. fonts.verification, font_subs and fonts-ocr.json retain all decisions;
small font-evidence crops remain, but full-page scratch rasters do not.

The two older OCR passes remain available as independent replacement evidence:

Keep subset font names distinct. Sample at most twelve runs per font, balanced
across suspect characters and pages. Each character gets one vote per run;
three agreeing runs and >=70% of ALL sampled runs containing that character
(including unreadable crops) are required. Native-letter readings count against
a substitution. No dictionary, font-name or paper-specific guesses are used.

For the older run-OCR pass only, eligible contexts are standalone tokens, numeric punctuation,
statistical operators, or an exact unit prefix. Ordinary words are never edited.
OCR glyph boxes must overlap native boxes and have unchanged nearby anchors
(or be the sole native and OCR glyph in a standalone run);
character confidence must be >=90. Equality strokes and comparison underlines
also have a raster veto. Original text stays intact; font_subs records every proposed edit, by offset and
character ID. The copy hook validates the evidence and updates both runs and
its private table characters. Every applied font/character pair is flagged.
Older page JSON is supported by verifying IDs against the PDF before adding
font metadata. Failed/misaligned OCR is abstention, never evidence of a sign.

A second, independent pass tests individual suspect occurrences with psm 10.
Its only symbol whitelist is µ≤≥°*±×®−<>=; a second OCR call permits only the
claimed native character. A symbol needs confidence >=75 and a margin >=15
over the native reading, plus matching raster geometry. An empty OCR result
has zero confidence (recorded as empty, not invented OCR evidence); execution
errors never qualify. Both empty results always abstain. Contiguous alphabetic
tokens of three or more letters are protected, including their end letters.

Each crop is the reader's own glyph box at 300 dpi plus two pixels. Rendering
a page once and slicing on integer pixel boundaries shares only raster work;
neighbour boxes are whitened, and overlapping glyph boxes cause abstention.
Raster vetoes run first to avoid expensive OCR on ordinary digits/letters.
Identical isolated bitmaps may share OCR, never decisions or font mappings.
Those occurrence edits carry both readings/confidences and raster evidence in font_subs;
the copy hook checks them and reports the paper's lowest accepted margin.

The unmapped-glyph pass also uses comparison_decision: a matching chevron
with a separate lower stroke upgrades OCR < or > to ≤ or ≥. Ambiguous or
contradictory geometry abstains; this helper never trusts the native code.

Private-use text codes (Unicode category Co) are decided once per font,
source code and claim. A code in U+F020-U+F0FF (or one of the Adobe Glyph
List's private Symbol values) in a font marked as a Symbol font by its name,
its PDF encoding or its embedded glyph name is read through the Adobe Symbol
encoding (Unicode's published table: Greek letters, not the U+2206/U+2126/
U+00B5 compatibility signs). The existing outline decision then checks that
reading against the embedded outline, using the outline references plus
Symbol-only DejaVu references (symbol_shapes.json.gz, which compete in no
other decision): confirmed readings are applied and counted in one copy
line; weak or unchecked readings are applied and listed; a contradicting
glyph name, a separated competing outline, an unmarked font or a code without
a Symbol reading gives U+FFFD, listed. No competitor is guessed as a reading.
These decisions replace earlier raster/OCR decisions at the same occurrence
(kept under "previous"). The copy's guard then shows any private-use code
still left as U+FFFD, so none reaches a copy (AH07: SymbolGreek β, Δ, α,
γ, μ, τ). Rebuild the Symbol references with --build-symbol-shapes.

Sign faces and quote marks in numbers (lane glyphsigns): every used code of a
Pi, Symbol, Math or Greek face, of a symbolic built-in encoding whose glyph
names are no Latin names, and every quote or inverted mark claimed beside a
digit in any face, is decided from its embedded outline alone, once per
font/code, regardless of the claimed character (the Wiley WPi-One,
WTimesGreekSF and MathematicalPi-One faces claim ” » ¿ „ . , for ± − × + # < >).
Stroke geometry comes first (a plus over a bar, two bars, a chevron over a
straight or slanted stroke, a plus, a cross, a bar at the math axis), then the
reference silhouettes: a sign of ± − + × # ≤ ≥ < > ° μ α β κ ′ = • ® © whose
own silhouette scores >=.55, .20 above the claim's own silhouette and .10 above
every other lookalike family is printed (a lookalike's score never prints the
family's sign); a claim inside the winning family keeps its character; a claim
no sign replaces is kept only when its own silhouette scores >=.45, else a text
claim (ASCII, a quote mark, or another Latin 8-bit encoding character) is shown
as U+FFFD and a claimed sign or symbol is left as claimed. A claimed double
quotation mark drawn as two comma or apostrophe marks side by side (at least as
wide as tall) is a real quotation mark and kept, whatever digit stands beside it. These decisions displace the raster/OCR decisions at the
same places (kept under "previous") and are listed once per paper with their
count. The second pass (rule 9) applies the same decision and lists any code
the copy's list does not name.

Usage: /usr/bin/python3 -I tools/check_fonts.py PAPER_DIR PAPER.pdf
       /usr/bin/python3 -I tools/check_fonts.py --build-symbol-shapes
The same check also runs from read_signs.py, hence from copy_pdf.sh.
"""
import argparse
import collections
import functools
import gzip
import hashlib
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('_font_signs', ROOT / 'tools/read_signs.py')
signs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signs)
SUSPECTS = frozenset('mM45o1nsblRE')
SIGNS = frozenset('µ≤≥<>=°*®±×−βλ∑∈')
MODEL = 'tesseract-300dpi-psm7-font-v1'
SYMBOL_MODEL = 'tesseract-300dpi-psm10-symbol-v1'
SYMBOL_WHITELIST = 'µ≤≥°*±×®−<>='
VERIFY_MODEL = 'dejavu-300dpi-ncc-v6'
POSITION_MODEL = 'elevated-temperature-ring-v1'
SIGN_FONT = re.compile(r'Pi|Symbol|Math|AdvP4C4E|AdvPi|AdvMPi|MT-Extra|Universal|Wingdings|Dingbat|Special', re.I)
VERIFY_WHITELIST = SYMBOL_WHITELIST+'+'
# N-set calibration: 5 needs a higher floor because two bars share its top
# and bottom. These floors separate the measured digit/sign errors. The
# following classes overlap correct small caps, italic p/v or asterisk styles;
# shape failure alone is not evidence for replacing those classes.
VERIFY_THRESHOLD = .35
VERIFY_THRESHOLDS = {'5': .45}
OVERLAPPING_CLASSES = frozenset('abcdelpv*')
ALTERNATIVES = 'αβγδεκλμπσχω'+VERIFY_WHITELIST
ALTERNATIVE_FLOOR = .60
ALTERNATIVE_MARGIN = .20
SIGN_ALTERNATIVES = '±≤≥×‖−·′°∼≈≠→←↑↓∞∑√∫'+VERIFY_WHITELIST+'¶†‡§'
MARKERS = '‖¶†‡§*'
# Two-part punctuation: each drawn as exactly two separate ink parts. A sign
# face's text layer can claim one of these for a sign (J Periodontol 2008:
# a tilde claimed as ';' before a number, AG04). Single-part punctuation
# (period, comma, apostrophes) is not selected: its silhouette overlaps the
# dot and prime templates, so a shape score cannot separate it.
PUNCTUATION_SIGNS = ';:!?'
SIGN_FLOOR = .55
SHAPE_FLOOR = .55
SHAPE_MARGIN = .30
OUTLINE_MODEL = 'embedded-outline-v1'
PRIVATE_MODEL = 'symbol-encoding-outline-v1'
# A face named Symbol (Symbol, SymbolMT, SymbolGreek ...). Pi, math and
# dingbat faces use other layouts: their private-use codes are not Symbol codes.
SYMBOL_FACE = re.compile(r'Symbol', re.I)
# The Adobe Symbol encoding, codes 0x21-0xFF, as Unicode publishes it
# (MAPPINGS/VENDORS/ADOBE/symbol.txt): Greek letters rather than the
# compatibility signs U+2206/U+2126/U+00B5, plain ® © ™ for the serif and sans
# forms and U+23xx for the bracket, brace and integral pieces. NUL marks a code
# without a Unicode reading (radicalex stays private in that table; unused codes).
# tools/test_symbolpua.py checks it against the reader's Symbol glyph names.
SYMBOL_ENCODING = {code: ch for start, row in (
    (0x21, '!∀#∃%&∋()∗+,−./0123456789:;<=>?'),
    (0x40, '≅ΑΒΧΔΕΦΓΗΙϑΚΛΜΝΟ'
           'ΠΘΡΣΤΥςΩΞΨΖ[∴]⊥_'),
    (0x60, '\x00αβχδεφγηιϕκλμνο'
           'πθρστυϖωξψζ{|}∼\x00'),
    (0xa0, '€ϒ′≤⁄∞ƒ♣♦♥♠↔←↑→↓'
           '\xb0\xb1″≥\xd7∝∂•\xf7≠≡≈…⏐⎯↵'),
    (0xc0, 'ℵℑℜ℘⊗⊕∅∩∪⊃⊇⊄⊂⊆∈∉'
           '∠∇\xae\xa9™∏√⋅\xac∧∨⇔⇐⇑⇒⇓'),
    (0xe0, '◊〈\xae\xa9™∑⎛⎜⎝⎡⎢⎣⎧⎨⎩⎪'
           '\x00〉∫⌠⎮⌡⎞⎟⎠⎤⎥⎦⎫⎬⎭\x00'),
) for code, ch in enumerate(row, start) if ch != '\x00'}
# The Adobe Glyph List gives some Symbol glyph names Adobe's own private-use
# values (a reader decoding /parenlefttp emits U+F8EB). Their Symbol codes:
ADOBE_SYMBOL_PRIVATE = {0xF8E5: 0x60, 0xF8E6: 0xBD, 0xF8E7: 0xBE, 0xF6D9: 0xD3, 0xF6DA: 0xD2, 0xF6DB: 0xD4,
                        0xF8E8: 0xE2, 0xF8E9: 0xE3, 0xF8EA: 0xE4, 0xF8F5: 0xF4,
                        **{0xF8EB+i: 0xE6+i for i in range(10)}, **{0xF8F6+i: 0xF6+i for i in range(9)}}
SYMBOL_SHAPES = 'symbol_shapes.json.gz'


@functools.lru_cache(maxsize=1)
def outline_references():
    """Precomputed versions of the raster verifier's eight DejaVu references.

    Runtime needs only the standard library and the reader's vendored font
    parser. A 32-pixel silhouette is independent of page size and resolution.
    """
    with gzip.open(Path(__file__).with_name('glyph_shapes.json.gz'), 'rt') as stream:
        data = json.load(stream)['shapes']
    result = {ch: [(int(mask, 16), aspect, ink) for mask, aspect, ink in rows]
              for ch, rows in data.items()}
    # Small caps are typography, not wrong Unicode. Plain stems are also
    # legitimate designs of one, lowercase ell and uppercase eye. Shape alone
    # cannot distinguish their semantic identities, even in an address.
    original = result.copy()
    for ch in result:
        if ch.isascii() and ch.isalpha(): result[ch] = original[ch]+original.get(ch.swapcase(), [])
    stems = [shape for ch in '1Il|' for shape in result[ch] if shape[1] < .4 and shape[2] > .8]
    stems += result['/']  # plain slanted stems in italic one/ell/eye designs
    for ch in '1Il|': result[ch] += stems
    return {ch: list(dict.fromkeys(shapes)) for ch, shapes in result.items()}


def outline_shape(font, code):
    """Rasterize the selected embedded outline, never its claimed glyph name.

    Curves are flattened in font units, then filled with the nonzero winding
    rule at 32 scanlines. Composite and quadratic outlines use the reader's
    vendored BasePen. Missing programs, .notdef and open contours abstain.
    """
    from fontTools.pens.basePen import BasePen
    p = font.prog
    if p is None or not isinstance(code, int) or code < 0:
        raise ValueError('no embedded outline')
    if font.cid:
        if p.kind == 'truetype':
            gid = code if font.cid2gid is None else (int.from_bytes(font.cid2gid[2*code:2*code+2], 'big')
                                                    if 2*code+1 < len(font.cid2gid) else 0)
        else:
            gid = (code if p.kind == 'cidcff' and getattr(p.top, 'ROS', None) is None else
                   p.names.get('cid%05d' % code, code if p.kind != 'cidcff' else 0))
    else: gid = font.gmap.get(code)
    if gid is None or not 0 < gid < len(p.order): raise ValueError('missing selected glyph')
    if p.kind == 'truetype':
        if not hasattr(p, '_outline_glyphs'):
            # PDF subsets sometimes omit unused hmtx entries. getGlyphSet()
            # asks for complete advance metrics, which silhouettes do not need.
            # Draw glyf directly, including transformed composite components.
            glyf = p.tt['glyf']
            class Glyph:
                def __init__(self, name): self.name = name
                def draw(self, pen): glyf[self.name].draw(pen, glyf)
            class Glyphs(dict):
                def __missing__(self, name):
                    if name not in glyf: raise KeyError(name)
                    self[name] = result = Glyph(name)
                    return result
            p._outline_glyphs = Glyphs()
        glyphs = p._outline_glyphs
    else: glyphs = p.glyphs

    class Pen(BasePen):
        skipMissingComponents = False
        def __init__(self):
            super().__init__(glyphs); self.contours = []; self.points = []
        def _moveTo(self, point): self.points = [point]
        def _lineTo(self, point): self.points.append(point)
        def _curveToOne(self, a, b, c):
            start = self.points[-1]
            for i in range(1, 13):
                t = i/12; u = 1-t
                self.points.append(tuple(u**3*start[k]+3*u*u*t*a[k]+3*u*t*t*b[k]+t**3*c[k] for k in (0, 1)))
        def _qCurveToOne(self, a, b):
            start = self.points[-1]
            for i in range(1, 11):
                t = i/10; u = 1-t
                self.points.append(tuple(u*u*start[k]+2*u*t*a[k]+t*t*b[k] for k in (0, 1)))
        def _closePath(self):
            if self.points: self.contours.append(self.points)
            self.points = []
        def _endPath(self): raise ValueError('open glyph contour')
    pen = Pen(); glyphs[p.order[gid]].draw(pen)
    points = [q for contour in pen.contours for q in contour]
    if not points: raise ValueError('empty outline')
    xs, ys = zip(*points); x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = x1-x0, y1-y0
    if min(w, h) <= 0: raise ValueError('empty outline bounds')
    edges = [(a, b) for contour in pen.contours for a, b in zip(contour, contour[1:]+contour[:1])]
    mask = 0
    for row in range(32):
        y = y1-(row+.5)*h/32
        crossings = sorted((a[0]+(y-a[1])*(b[0]-a[0])/(b[1]-a[1]), 1 if b[1] > a[1] else -1)
                           for a, b in edges if min(a[1], b[1]) <= y < max(a[1], b[1]))
        winding = 0; left = None
        for x, direction in crossings:
            if winding and left is not None:
                start = max(0, math.ceil((left-x0)*32/w-.5))
                stop = min(32, math.ceil((x-x0)*32/w-.5))
                if stop > start: mask |= ((1 << (stop-start))-1) << ((row+4)*40+start+4)
            winding += direction; left = x
    if not mask: raise ValueError('empty outline silhouette')
    return mask, w/h, mask.bit_count()/1024


def outline_similarity(shape, reference):
    """The existing correlation/aspect/ink metric, on resolution-free outlines."""
    points, aspect, ink = shape; other, ratio, share = reference
    a, b, n = points.bit_count(), other.bit_count(), 1600
    denominator = math.sqrt(a*b*(1-a/n)*(1-b/n))
    if not denominator: return 0.0
    correlation = max(((points & (other << shift if shift >= 0 else other >> -shift)).bit_count()-a*b/n)/denominator
                      for shift in (-41,-40,-39,-1,0,1,39,40,41))
    return correlation*(.5+.25*min(aspect/ratio, ratio/aspect)+.25*min(ink/share, share/ink))


ADDRESS = re.compile(r'(?:[a-z][a-z0-9+.-]*://|www\.|10\.\d{4,9}/)[^\s<>"“”]+'
                     r'|[\w.!#$%&\x27*+/=?^`{|}~-]+@[\w.-]+\.[A-Za-z]{2,}', re.I)


def address_offsets(text):
    return {i for match in ADDRESS.finditer(text) for i in range(*match.span())}


def unit_prefix_offsets(text):
    """Select l/m/u before an exact unit after a number, never inside a word.

    Context only requests a shape check. Millimetres and other honest Latin
    prefixes retain their own outlines; the unit itself supplies no reading.
    """
    return {m.start(1) for m in re.finditer(
        r'(?<![\w.])\d+(?:[.,]\d+)?\s*([lmu])(?:[lgmLsM]|mol|Hz|Pa)(?![A-Za-z])', text)}


def outline_plus_minus(shape):
    """Two straight bars and a central cross, independent of the claimed code.

    The normalized silhouette must have exactly a plus and a separate lower
    bar. A serif digit's foot alone cannot supply the upper crossing stroke.
    Accept both measured tuples and the serialized outline used by copy QA.
    Joined design (lane claims2): the plus's stem may run down onto the lower
    bar, one connected shape (Computer Modern CMSY10 glyph 6 on AQ24, checked
    on a 1200 dpi render: hairline strokes, the stem meets the bar). The lower
    bar is then the full rows at the foot; everything above it must be the
    same plus (crossbar band, stem in the centre columns down to the bar).
    """
    if not isinstance(shape, (tuple, list)) or len(shape) != 3: return False
    try:
        mask = int(shape[0], 16) if isinstance(shape[0], str) else shape[0]
        if not isinstance(mask, int) or not 0 < mask < (1 << 1600): return False
        if not .45 < shape[1] < 1.5: return False
        ink = {(x,y) for y in range(32) for x in range(32) if mask >> ((y+4)*40+x+4) & 1}
        groups = components(ink)
        if len(groups) == 2:
            upper, lower = sorted(groups, key=lambda g:min(y for x,y in g))
        elif len(groups) == 1:
            full = {y for y in range(32) if sum((x,y) in ink for x in range(32)) >= 29}
            if 31 not in full: return False
            foot = 31
            while foot-1 in full: foot -= 1
            lower = {(x,y) for x,y in ink if y >= foot}; upper = ink-lower
            # the stem must reach the bar: the row just above the foot holds stem ink only
            if not any((x,foot-1) in upper for x in range(32)): return False
        else: return False
        if not upper or not lower: return False
        bottom = min(y for x,y in lower)
        if bottom < 25 or max(y for x,y in lower)-bottom > 6: return False
        if any(sum((x,y) in lower for x in range(32)) < 29 for y in range(bottom,32)): return False
        bands = [y for y in range(bottom) if sum((x,y) in upper for x in range(32)) >= 29]
        if not bands or not 5 <= min(bands) <= max(bands) <= 20: return False
        if bands != list(range(min(bands),max(bands)+1)) or len(bands)>6: return False
        stem = {(x,y) for x,y in upper if y not in bands}
        return (bool(stem) and all(11 <= x <= 20 for x,y in stem) and
                all(any((x,y) in stem for x in range(11,21))
                    for y in range(max(y for x,y in upper)+1) if y not in bands) and
                max(y for x,y in upper) >= max(bands)+5)
    except (TypeError, ValueError): return False


def outline_ink(shape):
    """Validate a saved silhouette before using its stroke geometry."""
    if not isinstance(shape, (tuple, list)) or len(shape) != 3: return set()
    try:
        mask = int(shape[0], 16) if isinstance(shape[0], str) else shape[0]
        if not isinstance(mask, int) or not 0 < mask < (1 << 1600): return set()
        if not all(isinstance(v, (int, float)) and math.isfinite(v) and v > 0 for v in shape[1:]): return set()
        ink = {(x, y) for y in range(32) for x in range(32) if mask >> ((y+4)*40+x+4) & 1}
        if abs(len(ink)/1024-shape[2]) > .001: return set()
        return ink
    except (TypeError, ValueError): return set()


def outline_dash(shape, geometry):
    """A solid mid-em bar, with its length retained in font units.

    Tight silhouettes alone lose baseline and length: underscore, minus and
    dash all become rectangles. Require a midline bar, narrow thickness,
    nearly full advance width, and a half/three-quarter or full-em advance.
    Short hyphens, low underscores and ambiguous lengths abstain. This rule
    is used only for letter claims, never to relabel existing punctuation.
    """
    ink = outline_ink(shape)
    if len(ink) < 1000 or not isinstance(geometry, dict): return None
    try:
        left, top, right, bottom = geometry['bounds_em']; advance = geometry['advance_em']
        if not all(isinstance(v, (int, float)) and math.isfinite(v)
                   for v in (left, top, right, bottom, advance)): return None
        width, height = right-left, top-bottom
        if not (.02 <= height <= .12 and .20 <= (top+bottom)/2 <= .40 and
                0 <= left <= .12 and .8*advance <= width <= advance and
                5 <= width/height and abs(width/height-shape[1]) <= .05*shape[1]): return None
        if .48 <= advance <= .78: return '–'
        if .90 <= advance <= 1.10: return '—'
    except (KeyError, TypeError, ValueError, ZeroDivisionError): pass
    return None


def outline_arrow(shape):
    """Prove a straight shaft and two symmetric, converging arrowhead wings.

    Work in the outline's own frame, testing all four directions. The long
    centre stem must reach the tip. Wings occupy just one end, widen on both
    sides, then converge monotonically. Crosses, quotes, hashes, daggers and
    double-headed arrows fail these independent topology checks.
    """
    ink = outline_ink(shape)
    if not ink: return None
    found = []
    for direction in '↓↑→←':
        if direction in '↓↑' and not .2 <= shape[1] <= .85: continue
        if direction in '→←' and not .2 <= 1/shape[1] <= .85: continue
        points = {(x,y) if direction == '↓' else (x,31-y) if direction == '↑'
                  else (y,x) if direction == '→' else (y,31-x) for x,y in ink}
        rows = [{x for x,y in points if y == row} for row in range(32)]
        if any(not row or not row.intersection(range(14,18)) for row in rows): continue
        wings = [y for y,row in enumerate(rows) if min(row)<11 or max(row)>20]
        if not wings or not 17 <= min(wings) <= 25 or max(wings)>29: continue
        start = min(wings)
        if any(min(row)<12 or max(row)>19 or max(row)-min(row)>7 for row in rows[:start]): continue
        if any(abs(min(row)+max(row)-31)>2 for row in rows): continue
        if min(rows[start])>2 or max(rows[start])<29: continue
        if len(wings)<4 or wings != list(range(start,max(wings)+1)): continue
        if any(min(rows[y+1])<min(rows[y])-1 or max(rows[y+1])>max(rows[y])+1
               for y in range(start,31)): continue
        # Thin, open wings and filled triangular heads are both supported;
        # no stray ink or second cross is permitted in the shaft.
        if any(len(row) != max(row)-min(row)+1 for row in rows[:start]): continue
        if max(rows[-1])-min(rows[-1])>7: continue
        found.append(direction)
    return found[0] if len(found) == 1 else None


# --- Sign faces and sign claims (lane glyphsigns) ----------------------------------
# A text layer can claim a quote mark, a Latin letter or a punctuation mark for a
# glyph whose outline is a sign: the Wiley WPi-One, WTimesGreekSF and
# MathematicalPi-One faces of J Clin Periodontol 2001 and Periodontology 2000
# papers claim ” » ¿ „ . , for ± − × + # < > (AL04, AM09, AM01). Every used code
# of a sign face (named as one, or a symbolic built-in encoding whose glyph names
# are no Latin letter, digit or ASCII names), and every quote-mark claim touching
# a digit in any face, is decided from its embedded outline alone: stroke geometry
# first (a plus over a bar, two bars, a chevron over a bar, a plus, a cross, a bar
# at the math axis), then the reference silhouettes. A sign at the established
# thresholds is printed; a claim whose own silhouette is not confirmed is shown as
# U+FFFD and listed once per paper with its count, never printed as the claimed
# quote mark or letter. Silhouette lookalikes form families: the first member is
# the sign printed for a sign-face glyph, and a claim inside the family keeps its
# own character (a period in a Pi face stays a period, a cross claimed 'x' stays).
SIGN_FACE = re.compile(r'Pi(?![a-z])|Symbol|Math|Greek|MT-?Extra|Universal|Wingdings|Dingbat|Special|AdvP4C4E', re.I)
SIGN_SET = '±−+×#≤≥<>°μαβκ′=•®©'
SIGN_FAMILIES = ('×xXχΧ', '−-_–—‐', 'μµ', "′'`’‘´,", '°º', '•.·⋅∙', '∼~˜', '<‹', '>›', '"“”„‚', '‖∥', '*⁎∗')
QUOTE_CLAIMS = '"\'‚„‹›«»“”‘’¿¡`´¨˜ˆ'
QUOTE_PAIR_CLAIMS = '"“”„'   # double quotation marks: confirmed by two comma-or-apostrophe strokes side by side
SIGN_TEMPLATE_FLOOR = .55     # r09_glyphs and SIGN_FLOOR: a sign silhouette at least this close,
SIGN_NATIVE_MARGIN = .20      # this far above the claim's own silhouette,
SIGN_RUNNER_MARGIN = .10      # and above every other family
SIGN_STRUCTURE_FLOOR = .40    # a sign proven by its strokes needs only this much silhouette support
SIGN_CLAIM_FLOOR = .45        # a claim below this (r09's native floor) is rejected when no sign is found
SIGN_EXTRA_REFERENCES = '®©'  # Symbol-only references that also compete in sign-face decisions
# Small faces (lane claims, rule R1). A face using at most SMALL_FACE_CODES distinct codes on the paper is
# a sign or Greek face whatever its name, encoding or glyph names say (AP24 AdvPS586B: Differences,
# ToUnicode and glyph names all say comma and period for '<' and '>'; AP01 AdvPSMP13 'c' for gamma).
# DIAGNOSIS-AP E1, 7,440 used font/code pairs on 24 papers, 34 wrong claims: in faces of <= 5 used codes
# (64 of 238 font instances) a claim floor of .45 (SIGN_CLAIM_FLOOR) catches 29 of 34 and flags 0
# legitimate codes (at .50: 33 of 34, 2 legitimate flagged); in all faces no floor works (a legitimate
# asterisk scores .084). Every code of such a face is decided by sign_outline_decision among the sign
# set and the Greek letters: a winner at the sign thresholds is printed, a claim measured under the floor
# with no winner is shown as U+FFFD and listed with font, code, count, pages and score.
SMALL_FACE_CODES = 5
SMALL_FACE_GREEK = 'αβγδεκλμπσχω'   # the Greek letters among the outline references
# Running text (lane claims3). The SIGN_FACE name is only a prior: a commercial Latin text face can carry
# "Symbol" (or Math, Pi ...) in its family name and set running words, reference numbers and page numbers;
# its digits, of another design, score under SIGN_CLAIM_FLOOR against the reference silhouettes and no
# sign beats them. A face named like a sign face is a sign face only when its used codes do not form
# running text: it sets at least TEXT_USE_LETTERS distinct Latin letters inside words of at least
# TEXT_USE_WORD letters set wholly in that face, or at least TEXT_USE_DIGITS distinct digits inside numbers
# of at least two digits set wholly in that face. Evidence (lane claims3, out-claims3/sim and g1_faces.txt:
# the measure as verify_outlines computes it, on 86 copies of AL, AM, AN, AP, AQ and the six gate papers):
# the 92 name-selected face instances (49 papers) that are real sign faces (AdvPi, AdvMPi, AdvMathPi,
# AdvP4C4E, MathematicalPi, Universal-GreekwithMathPi, WPi, WTimesGreekSF, ZapfDingbats, Wingdings, Symbol,
# SymbolMT, Latmath, STIX math faces setting signs) set at most 1 distinct letter in such words and no such
# number; the 93rd, AQ20 STIXMath-Regular, is a math face setting words (24 distinct letters, 2 digits; no
# outline record either way). Unnamed faces of at least 100 glyphs: 387 of 403 pass (the 16 others are
# ligature, space and dash faces, unnamed sign faces and a Greek face claimed as Latin letters). Treating
# every face of those papers as named like a sign face shows the fault: 7,068 places shown as U+FFFD
# against 239 (93 faces newly flagged); with this measure 245 (the 2 faces left are dash/space faces).
# In a running-text face the sign decision may still replace a claim a sign clearly beats; a claim it
# would reject goes to the ordinary outline decision, as in every text face (the copy before glyphsigns).
TEXT_USE_WORD = 3
TEXT_USE_LETTERS = 4
TEXT_USE_DIGITS = 4
# Place on the line (re-ladder of lane claims). A silhouette is normalized to the glyph's own box, so it
# loses where the glyph sits on the line: an italic chi (descends below the baseline) scores as an 'x'
# (AdvPS7DA6: x .78, chi .69), a tau (stops at the x-height) as a 'T' merged into the 't' claim (.71).
# Each reference character therefore also carries its vertical place in em (bottom and top of its outline
# relative to the baseline), measured from the outlines of the eight DejaVu faces and of the italic and
# math-italic faces of other designs (EXTENT_FACES; a Latin letter takes its other case too, as its
# silhouettes do). In a small face (rule R1) a Latin or Greek letter competes only when the glyph's own
# outline box (the font's bbox for the code) lies within that range widened by EXTENT_TOLERANCE on both
# ends (.08 em: the glyph's design may lie outside the 17 faces, whose x-heights already differ by .11 em;
# at .05 an italic capital P of a face with .59 em capitals lost its own letter) (signs, arrows, digits and punctuation are placed where each design puts them and are not tested);
# a letter claim the glyph's place contradicts, with no placed character to replace it, is shown as U+FFFD;
# a sign or Greek claim under the floor is flagged only by a placed rival that itself reaches the floor
# (AS10: a correct PazoMath-Italic gamma scores .34, best .38 against 75 system faces including math
# italics; the '7' that beat it scored .435, under the floor). In a small face a Latin and a Greek letter
# are different families (small_family): x and chi share the sign family of the multiplication cross.
# A digit is placed too (as a rival only; a digit claim keeps its own score: old-style figures descend).
# A small face whose outlines replace one Latin claim by a Greek letter draws Greek letters (greek_face):
# there a Latin claim scores only by the silhouettes of the case whose place the glyph takes (case_scores),
# and one that a placed Greek letter beats by SIGN_RUNNER_MARGIN at SIGN_TEMPLATE_FLOOR, but not by the
# replacement margins, is shown as U+FFFD (a tau in a design whose x-height reaches the t's range).
# Elsewhere it stands: a single-storey italic 'a' or an italic 'v' scores closer to alpha or upsilon than
# to the DejaVu a and v (C059 and URW Bookman italics, measured).
EXTENT_TOLERANCE = .08
EXTENT_SHAPES = 'glyph_extents.json.gz'
EXTENT_FACES = ('truetype/dejavu/DejaVuSans.ttf', 'truetype/dejavu/DejaVuSans-Bold.ttf',
                'truetype/dejavu/DejaVuSans-Oblique.ttf', 'truetype/dejavu/DejaVuSans-BoldOblique.ttf',
                'truetype/dejavu/DejaVuSerif.ttf', 'truetype/dejavu/DejaVuSerif-Bold.ttf',
                'truetype/dejavu/DejaVuSerif-Italic.ttf', 'truetype/dejavu/DejaVuSerif-BoldItalic.ttf',
                'truetype/noto/NotoSerif-Italic.ttf', 'truetype/noto/NotoSans-Italic.ttf',
                'truetype/liberation/LiberationSerif-Italic.ttf', 'truetype/liberation/LiberationSans-Italic.ttf',
                'opentype/urw-base35/NimbusRoman-Italic.otf', 'opentype/urw-base35/NimbusSans-Italic.otf',
                'opentype/urw-base35/C059-Italic.otf', 'opentype/urw-base35/P052-Italic.otf',
                'truetype/noto/NotoSansMath-Regular.ttf')
# Lowercase Greek letters the outline references lack (AdvPS7DA6 claims 't' for tau): silhouettes from the
# same eight DejaVu faces and renderer as glyph_shapes.json.gz; they compete only in small-face decisions.
EXTRA_GREEK = 'ζηθινξορτυφψς'
SQUARE_SIDE_FLOOR = 1/3       # a solid block this many em on each side is a black square, not a dot


@functools.lru_cache(maxsize=1)
def sign_references():
    """The outline references plus ® and © (Pi faces claim 'A' and 'C' for them)."""
    result = dict(outline_references()); extra = symbol_references()
    for ch in SIGN_EXTRA_REFERENCES:
        if ch in extra: result.setdefault(ch, extra[ch])
    return result


def math_italic(ch):
    """The Mathematical Italic code point of a Latin or lowercase Greek letter (NotoSansMath sets its
    italic math letters there), else the character itself."""
    if 'a' <= ch <= 'z': return '\u210e' if ch == 'h' else chr(0x1D44E+ord(ch)-ord('a'))
    if 'A' <= ch <= 'Z': return chr(0x1D434+ord(ch)-ord('A'))
    greek = 'αβγδεζηθικλμνξοπρςστυφχψω'
    return chr(0x1D6FC+greek.index(ch)) if ch in greek else ch


def build_glyph_extents(path=None, root=Path('/usr/share/fonts')):
    """Precompute the place on the line of every reference character, and the EXTRA_GREEK silhouettes.

    Extents: (lowest bottom, highest bottom, lowest top, highest top) in em, over the outlines of
    EXTENT_FACES that cover the character (NotoSansMath: its math-italic letters), each character by itself
    (placed takes a Latin letter's other case as its own alternative, as outline_references merges the two
    cases' silhouettes). Silhouettes: check_fonts.reference_shapes, as glyph_shapes.json.gz. Needs Pillow and the
    reader's vendored fontTools: /usr/bin/python3 -I tools/check_fonts.py --build-glyph-extents
    """
    sys.path.insert(0, str(ROOT/'standalone/vendor'))
    from fontTools.ttLib import TTFont
    from fontTools.pens.boundsPen import BoundsPen
    faces = []
    for name in EXTENT_FACES:
        font = TTFont(str(root/name)); faces.append((name, font.getGlyphSet(), font.getBestCmap(), font['head'].unitsPerEm))
    def own(ch):
        rows = []
        for name, glyphs, cmap, upm in faces:
            code = ord(math_italic(ch)) if 'Math' in name else ord(ch)
            if code not in cmap: continue
            pen = BoundsPen(glyphs); glyphs[cmap[code]].draw(pen)
            if pen.bounds is None: continue
            rows.append((pen.bounds[1]/upm, pen.bounds[3]/upm))
        return rows
    base = outline_references(); extents = {}
    for ch in sorted(set(base) | set(EXTRA_GREEK)):
        rows = own(ch)
        if rows:
            extents[ch] = [round(min(b for b, t in rows), 4), round(max(b for b, t in rows), 4),
                           round(min(t for b, t in rows), 4), round(max(t for b, t in rows), 4)]
    shapes = {ch: [[hex(mask), round(aspect, 6), round(ink, 6)] for face, (mask, aspect, ink) in reference_shapes(ch, 48)]
              for ch in EXTRA_GREEK}
    data = dict(description='Place on the line of each outline reference character: [lowest bottom, highest '
                'bottom, lowest top, highest top] in em over the outlines of check_fonts.EXTENT_FACES (DejaVu Sans '
                'and Serif regular/bold/italic, Noto, Liberation, Nimbus, C059 and P052 italics, NotoSansMath '
                'math italic), each character by itself. Shapes: 32-pixel silhouettes of the '
                'EXTRA_GREEK letters from the eight DejaVu faces (check_fonts.reference_shapes at 48 pixels). '
                'Produced by check_fonts.build_glyph_extents; used only in small-face decisions.',
                faces=list(EXTENT_FACES), extents=extents, shapes=shapes)
    with gzip.open(path or Path(__file__).with_name(EXTENT_SHAPES), 'wt') as stream:
        json.dump(data, stream, ensure_ascii=True, sort_keys=True)
    return len(extents), len(shapes)


@functools.lru_cache(maxsize=1)
def glyph_extents():
    """(extents, extra silhouettes) from EXTENT_SHAPES; a missing file gives neither (no extent test)."""
    try:
        with gzip.open(Path(__file__).with_name(EXTENT_SHAPES), 'rt') as stream: data = json.load(stream)
    except (OSError, ValueError): return {}, {}
    return ({ch: tuple(v) for ch, v in data.get('extents', {}).items()},
            {ch: [(int(mask, 16), aspect, ink) for mask, aspect, ink in rows] for ch, rows in data.get('shapes', {}).items()})


@functools.lru_cache(maxsize=1)
def small_references():
    """The sign references plus the EXTRA_GREEK silhouettes: what competes in a small-face decision."""
    result = dict(sign_references())
    for ch, rows in glyph_extents()[1].items(): result.setdefault(ch, rows)
    return result


def outline_extent(bounds):
    """(bottom, top) in em from a font bbox in 1/1000 em (left, top, right, bottom), or None when unusable."""
    try:
        left, top, right, bottom = (float(v)/1000 for v in bounds)
    except (TypeError, ValueError): return None
    if not all(math.isfinite(v) for v in (top, bottom)) or not -1 < bottom < top < 2: return None
    return round(bottom, 4), round(top, 4)


def placed_exactly(ch, extent):
    """The glyph's place on the line (bottom, top in em) is one this very letter or digit takes: within
    its reference range widened by EXTENT_TOLERANCE. Only Latin and Greek letters and the digits 0-9 are
    tested: their zones (baseline, x-height, ascender or figure height, descender) hold across designs,
    while signs, arrows and punctuation sit where each design puts them (cm-super's arrows reach .09 em
    lower than DejaVu's). A digit is tested only as a rival (sign_outline_decision keeps a non-letter
    claim's own family: old-style figures descend). Any other character, a character without a measured
    range, and a glyph without a usable box give no evidence (True)."""
    rng = glyph_extents()[0].get(ch)
    tested = (ch.isalpha() and letter_script(ch) != 'other') or (len(ch) == 1 and ch in '0123456789')
    if rng is None or extent is None or not tested: return True
    bottom, top = extent
    return (rng[0]-EXTENT_TOLERANCE <= bottom <= rng[1]+EXTENT_TOLERANCE and
            rng[2]-EXTENT_TOLERANCE <= top <= rng[3]+EXTENT_TOLERANCE)


def placed(ch, extent):
    """placed_exactly, a Latin letter's other case counting as the letter (small capitals: the claim's
    silhouettes hold both cases, outline_references)."""
    if placed_exactly(ch, extent): return True
    return ch.isascii() and ch.isalpha() and placed_exactly(ch.swapcase(), extent)


@functools.lru_cache(maxsize=1)
def case_references():
    """The Latin letters' silhouettes per case (glyph_shapes.json.gz before outline_references merges
    the cases), the plain stems kept with I and l as outline_references adds them."""
    with gzip.open(Path(__file__).with_name('glyph_shapes.json.gz'), 'rt') as stream:
        data = json.load(stream)['shapes']
    merged = outline_references()
    result = {ch: [(int(mask, 16), aspect, ink) for mask, aspect, ink in rows]
              for ch, rows in data.items() if ch.isascii() and ch.isalpha()}
    for ch in 'Il': result[ch] = merged[ch]
    return result


def case_scores(shape, scores, extent):
    """Greek-face scores with a place: a Latin letter scores by the silhouettes of each of its cases whose
    place the glyph takes (a tau at the x-height no longer scores as the capital T merged into 't').
    Other characters keep their scores. Used only in a small face that draws Greek letters (greek_face):
    elsewhere small capitals keep both cases' silhouettes."""
    if extent is None: return scores
    cases = case_references(); result = dict(scores)
    for ch in scores:
        if not (ch.isascii() and ch.isalpha()) or ch not in cases: continue
        own = [v for v in (ch, ch.swapcase()) if v in cases and placed_exactly(v, extent)]
        if own: result[ch] = max(outline_similarity(shape, r) for v in own for r in cases[v])
    return result


def letter_script(ch):
    name = unicodedata.name(ch, '') if len(ch) == 1 else ''
    return 'latin' if 'LATIN' in name else 'greek' if 'GREEK' in name or name == 'MICRO SIGN' else 'other'


def small_family(ch):
    """A sign family split by script: in a small face a Latin letter and a Greek letter are different
    claims, whatever their silhouettes share (x and chi; the sign family keeps them together for signs)."""
    script = letter_script(ch)
    return ''.join(c for c in sign_family(ch) if letter_script(c) == script) or ch


def latin_glyph_name(name):
    """A glyph name that denotes a Latin letter, a digit or an ASCII character."""
    if not name or name == '.notdef': return False
    if len(name) == 1 and name.isascii() and name.isalnum(): return True
    reader = sys.modules.get('_copy_table_reader')
    u = reader.sc_uni(name) if reader else ''
    if len(u) != 1: return False
    return (u.isascii() and u.isalnum()) or 'LATIN' in unicodedata.name(u, '')


def sign_face(font):
    """Why a font is a sign face: its name, or a symbolic built-in encoding whose
    embedded glyph names are no Latin names (WTimesGreekSF-Two: plusminus, pi,
    integral, ordfeminine, Omega, questiondown name ± > + ± − = × outlines)."""
    if SIGN_FACE.search(re.sub(r'^[A-Z]{6}\+', '', font.basefont)): return 'sign face'
    p = getattr(font, 'prog', None)
    if (getattr(font, 'base', None) == 'builtin' and p is not None and getattr(p, 'kind', None) != 'truetype'
            and not getattr(font, 'cid', False)):
        names = [n for n in getattr(p, 'order', []) if n != '.notdef']
        if names and not any(latin_glyph_name(n) for n in names): return 'symbolic encoding'
    return None


def face_text_use(runs):
    """Per face, (distinct Latin letters inside words of at least TEXT_USE_WORD letters set wholly in the
    face, distinct digits inside numbers of at least two digits set wholly in the face). runs: (text, faces)
    pairs, faces mapping a text offset to its face (offsets without a glyph map to nothing)."""
    letters = collections.defaultdict(set); digits = collections.defaultdict(set)
    for text, faces in runs:
        for m in re.finditer(r'[^\W\d_]{%d,}|[0-9]{2,}' % TEXT_USE_WORD, text):
            used = {faces.get(i) for i in range(m.start(), m.end())}
            if len(used) != 1 or None in used: continue
            face = used.pop(); token = m.group()
            if token[0].isdigit(): digits[face].update(token)
            elif all('LATIN' in unicodedata.name(ch, '') for ch in token): letters[face].update(token)
    return {face: (len(letters[face]), len(digits[face])) for face in set(letters) | set(digits)}


def running_text(use):
    """A face whose used codes form running text (face_text_use): never a sign face by its name alone."""
    return bool(use) and (use[0] >= TEXT_USE_LETTERS or use[1] >= TEXT_USE_DIGITS)


def quote_in_number(text, offset):
    """A quote or inverted mark claimed next to a digit ("25”4", "»26", "4¿", "„0.25")."""
    ch = text[offset]
    if ch not in QUOTE_CLAIMS and unicodedata.category(ch) not in ('Pi', 'Pf'): return False
    return bool(offset and text[offset-1].isdigit() or offset+1 < len(text) and text[offset+1].isdigit())


def sign_family(ch):
    return next((f for f in SIGN_FAMILIES if ch in f), ch)


def text_claim(ch):
    """A character a text layer claims by code for an ordinary glyph: ASCII, a quote
    or inverted mark, or any other non-symbol character of the Latin 8-bit text
    encoding (a letter, a currency sign, a fraction, a dagger: what a symbol face's
    codes read as through a Latin encoding vector). Rule R2 rejects these when the
    outline contradicts them; a claimed sign, symbol or Greek letter that no sign
    replaces is left as claimed."""
    if ch.isascii() or unicodedata.category(ch) in ('Pi', 'Pf') or ch in '„‚¿¡': return True
    if unicodedata.category(ch) in ('Sm', 'So'): return False
    try: ch.encode('cp1252')
    except UnicodeEncodeError: return False
    return True


def outline_bar_component(group):
    """A thin, wide horizontal bar: at most 7 rows, at least 24 columns, every row nearly full."""
    ys = {y for x, y in group}; xs = {x for x, y in group}
    if not group or len(ys) > 7 or len(xs) < 24: return False
    return all(sum((x, y) in group for x in range(32)) >= len(xs)-2 for y in ys)


def outline_component_shape(group, shape):
    """One connected component renormalized to its own 32-pixel silhouette."""
    xs = [x for x, y in group]; ys = [y for x, y in group]
    x0, x1, y0, y1 = min(xs), max(xs)+1, min(ys), max(ys)+1
    w, h = x1-x0, y1-y0
    mask = 0
    for ty in range(32):
        sy = y0+int((ty+.5)*h/32)
        for tx in range(32):
            if (x0+int((tx+.5)*w/32), sy) in group: mask |= 1 << ((ty+4)*40+tx+4)
    return mask, shape[1]*w/h, mask.bit_count()/1024


def outline_plus(shape):
    """One horizontal and one vertical bar crossing near the centre, nothing else (a plus)."""
    ink = outline_ink(shape)
    if not ink or not .6 <= shape[1] <= 1.6 or len(components(ink)) != 1: return False
    rows = [y for y in range(32) if sum((x, y) in ink for x in range(32)) >= 29]
    cols = [x for x in range(32) if sum((x, y) in ink for y in range(32)) >= 29]
    if not rows or not cols or len(rows) > 9 or len(cols) > 9: return False
    if rows != list(range(rows[0], rows[-1]+1)) or cols != list(range(cols[0], cols[-1]+1)): return False
    if not 9 <= (rows[0]+rows[-1])/2 <= 22 or not 9 <= (cols[0]+cols[-1])/2 <= 22: return False
    return all(y in rows or x in cols for x, y in ink)


def outline_cross(shape):
    """Two straight diagonals crossing at the centre, nothing else (a multiplication cross)."""
    ink = outline_ink(shape)
    if not ink or not .6 <= shape[1] <= 1.6 or len(components(ink)) != 1: return False
    if not all(min(abs(x-y), abs(x+y-31)) <= 5 for x, y in ink): return False
    return all(any((x, y) in ink and abs(x-y) <= 3 for x in range(32)) and
               any((x, y) in ink and abs(x+y-31) <= 3 for x in range(32)) for y in range(32))


def outline_equals(shape):
    """Two separate horizontal bars, one above the other, nothing else."""
    ink = outline_ink(shape)
    if not ink or shape[1] < 1.2: return False
    groups = components(ink)
    if len(groups) != 2 or not all(outline_bar_component(g) for g in groups): return False
    upper, lower = sorted(groups, key=lambda g: min(y for x, y in g))
    return max(y for x, y in upper) < min(y for x, y in lower)


def outline_stroke_component(group):
    """A thin straight or slanted line spanning at least 24 columns: in every
    column its ink is one run at most 7 pixels tall (a bar under ≤, ≥ or ⩽, ⩾)."""
    columns = collections.defaultdict(list)
    for x, y in group: columns[x].append(y)
    if len(columns) < 24: return False
    return all(max(ys)-min(ys)+1 == len(ys) <= 7 for ys in columns.values())


def outline_comparison(shape, references):
    """A chevron over a separate straight or slanted stroke: ≤ or ≥, by the chevron's own silhouette."""
    ink = outline_ink(shape)
    if not ink or not .6 <= shape[1] <= 1.8: return None
    groups = components(ink)
    if len(groups) != 2: return None
    upper, lower = sorted(groups, key=lambda g: sum(y for x, y in g)/len(g))
    if not outline_stroke_component(lower) or len(upper) < 2*len(lower)/3: return None
    top = collections.defaultdict(list); bottom = collections.defaultdict(list)
    for x, y in upper: top[x].append(y)
    for x, y in lower: bottom[x].append(y)
    if any(max(top[x]) >= min(bottom[x]) for x in top if x in bottom): return None
    chevron = outline_component_shape(upper, shape)
    scores = {ch: max(outline_similarity(chevron, r) for r in references[ch]) for ch in '<>' if ch in references}
    if len(scores) != 2: return None
    best = max(scores, key=scores.get)
    if scores[best] >= SIGN_TEMPLATE_FLOOR and scores[best]-min(scores.values()) >= SIGN_RUNNER_MARGIN:
        return '≤' if best == '<' else '≥'
    return None


def outline_turned(shape):
    """The same silhouette turned half a circle (an opening quote is a comma upside down)."""
    mask = 0
    for x, y in outline_ink(shape): mask |= 1 << ((35-y)*40+35-x)
    return mask, shape[1], shape[2]


def outline_quote_pair(shape, references):
    """Two separate marks side by side, alike in size and height, each a comma or an
    apostrophe by its own silhouette, upright or turned: a double quotation mark of
    any face (the references hold only the straight double quote). The pair is at
    least as wide as it is tall: two tall bars side by side are a parallel sign."""
    ink = outline_ink(shape)
    if not ink or shape[1] < 1: return False
    groups = components(ink)
    if len(groups) != 2: return False
    left, right = sorted(groups, key=lambda g: min(x for x, y in g))
    if max(x for x, y in left) >= min(x for x, y in right): return False
    tops = [min(y for x, y in g) for g in (left, right)]; bottoms = [max(y for x, y in g) for g in (left, right)]
    if min(bottoms)-max(tops)+1 < .5*min(b-t+1 for t, b in zip(tops, bottoms)): return False
    if min(len(left), len(right)) < .5*max(len(left), len(right)): return False
    singles = [r for ch in sign_family("'") if ch in references for r in references[ch]]
    if not singles: return False
    for group in (left, right):
        part = outline_component_shape(group, shape)
        if max(outline_similarity(s, r) for s in (part, outline_turned(part)) for r in singles) < SIGN_CLAIM_FLOOR:
            return False
    return True


def outline_square(shape, geometry):
    """A solid, nearly square block at least a third of an em on each side: a black
    square (an end-of-article mark, a box bullet). No letter or digit fills its own
    box (every one has a counter, a notch or a slant), and a period or middle dot is
    a solid block only at dot size; the tight silhouette alone cannot tell them
    apart, so the block's size is read from the font's bounds."""
    ink = outline_ink(shape)
    if len(ink) < 1000 or not isinstance(geometry, dict): return None
    try:
        left, top, right, bottom = geometry['bounds_em']
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (left, top, right, bottom)): return None
        width, height = right-left, top-bottom
        if (width >= SQUARE_SIDE_FLOOR and height >= SQUARE_SIDE_FLOOR and 2/3 <= width/height <= 3/2
                and abs(width/height-shape[1]) <= .05*shape[1]): return '■'
    except (KeyError, TypeError, ValueError, ZeroDivisionError): pass
    return None


def outline_bar(shape, geometry):
    """One solid bar at the math axis, at least a third of an em wide: a minus.
    Underscores (below the baseline), short marks and tall shapes abstain."""
    ink = outline_ink(shape)
    if len(ink) < 980 or shape[1] < 4 or not isinstance(geometry, dict): return None
    try:
        left, top, right, bottom = geometry['bounds_em']
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (left, top, right, bottom)): return None
        height = abs(top-bottom); centre = (top+bottom)/2
        if .02 <= height <= .15 and .15 <= centre <= .50 and right-left >= .30: return '−'
    except (KeyError, TypeError, ValueError): pass
    return None


def sign_outline_decision(before, scores, shape=None, geometry=None, small=False, text=False, extent=None,
                          greek_face=False, named=False):
    """Decide a sign-face glyph or a quote-mark claim in a number from its outline.

    Strokes first, then the reference silhouettes at the established thresholds,
    measured on the sign's own silhouette; a claim inside the winning family is
    kept; a claim that no sign replaces is confirmed only by its own silhouette
    (>= SIGN_CLAIM_FLOOR), else a text claim is rejected (U+FFFD, listed) and a
    claimed sign or symbol is left as claimed: the nearest sign is never printed.
    small (rule R1, a face of at most SMALL_FACE_CODES used codes): the Greek
    letters compete beside the sign set, the best-scoring allowed member of the
    winning family is printed (when its own silhouette clears the floors), and any
    claim measured under the floor that no sign or Greek letter replaces is rejected,
    not only text-layer claims.
    In a small face a Latin and a Greek letter are different families (small_family), and with
    extent (the glyph's bottom and top in em) only the characters whose place on the line it takes
    compete (placed); a claim its place contradicts is rejected unless another character replaces it.
    A sign or Greek claim under the floor is flagged only by a rival that reaches SIGN_CLAIM_FLOOR.
    greek_face (a small face whose outlines replace another Latin claim of it by a Greek letter): a Latin
    claim there that a placed Greek letter beats clearly but not by the replacement margins is rejected.
    text (lane claims3, a face named like a sign face whose codes form running text): a claim that no
    sign replaces is never rejected here ('unchanged'); the ordinary outline decision then decides it.
    named (lane r3-glyphmap, a face whose glyph names its outlines contradict, names_contradicted): a dot is
    printed as the dot its place on the line takes (dot_by_place: a raised decimal point is '·', not '•'), and a
    letter claim with no reference silhouette that no sign replaces is rejected, never printed as the letter.
    """
    # A double quotation mark drawn as two commas or apostrophes is confirmed by its strokes.
    if before in QUOTE_PAIR_CLAIMS and shape is not None and outline_quote_pair(shape, sign_references()):
        return 'confirmed', before
    # A solid block a third of an em or more on each side is a black square: a letter,
    # digit or other text claim is replaced by it; a bullet or a claimed symbol stays.
    if shape is not None and outline_square(shape, geometry):
        if before in sign_family('•') or not text_claim(before): return 'confirmed', before
        return 'replaced', '■'
    allowed = SIGN_SET + (SMALL_FACE_GREEK+EXTRA_GREEK if small else '')
    family_of = small_family if small else sign_family
    contradicted = False
    if small and extent is not None:
        own = [c for c in family_of(before) if c in scores]
        letter = before.isalpha() and letter_script(before) != 'other'
        contradicted = letter and bool(own) and not any(placed(c, extent) for c in own)
        keep = set() if letter else set(own)   # a non-letter claim is never displaced by its own place
        scores = {ch: v for ch, v in scores.items() if ch in keep or placed(ch, extent)}
    # A claim without a reference silhouette (a curly quote) is measured by its family.
    native = max((scores[ch] for ch in family_of(before) if ch in scores), default=None)
    found = None
    if shape is not None:
        if outline_plus_minus(shape): found = '±'
        elif outline_equals(shape): found = '='
        elif outline_plus(shape): found = '+'
        elif outline_cross(shape): found = '×'
        else: found = outline_comparison(shape, sign_references()) or outline_bar(shape, geometry)
    # Strokes that prove the claimed sign itself confirm it whatever the silhouettes say (lane claims2: the
    # text layer and the strokes agree; a hairline design such as CMSY10's ± scores .35 against the heavy
    # DejaVu references and .52 against '+'). A replacement still needs SIGN_STRUCTURE_FLOOR support.
    if found and found == before: return 'confirmed', before
    if found and scores.get(found, 0) >= SIGN_STRUCTURE_FLOOR:
        if before in family_of(found): return 'confirmed', before
        return 'replaced', found
    ranked = sorted(((v, ch) for ch, v in scores.items()), reverse=True)
    if ranked:
        best, ch = ranked[0]; family = family_of(ch)
        if before in family and best >= SIGN_CLAIM_FLOOR: return 'confirmed', before
        runner = max((v for v, c in ranked if c not in family), default=0)
        # The sign printed is the outline's own match: its own silhouette clears the
        # floors, not a lookalike's (a filled square nearest a period is no bullet; a
        # chi nearest the cross family is no multiplication sign).
        if small: sign = max((c for c in family if c in allowed), key=lambda c: scores.get(c, 0), default=None)
        else: sign = next((c for c in family if c in SIGN_SET), None)
        own = scores.get(sign, 0) if sign else 0
        # A dot in a face whose names lie is the dot whose place it takes (its own family's silhouettes).
        if named and sign and family == sign_family('•') and dot_by_place(geometry):
            sign = dot_by_place(geometry); own = max(scores.get(c, 0) for c in family)
        if (sign and own >= SIGN_TEMPLATE_FLOOR-1e-9 and own-(native or 0) >= SIGN_NATIVE_MARGIN-1e-9
                and own-runner >= SIGN_RUNNER_MARGIN-1e-9):
            return 'replaced', sign
    # In a small face that draws Greek letters for Latin claims (greek_face), a Latin claim a placed Greek
    # letter beats clearly (at SIGN_TEMPLATE_FLOOR and SIGN_RUNNER_MARGIN above the claim) but not by the
    # replacement margins is not printed as claimed. Only there: a single-storey italic 'a' or an italic 'v'
    # of an ordinary italic face scores closer to alpha or upsilon than to the DejaVu a and v.
    if small and greek_face and native is not None and letter_script(before) == 'latin':
        greek = max((v for c, v in scores.items() if letter_script(c) == 'greek'), default=0)
        if greek >= SIGN_TEMPLATE_FLOOR-1e-9 and greek-native >= SIGN_RUNNER_MARGIN-1e-9: return 'rejected', '\ufffd'
    if native is not None and native >= SIGN_CLAIM_FLOOR: return 'confirmed', before
    if contradicted: return 'rejected', '\ufffd'
    # Lane claims2: in a small face a claim that is itself a sign or Greek letter is flagged only when a
    # rival outside its family scores above it; the best-scoring claim is printed as claimed. The rival must
    # itself reach SIGN_CLAIM_FLOOR: a rival under the floor is no better evidence than the claim (AS10's
    # PazoMath-Italic gamma, .34, against a '7' at .435 that does not even reach below the baseline).
    if small and native is not None and sign_or_greek(before):
        rival = max((v for c, v in scores.items() if c not in family_of(before)), default=0)
        if rival <= native or rival < SIGN_CLAIM_FLOOR: return 'confirmed', before
    # Lane r3-glyphmap: in a face whose glyph names its outlines contradict, a letter claim nothing can confirm
    # (no reference silhouette) and no sign replaces is the name's letter, not the drawn glyph: flagged.
    if named and native is None and before.isalpha(): return 'rejected', '\ufffd'
    if text: return 'unchanged', before
    if not text_claim(before) and not (small and native is not None): return 'unchanged', before
    return 'rejected', '\ufffd'


def outline_sign_strokes(shape, geometry=None):
    """The sign an outline's strokes prove by themselves (plus-minus, equals, plus, cross, a chevron over
    a stroke, a minus bar), or None. No letter or ligature of letters is drawn by these strokes alone."""
    if shape is None: return None
    if outline_plus_minus(shape): return '±'
    if outline_equals(shape): return '='
    if outline_plus(shape): return '+'
    if outline_cross(shape): return '×'
    return outline_comparison(shape, sign_references()) or outline_bar(shape, geometry)


def dot_by_place(geometry):
    """Lane r3-glyphmap: the dot (period, middle dot or bullet) whose place on the line a round dot takes: the
    member of the dot family whose reference range (glyph_extents: bottom and top in em over the extent faces)
    lies nearest the glyph's own bottom and top (the font's bounds). None without bounds or extents."""
    try:
        left, top, right, bottom = geometry['bounds_em']
        if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in (top, bottom)) or top <= bottom: return None
    except (KeyError, TypeError, ValueError): return None
    extents = glyph_extents()[0]
    def gap(v, low, high): return max(low-v, 0, v-high)
    ranked = sorted((gap(bottom, r[0], r[1])+gap(top, r[2], r[3]), ch) for ch in '.·•' for r in [extents.get(ch)] if r)
    return ranked[0][1] if ranked else None


def outline_geometry(font, code):
    """The glyph's bounds and advance in em from the font (as verify_outlines saves them)."""
    return dict(bounds_em=[v/1000 for v in font.bbox(code)], advance_em=font.width(code)/1000)


def named_claim(font, code, claim):
    """The claim is the character the code's own glyph name gives (the encoding names the glyph)."""
    reader = sys.modules.get('_copy_table_reader')
    try: name = font.selected_glyph_name(code) if reader else None
    except Exception: return False
    return bool(name) and reader.sc_uni(name) == claim


def names_contradicted(font, code, claim):
    """Lane r3-glyphmap: the code's claim is a letter (any script, ordinals included) that its glyph name gives,
    and the outline under that name is a sign: sign_outline_decision replaces the claim by a character that is no
    letter (WTimesGreekSF-type faces name a minus /ordfeminine and an equals sign /Omega; a raised decimal point
    is named /AE). One such code shows that the face's names do not describe its outlines."""
    if not (isinstance(claim, str) and len(claim) == 1 and claim.isalpha() and named_claim(font, code, claim)): return False
    try:
        shape = outline_shape(font, code); geometry = outline_geometry(font, code)
        scores = {ch: max(outline_similarity(shape, ref) for ref in refs) for ch, refs in sign_references().items()}
        status, after = sign_outline_decision(claim, scores, shape=shape, geometry=geometry, named=True)
    except Exception: return False
    return status == 'replaced' and not after.isalpha()


def ligature_outline_decision(before, scores, shape=None, geometry=None):
    """Lane r2-signs: one glyph whose text layer claims several letters (a ligature: 'fl', 'ffi').

    The claim is replaced only when the outline's own strokes prove a sign (outline_sign_strokes) and
    the sign's silhouette gives it SIGN_STRUCTURE_FLOOR support: a ligature of letters never draws
    a chevron over a separate bar, two bars or a crossing. Anything else keeps the claim."""
    if not (isinstance(before, str) and len(before) >= 2 and before.isalpha()): return 'unchanged', before
    found = outline_sign_strokes(shape, geometry)
    if found and isinstance(scores.get(found), (int, float)) and scores[found] >= SIGN_STRUCTURE_FLOOR:
        return 'replaced', found
    return 'unchanged', before


def ligature_glyphs(font_glyphs):
    """Groups of a run's characters that one glyph gives (a ligature): consecutive offsets and character
    IDs, one face and code, one box. Groups of one character are left out."""
    glyphs = sorted(font_glyphs, key=lambda c: c['offset']); groups = []; i = 0
    while i < len(glyphs):
        j = i+1
        while (j < len(glyphs) and glyphs[j]['offset'] == glyphs[j-1]['offset']+1
               and glyphs[j]['char_id'] == glyphs[j-1]['char_id']+1 and glyphs[j]['font'] == glyphs[i]['font']
               and glyphs[j]['source_code'] == glyphs[i]['source_code'] and glyphs[j]['box_px'] == glyphs[i]['box_px']):
            j += 1
        if j-i >= 2 and isinstance(glyphs[i]['source_code'], int): groups.append(glyphs[i:j])
        i = j
    return groups


def sign_or_greek(ch):
    """A claim that is itself a member of the sign or Greek set: the sign set, the Greek letters
    the outline references hold, or any other non-ASCII symbol or punctuation that is no quote mark."""
    return (ch in SIGN_SET or ch in SMALL_FACE_GREEK or
            (len(ch) == 1 and not ch.isascii() and not ch.isalnum() and not text_claim(ch)))


def outline_greek(before, scores):
    """Rule R2: the Greek letter an embedded outline names for a Latin letter claim, or None.

    The claim scores under SIGN_CLAIM_FLOOR; the best Greek reference scores at least SIGN_TEMPLATE_FLOOR,
    SIGN_NATIVE_MARGIN above the claim and SIGN_RUNNER_MARGIN above every reference outside its family
    (the thresholds of second-pass rule 9 and the sign decision). This names; it never prints alone: the
    raster verifier also needs its own separated Greek alternative and the letter alone in its face.
    """
    if not (isinstance(before, str) and len(before) == 1 and before.isascii() and before.isalpha()): return None
    native = scores.get(before)
    if not isinstance(native, (int, float)) or native >= SIGN_CLAIM_FLOOR: return None
    greek = [ch for ch in SMALL_FACE_GREEK if isinstance(scores.get(ch), (int, float))]
    if not greek: return None
    g = max(greek, key=scores.get); family = sign_family(g)
    runner = max((v for ch, v in scores.items() if ch not in family and ch != g and isinstance(v, (int, float))), default=0)
    if (scores[g] >= SIGN_TEMPLATE_FLOOR-1e-9 and scores[g]-native >= SIGN_NATIVE_MARGIN-1e-9
            and scores[g]-runner >= SIGN_RUNNER_MARGIN-1e-9): return g
    return None


def saved_extent(value):
    """A saved (bottom, top) place on the line, validated, or None."""
    if (isinstance(value, (list, tuple)) and len(value) == 2 and
            all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in value)
            and -1 < value[0] < value[1] < 2): return tuple(value)
    return None


def saved_outline_decision(proof, unit=False):
    if proof.get('ligature') is True:
        return ligature_outline_decision(proof['before'], proof['scores'], shape=proof.get('outline'),
                                         geometry=proof.get('geometry'))
    if proof.get('sign_claim'):
        return sign_outline_decision(proof['before'], proof['scores'], shape=proof.get('outline'),
                                     geometry=proof.get('geometry'), small=proof.get('small_face') is True,
                                     text=proof.get('text_face') is True, extent=saved_extent(proof.get('extent')),
                                     greek_face=proof.get('greek_face') is True, named=proof.get('named_mismatch') is True)
    return outline_decision(proof['before'], proof['scores'], unit=unit,
                            shape=proof.get('outline'), geometry=proof.get('geometry'),
                            symbol=proof.get('symbol_font', False))


def outline_decision(before, scores, unit=False, shape=None, geometry=None, symbol=False):
    """Only a separated, high-scoring competitor may replace a valid claim.

    Similar typography (I/l/1, O/0, dash variants, Greek/Latin lookalikes)
    cannot win a unique-character margin. Weak disagreements are diagnostic,
    but a digit contradicted by a non-digit must not survive as a false value.
    """
    native = scores.get(before)
    if native is None: return 'unmeasured', None
    if len(before) == 1 and before.isascii() and before.isalpha():
        dash = outline_dash(shape, geometry)
        if dash: return 'replaced', dash
    # A letter or digit whose outline is a solid block a third of an em on each side
    # is a black square whatever its own silhouette score (a box overlaps an 'n' at .64).
    if len(before) == 1 and before.isascii() and before.isalnum() and outline_square(shape, geometry):
        return 'replaced', '■'
    ambiguous_arrow = False
    if symbol and native < .40:
        arrow = outline_arrow(shape)
        if arrow and scores.get(arrow, 0) >= .45 and scores[arrow]-native >= .20:
            return 'replaced', arrow
        ambiguous_arrow = bool(arrow or max((scores.get(ch, 0) for ch in '↑↓←→'), default=0) >= max(.45, native+.20))
    others = sorted(((v, ch) for ch, v in scores.items() if ch != before), reverse=True)
    if not others: return ('uncertain' if ambiguous_arrow else 'confirmed' if native >= .55 else 'unchanged'), before
    best, after = others[0]; runner = max(native, others[1][0] if len(others) > 1 else 0)
    if native < .40 and best >= .80 and best-native >= .30 and best-runner >= .10:
        return 'replaced', after
    if native < .40 and best >= .72 and best-native >= .20:
        if before.isdigit() and not after.isdigit(): return 'rejected', '\ufffd'
        return 'uncertain', before
    if (before.isdigit() and after == '±' and best >= .70 and best-native >= .18
            and best-runner >= .18 and outline_plus_minus(shape)):
        return 'rejected', '\ufffd'
    # Greek mu and the micro sign share a reading in units. A weaker but
    # separated family match warrants a location-specific warning, never an
    # automatic substitution. Retain the ordinary replacement thresholds.
    if unit and before in 'lmu':
        mu = max(scores.get('μ', 0), scores.get('µ', 0))
        other = max((v for ch, v in scores.items() if ch not in ('μ', 'µ')), default=0)
        if mu >= .60 and mu-native >= .20 and mu-other >= .10:
            return 'uncertain', before
    # Extra arrow warnings extend the mismatch screen; they must never
    # preempt an existing, strongly separated replacement or digit rejection.
    if ambiguous_arrow: return 'uncertain', before
    return ('confirmed' if native >= .55 else 'unchanged'), before


def verify_outlines(doc, runs):
    """Check each used font/code once, including apparently valid text.

    URL/DOI/e-mail membership and two codes claiming one letter/digit are
    selection evidence, never substitution evidence. All referenced claims
    are also screened for strongly separated shape alternatives. Full subset
    names stay distinct; colliding font dictionaries must agree by outline.
    """
    started = time.perf_counter(); cpu_started = time.process_time(); references = outline_references()
    fonts = collections.defaultdict(list)
    for font in doc.fonts.values(): fonts[font.basefont].append(font)
    occurrences = collections.defaultdict(list); claims = collections.defaultdict(set)
    # Rule R1: the face's distinct used codes on the paper (any claim, ligatures included) and the body face.
    face_codes = collections.defaultdict(set); letters = collections.Counter()
    for run in runs:
        for c in run['font_glyphs']:
            # A glyph the text layer set as a space (flagged in place by the reader) is no text code the face sets.
            if c.get('inked_space'): continue
            if isinstance(c['source_code'], int): face_codes[c['font']].add(c['source_code'])
            if c['before'].isalpha(): letters[c['font']] += 1
    body_face = letters.most_common(1)[0][0] if letters else None
    # A face is small only beside a body face of more codes (a paper of a few codes has no such contrast).
    contrast = body_face is not None and len(face_codes[body_face]) > SMALL_FACE_CODES
    # Lane claims3: what each face sets (running words and numbers, or isolated codes).
    text_use = face_text_use((run['source'], {c['offset']: c['font'] for c in run['font_glyphs']}) for run in runs)
    previous = None
    for run in runs:
        addresses = address_offsets(run['source'])
        # A URL at the end of one printed line can continue in the next run.
        if previous and previous['page'] == run['page'] and previous.get('_address_tail'):
            a, b = previous['crop_xywh'], run['crop_xywh']
            if 0 <= b[1]-a[1] <= 2.5*max(a[3], b[3]) and abs(a[0]-b[0]) < max(a[2], b[2]):
                token = re.match(r'[^\s<>"“”]+', run['source'])
                if token: addresses.update(range(*token.span()))
        run['_address_tail'] = bool(addresses and len(run['source'].rstrip())-1 in addresses)
        previous = run
        for c in run['font_glyphs']:
            key = c['font'], c['source_code']
            if not isinstance(key[1], int) or len(c['before']) != 1 or c['before'].isspace(): continue
            occurrences[key].append((run, c, c['offset'] in addresses))
            if c['before'].isalnum(): claims[c['font'], c['before']].add(key[1])
    records = []; measured = 0; cache = {}; unavailable = []; selection = collections.Counter(); decisions = collections.Counter()
    greek_named = []; pending = []; greek_faces = set()
    # Lane r3-glyphmap: a face whose encoding names a letter for a code whose outline is a sign (names_contradicted)
    # keeps sign treatment for every code, whatever the claimed character's class and whatever touches it. A face
    # whose codes form running text (lane claims3) is never selected so.
    named_faces = {font for (font, code), rows in occurrences.items()
                   if fonts[font] and not running_text(text_use.get(font)) and rows[0][1]['before'].isalpha()
                   and all(c['before'] == rows[0][1]['before'] for r, c, u in rows)
                   and names_contradicted(fonts[font][0], code, rows[0][1]['before'])}

    def emit(font, code, before, after, status, reasons, scores, shape, geometry, symbol, sign, small, extent, text, rows,
             greek_face=False, named=False):
        reasons = reasons+['separated outline mismatch']
        record = dict(model=OUTLINE_MODEL, font=font, source_code=code, before=before,
                      after=after, status=status, reasons=reasons, scores=scores,
                      outline=[hex(shape[0]), shape[1], shape[2]], geometry=geometry, symbol_font=symbol, places=[])
        if sign: record['sign_claim'] = sign
        if small and sign: record['small_face'] = True; record['face_codes'] = len(face_codes[font])
        if small and sign and extent is not None: record['extent'] = list(extent)
        if text and sign: record['text_face'] = True
        if greek_face: record['greek_face'] = True
        if named and sign: record['named_mismatch'] = True
        for run, c, address in rows:
            if sign: pass   # one decision per font/code: every place follows it
            elif outline_decision(before, scores, shape=shape, geometry=geometry, symbol=symbol) != (status, after) and c['offset'] not in unit_prefix_offsets(run['source']): continue
            record['places'].append(dict(page=run['page'], id=run['id'], offset=c['offset'],
                                         char_id=c['char_id'], box_px=c['box_px'], source=run['source']))
            run.setdefault('outline_records', []).append((c, record))
        records.append(record)

    parser_errors = (ValueError, KeyError, TypeError, AttributeError, IndexError, NotImplementedError,
                     AssertionError, getattr(sys.modules.get('fontTools.ttLib'), 'TTLibError', ValueError))
    for (font, code), rows in occurrences.items():
        before = rows[0][1]['before']
        reasons = []
        if any(u for r, c, u in rows): reasons.append('address')
        if len(claims[font, before]) > 1: reasons.append('duplicate claim')
        unit = any(c['offset'] in unit_prefix_offsets(r['source']) for r, c, u in rows)
        if unit: reasons.append('number-unit prefix')
        # Sign faces and quote marks in numbers (lane glyphsigns): decided by
        # sign_outline_decision; private-use and unmapped claims belong to other passes.
        sign = None; text = False; named = False
        if len(before) == 1 and not private_use(before) and before != '�' and fonts[font]:
            sign = sign_face(fonts[font][0])
            # Letters and digits of an opaque-named face (AdvOT, AdvTT) keep the ordinary
            # checks; a letter inside a word is never a sign (the raster pass's own rule).
            # A face whose glyph names its outlines contradict keeps sign treatment (lane r3-glyphmap).
            named = font in named_faces
            if sign == 'symbolic encoding' and before.isalnum() and not named: sign = None
            if (sign and before.isalpha() and not named
                    and any(inside_word(r['source'], c['offset']) for r, c, u in rows)): sign = None
            if not sign and any(quote_in_number(r['source'], c['offset']) for r, c, u in rows): sign = 'quote mark in a number'
            # The name is only a prior (lane claims3): a face named like a sign face whose codes form
            # running text keeps the ordinary checks unless a sign clearly beats a claim.
            if sign == 'sign face' and running_text(text_use.get(font)): text = True; reasons.append('running text')
        # Rule R1: every code of a small face, whatever its name, encoding or place in a word, when the
        # claim has its own reference silhouette (a claim without one, such as a letter with a diacritic,
        # cannot be scored against itself and keeps the existing checks) and its glyph gives one character
        # (a ligature's glyph is exempt: the reader gives each of its characters the glyph's own box, so two
        # occurrences of the code share one page and box; AG10, AL09, AP05 'ff' claimed as 'f' 'f').
        face_sign = sign
        glyph_ids = [(r['page'], tuple(c['box_px'])) for r, c, u in rows]
        small = bool(contrast and len(before) == 1 and not private_use(before) and before != '�' and fonts[font]
                     and font != body_face and len(face_codes[font]) <= SMALL_FACE_CODES
                     and before in references and len(set(glyph_ids)) == len(glyph_ids))
        if small and not sign: sign = 'small face'   # a named sign face keeps its own reason and notice
        if named and not sign: sign = 'glyph names contradicted by outlines'   # lane r3-glyphmap
        if sign: reasons.append(sign)
        selection.update(reasons)
        try:
            if before not in references and not sign: raise ValueError('no reference for claimed character')
            if any(c['before'] != before for r, c, u in rows): raise ValueError('mixed claims for the same code')
            shapes = [outline_shape(f, code) for f in fonts[font]]
            if not shapes or any(s != shapes[0] for s in shapes): raise ValueError('ambiguous font dictionaries')
        except parser_errors as exc:
            if reasons:
                unavailable.append(dict(font=font, source_code=code, before=before, reasons=reasons, small_face=small,
                                        reason=str(exc), places=[dict(page=r['page'], id=r['id'], offset=c['offset'])
                                                               for r, c, u in rows if u or 'duplicate claim' in reasons]))
            continue
        shape = shapes[0]; measured += 1
        geometry = None
        if ((before.isascii() and before.isalpha() and shape[1] >= 5 and shape[2] >= .97) or (sign and shape[1] >= 4)
                or (shape[2] >= .97 and (sign or (before.isascii() and before.isalnum()))) or named):
            try:
                metrics = [dict(bounds_em=[v/1000 for v in f.bbox(code)], advance_em=f.width(code)/1000)
                           for f in fonts[font]]
                if all(m == metrics[0] for m in metrics): geometry = metrics[0]
            except parser_errors: pass
        symbol = bool(SIGN_FONT.search(re.sub(r'^[A-Z]{6}\+', '', font)) or
                      re.search(r'^CM(?:SY|EX)\d', re.sub(r'^[A-Z]{6}\+', '', font), re.I))
        # A small face's glyph also carries its place on the line (the font's bbox for the code, in em).
        extent = None
        if small:
            try:
                boxes = [outline_extent(f.bbox(code)) for f in fonts[font]]
                if boxes and all(b == boxes[0] for b in boxes): extent = boxes[0]
            except parser_errors: pass
        key = shape, before, unit, bool(sign), small, extent, named
        if key not in cache:
            if sign:
                scores = {ch: max(outline_similarity(shape, ref) for ref in refs)
                          for ch, refs in (small_references() if small else sign_references()).items()}
            else:
                native = max(outline_similarity(shape, ref) for ref in references[before])
                scores = {before: native}
                # Alternatives are measured under the claim floor (.45): outline_decision acts only under .40;
                # outline_greek (rule R2) reads the scores between .40 and .45 too.
                if native < SIGN_CLAIM_FLOOR or unit or before.isdigit():
                    scores.update((ch, max(outline_similarity(shape, ref) for ref in refs))
                                  for ch, refs in references.items() if ch != before)
            cache[key] = scores
        scores = cache[key]
        if sign:
            status, after = sign_outline_decision(before, scores, shape=shape, geometry=geometry, small=small, text=text,
                                                  extent=extent, named=named)
            # A small face that is no sign face keeps the ordinary decision's strongly separated replacement
            # first (AI11: an em dash claimed as 'd' stays an em dash, not the sign set's minus); so does a face
            # selected only by its contradicted glyph names (lane r3-glyphmap).
            if (status != 'replaced' or ((small or named) and not face_sign)) and before in references:
                # The ordinary decision still names what the sign set lacks (AL01: a
                # Pi-face '?' drawn as an arrow); it is saved and revalidated as itself.
                plain = {ch: v for ch, v in scores.items() if ch in references}
                ordinary = outline_decision(before, plain, unit=unit, shape=shape, geometry=geometry, symbol=symbol)
                # A running-text face's claim that no sign replaces is decided as in any text face (lane claims3).
                if ordinary[0] == 'replaced' or (text and status != 'replaced'):
                    (status, after), sign, scores = ordinary, None, plain
        else: status, after = outline_decision(before, scores, unit=unit, shape=shape, geometry=geometry, symbol=symbol)
        greek = None if sign else outline_greek(before, scores)
        if greek: greek_named.append(dict(font=font, source_code=code, before=before, character=greek, scores=dict(scores)))
        decisions[status] += 1
        if small and sign and status == 'confirmed' and letter_script(before) == 'latin':
            pending.append((font, code, before, rows, reasons, scores, shape, geometry, symbol, sign, extent, text))
        if small and sign and status == 'replaced' and letter_script(before) == 'latin' and letter_script(after) == 'greek':
            greek_faces.add(font)
        if status not in ('replaced', 'rejected', 'uncertain'): continue
        emit(font, code, before, after, status, reasons, scores, shape, geometry, symbol, sign, small, extent, text, rows,
             named=named)
    # A small face whose outlines replace a Latin claim by a Greek letter draws Greek letters: its other Latin
    # claims that a Greek letter beats clearly are decided again with greek_face (re-ladder of lane claims).
    for font, code, before, rows, reasons, scores, shape, geometry, symbol, sign, extent, text in pending:
        if font not in greek_faces: continue
        scores = case_scores(shape, scores, extent)
        status, after = sign_outline_decision(before, scores, shape=shape, geometry=geometry, small=True, text=text,
                                              extent=extent, greek_face=True)
        if status == 'confirmed': continue
        decisions['confirmed'] -= 1; decisions[status] += 1
        if status not in ('replaced', 'rejected', 'uncertain'): continue
        emit(font, code, before, after, status, reasons+['Greek face'], scores, shape, geometry, symbol, sign, True,
             extent, text, rows, greek_face=True)
    # Lane r2-signs: a glyph whose text layer claims several letters (a ligature) is checked against its
    # outline too; a sign its strokes prove replaces the claim (the first letter becomes the sign, the
    # others are removed), once per font/code for every place.
    ligatures = collections.defaultdict(list)
    for run in runs:
        for group in ligature_glyphs(run['font_glyphs']): ligatures[group[0]['font'], group[0]['source_code']].append((run, group))
    for (font, code), rows in ligatures.items():
        before = {''.join(c['before'] for c in group) for run, group in rows}
        if len(before) != 1 or not fonts[font]: continue
        before = before.pop()
        if not before.isalpha(): continue
        try:
            shapes = [outline_shape(f, code) for f in fonts[font]]
            if not shapes or any(v != shapes[0] for v in shapes): raise ValueError('ambiguous font dictionaries')
        except parser_errors: continue
        shape = shapes[0]; geometry = None
        try:
            metrics = [dict(bounds_em=[v/1000 for v in f.bbox(code)], advance_em=f.width(code)/1000) for f in fonts[font]]
            if all(m == metrics[0] for m in metrics): geometry = metrics[0]
        except parser_errors: pass
        scores = {ch: max(outline_similarity(shape, ref) for ref in refs) for ch, refs in sign_references().items()}
        status, after = ligature_outline_decision(before, scores, shape=shape, geometry=geometry)
        selection['ligature claim'] += 1
        if status != 'replaced': continue
        decisions[status] += 1
        record = dict(model=OUTLINE_MODEL, font=font, source_code=code, before=before, after=after, status=status,
                      reasons=['ligature claim', 'outline strokes prove a sign'], scores=scores,
                      outline=[hex(shape[0]), shape[1], shape[2]], geometry=geometry, symbol_font=False,
                      sign_claim='ligature claim', ligature=True, places=[])
        for run, group in rows:
            first = group[0]
            record['places'].append(dict(page=run['page'], id=run['id'], offset=first['offset'], char_id=first['char_id'],
                                         box_px=first['box_px'], source=run['source'], characters=len(group)))
            for index, c in enumerate(group):
                run.setdefault('outline_records', []).append((dict(c, ligature_index=index), record))
        records.append(record)
    for run in runs: run.pop('_address_tail', None)
    return dict(model=OUTLINE_MODEL, seconds=time.perf_counter()-started, cpu_seconds=time.process_time()-cpu_started,
                unique_codes=len(occurrences), selected=dict(selection), unavailable=unavailable,
                measured=measured, decisions=dict(decisions), records=records, greek_named=greek_named)


def private_use(character):
    """Unicode private-use code points (U+E000-U+F8FF and planes 15-16)."""
    return len(character) == 1 and unicodedata.category(character) == 'Co'


def symbol_code(character):
    """The Adobe Symbol code a private-use text code stands for, or None.

    Symbol fonts set their text in U+F020-U+F0FF (U+F000 plus the code); the
    Adobe Glyph List's private Symbol values are also accepted. Nothing else is.
    """
    if not private_use(character): return None
    value = ord(character)
    if 0xF020 <= value <= 0xF0FF: return value-0xF000
    return ADOBE_SYMBOL_PRIVATE.get(value)


def truetype_covers(path, character):
    """True when a TrueType file's Unicode cmap (format 4 or 12) maps the character.

    Pillow draws an uncovered character as the font's .notdef box, which must
    never become a reference shape.
    """
    import struct
    data = Path(path).read_bytes(); value = ord(character)
    tables = {data[12+16*i:16+16*i]: struct.unpack('>II', data[20+16*i:28+16*i])
              for i in range(struct.unpack('>H', data[4:6])[0])}
    start = tables[b'cmap'][0]
    for i in range(struct.unpack('>H', data[start+2:start+4])[0]):
        platform, encoding, offset = struct.unpack('>HHI', data[start+4+8*i:start+12+8*i])
        if (platform, encoding) not in ((3, 1), (3, 10), (0, 3), (0, 4)): continue
        sub = start+offset; kind = struct.unpack('>H', data[sub:sub+2])[0]
        if kind == 4 and value <= 0xFFFF:
            count = struct.unpack('>H', data[sub+6:sub+8])[0]//2
            ends = struct.unpack('>%dH' % count, data[sub+14:sub+14+2*count])
            starts = struct.unpack('>%dH' % count, data[sub+16+2*count:sub+16+4*count])
            deltas = struct.unpack('>%dh' % count, data[sub+16+4*count:sub+16+6*count])
            ranges = sub+16+6*count
            for k in range(count):
                if starts[k] <= value <= ends[k]:
                    shift = struct.unpack('>H', data[ranges+2*k:ranges+2*k+2])[0]
                    if not shift: return (value+deltas[k]) & 0xFFFF != 0
                    at = ranges+2*k+shift+2*(value-starts[k])
                    glyph = struct.unpack('>H', data[at:at+2])[0]
                    return glyph != 0 and (glyph+deltas[k]) & 0xFFFF != 0
        if kind == 12:
            for k in range(struct.unpack('>I', data[sub+12:sub+16])[0]):
                first, last, glyph = struct.unpack('>III', data[sub+16+12*k:sub+28+12*k])
                if first <= value <= last: return glyph+value-first != 0
    return False


def build_symbol_shapes(path=None):
    """Precompute reference silhouettes for Symbol readings the outline references lack.

    Same DejaVu faces, renderer and 48-pixel height as glyph_shapes.json.gz
    (check_fonts.reference_shapes); faces that do not cover a character are
    skipped. Needs Pillow, so run it in a process without the reader's PIL shim:
    /usr/bin/python3 -I tools/check_fonts.py --build-symbol-shapes
    """
    base = outline_references(); shapes = {}
    folder = Path('/usr/share/fonts/truetype/dejavu')
    for character in sorted(set(SYMBOL_ENCODING.values())-set(base)):
        rows = [[hex(mask), round(aspect, 6), round(ink, 6)] for face, (mask, aspect, ink)
                in reference_shapes(character, 48) if truetype_covers(folder/(face+'.ttf'), character)]
        if rows: shapes[character] = rows
    data = dict(description='32-pixel silhouettes, 40-pixel canvas; DejaVu Sans and Serif, regular/bold/'
                'italic/bold italic, covering faces only; produced by check_fonts.build_symbol_shapes at 48 '
                'pixels for Adobe Symbol readings absent from glyph_shapes.json.gz. Used only to check '
                'private-use Symbol codes.', shapes=shapes)
    with gzip.open(path or Path(__file__).with_name(SYMBOL_SHAPES), 'wt') as stream:
        json.dump(data, stream, ensure_ascii=True, sort_keys=True)
    return len(shapes)


@functools.lru_cache(maxsize=1)
def symbol_references():
    """The outline references plus the Symbol-only references, for private-use codes only.

    The extra characters compete in no other outline decision, except ® and ©
    in sign-face decisions (sign_references).
    """
    result = dict(outline_references())
    with gzip.open(Path(__file__).with_name(SYMBOL_SHAPES), 'rt') as stream:
        extra = json.load(stream)['shapes']
    for ch, rows in extra.items():
        result.setdefault(ch, [(int(mask, 16), aspect, ink) for mask, aspect, ink in rows])
    return result


def glyph_name_verdict(names, code, reading, reader):
    """The selected embedded glyph names as evidence for one Symbol reading.

    'agrees': the Symbol name of the code, or a name whose Unicode is the
    reading. 'neutral': no name, an opaque or private-use name, or the Latin
    letter of the code itself (Symbol-layout fonts named b for beta).
    'contradicts': a name for any other character.
    """
    verdicts = set()
    for name in names:
        unicode = reader.sc_uni(name) if name else ''
        if name and (name == reader.SC_SYMBOL_NAMES.get(code) or unicode == reading): verdicts.add('agrees')
        elif not name or len(unicode) != 1 or private_use(unicode) or unicode == chr(code): verdicts.add('neutral')
        else: verdicts.add('contradicts')
    if 'contradicts' in verdicts: return 'contradicts'
    return 'agrees' if verdicts == {'agrees'} else 'neutral'


PRIVATE_MARKS = ('font name', 'font encoding', 'embedded glyph name')


def private_decision(proof):
    """Map a private-use code through the Adobe Symbol encoding, then check its outline.

    A reading needs a code in the Symbol block, a font marked as a Symbol font
    (its name, its PDF encoding or the embedded glyph name) and no contradicting
    glyph name. The existing outline decision then tests the reading as if the
    text layer had claimed it: confirmed -> 'mapped'; weak with no separated
    competitor -> 'mapped-unconfirmed' (listed); no outline or reference ->
    'mapped-unchecked' (listed); a separated competitor -> 'contradicted'.
    Every failure shows U+FFFD; no competitor is ever guessed as the reading.
    """
    before = proof.get('before')
    if not isinstance(before, str) or not private_use(before): return 'invalid', None
    code = symbol_code(before); reading = SYMBOL_ENCODING.get(code) if code is not None else None
    marks = proof.get('marks')
    if (proof.get('symbol_code') != code or proof.get('reading') != reading or not isinstance(marks, list)
            or any(m not in PRIVATE_MARKS for m in marks)
            or ('embedded glyph name' in marks) != (proof.get('glyph_name_verdict') == 'agrees')):
        return 'invalid', None
    if not reading or not marks or proof.get('glyph_name_verdict') == 'contradicts': return 'unmapped', '�'
    scores = proof.get('scores')
    if not scores: return 'mapped-unchecked', reading
    if (not isinstance(scores, dict) or reading not in scores or
            any(not isinstance(v, (int, float)) or not math.isfinite(v) or not -1 <= v <= 1.000001
                for v in scores.values())): return 'invalid', None
    status, _ = outline_decision(reading, scores, shape=proof.get('outline'), symbol=True)
    if status == 'confirmed': return 'mapped', reading
    if status == 'unchanged': return 'mapped-unconfirmed', reading
    return 'contradicted', '�'


def private_key(proof):
    return f"{proof['source_code']}:U+{ord(proof['before']):04X}"


PRIVATE_PROOF_KEYS = ('model', 'font', 'source_code', 'before', 'symbol_code', 'reading', 'marks',
                      'glyph_names', 'glyph_name_verdict', 'scores', 'outline', 'outline_reason', 'status', 'after')


def verify_private_codes(doc, runs):
    """Decide every private-use text code once per font, source code and claim.

    Measures the embedded outline against all outline references and the
    Symbol-only references. Saved native text is unchanged; the copy hook
    revalidates and applies each occurrence (font_subs, PRIVATE_MODEL).
    """
    started = time.perf_counter(); reader = sys.modules['_copy_table_reader']
    fonts = collections.defaultdict(list)
    for font in doc.fonts.values(): fonts[font.basefont].append(font)
    occurrences = collections.defaultdict(list)
    for run in runs:
        for c in run['font_glyphs']:
            if private_use(c['before']): occurrences[c['font'], c['source_code'], c['before']].append((run, c))
    parser_errors = (ValueError, KeyError, TypeError, AttributeError, IndexError, NotImplementedError,
                     AssertionError, getattr(sys.modules.get('fontTools.ttLib'), 'TTLibError', ValueError))
    references = symbol_references() if occurrences else {}
    records = []
    for (font, code, before), rows in occurrences.items():
        symbol = symbol_code(before); reading = SYMBOL_ENCODING.get(symbol) if symbol is not None else None
        objects = fonts.get(font, []); marks = []
        if SYMBOL_FACE.search(re.sub(r'^[A-Z]{6}\+', '', font)): marks.append('font name')
        if any(getattr(f, 'base', None) == 'Symbol' for f in objects): marks.append('font encoding')
        names = []
        for f in objects:
            try: names.append(f.selected_glyph_name(code))
            except parser_errors: names.append(None)
        verdict = glyph_name_verdict(names, symbol, reading, reader) if reading else None
        if verdict == 'agrees': marks.append('embedded glyph name')
        scores = outline = reason = None
        if reading and marks and verdict != 'contradicts':
            try:
                if reading not in references: raise ValueError('no reference shape for the Symbol reading')
                shapes = [outline_shape(f, code) for f in objects]
                if not shapes or any(s != shapes[0] for s in shapes): raise ValueError('ambiguous font dictionaries')
                shape = shapes[0]
                scores = {ch: max(outline_similarity(shape, ref) for ref in refs) for ch, refs in references.items()}
                outline = [hex(shape[0]), shape[1], shape[2]]
            except parser_errors as exc: reason = str(exc)
        record = dict(model=PRIVATE_MODEL, font=font, source_code=code, before=before, symbol_code=symbol,
                      reading=reading, marks=marks, glyph_names=names, glyph_name_verdict=verdict,
                      scores=scores, outline=outline, outline_reason=reason, places=[])
        record['status'], record['after'] = private_decision(record)
        for run, c in rows:
            record['places'].append(dict(page=run['page'], id=run['id'], offset=c['offset'], char_id=c['char_id']))
            run.setdefault('private_records', []).append((c, record))
        records.append(record)
    return dict(model=PRIVATE_MODEL, seconds=time.perf_counter()-started, unique_codes=len(occurrences),
                decisions=dict(collections.Counter(r['status'] for r in records)), records=records)


def valid_private_occurrence(page, element, sub, chars):
    """Revalidate one private-use edit: identity, source code and the saved decision."""
    if sub.get('model') != PRIVATE_MODEL or not chars: return False
    offset = sub.get('offset'); before = sub.get('before'); font = sub.get('font')
    if not isinstance(offset, int) or not 0 <= offset < len(element.get('text', '')): return False
    if element['text'][offset] != before or not isinstance(before, str) or not private_use(before): return False
    indexed = indexed_run(element, chars); cid = sub.get('char_id')
    if indexed is None or indexed.get(offset) != cid: return False
    if chars[cid]['font'] != font or chars[cid].get('source_code') != sub.get('source_code'): return False
    proof = page.get('fonts', {}).get(font, {}).get('private_codes', {}).get(
        private_key(dict(source_code=sub.get('source_code'), before=before)), {})
    if any(proof.get(k) != sub.get(k) for k in ('model', 'font', 'source_code', 'before', 'after', 'status')): return False
    return private_decision(proof) == (sub.get('status'), sub.get('after'))


def private_notices(rows, proofs):
    """Copy notices for applied private-use edits, grouped per font/code/claim."""
    notices = []; confirmed = collections.Counter()
    for (font, code, before, after, status), count in rows.items():
        proof = proofs[font, code, before]
        if status == 'mapped':
            confirmed[f"U+{ord(before):04X}→{after}"] += count; continue
        place = f"font {font}, glyph {code}: private-use code U+{ord(before):04X}"
        reading = proof.get('reading'); scores = proof.get('scores') or {}
        if status == 'mapped-unconfirmed':
            notices.append(f"{place} read as '{after}' through the Adobe Symbol encoding in {count} places; "
                           f"its embedded outline does not confirm it (similarity {scores.get(reading, 0):.3f}); check the printed glyph")
        elif status == 'mapped-unchecked':
            notices.append(f"{place} read as '{after}' through the Adobe Symbol encoding in {count} places; "
                           f"not checked by outline ({proof.get('outline_reason') or 'no embedded outline'}); check the printed glyph")
        else:
            if status == 'contradicted':
                best = max((ch for ch in scores if ch != reading), key=scores.get, default='?')
                why = (f"its embedded outline is closer to '{best}' ({scores.get(best, 0):.3f}) than to "
                       f"the Symbol reading '{reading}' ({scores.get(reading, 0):.3f})")
            elif not reading: why = 'it has no reading in the Adobe Symbol encoding'
            elif proof.get('glyph_name_verdict') == 'contradicts':
                why = 'its embedded glyph name ' + '/'.join(n for n in proof.get('glyph_names', []) if n) + f" contradicts the Symbol reading '{reading}'"
            else: why = 'its font is not marked as a Symbol font'
            notices.append(f"{place}: {why}; shown as � in {count} places; check the printed glyph")
    if confirmed:
        notices.insert(0, f"{sum(confirmed.values())} private-use Symbol-font codes read through the Adobe Symbol "
                          "encoding and confirmed by their embedded outlines (" +
                          ', '.join(f"{k} {v}" for k, v in sorted(confirmed.items(), key=lambda kv: -kv[1])) + ")")
    return notices


def sign_claim(character):
    """Unicode operators, currencies, dashes, fractions and typographic signs."""
    return (unicodedata.category(character) in ('Sm','Sc','Sk','So','Pd') or
            character in '†‡§¶·•‣⁃‖′″‴*%‰‱' or
            unicodedata.name(character,'').startswith('VULGAR FRACTION'))


def sign_context(text, offset):
    """Numbers or an adjacent unit select body-font signs, never their reading."""
    left,right = text[:offset],text[offset+1:]
    unit = r'(?:[kmunpµμ]?(?:m|g|l|L|s|mol|M|Hz|Pa|V|W)|[CFK]|mmHg|IU|rpm|%)'
    return bool(re.search(r'\d\s*$',left) or re.match(r'\s*\d',right) or
                re.search(r'(?<!\w)'+unit+r'\s*$',left) or
                re.match(r'\s*'+unit+r'(?!\w)',right))


def sign_like(character):
    """Claims measured against the sign templates: signs and two-part punctuation."""
    return sign_claim(character) or character in PUNCTUATION_SIGNS


def sign_verification_eligible(text, offset, font, body_font):
    """A sign in another face or beside a number/unit; two-part punctuation
    only when both hold (it is ordinary prose punctuation otherwise)."""
    if text[offset] in PUNCTUATION_SIGNS:
        return font != body_font and sign_context(text,offset)
    return sign_claim(text[offset]) and (font != body_font or sign_context(text,offset))


def scientific_token(text, offset):
    """Latin glyphs touching chemical punctuation or numeric/statistical notation.

    Use the complete run, not its font span: a sign face often contains only
    the claimed letter while the parentheses and exponent use the body face.
    This is a selection rule, never evidence that the letter is wrong.
    """
    if not text[offset].isascii() or not text[offset].isalpha(): return False
    left, right = text[:offset], text[offset+1:]
    return bool((left and (left[-1] in '(-−' or left[-1].isnumeric())) or
                (right and (right[0] in '-−' or right[0].isnumeric())) or
                re.match(r'\s*[=<>≤≥]', right) or re.search(r'[=<>≤≥]\s*$', left))


def temperature_token(text, offset):
    """Select a mapped ring in a temperature token, regardless of font share."""
    return (text[offset] == '◦' and bool(re.search(r'\d\s*$',text[:offset])) and
            bool(re.match(r'\s*[CF]\b',text[offset+1:])))


def verification_eligible(text, offset, font, share):
    """Scientific tokens regardless of share; sign faces and minority symbols."""
    return (scientific_token(text,offset) or temperature_token(text,offset) or
            font_verification_eligible(text,offset,font,share))


def font_verification_eligible(text, offset, font, share):
    """The original native-shape calibration population, before context expansion."""
    ch = text[offset]
    if ch.isspace() or ch == '\ufffd': return False
    # A random six-letter subset prefix is not part of the face's name.
    if SIGN_FONT.search(re.sub(r'^[A-Z]{6}\+', '', font)): return True
    if share >= .03: return False
    if ch.isnumeric() or ch in '+=<>*®°×±µ': return True
    start = end = offset
    while start and text[start-1].isalpha(): start -= 1
    while end+1 < len(text) and text[end+1].isalpha(): end += 1
    return ch.isalpha() and end-start+1 <= 2


def inside_word(text, offset):
    """U+FFFD must not change the alphabetic tokens used by layout classifiers."""
    if not text[offset].isalpha(): return False
    start = end = offset
    while start and text[start-1].isalpha(): start -= 1
    while end+1 < len(text) and text[end+1].isalpha(): end += 1
    return end-start+1 >= 3


def binary_shape(image):
    """Tight ink bounds; a fixed centred canvas preserves aspect and ink share."""
    from PIL import Image
    w,h,data = image
    source = Image.frombytes('RGB',(w,h),data).convert('L').point(lambda p: 255 if p < 160 else 0)
    box = source.getbbox()
    if box is None: raise ValueError('empty glyph raster')
    source = source.crop(box); w,h = source.size
    if w*h < 4: raise ValueError('undersampled glyph raster')
    ink_share = sum(bool(p) for p in source.getdata())/(w*h)
    source = source.resize((32,32),Image.Resampling.NEAREST)
    canvas = Image.new('L',(40,40)); canvas.paste(source,(4,4))
    points = sum(1 << i for i,p in enumerate(canvas.getdata()) if p)
    return points,w/h,ink_share


@functools.lru_cache(maxsize=4096)
def reference_shapes(character, height):
    """Render one requested character in both DejaVu families and styles."""
    from PIL import Image, ImageDraw, ImageFont
    result = []
    for face in ('DejaVuSans','DejaVuSans-Bold','DejaVuSans-Oblique','DejaVuSans-BoldOblique',
                 'DejaVuSerif','DejaVuSerif-Bold','DejaVuSerif-Italic','DejaVuSerif-BoldItalic'):
        path = Path('/usr/share/fonts/truetype/dejavu')/(face+'.ttf')
        font = ImageFont.truetype(str(path),max(8,height))
        box = font.getbbox(character)
        if box[3] <= box[1]: continue
        font = ImageFont.truetype(str(path),max(1,round(max(8,height)*height/(box[3]-box[1]))))
        box = font.getbbox(character)
        img = Image.new('RGB',(max(1,box[2]-box[0])+4,max(1,box[3]-box[1])+4),'white')
        ImageDraw.Draw(img).text((2-box[0],2-box[1]),character,font=font,fill='black')
        # A tiny dot/prime template can rasterize to fewer than four pixels.
        # It supplies no evidence; it must not discard the measured native
        # glyph or another usable face/competitor in this same comparison.
        try: shape = binary_shape((img.width,img.height,img.tobytes()))
        except ValueError: continue
        result.append((face,shape))
    return result


@functools.lru_cache(maxsize=8192)
def shape_similarities(image, characters):
    """Binary Pearson correlation, penalized by aspect and ink-share mismatch.

    Compare centred silhouettes scaled to equal ink height and width, allowing
    one raster pixel of alignment error. Aspect and ink share are separate
    penalties, so condensed type is not penalized twice for the same width.
    Bit masks give exactly the same intersections as sets, including the nine
    translations. One crop normalization is shared by all requested templates.
    """
    points,aspect,ink = binary_shape(image)
    # Match the raster's actual ink height, rather than its font-metric box.
    w,h,data = image
    ys = [i//w for i in range(w*h) if min(data[3*i:3*i+3]) < 160]
    result = {}
    for character in characters:
        # Similarity cannot exceed 1. Once the native claim is above 0.80,
        # no alternative can beat it by 0.20. This exact upper bound avoids
        # rendering every Greek template for clearly matching body letters.
        if result and result[characters[0]]['similarity'] > 1-ALTERNATIVE_MARGIN: break
        best = dict(similarity=-1.0)
        for face,(other,ratio,share) in reference_shapes(character,max(2,max(ys)-min(ys)+1)):
            a,b,n = points.bit_count(),other.bit_count(),40*40
            denominator = math.sqrt(a*b*(1-a/n)*(1-b/n))
            if not denominator: continue
            correlation = max(((points & (other << shift if shift >= 0 else other >> -shift)).bit_count()-a*b/n)/denominator
                              for shift in (-41,-40,-39,-1,0,1,39,40,41))
            aspect_match = min(aspect/ratio,ratio/aspect)
            ink_match = min(ink/share,share/ink)
            score = correlation*(.5+.25*aspect_match+.25*ink_match)
            if score > best['similarity']:
                best = dict(similarity=score,correlation=correlation,aspect_match=aspect_match,
                            ink_match=ink_match,aspect=aspect,ink_share=ink,reference=face)
        if 'reference' not in best:
            if character == characters[0]: raise ValueError('no usable claimed-character template')
            continue
        result[character] = best
    return result


def shape_similarity(image, character):
    """The claimed character's score, with the original metric unchanged."""
    return shape_similarities(image, character)[character]


def symbol_eligible(text, offset):
    """Protect whole words, even at an edge; allow short units/statistics."""
    if not 0 <= offset < len(text) or text[offset] not in SUSPECTS: return False
    start = end = offset
    while start and text[start-1].isalpha(): start -= 1
    while end+1 < len(text) and text[end+1].isalpha(): end += 1
    if text[offset].isalpha() and end-start+1 >= 3: return False
    return eligible(text, offset) or (text[offset].isalpha() and (start == offset or end == offset))


def eligible(text, offset):
    """No word-internal letters; exact unit prefixes/statistical notation are tokens."""
    ch = text[offset]
    if ch not in SUSPECTS: return False
    left, right = text[:offset], text[offset+1:]
    # A micro prefix can touch the following unit letter, but never be part of
    # a word or the denominator's metre/milli prefix. The unit is an exact token.
    if ch in 'mM' and re.match(r'(?:mol|[mMgLl])(?:[²³23])?(?=$|[\s/),.;:\]−–-])', right):
        return not left or not left[-1].isalpha()
    # P<0.05 and *P<0.05 may be set without spaces, each sign in its own font.
    if ch in 'o45' and re.search(r'[PpNn]\s*$', left) and re.match(r'\s*\d', right): return True
    if ch == 'n' and re.search(r'(?:^|[^\w]|\d)n*$', left) and re.match(r'n*[Pp]\s*[o45<>=]\s*\d', right): return True
    if (left and left[-1].isalpha()) or (right and right[0].isalpha()): return False
    if (not left or not left[-1].isalnum()) and (not right or not right[0].isalnum()): return True
    return bool(re.search(r'\d[\s.,:;()\[\]±+−–-]*$', left) or
                re.match(r'[\s.,:;()\[\]±+−–-]*\d', right) or
                ch == '5' and re.search(r'[PpNn(]\s*$', left))


def indexed_run(element, chars):
    ids = element.get('char_ids', [])
    if not ids or any(not isinstance(i, int) or i < 0 or i >= len(chars) for i in ids): return None
    expanded = [(i, c) for i in ids for c in chars[i]['text'] if not c.isspace()]
    positions = [(i, c) for i, c in enumerate(element['text']) if not c.isspace()]
    if [c for i,c in expanded] != [c for i,c in positions]: return None
    return {offset: cid for (offset, _), (cid, _) in zip(positions, expanded)}


def annotate(page, chars):
    """Use the reader's metadata helper, also on old JSON and split runs."""
    reader = sys.modules['_copy_table_reader']
    reader.sc_font_metadata(page, chars)


def collect(folder, pdf):
    pages, runs, unverified = {}, [], []
    body_counts = collections.Counter()
    for path in sorted(folder.glob('page-[0-9]*.json')):
        raw = path.read_bytes(); page = json.loads(raw)
        pages[str(path)] = (raw, page)
        view = dict(page, _table_pdf=str(pdf))
        chars = signs.copy.table_characters(view)
        annotate(page, chars)
        font_counts = collections.Counter(c['font'] for c in chars if not c['text'].isspace())
        total_chars = max(1,sum(font_counts.values()))
        body_counts.update(c['font'] for c in chars if c['text'].isalpha())
        doc = sys.modules['_copy_table_reader'].sc_doc(str(pdf))
        dpi = page.get('params', {}).get('dpi', 150)
        transform, rotation = signs.page_transform(doc, page['page'], dpi)
        for index, e in enumerate(page['elements']):
            if e.get('kind') != 'text': continue
            by_position = indexed_run(e, chars)
            if by_position is None:
                unverified.append(dict(page=page['page'],id=e['id'],reason='character IDs do not match native text'))
                continue
            candidates = []; symbol_candidates = []; verification_candidates = []; font_glyphs = []
            for offset, cid in by_position.items():
                c = chars[cid]; ox,oy = c['origin']
                full = dict(offset=offset,char_id=cid,before=e['text'][offset],font=c['font'],
                            **({'inked_space':True} if c.get('inked_space_claim') else {}),
                            source_code=c.get('source_code'),em=c['size']*300/dpi,
                            box_px=transform([c[k] for k in ('x0','y0','x1','y1')]),
                            origin_px=transform([ox,oy,ox,oy]))
                font_glyphs.append(full)
                span = next(s for s in e['font_spans'] if s['start'] <= offset < s['end'])
                legacy = font_verification_eligible(e['text'][span['start']:span['end']],offset-span['start'],
                                                    chars[cid]['font'],font_counts[chars[cid]['font']]/total_chars)
                verify = scientific_token(e['text'],offset) or temperature_token(e['text'],offset) or legacy
                if eligible(e['text'], offset) or symbol_eligible(e['text'], offset) or verify:
                    c = chars[cid]
                    candidate = dict(offset=offset, char_id=cid, before=e['text'][offset],
                                     font=c['font'], box_px=transform([c[k] for k in ('x0','y0','x1','y1')]))
                    if eligible(e['text'], offset): candidates.append(candidate)
                    if symbol_eligible(e['text'], offset):
                        ox, oy = c['origin']
                        symbol_candidates.append(dict(candidate, em=c['size']*300/dpi,
                                                      origin_px=transform([ox,oy,ox,oy])))
                    if verify:
                        ox,oy = c['origin']
                        verification_candidates.append(dict(candidate,source_code=c.get('source_code'),legacy_selected=legacy,
                            em=c['size']*300/dpi,origin_px=transform([ox,oy,ox,oy])))
            # Rule R2: a letter whose neighbouring letters in the run are set in another face (or that has
            # none) sits alone in its face, as a Greek letter taken from a Greek face does; a Latin face's own
            # letters inside its words (Korinna-Kursiv 'w', 'y', whose outlines resemble omega and mu) do not.
            faces = {g['offset']: g['font'] for g in font_glyphs}
            for g in font_glyphs:
                o = g['offset']; text = e['text']
                g['alone'] = all(faces.get(j) != g['font'] for j in (o-1, o+1)
                                 if 0 <= j < len(text) and text[j].isalpha())
            angle = (round(e['angle']) - rotation) % 360
            if angle not in (0,90,180,270): continue
            runs.append(dict(file=str(path), index=index, id=e['id'], page=page['page'],
                             pdf=str(pdf), source=e['text'], boxer_dpi=dpi, angle=angle,
                             crop_xywh=signs.shapes.crop_rectangle(transform(e['box_px']), dpi),
                             candidates=candidates, symbol_candidates=symbol_candidates,
                             verification_candidates=verification_candidates, font_glyphs=font_glyphs,
                             glyphs=[dict(offset=offset,text=e['text'][offset],
                                          box_px=transform([chars[cid][k] for k in ('x0','y0','x1','y1')]))
                                     for offset,cid in by_position.items()]))
        # Include neighbours from other runs (superscripts and split words).
        page['_font_glyph_boxes'] = [(i, transform([c[k] for k in ('x0','y0','x1','y1')]))
                                     for i,c in enumerate(chars) if not c['text'].isspace()]
    # Decide the body face across the paper: a table/figure face can dominate
    # one page without becoming body text. Metadata and IDs were verified
    # above; retain full subset names for the eventual font/code decisions.
    body_font = body_counts.most_common(1)[0][0] if body_counts else None
    for run in runs:
        offsets = {c['offset'] for c in run['verification_candidates']}
        run['verification_candidates'].extend(dict(c,legacy_selected=False) for c in run['font_glyphs']
            if c['offset'] not in offsets and sign_verification_eligible(run['source'],c['offset'],c['font'],body_font))
    selected = {(c['font'],c['source_code']) for r in runs for c in r['verification_candidates']
                if isinstance(c['source_code'],int)}
    legacy_selected = {(c['font'],c['source_code']) for r in runs for c in r['verification_candidates']
                       if c.get('legacy_selected')}
    outline_report = verify_outlines(doc, runs) if runs else dict(model=OUTLINE_MODEL, seconds=0, records=[])
    if runs: outline_report['private_codes'] = verify_private_codes(doc, runs)
    # Rule R2: a code its outline names as a Greek letter, set alone in its face somewhere, is measured by
    # the raster verifier too (its decision, not this selection, says whether the letter changes).
    named = {(g['font'], g['source_code']) for g in outline_report.get('greek_named', [])}
    selected |= {(c['font'], c['source_code']) for r in runs for c in r['font_glyphs']
                 if (c['font'], c['source_code']) in named and c.get('alone')}
    # A code denotes the same glyph even on a page where its face is common,
    # or inside a word. Decide once, and check/apply every occurrence of it.
    for run in runs:
        run['verification_candidates'] = [dict(c,legacy_selected=(c['font'],c['source_code']) in legacy_selected)
                                           for c in run.pop('font_glyphs')
                                           if (c['font'],c['source_code']) in selected and c['before'] != '\ufffd']
    return pages, runs, unverified, outline_report


def sample_runs(runs):
    """Round-robin character classes and spread page locations; cap PER FONT."""
    fonts = collections.defaultdict(lambda: collections.defaultdict(list))
    for index, run in enumerate(runs):
        for font, ch in sorted({(c['font'], c['before']) for c in run['candidates']}):
            fonts[font][ch].append(index)
    selected = collections.defaultdict(set)
    for font, classes in sorted(fonts.items()):
        # Long runs with multiple candidates remain one independent observation.
        queues = {}
        for ch, indices in sorted(classes.items()):
            # Evenly spread the candidates before taking a prefix, so one local
            # table or repeated page header does not consume the entire sample.
            order = sorted(range(len(indices)), key=lambda i: (i % max(1, len(indices)//12), i))
            queues[ch] = [indices[i] for i in order]
        while len(selected[font]) < 12 and any(queues.values()):
            for ch in sorted(queues):
                while queues[ch] and queues[ch][0] in selected[font]: queues[ch].pop(0)
                if queues[ch] and len(selected[font]) < 12: selected[font].add(queues[ch].pop(0))
    return {font: sorted(indices) for font, indices in selected.items()}


def recognize(task, scratch, binary, data, libs):
    result = dict(status='unresolved', readings=[])
    with tempfile.TemporaryDirectory(dir=scratch, prefix='run-') as temp:
        path = Path(temp)/'crop.ppm'
        try:
            x,y,w,h = task['crop_xywh']
            subprocess.run(['pdftoppm','-cropbox','-f',str(task['page']),'-l',str(task['page']),
                            '-singlefile','-r','300','-x',str(x),'-y',str(y),'-W',str(w),'-H',str(h),
                            task['pdf'],str(path.with_suffix(''))],check=True,capture_output=True,timeout=30)
            original = signs.ppm_read(path)
            width,height,pixels = signs.upright(*original, task['angle'])
            # White OCR border avoids a tight glyph box being treated as a crop
            # edge; it adds no strokes and does not alter alignment or evidence.
            border = 10; white = b'\xff' * ((width+2*border)*3)
            pixels = white*border + b''.join(b'\xff'*(border*3)+pixels[y*width*3:(y+1)*width*3]+b'\xff'*(border*3) for y in range(height)) + white*border
            path.write_bytes(f'P6\n{width+2*border} {height+2*border}\n255\n'.encode()+pixels)
            env = dict(os.environ, OMP_THREAD_LIMIT='1')
            env['LD_LIBRARY_PATH'] = str(libs)+(os.pathsep+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
            output = Path(temp)/'ocr'
            subprocess.run([str(binary),str(path),str(output),'--tessdata-dir',str(data),'-l','eng',
                            '--psm','7','-c','tessedit_create_tsv=1','-c','tessedit_create_hocr=1',
                            '-c','hocr_char_boxes=1'],check=True,capture_output=True,text=True,env=env,timeout=30)
            words = signs.tsv_words(output.with_suffix('.tsv').read_text())
            result.update(status='read', reading=' '.join(w for w,c in words), words=words)
            readings = spatial_readings(task, output.with_suffix('.hocr').read_text(), original, border)
            # Equality must have two separate horizontal bars; this prevents
            # treating OCR's '=' for a printed plus/minus as font evidence.
            by_offset = {c['offset']:c for c in task['candidates']}
            result['readings'] = []
            result['rejected'] = []
            for r in readings:
                c = by_offset[r['offset']]
                if r['reading'] == '=' and signs.arithmetic_shape(original,c['box_px'],task['crop_xywh'],task['boxer_dpi'],task['angle']) != '=':
                    result['rejected'].append(dict(r,reason='glyph is not two separate horizontal bars')); continue
                if r['reading'] in '<>≤≥' and comparator_bar(task,c,original) != (r['reading'] in '≤≥'):
                    result['rejected'].append(dict(r,reason='comparison underline disagrees with OCR')); continue
                result['readings'].append(r)
        except (ValueError, ET.ParseError) as exc: result['reason'] = str(exc)
        except (OSError, subprocess.SubprocessError) as exc:
            result.update(status='error', reason=f'{type(exc).__name__}: {exc}')
    return result


def local_box(task, box, image, border=0):
    """Boxer glyph -> upright OCR crop coordinates (same scale as its pixels)."""
    x,y,_,_ = task['crop_xywh']; width,height,_ = image; scale=300/task['boxer_dpi']
    points=[]
    for u,v in ((box[0],box[1]),(box[2],box[1]),(box[2],box[3]),(box[0],box[3])):
        u,v=u*scale-x,v*scale-y
        u,v={0:(u,v),90:(height-v,u),180:(width-u,height-v),270:(v,width-u)}[task['angle']]
        points.append((u+border,v+border))
    return [min(u for u,v in points),min(v for u,v in points),max(u for u,v in points),max(v for u,v in points)]


def spatial_readings(task, hocr, image, border):
    """Align actual OCR character boxes, with unchanged nearby glyph anchors.

    English OCR sometimes adds a letter before zero or loses a decimal point.
    Text edit-distance alone can then attach a sign to the wrong native glyph.
    Require a unique overlapping OCR box and native anchors on each available
    side; OCR never supplies the native numbers or punctuation themselves.
    """
    recognized=[]
    for e in ET.fromstring(hocr).iter():
        if e.get('class') != 'ocrx_cinfo': continue
        match=re.search(r'x_bboxes (\d+) (\d+) (\d+) (\d+); x_conf ([\d.]+)',e.get('title',''))
        if match and len(e.text or '') == 1:
            recognized.append(dict(text=e.text.replace('μ','µ').replace('⩽','≤').replace('⩾','≥'),
                                   box=list(map(int,match.groups()[:4])),confidence=float(match[5])))
    def overlaps(a,b):
        area=max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
        aa=max(1,(a[2]-a[0])*(a[3]-a[1]));bb=max(1,(b[2]-b[0])*(b[3]-b[1]))
        return area/max(aa,bb) >= .45 and area/min(aa,bb) >= .75
    aligned={}
    for glyph in task['glyphs']:
        box=local_box(task,glyph['box_px'],image,border)
        matches=[r for r in recognized if overlaps(box,r['box'])]
        if len(matches)==1: aligned[glyph['offset']]=matches[0]
    offsets=[g['offset'] for g in task['glyphs']]; source=task['source']
    candidates={c['offset'] for c in task['candidates']};result=[]
    for offset in candidates:
        r=aligned.get(offset)
        if r is None or r['confidence'] < 90 or r['text'] not in SIGNS | {source[offset]}: continue
        i=offsets.index(offset); anchored=True
        anchors=0
        for side in (offsets[max(0,i-4):i],offsets[i+1:i+5]):
            known=[j for j in side if source[j] != '�' and
                   (j not in candidates or j in aligned and aligned[j]['text']==source[j])]
            if known and not any(j in aligned and aligned[j]['text']==source[j] for j in known): anchored=False
            anchors+=sum(j in aligned and aligned[j]['text']==source[j] for j in known)
        isolated = len(offsets) == len(recognized) == 1 and r['text'] in SIGNS
        if anchored and (anchors or isolated):
            result.append(dict(offset=offset,reading=r['text'],confidence=r['confidence']))
    return result


def comparator_bar(task, candidate, image):
    """Veto a lost equality stroke, horizontal OR slanted (U+2A7D/U+2A7E)."""
    width,height,pixels=signs.upright(*image,task['angle'])
    box=local_box(task,candidate['box_px'],image)
    x0,y0,x1,y1=[round(v) for v in box]
    ink=[(x,y) for y in range(max(0,y0),min(height,y1+1)) for x in range(max(0,x0),min(width,x1+1))
         if min(pixels[(y*width+x)*3:(y*width+x+1)*3]) < 160]
    if not ink: return None
    left,right=min(x for x,y in ink),max(x for x,y in ink)
    top,bottom=min(y for x,y in ink),max(y for x,y in ink)
    rows=collections.Counter(y for x,y in ink)
    if any(rows[y] >= .7*(right-left+1) for y in range(round(top+.7*(bottom-top)),bottom+1)): return True
    remaining=set(ink);components=[]
    while remaining:
        todo=[remaining.pop()];component=[]
        while todo:
            x,y=todo.pop();component.append((x,y))
            for dx,dy in ((-1,-1),(0,-1),(1,-1),(-1,0),(1,0),(-1,1),(0,1),(1,1)):
                point=x+dx,y+dy
                if point in remaining: remaining.remove(point);todo.append(point)
        components.append(component)
    components.sort(key=len,reverse=True)
    return len(components)>1 and len(components[1]) >= .15*len(components[0])


def components(points, diagonal=True):
    remaining = set(points); groups = []
    steps = [(x,y) for x in (-1,0,1) for y in (-1,0,1)
             if (x or y) and (diagonal or not x or not y)]
    while remaining:
        todo = [remaining.pop()]; group = set(todo)
        while todo:
            x,y = todo.pop()
            for dx,dy in steps:
                point = x+dx,y+dy
                if point in remaining:
                    remaining.remove(point); group.add(point); todo.append(point)
        groups.append(group)
    return sorted(groups, key=len, reverse=True)


def skeleton_ends(ink):
    """Count terminal arms after topology-preserving Zhang-Suen thinning."""
    ink = set(ink)
    offsets = [(0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1)]
    for _ in range(100):
        changed = False
        for phase in (0,1):
            remove = set()
            for x,y in ink:
                p = [(x+dx,y+dy) in ink for dx,dy in offsets]
                if not 2 <= sum(p) <= 6 or sum(not p[i] and p[(i+1)%8] for i in range(8)) != 1: continue
                if phase == 0 and (p[0] and p[2] and p[4] or p[2] and p[4] and p[6]): continue
                if phase == 1 and (p[0] and p[2] and p[6] or p[0] and p[4] and p[6]): continue
                remove.add((x,y))
            if remove: ink -= remove; changed = True
        if not changed: break
    return [(x,y) for x,y in ink if sum((x+dx,y+dy) in ink for dx,dy in offsets) == 1]


def raster_symbols(image, em, baseline):
    """Conservative vetoes, not a recognizer: OCR must independently agree.

    Check descender/stem geometry for micro; an elevated hollow ring for degree;
    a ring with an internal R for registered; at least five star arms at the
    x-height top; one flat crest-then-trough wave above the baseline for a
    tilde; and an actual separate lower bar for an inclusive comparator.
    Unknown, undersampled or ambiguous outlines return no candidates.
    """
    width,height,pixels = image
    if not math.isfinite(em) or em <= 0 or width*height > 100000: return []
    raw = {(i%width,i//width) for i in range(width*height) if min(pixels[i*3:i*3+3]) < 160}
    if len(raw) < 8: return []
    x0,y0 = min(x for x,y in raw),min(y for x,y in raw)
    w,h = max(x for x,y in raw)-x0+1,max(y for x,y in raw)-y0+1
    ink = {(x-x0,y-y0) for x,y in raw}; baseline -= y0
    groups = [g for g in components(ink) if len(g) >= 2]
    holes = [g for g in components({(x,y) for x in range(w) for y in range(h)}-ink, False)
             if all(0 < x < w-1 and 0 < y < h-1 for x,y in g) and len(g) >= 2]
    result = []
    rows = collections.Counter(y for x,y in ink)
    # Two stems start at roughly the same height, with a white trough between.
    left = [(x,y) for x,y in ink if x < .4*w]
    right = [(x,y) for x,y in ink if x > .6*w]
    top_middle = sum(.35*w < x < .65*w and y < .35*h for x,y in ink)
    if (len(groups) == 1 and not holes and .25*em < w < .95*em and .4*em < h < 1.05*em
        and .45*h < baseline < .88*h and left and right and top_middle < .06*w*h
        and abs(min(y for x,y in left)-min(y for x,y in right)) < .15*h
        and max(y for x,y in left)-max(y for x,y in right) > .12*h): result.append('µ')
    # A double-bar marker has two separate, equally tall straight stems.
    # Dotted i, equals and the two crossed strokes of a dagger fail this gate.
    if len(groups) == 2 and not holes and .15 < w/h < .8 and h < 1.2*em:
        bounds = [(min(x for x,y in g),min(y for x,y in g),max(x for x,y in g),max(y for x,y in g))
                  for g in groups]
        if (all(x1-x0+1 <= .2*h and y1-y0+1 >= .85*h for x0,y0,x1,y1 in bounds) and
            abs(bounds[0][1]-bounds[1][1]) <= .1*h and abs(bounds[0][3]-bounds[1][3]) <= .1*h):
            result.append('‖')
    if (.75 < w/h < 1.3 and w < .5*em and h < .5*em and h < baseline-.28*em
        and len(groups) == 1 and len(holes) == 1 and len(holes[0]) > .18*w*h): result.append('°')
    # An enclosing circular outline must cover every angular sector. Internal
    # ink must have the left stem, upper bowl and lower-right leg of an R.
    if .75 < w/h < 1.3 and .55*em < w < 1.2*em and .55*em < h < 1.2*em:
        sectors = set(); inner = set()
        for x,y in ink:
            u,v = (2*x+1-w)/w,(2*y+1-h)/h
            radius = math.hypot(u,v)
            if .78 <= radius <= 1.15: sectors.add(int((math.atan2(v,u)+math.pi)*12/math.pi)%24)
            if radius < .6: inner.add((x,y))
        stem = sum(any((x,y) in inner for x in range(round(.25*w),round(.46*w)))
                   for y in range(round(.25*h),round(.76*h)))
        bowl = sum(x > .5*w and y < .5*h for x,y in inner)
        leg = sum(x > .5*w and y > .55*h for x,y in inner)
        # At small sizes antialiasing can open a one-pixel gap in the ring;
        # angular coverage and the inner R are more stable than flood-fill holes.
        if len(sectors) >= 23 and stem >= .35*h and bowl >= 2 and leg >= 2: result.append('®')
    # Asterisk/X topology is used only after size and vertical placement gates.
    if len(groups) == 1 and not holes and .2*em < w < .8*em and .2*em < h < .8*em:
        ends = skeleton_ends(ink)
        if 5 <= len(ends) <= 8 and h < baseline-.2*em: result.append('*')
        if (len(ends) == 4 and .7 < w/h < 1.4 and
            all(abs(x-(w-1)/2) > .25*w and abs(y-(h-1)/2) > .25*h for x,y in ends)):
            result.append('×')
    # A tilde operator is one flat wave on the math axis, wholly above the
    # baseline: its column centres rise to a crest in the left part and fall
    # to a trough in the right part, and both ends turn back. A dash is flat,
    # an approximately-equal sign has two strokes, two-part punctuation two parts.
    if (len(groups) == 1 and not holes and 1.6 < w/h < 6 and .25*em < w < 1.2*em and
            h < .4*em and h-1 < baseline-.05*em and baseline < .8*em):
        columns = collections.defaultdict(list)
        for x,y in ink: columns[x].append(y)
        def centre(lo, hi):
            values = [sum(ys)/len(ys) for x,ys in columns.items() if lo*w <= x < hi*w]
            return sum(values)/len(values) if values else None
        left,crest,trough,right = centre(0,.12),centre(.18,.38),centre(.62,.82),centre(.88,1.01)
        if (None not in (left,crest,trough,right) and trough-crest > .3*h and
                left-crest > .15*h and trough-right > .15*h): result.append('∼')
    # Reuse the stricter arithmetic stroke test on the isolated crop.
    arithmetic = signs.arithmetic_shape(image,[0,0,width,height],[0,0,width,height],300,0)
    if not holes and ((arithmetic == '−' and len(groups) == 1) or
                      (arithmetic == '+' and len(groups) == 1) or
                      (arithmetic in ('±','=') and len(groups) == 2)):
        result.append(arithmetic)
    if not holes and 1 <= len(groups) <= 2 and .3*em < w < 1.1*em and baseline < .95*em:
        angle = groups[0]; bar = None
        if len(groups) == 2:
            upper,lower = sorted(groups, key=lambda g:min(y for x,y in g))
            bw = max(x for x,y in lower)-min(x for x,y in lower)+1
            bh = max(y for x,y in lower)-min(y for x,y in lower)+1
            # Includes slanted bars, but requires separation from the chevron.
            if bw >= .7*w and bw >= 1.5*bh and min(y for x,y in lower) > min(y for x,y in upper)+.4*h:
                angle,bar = upper,lower
            else: angle = set()
        if angle:
            top,bottom = min(y for x,y in angle),max(y for x,y in angle)
            ah = bottom-top+1
            bands = [[x for x,y in angle if a <= (y-top)/ah < b] for a,b in ((0,.2),(.4,.6),(.8,1.01))]
            if all(bands) and .4*w < ah < 2*w:
                centers = [sum(b)/len(b) for b in bands]
                direction = '<' if centers[0]-centers[1] > .25*w and centers[2]-centers[1] > .25*w else (
                    '>' if centers[1]-centers[0] > .25*w and centers[1]-centers[2] > .25*w else None)
                if direction: result.append({'<':'≤','>':'≥'}[direction] if bar else direction)
    return sorted(set(result))


def isolate_glyph(image, box, neighbours, dpi):
    """Slice exactly the glyph box plus 2 px; never feed neighbour ink to OCR."""
    width,height,pixels = image
    crop = signs.shapes.crop_rectangle(box,dpi)
    x,y,w,h = crop
    if x+w > width or y+h > height: raise ValueError('glyph crop outside rendered page')
    data = bytearray(b''.join(pixels[(v*width+x)*3:(v*width+x+w)*3] for v in range(y,y+h)))
    scale = 300/dpi
    # The margin is white padding, not permission to include a neighbour's
    # antialiased fringe just outside its geometric box.
    own = [math.floor(box[0]*scale)-x,math.floor(box[1]*scale)-y,
           math.ceil(box[2]*scale)-x,math.ceil(box[3]*scale)-y]
    if min(own[:2]) < 0 or own[2] > w or own[3] > h: raise ValueError('clipped glyph box')
    for v in range(h):
        if not own[1] <= v < own[3]: data[v*w*3:(v+1)*w*3] = b'\xff'*(w*3)
        else:
            data[v*w*3:(v*w+own[0])*3] = b'\xff'*(own[0]*3)
            data[(v*w+own[2])*3:(v+1)*w*3] = b'\xff'*((w-own[2])*3)
    for b in neighbours:
        if min(box[2],b[2])-max(box[0],b[0]) > .25 and min(box[3],b[3])-max(box[1],b[1]) > .25:
            raise ValueError('overlapping neighbour glyph')
        left,top = max(0,math.floor(b[0]*scale)-x),max(0,math.floor(b[1]*scale)-y)
        right,bottom = min(w,math.ceil(b[2]*scale)-x),min(h,math.ceil(b[3]*scale)-y)
        if left >= right or top >= bottom: continue
        for v in range(top,bottom): data[(v*w+left)*3:(v*w+right)*3] = b'\xff'*((right-left)*3)
    return crop,(w,h,bytes(data))


def single_read(path, whitelist, binary, data, libs):
    env = dict(os.environ, OMP_THREAD_LIMIT='1')
    env['LD_LIBRARY_PATH'] = str(libs)+(os.pathsep+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    output = subprocess.run([str(binary),str(path),'stdout','--tessdata-dir',str(data),'-l','eng',
                             '--psm','10','-c','tessedit_char_whitelist='+whitelist,'tsv'],
                            check=True,capture_output=True,text=True,env=env,timeout=5)
    try: words = signs.tsv_words(output.stdout)
    except ValueError as exc:
        if str(exc) != 'OCR returned no words': raise
        return dict(text='',confidence=0.0,status='empty')
    if len(words) != 1 or len(words[0][0]) != 1 or words[0][0] not in whitelist:
        return dict(text='',confidence=0.0,status='not-single-character')
    return dict(text=words[0][0],confidence=words[0][1],status='read')


def symbol_decision(before, symbol, letter, shapes, whitelist=SYMBOL_WHITELIST):
    """Empty readings cannot win; errors and invalid confidences fail closed."""
    for reading in (symbol,letter):
        conf = reading.get('confidence')
        if (reading.get('status') not in ('read','empty','not-single-character') or
            not isinstance(conf,(int,float)) or not math.isfinite(conf) or not 0 <= conf <= 100):
            return None,'invalid OCR evidence'
        if reading.get('status') != 'read' and (conf or reading.get('text')): return None,'invalid empty reading'
    if letter['status'] == 'read' and letter.get('text') != before: return None,'wrong native whitelist reading'
    after = symbol.get('text')
    if symbol['status'] != 'read' or not isinstance(after,str) or len(after) != 1 or after not in whitelist:
        return None,'no single symbol reading'
    if symbol['confidence'] < 75: return None,'symbol confidence below 75'
    if symbol['confidence']-letter['confidence'] < 15: return None,'confidence margin below 15'
    if after not in shapes: return None,'raster disagrees with symbol'
    return after,'accepted'


def comparison_decision(reading, shapes):
    """Confirm a comparison's lower stroke before accepting occurrence OCR.

    The chevron direction must match the isolated glyph. A separately visible
    horizontal or slanted lower stroke upgrades < or > to ≤ or ≥. A missing,
    ambiguous or contradictory shape is an abstention, never a strict sign.
    Native text is not evidence. Keep the symbol pass's confidence floor of 75.
    """
    conf = reading.get('confidence')
    if (reading.get('status') != 'read' or not isinstance(conf,(int,float)) or
        not math.isfinite(conf) or not 75 <= conf <= 100):
        return None, 'comparison OCR confidence below 75 or invalid'
    after = reading.get('text')
    if after not in ('<','>','≤','≥'): return None, 'not a comparison reading'
    direction = '<' if after in '<≤' else '>'
    inclusive = {'<':'≤','>':'≥'}[direction]
    choices = set(shapes) & {direction,inclusive}
    if len(choices) != 1: return None, 'comparison lower bar is undecided'
    decision = next(iter(choices))
    if after in '≤≥' and decision == direction:
        return None, 'OCR lower bar disagrees with raster'
    return decision, 'comparison lower bar confirmed'


def recognize_symbol_page(task, scratch, binary, data, libs):
    """One raster per page; all decisions remain attached to native occurrences."""
    records = []; cache = {}
    with tempfile.TemporaryDirectory(dir=scratch,prefix='symbols-') as temp:
        path = Path(temp)/'page.ppm'
        subprocess.run(['pdftoppm','-cropbox','-f',str(task['page']),'-l',str(task['page']),
                        '-singlefile','-r','300',task['pdf'],str(path.with_suffix(''))],
                       check=True,capture_output=True,timeout=10)
        image = signs.ppm_read(path); path.unlink()
        for run in task['runs']:
            for c in run['symbol_candidates']:
                r = dict(c,page=run['page'],id=run['id'],source=run['source'],model=SYMBOL_MODEL,
                         status='unresolved',after=None)
                records.append(r)
                if run['angle'] != 0:
                    r['reason'] = 'rotated glyph needs a baseline transform'; continue
                try:
                    # Bounding boxes also exclude neighbours belonging to other runs.
                    neighbours = [b for cid,b in task['boxes'] if cid != c['char_id'] and
                                  b[0] < c['box_px'][2]+2 and b[2] > c['box_px'][0]-2 and
                                  b[1] < c['box_px'][3]+2 and b[3] > c['box_px'][1]-2]
                    crop,glyph = isolate_glyph(image,c['box_px'],neighbours,run['boxer_dpi'])
                    baseline = c['origin_px'][1]*300/run['boxer_dpi']-crop[1]
                    shapes = raster_symbols(glyph,c['em'],baseline)
                    r.update(crop_xywh=crop,raster_symbols=shapes)
                    if not shapes:
                        r['reason'] = 'raster matches no supported symbol'; continue
                    key = (glyph,c['before'])
                    if key not in cache:
                        w,h,pixels = glyph; path.write_bytes(f'P6\n{w} {h}\n255\n'.encode()+pixels)
                        cache[key] = (single_read(path,SYMBOL_WHITELIST,binary,data,libs),
                                      single_read(path,c['before'],binary,data,libs))
                        path.unlink()
                    symbol,letter = cache[key]
                    after,reason = symbol_decision(c['before'],symbol,letter,shapes)
                    r.update(after=after,reason=reason,symbol_ocr=symbol,letter_ocr=letter,
                             symbol_confidence=symbol['confidence'],letter_confidence=letter['confidence'],
                             margin=symbol['confidence']-letter['confidence'])
                    if after: r['status'] = 'accepted'
                except ValueError as exc: r['reason'] = str(exc)
                except (OSError,subprocess.SubprocessError) as exc:
                    r.update(status='error',reason=f'{type(exc).__name__}: {exc}')
    return records


def verify_page(task, scratch, evidence_dir):
    """Measure every suspect occurrence; retain small isolated crops for audit."""
    from PIL import Image
    records = []
    # Context selection can include a body face. Index neighbours by vertical
    # strip so measuring a dense page is not quadratic in its character count.
    strips = collections.defaultdict(dict)
    for cid,box in task['boxes']:
        for strip in range(math.floor(box[1]/32),math.floor(box[3]/32)+1):
            strips[strip][cid] = box
    with tempfile.TemporaryDirectory(dir=scratch,prefix='verify-') as temp:
        path = Path(temp)/'page.ppm'
        subprocess.run(['pdftoppm','-cropbox','-f',str(task['page']),'-l',str(task['page']),
                        '-singlefile','-r','300',task['pdf'],str(path.with_suffix(''))],
                       check=True,capture_output=True,timeout=30)
        image = signs.ppm_read(path); path.unlink()
        for run in task['runs']:
            for c in run['verification_candidates']:
                r = dict(c,page=run['page'],id=run['id'],source=run['source'],model=VERIFY_MODEL,
                         status='unresolved',after=None)
                records.append(r)
                try:
                    nearby = {}
                    for strip in range(math.floor((c['box_px'][1]-2)/32),math.floor((c['box_px'][3]+2)/32)+1):
                        nearby.update(strips.get(strip,{}))
                    neighbours = [b for cid,b in nearby.items() if cid != c['char_id'] and
                                  b[0] < c['box_px'][2]+2 and b[2] > c['box_px'][0]-2 and
                                  b[1] < c['box_px'][3]+2 and b[3] > c['box_px'][1]-2]
                    crop,glyph = isolate_glyph(image,c['box_px'],neighbours,run['boxer_dpi'])
                    glyph = signs.upright(*glyph,run['angle'])
                    latin = c['before'].isascii() and c['before'].isalpha()
                    marker_font = bool(SIGN_FONT.search(re.sub(r'^[A-Z]{6}\+', '', c['font'])))
                    alternatives = (SIGN_ALTERNATIVES if sign_like(c['before']) else
                                    ALTERNATIVES+(MARKERS if marker_font else '') if latin else '')
                    competitive = bool(alternatives)
                    scores = shape_similarities(glyph,''.join(dict.fromkeys(c['before']+alternatives)))
                    r.update(scores[c['before']],crop_xywh=crop,status='measured')
                    r['marker_font'] = marker_font
                    if competitive:
                        r['alternatives'] = {ch:result['similarity'] for ch,result in scores.items() if ch != c['before']}
                    w,h,pixels = glyph
                    coloured = sum(max(pixels[i:i+3])-min(pixels[i:i+3]) > 40 for i in range(0,len(pixels),3))
                    ink = {(i%w,i//w) for i in range(w*h) if min(pixels[3*i:3*i+3]) < 160}
                    x0,x1 = min(x for x,y in ink),max(x for x,y in ink)
                    y0,y1 = min(y for x,y in ink),max(y for x,y in ink)
                    if sign_claim(c['before']):
                        wide_rows = sorted(y for y,count in collections.Counter(y for x,y in ink).items()
                                           if count >= .7*(x1-x0+1))
                        r['horizontal_bands'] = sum(i==0 or y>wide_rows[i-1]+1 for i,y in enumerate(wide_rows))
                    if c['before'] in PUNCTUATION_SIGNS:
                        # The claim's own structure: two separate ink parts.
                        r['ink_parts'] = sum(len(g) >= 2 for g in components(ink))
                    # Reversed signs can lose one corner where a white stroke
                    # touches the crop edge; three dark corners still expose
                    # the background. Keep the established letter criterion.
                    corners = sum((x,y) in ink for x in (x0,x1) for y in (y0,y1))
                    rectangle = (r['aspect'] > .3 and r['ink_share'] > .55 and
                                 corners >= (3 if sign_claim(c['before']) else 4))
                    # Thin solid strokes/dots are ordinary sign silhouettes,
                    # not reversed figure backgrounds. Keep the original veto
                    # for letters and for backgrounds with internal light strokes.
                    # A solid dash/dot has no such holes; reversed white text does.
                    sign_rectangle = (sign_claim(c['before']) and len(ink) == (x1-x0+1)*(y1-y0+1) and
                                      (x1-x0 < .8*c['em'] or y1-y0 < .8*c['em']))
                    if coloured > .02*w*h or rectangle and not sign_rectangle:
                        r.update(status='uncalibrated',reason='coloured or reversed figure glyph')
                    if c['before'] == '◦' and run['angle'] == 0:
                        r['position_rejection'] = temperature_ring(run,c,r)
                    if run['angle'] == 0:
                        baseline = c['origin_px'][1]*300/run['boxer_dpi']-crop[1]
                        r['raster_symbols'] = raster_symbols(glyph,c['em'],baseline)
                    else: r['raster_symbols'] = []
                    key = hashlib.sha256(str(glyph[:2]).encode()+glyph[2]).hexdigest()[:24]
                    target = Path(evidence_dir)/(key+'.png')
                    if not target.exists(): Image.frombytes('RGB',glyph[:2],glyph[2]).save(target)
                    r['crop'] = str(target)
                except ValueError as exc: r['reason'] = str(exc)
    return records


def temperature_ring(run, candidate, measurement):
    """A raised hollow ring between a number and a unit is not a list bullet.

    The PDF may map it to U+25E6, which the copy formatter consumes as a list
    marker. Retain its position as U+FFFD, without inferring a degree reading
    from context alone. Compare the ring with the adjacent unit's actual box;
    a superscript's own baseline cannot establish elevation above body text.
    """
    offset = candidate['offset']; source = run['source']
    unit = re.match(r'\s*([CF])\b',source[offset+1:])
    if not unit or not re.search(r'\d\s*$',source[:offset]): return None
    following = next((g for g in run['glyphs'] if g['offset'] == offset+1+unit.start(1)),None)
    if following is None: return None
    x0,y0,x1,y1 = candidate['box_px']; u0,v0,u1,v1 = following['box_px']
    height = v1-v0
    if (height <= 0 or not 0 < y1-y0 < .65*height or
        not y0 < v0+.4*height or not y1 < v0+.65*height or
        not -.1*height <= u0-x1 <= .6*height or
        not .7 <= measurement.get('aspect',0) <= 1.3 or
        not .15 <= measurement.get('ink_share',0) <= .6 or
        measurement.get('status') != 'measured' or measurement['similarity'] < .5): return None
    return dict(model=POSITION_MODEL,before='◦',after='\ufffd',
                ring_box=candidate['box_px'],unit_box=following['box_px'],unit_offset=following['offset'],
                similarity=measurement['similarity'],aspect=measurement['aspect'],ink_share=measurement['ink_share'])


def alternative_evidence(rows):
    """Reject a claim only when every measurable crop prefers one alternative.

    Require the same alternative to clear both the absolute floor and the
    margin on every valid occurrence. A true native occurrence or contradictory
    outline vetoes the font/code decision. Unmeasurable crops are not votes.
    """
    if not rows or any(not r.get('alternatives') for r in rows): return None
    # Two-part punctuation is rejected only when its raster contradicts the
    # claim's structure on every crop: not exactly two separate ink parts.
    if any(r.get('before') in PUNCTUATION_SIGNS and
           (not isinstance(r.get('ink_parts'),int) or r['ink_parts'] == 2) for r in rows): return None
    choices = []
    for ch in dict.fromkeys(ALTERNATIVES+SIGN_ALTERNATIVES):
        # A template must not win by ignoring a native sign's extra bar.
        # Some correctly mapped plus/minus designs connect the vertical stem
        # to the lower bar; normalized silhouettes then prefer a plain plus.
        # The two wide stroke bands still contradict that simpler reading.
        if ch in '+−<>·' and any(r.get('before') in ('±','=','≤','≥','≠') and
                                  r.get('horizontal_bands',0) >= 2 for r in rows): continue
        calibrated_floor = (SIGN_FLOOR if all(sign_like(r.get('before',' ')) for r in rows) or
                            ch in MARKERS and all(r.get('marker_font') for r in rows) else ALTERNATIVE_FLOOR)
        floor = min(r['alternatives'].get(ch,-1) for r in rows)
        margin = min(r['alternatives'].get(ch,-1)-r['similarity'] for r in rows)
        if floor >= calibrated_floor and margin >= ALTERNATIVE_MARGIN:
            choices.append((margin,floor,ch,calibrated_floor))
    if not choices: return None
    margin,floor,ch,calibrated_floor = max(choices)
    return dict(character=ch,minimum_similarity=floor,minimum_margin=margin,
                floor=calibrated_floor,margin=ALTERNATIVE_MARGIN,measured=len(rows))


def valid_alternative(proof):
    """Finite competing-shape evidence; naming also needs decisive_sign or OCR."""
    if not isinstance(proof,dict) or proof.get('character') not in set(ALTERNATIVES+SIGN_ALTERNATIVES): return False
    floor,margin = proof.get('minimum_similarity'),proof.get('minimum_margin')
    return (all(isinstance(v,(int,float)) and math.isfinite(v) for v in (floor,margin)) and
            proof.get('floor') in (SIGN_FLOOR,ALTERNATIVE_FLOOR) and proof['floor'] <= floor <= 1 and
            ALTERNATIVE_MARGIN <= margin <= 2 and proof.get('margin') == ALTERNATIVE_MARGIN and
            isinstance(proof.get('measured'),int) and proof['measured'] > 0)


def decisive_sign(before, alternative, rows):
    """Name only separated, independently stroke-checked signs or marker shapes.

    Each measured crop must support the same result. A marker also needs a
    sign face and separation from the other marker templates. This does not
    turn the broader Latin/common-sign diagnostic into an automatic edit.
    """
    if not valid_alternative(alternative): return None
    after = alternative['character']
    if alternative['minimum_similarity'] < SHAPE_FLOOR: return None
    if sign_like(before) and after in '±≤≥×':
        if (alternative['minimum_margin'] >= SHAPE_MARGIN and
            all(after in r.get('raster_symbols',[]) for r in rows)): return after
    if before.isascii() and before.isalpha() and after in MARKERS:
        if alternative['minimum_margin'] >= .25 and all(r.get('marker_font') and r['alternatives'][after] -
               max((v for ch,v in r['alternatives'].items() if ch != after),default=-1) >= .10
               and (after in r.get('raster_symbols',[]) or alternative['minimum_similarity'] >= .70)
               for r in rows): return after
    return None


def punctuation_structure(before, rows):
    """Two-part punctuation drawn as something else: name the drawn sign or flag.

    Every measured crop must contradict the claim twice: its ink is not exactly
    two separate parts, and the claim's own template scores below the 0.35
    confirmation floor. The drawn sign is named only when the independent
    stroke check finds exactly one sign on every crop and that sign is also the
    best template on every crop, beating the claim by the 0.20 margin.
    Otherwise the glyph is U+FFFD. Context never names a character.
    """
    if before not in PUNCTUATION_SIGNS or not rows: return None
    if any(not isinstance(r.get('ink_parts'),int) or r['ink_parts'] == 2 or
           not isinstance(r.get('similarity'),(int,float)) or not math.isfinite(r['similarity']) or
           r['similarity'] >= VERIFY_THRESHOLD for r in rows): return None
    shapes = [set(r.get('raster_symbols') or ()) for r in rows]
    if all(len(s) == 1 for s in shapes) and len(set.union(*shapes)) == 1:
        drawn = next(iter(shapes[0]))
        if all(isinstance(r.get('alternatives'),dict) and drawn in r['alternatives'] and
               r['alternatives'][drawn]-r['similarity'] >= ALTERNATIVE_MARGIN and
               r['alternatives'][drawn] >= max(r['alternatives'].values()) for r in rows):
            # A tilde's shape cannot tell the operator from the ASCII tilde;
            # write the plain form, valid in an approximate value and a URL.
            return '~' if drawn == '∼' else drawn
    return '�'


def measure_page(task, scratch, evidence_dir):
    """Keep real Pillow outside the reader process's standard-library PIL shim."""
    with tempfile.TemporaryDirectory(dir=scratch,prefix='measure-') as temp:
        path = Path(temp)/'task.json'
        path.write_text(json.dumps(dict(task=task,scratch=temp,evidence_dir=str(evidence_dir))))
        process = subprocess.run([sys.executable,'-I',str(Path(__file__).resolve()),'--verify-task',str(path)],
                                 capture_output=True,timeout=180,text=True)
        if process.returncode:
            raise ValueError(f"glyph measurement failed on page {task['page']}: {process.stderr[-2000:]}")
        return json.loads(path.with_suffix('.result.json').read_text())


def decide_verification(records, evidence, binary, data, libs, greek_named=None):
    """One decision per full font/code; any confirmed occurrence protects it.

    Empty OCR can never name a replacement. A calibrated shape failure may
    instead produce U+FFFD. Overlapping letter classes need independent OCR;
    unmeasurable crops and unsupported backgrounds never count as failures.
    """
    groups = collections.defaultdict(list); decisions = {}
    for r in records: groups[r['font'],r['source_code']].append(r)
    for (font,code),rows in sorted(groups.items()):
        claims = {r['before'] for r in rows}
        d = dict(model=VERIFY_MODEL,font=font,source_code=code,occurrences=len(rows),status='unresolved')
        decisions.setdefault(font,{})[str(code)] = d
        if len(claims) != 1:
            d['reason'] = 'one source code has multiple Unicode claims'; continue
        before = next(iter(claims)); d['before'] = before
        valid = [r for r in rows if r['status']=='measured']
        if not valid:
            d['reason'] = 'no isolated, calibrated raster'; continue
        best = max(valid,key=lambda r:r['similarity'])
        threshold = VERIFY_THRESHOLDS.get(before,VERIFY_THRESHOLD)
        d.update(similarity=best['similarity'],threshold=threshold,crop=best['crop'],
                 measured=len(valid),after=before)
        structure = punctuation_structure(before,valid)
        if structure:
            rows = [{k:r.get(k) for k in ('before','similarity','alternatives','raster_symbols','ink_parts')} for r in valid]
            d.update(status='rejected',after=structure,proof=dict(structure_rows=rows),
                     reason=('two-part punctuation claim drawn as one stroke-checked sign' if structure != '�'
                             else 'two-part punctuation claim contradicted by its drawn parts; no decisive sign'))
            continue
        competing = alternative_evidence(valid)
        decomposition = unicodedata.normalize('NFKD',before)
        attached_accent = (decomposition.startswith(' ') and len(decomposition) > 1 and
                           all(unicodedata.category(ch).startswith('M') for ch in decomposition[1:]) and
                           any(any(ch.isalpha() for ch in r['source'][max(0,r['offset']-1):r['offset']] +
                                   r['source'][r['offset']+1:r['offset']+2]) for r in rows))
        if competing and attached_accent:
            # A spacing accent beside a letter is composed by the formatter.
            # Tiny cedillas can resemble arrows after normalization; preserve
            # the native accent unless independent evidence rejects its shape.
            d.update(deferred_alternative=competing,
                     deferred_reason='spacing accent adjoining a letter needs independent evidence')
            competing = None
        if competing and before == '*':
            # Dense superscript asterisks in the calibration set can prefer a
            # dot silhouette (0.598 versus 0.309). Preserve the original
            # independent-OCR requirement for this known overlapping class.
            d.update(deferred_alternative=competing,
                     deferred_reason='asterisk styles overlap other signs; independent OCR required')
            competing = None
        # Rule R2: a Latin letter inside a word is replaced by a Greek letter when its embedded outline names
        # that letter (outline_greek), the raster's separated alternative is the same letter on every crop,
        # and every occurrence sits alone in its face (its neighbouring letters are in another face).
        named = (greek_named or {}).get((font, code))
        if (competing and named and before.isascii() and before.isalpha() and named.get('before') == before
                and competing['character'] == named.get('character') == outline_greek(before, named.get('scores', {}))
                and all(r.get('alone') is True for r in rows)):
            d.update(status='rejected', after=competing['character'], alternative=competing,
                     proof=dict(outline_greek=dict(character=named['character'], scores=named['scores']),
                                alone=len(rows)),
                     reason='Greek letter named by its embedded outline and its raster; alone in its face')
            continue
        marker = competing and competing['character'] in MARKERS and all(r.get('marker_font') for r in valid)
        named_marker = marker and decisive_sign(before,competing,valid)
        if competing and not sign_like(before) and (
                (competing['character'] not in 'αβγδεκλμπσχω' and not marker) or
                any(inside_word(r['source'],r['offset']) for r in rows) and not named_marker):
            # U+FFFD changes the copy formatter's word/heading/equation tests.
            # Calibration found paragraph reordering for operators and loss
            # of a true hyphen for a Greek prefix inside an identifier. Keep
            # the older policy until the formatter can classify native text
            # separately from its displayed, verified character stream.
            d.update(deferred_alternative=competing,
                     deferred_reason='new flag can change word/heading/equation layout')
            competing = None
        if best['similarity'] >= threshold and not competing:
            d.update(status='confirmed',reason='claimed shape confirmed'); continue
        if not competing and not any(r.get('legacy_selected',True) for r in rows):
            d['reason'] = 'context-selected letter has no separated alternative'; continue
        shape_after = decisive_sign(before,competing,valid) if competing else None
        if shape_after:
            proof_rows = [{k:r.get(k) for k in ('before','similarity','alternatives','raster_symbols','marker_font','horizontal_bands','ink_parts')} for r in valid]
            d.update(status='rejected',after=shape_after,alternative=competing,
                     proof=dict(shape_rows=proof_rows),reason='separated sign shape and stroke evidence')
            continue
        choices = {}; attempts = []
        prior = evidence.get(font,{}).get(before,{})
        if prior.get('status') == 'untrusted' and prior.get('after'):
            choices[prior['after']] = dict(legacy_ocr=prior)
        # At most three distinct isolated rasters. Agreement is by font/code,
        # not by how often one table happened to repeat the same image.
        seen = set()
        for r in sorted(valid,key=lambda r:r['similarity'],reverse=True):
            if r['crop'] in seen or not r.get('raster_symbols'): continue
            seen.add(r['crop'])
            if len(seen)>3: break
            symbol = single_read(Path(r['crop']),VERIFY_WHITELIST,binary,data,libs)
            letter = single_read(Path(r['crop']),before,binary,data,libs)
            after,reason = symbol_decision(before,symbol,letter,r['raster_symbols'],VERIFY_WHITELIST)
            attempt = dict(symbol_ocr=symbol,letter_ocr=letter,raster_symbols=r['raster_symbols'],
                           crop=r['crop'],after=after,reason=reason)
            attempts.append(attempt)
            if after and after != before: choices[after] = attempt
        d['ocr_attempts'] = attempts
        if len(choices) == 1:
            after,proof = next(iter(choices.items()))
            d.update(status='rejected',after=after,proof=proof,reason='shape rejected; OCR replacement')
            if competing: d['alternative'] = competing
        elif competing:
            d.update(status='rejected',after='\ufffd',alternative=competing,
                     reason='competing symbol beats claimed shape; no decisive replacement')
        elif before not in OVERLAPPING_CLASSES:
            if any(inside_word(r['source'],r['offset']) for r in rows):
                d.update(status='layout-protected',after=before,
                         reason='shape rejected; U+FFFD inside a word can change table/heading layout')
            else: d.update(status='rejected',after='\ufffd',reason='shape rejected; no accepted OCR replacement')
        else: d['reason'] = 'shape classes overlap; no agreeing OCR'
    return decisions


def valid_verification(proof, before, after):
    """Validate a saved decision again before the copy edits a character."""
    score = proof.get('similarity'); threshold = VERIFY_THRESHOLDS.get(before,VERIFY_THRESHOLD)
    if (proof.get('model') != VERIFY_MODEL or proof.get('before') != before or proof.get('after') != after or
        not isinstance(score,(int,float)) or not math.isfinite(score) or not -1 <= score <= 1 or
        proof.get('threshold') != threshold): return False
    structure_rows = proof.get('proof',{}).get('structure_rows')
    if structure_rows:
        return (proof.get('status') == 'rejected' and not proof.get('alternative') and
                score < threshold and punctuation_structure(before,structure_rows) == after)
    competing = proof.get('alternative')
    if competing:
        if (not (sign_like(before) or before.isascii() and before.isalpha()) or proof.get('status') != 'rejected' or
            not valid_alternative(competing)): return False
        if after == '\ufffd': return True
        greek = proof.get('proof',{}).get('outline_greek')
        if greek:   # rule R2
            return (isinstance(greek, dict) and before.isascii() and before.isalpha() and
                    competing['character'] == greek.get('character') == after and
                    outline_greek(before, greek.get('scores') or {}) == after and
                    isinstance(proof['proof'].get('alone'), int) and proof['proof']['alone'] > 0)
        shape_rows = proof.get('proof',{}).get('shape_rows')
        if shape_rows:
            return (alternative_evidence(shape_rows) == competing and
                    decisive_sign(before,competing,shape_rows) == after)
    if proof.get('status') == 'confirmed': return score >= threshold and after == before
    if proof.get('status') == 'layout-protected': return score < threshold and after == before
    if proof.get('status') != 'rejected' or (score >= threshold and not competing): return False
    if after == '\ufffd': return before not in OVERLAPPING_CLASSES
    evidence = proof.get('proof',{})
    prior = evidence.get('legacy_ocr',{})
    if prior:
        return (prior.get('after') == after and after in SIGNS and prior.get('status') == 'untrusted' and
                3 <= prior.get('wins',0) <= prior.get('samples',0) and prior['wins']/prior['samples'] >= .7)
    decision,_ = symbol_decision(before,evidence.get('symbol_ocr',{}),evidence.get('letter_ocr',{}),
                                evidence.get('raster_symbols',[]),VERIFY_WHITELIST)
    return decision is not None and decision == after


def decide(runs, selected):
    evidence = {}
    for font, indices in sorted(selected.items()):
        classes = collections.defaultdict(list)
        for index in indices:
            run = runs[index]; reads = {r['offset']:r['reading'] for r in run.get('readings',[])}
            for ch in sorted({c['before'] for c in run['candidates'] if c['font'] == font}):
                occurrences = [reads.get(c['offset']) for c in run['candidates'] if c['font'] == font and c['before'] == ch]
                # A run votes only when every aligned occurrence agrees; one
                # long row containing repeated signs cannot supply three votes.
                seen = set(occurrences)
                vote = next(iter(seen)) if len(seen) == 1 and None not in seen else None
                classes[ch].append(dict(page=run['page'], id=run['id'], vote=vote))
        evidence[font] = {}
        for ch, samples in sorted(classes.items()):
            votes = collections.Counter(s['vote'] for s in samples if s['vote'] in SIGNS)
            after, wins = votes.most_common(1)[0] if votes else (None, 0)
            accepted = wins >= 3 and wins / len(samples) >= .7
            evidence[font][ch] = dict(after=after if accepted else None, wins=wins, samples=len(samples),
                                       votes=samples, status='untrusted' if accepted else 'unchanged')
    return evidence


def apply_results(pages, runs, evidence, symbol_records=(), verification_records=(), verification=None):
    substitutions = []
    for _, page in pages.values():
        for font, summary in page['fonts'].items(): summary['checks'] = evidence.get(font,{})
        for e in page['elements']: e.pop('font_subs', None)
    for run in runs:
        e = pages[run['file']][1]['elements'][run['index']]
        subs = []
        for candidate in run['candidates']:
            proof = evidence.get(candidate['font'],{}).get(candidate['before'],{})
            if not proof.get('after'): continue
            sub = {k:candidate[k] for k in ('offset','char_id','before','font')}
            sub.update(after=proof['after'], wins=proof['wins'], samples=proof['samples'])
            subs.append(sub)
            substitutions.append(dict(page=run['page'],id=run['id'],source=run['source'],crop_xywh=run['crop_xywh'],
                                      angle=run['angle'],**sub))
        if subs: e['font_subs'] = subs
    elements = {(p['page'],e['id']):e for _,p in pages.values() for e in p['elements']}
    for record in symbol_records:
        if record['status'] != 'accepted': continue
        e = elements[record['page'],record['id']]
        if any(s['offset'] == record['offset'] for s in e.get('font_subs',[])):
            record.update(status='existing-font-substitution',reason='already accepted by repeated-run check')
            continue
        keys = ('offset','char_id','before','after','font','model','symbol_ocr','letter_ocr',
                'symbol_confidence','letter_confidence','margin','raster_symbols','crop_xywh')
        sub = {k:record[k] for k in keys}
        e.setdefault('font_subs',[]).append(sub)
        substitutions.append(dict(sub,page=record['page'],id=record['id'],source=record['source']))
    for record in verification_records:
        proof = (verification or {}).get(record['font'],{}).get(str(record['source_code']),{})
        after = proof.get('after')
        if not valid_verification(proof,record['before'],after): continue
        e = elements[record['page'],record['id']]
        e['font_subs'] = [s for s in e.get('font_subs',[]) if s['offset'] != record['offset']]
        substitutions = [s for s in substitutions if (s['page'],s['id'],s['offset']) !=
                         (record['page'],record['id'],record['offset'])]
        # Confirmation has already vetoed any earlier OCR edit at this offset.
        # Its font/code proof and occurrence raster remain in the reports;
        # serializing thousands of no-op font_subs bloats every copy's input.
        if proof['status'] == 'confirmed': continue
        sub = {k:record[k] for k in ('offset','char_id','before','font','source_code')}
        sub.update(after=after,model=VERIFY_MODEL,similarity=proof['similarity'],
                   threshold=proof['threshold'],status=proof['status'],crop=record.get('crop'))
        e['font_subs'].append(sub)
        if after != record['before']:
            substitutions.append(dict(sub,page=record['page'],id=record['id'],source=record['source']))
    for record in verification_records:
        position = record.get('position_rejection')
        if not position: continue
        e = elements[record['page'],record['id']]
        sub = {k:record[k] for k in ('offset','char_id','before','font','source_code','crop')}
        sub.update(after='\ufffd',model=POSITION_MODEL,position=position)
        e['font_subs'] = [s for s in e.get('font_subs',[]) if s['offset'] != record['offset']]+[sub]
        substitutions = [s for s in substitutions if (s['page'],s['id'],s['offset']) !=
                         (record['page'],record['id'],record['offset'])]
        substitutions.append(dict(sub,page=record['page'],id=record['id'],source=record['source']))
    for _,page in pages.values():
        for font,summary in page['fonts'].items():
            summary['verification'] = (verification or {}).get(font,{})
            summary.pop('outline_verification', None)
            summary.pop('private_codes', None)
        for e in page['elements']: e.pop('outline_warnings', None)
    for run in runs:
        page = pages[run['file']][1]; e = page['elements'][run['index']]
        for c, record in run.pop('outline_records', []):
            proof = {k: record[k] for k in ('model', 'font', 'source_code', 'before', 'after', 'status', 'scores')}
            for key in ('outline', 'geometry', 'symbol_font', 'sign_claim', 'small_face', 'face_codes', 'text_face', 'extent',
                        'greek_face', 'ligature', 'named_mismatch'):
                if key in record: proof[key] = record[key]
            page['fonts'][c['font']].setdefault('outline_verification', {})[str(c['source_code'])] = proof
            sub = {k: c[k] for k in ('offset', 'char_id', 'before', 'font', 'source_code')}
            sub.update(model=OUTLINE_MODEL, after=record['after'], status=record['status'])
            if record.get('ligature') is True:   # one glyph, several letters: the sign once, then nothing
                sub.update(ligature_index=c['ligature_index'], after=record['after'] if c['ligature_index'] == 0 else '')
            if record['status'] == 'uncertain':
                e.setdefault('outline_warnings', []).append(sub)
            elif record['status'] in ('replaced', 'rejected'):
                # Keep displaced OCR/raster decisions reviewable. This also
                # permits a paired comparison with the unchanged older pass.
                sub['previous'] = [s for s in e.get('font_subs', []) if s['offset'] == c['offset']]
                e['font_subs'] = [s for s in e.get('font_subs', []) if s['offset'] != c['offset']]+[sub]
                substitutions = [s for s in substitutions if (s['page'], s['id'], s['offset']) !=
                                 (run['page'], run['id'], c['offset'])]
                substitutions.append(dict(sub, page=run['page'], id=run['id'], source=run['source']))
    # Private-use codes last: a Symbol-encoding reading (or U+FFFD) replaces any
    # earlier raster/OCR decision about the same occurrence, which stays reviewable.
    for run in runs:
        page = pages[run['file']][1]; e = page['elements'][run['index']]
        for c, record in run.pop('private_records', []):
            page['fonts'][c['font']].setdefault('private_codes', {})[private_key(record)] = {
                k: record[k] for k in PRIVATE_PROOF_KEYS}
            sub = {k: c[k] for k in ('offset', 'char_id', 'before', 'font', 'source_code')}
            sub.update(model=PRIVATE_MODEL, after=record['after'], status=record['status'])
            sub['previous'] = [s for s in e.get('font_subs', []) if s['offset'] == c['offset']]
            e['font_subs'] = [s for s in e.get('font_subs', []) if s['offset'] != c['offset']]+[sub]
            if e.get('outline_warnings'):
                e['outline_warnings'] = [s for s in e['outline_warnings'] if s['offset'] != c['offset']]
                if not e['outline_warnings']: e.pop('outline_warnings')
            substitutions = [s for s in substitutions if (s['page'], s['id'], s['offset']) !=
                             (run['page'], run['id'], c['offset'])]
            substitutions.append(dict(sub, page=run['page'], id=run['id'], source=run['source']))
    for _,page in pages.values(): page.pop('_font_glyph_boxes',None)
    # Check every source before writing any page. An interrupted/failed OCR run
    # never writes half of an inferred font mapping.
    for filename,(raw,page) in pages.items():
        if Path(filename).read_bytes() != raw: raise ValueError('page changed during font OCR: '+filename)
    for filename,(_,page) in pages.items():
        path = Path(filename)
        with tempfile.NamedTemporaryFile('w', dir=path.parent, prefix='.fonts-', delete=False) as stream:
            temp = Path(stream.name)
            try: json.dump(page, stream, ensure_ascii=True, indent=1); stream.write('\n')
            except BaseException: temp.unlink(missing_ok=True); raise
        try: temp.chmod(path.stat().st_mode & 0o777); temp.replace(path)
        finally: temp.unlink(missing_ok=True)
    return substitutions


def valid_outline_occurrence(page, element, sub, chars):
    """Reject stale source codes, IDs, claims, scores and mapping decisions."""
    if sub.get('model') != OUTLINE_MODEL or not chars: return False
    offset = sub.get('offset'); before = sub.get('before'); font = sub.get('font')
    if not isinstance(offset, int) or not 0 <= offset < len(element.get('text', '')): return False
    if element['text'][offset] != before: return False
    indexed = indexed_run(element, chars)
    cid = sub.get('char_id')
    if indexed is None or indexed.get(offset) != cid: return False
    if chars[cid]['font'] != font or chars[cid].get('source_code') != sub.get('source_code'): return False
    proof = page.get('fonts', {}).get(font, {}).get('outline_verification', {}).get(str(sub.get('source_code')), {})
    if proof.get('ligature') is True: return valid_ligature_occurrence(page, element, sub, chars, proof, indexed)
    if any(proof.get(k) != sub.get(k) for k in ('model', 'font', 'source_code', 'before', 'after', 'status')): return False
    scores = proof.get('scores', {})
    if not scores or any(not isinstance(v, (int, float)) or not math.isfinite(v) or not -1 <= v <= 1.000001
                         for v in scores.values()): return False
    decision=saved_outline_decision(proof, unit=offset in unit_prefix_offsets(element['text']))
    # Older page files saved these same scores as a retained-digit warning.
    # Revalidate their original identity and proof, then apply the current
    # rejection policy; re-running OCR is not required to hide a false digit.
    legacy_digit=(sub.get('status')=='uncertain' and sub.get('after')==before
                  and decision==('rejected','\ufffd'))
    return decision == (sub.get('status'), sub.get('after')) or legacy_digit


def valid_ligature_occurrence(page, element, sub, chars, proof, indexed):
    """A ligature decision (lane r2-signs) applies to one letter of the claim: the whole claim is still
    in the text at its place, given by consecutive character IDs of the same face and code, and the
    saved proof still decides it (the sign for the first letter, nothing for the others)."""
    index = sub.get('ligature_index'); claim = proof.get('before'); offset = sub['offset']
    if not isinstance(index, int) or isinstance(index, bool) or not isinstance(claim, str) or not 0 <= index < len(claim):
        return False
    start = offset-index
    if start < 0 or element['text'][start:start+len(claim)] != claim or claim[index] != sub.get('before'): return False
    ids = [indexed.get(start+k) for k in range(len(claim))]
    if None in ids or ids != list(range(ids[0], ids[0]+len(claim))): return False
    if any(chars[i]['font'] != sub.get('font') or chars[i].get('source_code') != sub.get('source_code') for i in ids):
        return False
    if any(proof.get(k) != sub.get(k) for k in ('model', 'font', 'source_code', 'status')): return False
    if sub.get('after') != (proof.get('after') if index == 0 else ''): return False
    scores = proof.get('scores', {})
    if not scores or any(not isinstance(v, (int, float)) or not math.isfinite(v) or not -1 <= v <= 1.000001
                         for v in scores.values()): return False
    return saved_outline_decision(proof) == (sub.get('status'), proof.get('after'))


def sign_notice(font, code, sub, count, pages):
    """One line per paper for a sign-face or quote-in-number decision, with its count."""
    where = f"font {font}, glyph {code} ({sub['sign_claim']})"
    places = f"{count} place{'s' if count != 1 else ''} on page{'s' if len(pages) != 1 else ''} {', '.join(str(p) for p in pages)}"
    score = sub.get('claim_score'); extent = sub.get('extent')
    own = f" (its own outline scores {score:.2f})" if isinstance(score, (int, float)) else ''
    if extent: own = f" (its outline reaches from {extent[0]:.2f} to {extent[1]:.2f} em on the line, where that character does not)"
    if sub['status'] == 'replaced':
        return f"{where}: text layer '{sub['before']}'{own} printed as '{sub['after']}' by its embedded outline in {places}; check the printed glyph"
    known = 'a known sign or Greek letter' if 'small face' in sub['sign_claim'] else 'a known sign'
    return (f"{where}: text layer '{sub['before']}'{own} is neither that character nor {known} by its embedded outline; "
            f"shown as � in {places}; check the printed glyph")


def outline_notice(page, element, sub):
    place = f"page {page['page']}, {element['id']}, font {sub['font']}, glyph {sub['source_code']}"
    if sub['status'] == 'replaced':
        return f"{place}: text layer '{sub['before']}' corrected to '{sub['after']}' by embedded outline; check the printed glyph"
    if sub['status'] == 'rejected' and not sub['before'].isdigit():
        return f"{place}: text layer '{sub['before']}' disagrees with its outline and matches no known sign; shown as �, unresolved; check the printed glyph"
    if sub['status'] == 'rejected':
        return f"{place}: text layer digit '{sub['before']}' disagrees with a non-digit outline; shown as �, unresolved; check the printed glyph"
    offset = sub['offset']; context = element['text'][max(0, offset-25):offset+26]
    scores = page.get('fonts', {}).get(sub['font'], {}).get('outline_verification', {}).get(str(sub['source_code']), {}).get('scores', {})
    mu = max(scores.get('μ', 0), scores.get('µ', 0))
    hint = '; possible Greek mu in a number-unit token' if offset in unit_prefix_offsets(element['text']) and mu >= .60 and mu == max(scores.values(), default=0) else ''
    return f"{place}: text layer '{sub['before']}' disagrees with its outline near {context!r}{hint}; retained, unresolved; check the printed glyph"


def apply_copy(pages, uncertain):
    """One copy hook; verify font/offset/ID/evidence before touching prose or cells."""
    counts = collections.Counter(); symbol_margins = []; verified_counts = collections.Counter()
    position_notices = []; alternatives = {}; shape_named = set(); outline_notices = []
    private_counts = collections.Counter(); private_proofs = {}
    for page in pages:
        chars = page.get('_table_chars',[]); replacements = {}
        for e in page['elements']:
            warnings = [s for s in e.get('outline_warnings', []) if valid_outline_occurrence(page, e, s, chars)]
            subs = [s for s in warnings if s['before'].isdigit() and
                        saved_outline_decision(page['fonts'][s['font']]['outline_verification'][str(s['source_code'])])
                        == ('rejected','\ufffd')] + list(e.get('font_subs', []))
            rejected={s['offset'] for s in subs if s.get('model')==OUTLINE_MODEL
                      and valid_outline_occurrence(page,e,s,chars)
                      and saved_outline_decision(page['fonts'][s['font']]['outline_verification'][str(s['source_code'])])
                      == ('rejected','\ufffd')}
            # Outline ambiguity must not erase an independently established
            # sign. These saved alternatives still pass every ordinary
            # identity/OCR/raster check below before they can win a position.
            alternatives_before=[q for s in subs for q in [s]+s.get('previous',[])
                if q.get('offset') in rejected and q.get('model')!=OUTLINE_MODEL
                and q.get('after') and q['after']!='\ufffd' and not q['after'].isdigit()]
            subs=alternatives_before+subs
            if e.get('kind') != 'text': continue
            if not subs:
                outline_notices.extend((page, e, s) for s in warnings)
                continue
            old = e['text']; indexed = indexed_run(e, chars) if chars else None
            new = list(old); accepted = []
            for s in subs:
                offset = s.get('offset'); font = s.get('font'); before = s.get('before'); after = s.get('after')
                proof = page.get('fonts',{}).get(font,{}).get('checks',{}).get(before,{})
                if not isinstance(offset,int) or not 0 <= offset < len(old) or old[offset] != before: continue
                if s.get('model') == OUTLINE_MODEL:
                    if not valid_outline_occurrence(page, e, s, chars): continue
                    scores=page['fonts'][font]['outline_verification'][str(s['source_code'])]['scores']
                    status,after=saved_outline_decision(page['fonts'][font]['outline_verification'][str(s['source_code'])],
                        unit=offset in unit_prefix_offsets(old))
                    if status not in ('replaced','rejected'):continue
                    if (page['fonts'][font]['outline_verification'][str(s['source_code'])].get('ligature') is True
                            and s.get('ligature_index')): after=''   # a ligature's later letters give way to its sign
                    s=dict(s,status=status,after=after)
                elif s.get('model') == PRIVATE_MODEL:
                    if not valid_private_occurrence(page, e, s, chars): continue
                elif s.get('model') == POSITION_MODEL:
                    position = s.get('position',{})
                    # Recheck context/geometry and native ID; the source glyph
                    # stays unchanged in JSON, and the table/prose views agree.
                    if not chars or indexed is None or indexed.get(offset) != s.get('char_id'): continue
                    cid = s['char_id']; following = position.get('unit_offset')
                    if following not in indexed or chars[cid].get('source_code') != s.get('source_code'): continue
                    if before != '◦' or after != '\ufffd' or position.get('model') != POSITION_MODEL: continue
                    box = lambda c: [c[k] for k in ('x0','y0','x1','y1')]
                    run = dict(source=old,glyphs=[dict(offset=following,box_px=box(chars[indexed[following]]))])
                    candidate = dict(offset=offset,box_px=box(chars[cid]))
                    measured = dict(position,status='measured')
                    if temperature_ring(run,candidate,measured) is None: continue
                elif s.get('model') == VERIFY_MODEL:
                    proof = page.get('fonts',{}).get(font,{}).get('verification',{}).get(str(s.get('source_code')), {})
                    if (not valid_verification(proof,before,after) or proof.get('source_code') != s.get('source_code') or
                        proof.get('font') != font or s.get('similarity') != proof.get('similarity') or
                        s.get('threshold') != proof.get('threshold') or s.get('status') != proof.get('status')): continue
                elif s.get('model') == SYMBOL_MODEL:
                    decision,_ = symbol_decision(before,s.get('symbol_ocr',{}),s.get('letter_ocr',{}),s.get('raster_symbols',[]))
                    if (not symbol_eligible(old,offset) or decision is None or decision != after or
                        s.get('symbol_confidence') != s['symbol_ocr']['confidence'] or
                        s.get('letter_confidence') != s['letter_ocr']['confidence'] or
                        s.get('margin') != s['symbol_confidence']-s['letter_confidence']): continue
                elif (s.get('model') or after not in SIGNS or not eligible(old,offset) or proof.get('after') != after or
                      proof.get('status') != 'untrusted' or proof.get('wins',0) < 3 or
                      proof.get('samples',0) < 3 or proof['wins'] > proof['samples'] or
                      proof['wins']/proof['samples'] < .7): continue
                if chars:
                    cid = s.get('char_id')
                    if indexed is None or indexed.get(offset) != cid or chars[cid]['font'] != font: continue
                    if s.get('model') == VERIFY_MODEL and chars[cid].get('source_code') != s.get('source_code'): continue
                else:
                    spans = e.get('font_spans',[])
                    if not any(span['start'] <= offset < span['end'] and span['font'] == font for span in spans): continue
                if new[offset] != old[offset]: continue
                new[offset] = after
                if before != after or s.get('status') == 'layout-protected': accepted.append(s)
            for s in accepted:
                if chars: replacements[s['char_id']] = s['after']
                if s.get('model') == OUTLINE_MODEL:
                    outline_notices.append((page, e, s))
                elif s.get('model') == PRIVATE_MODEL:
                    key = s['font'], s['source_code'], s['before']
                    private_counts[key+(s['after'], s['status'])] += 1
                    private_proofs[key] = page['fonts'][s['font']]['private_codes'][private_key(s)]
                    page.setdefault('_private_readings', []).append((s['before'], s['after']))
                elif s.get('model') == VERIFY_MODEL:
                    verified_counts[s['font'],str(s['source_code']),s['before'],s['after'],s['similarity']] += 1
                    proof = page['fonts'][s['font']]['verification'][str(s['source_code'])]
                    if proof.get('alternative'): alternatives[s['font'],str(s['source_code'])] = proof['alternative']
                    if (proof.get('proof',{}).get('shape_rows') or proof.get('proof',{}).get('structure_rows') or
                        proof.get('proof',{}).get('outline_greek')): shape_named.add((s['font'],str(s['source_code'])))
                elif s.get('model') == POSITION_MODEL:
                    position_notices.append(f"page {page['page']}, {e['id']}, font {s['font']}, glyph {s['source_code']}: "
                                            "raised ring mapped as a bullet; shown as �, check the degree sign")
                elif s.get('model') == SYMBOL_MODEL: symbol_margins.append(s['margin'])
                else: counts[s['font'],s['before'],s['after']] += 1
            e['text'] = ''.join(new)
            outline_notices.extend((page, e, s) for s in warnings if new[s['offset']] == s['before'])
        if replacements:
            page['_table_chars'] = [dict(c,text=replacements[i]) if i in replacements else c for i,c in enumerate(chars)]
            for e in page['elements']:
                if e.get('_chars'): e['_chars'] = [page['_table_chars'][i] for i in e['char_ids']]
    for (font,before,after),count in sorted(counts.items()):
        uncertain.append(f"font {font}: '{before}' read as '{after}' by OCR in {count} places; check them")
    if symbol_margins:
        uncertain.append(f"{len(symbol_margins)} individual glyphs read as symbols by OCR; check them; "
                         f"lowest symbol-over-letter confidence margin {min(symbol_margins):.1f} points")
    uncertain.extend(position_notices)
    uncertain.extend(private_notices(private_counts, private_proofs))
    grouped = collections.defaultdict(list); signs = collections.defaultdict(list)
    for page, e, s in outline_notices:
        proof = page.get('fonts', {}).get(s['font'], {}).get('outline_verification', {}).get(str(s['source_code']), {})
        if proof.get('ligature') is True:   # one notice line per glyph: the whole claim, at its first letter
            if s.get('ligature_index'): continue
            s = dict(s, before=proof['before'])
        if proof.get('sign_claim') and s['status'] in ('replaced', 'rejected'):
            extra = {}
            if proof.get('sign_claim') == 'small face':   # rule R1: the claim's own score is named in the notice
                extra['claim_score'] = max((v for ch, v in proof.get('scores', {}).items() if ch in sign_family(s['before'])), default=None)
                # The claim's place names the reason only where it decides (re-ladder): a letter claim its place
                # contradicts, whose decision without the place would differ.
                extent = saved_extent(proof.get('extent')); scores = proof.get('scores', {})
                own = [ch for ch in small_family(s['before']) if ch in scores]
                letter = s['before'].isalpha() and letter_script(s['before']) != 'other'
                if (letter and extent is not None and own and not any(placed(ch, extent) for ch in own)
                        and saved_outline_decision({k: v for k, v in proof.items() if k != 'extent'})
                        != (s['status'], s['after'])):
                    extra = dict(extent=extent)
            signs[s['font'], s['source_code'], s['status']].append((page, e, dict(s, sign_claim=proof['sign_claim'], **extra)))
        else: grouped[page['page'], s['font'], s['source_code'], s['status']].append((page, e, s))
    # Rule R3 (lane glyphsigns): every resolved or unresolved sign once per paper, with its count.
    for (font, code, status), rows in sorted(signs.items(), key=lambda kv: (kv[0][0], str(kv[0][1]), kv[0][2])):
        uncertain.append(sign_notice(font, code, rows[0][2], len(rows), sorted({p['page'] for p, e, s in rows})))
    for rows in grouped.values():
        notice = outline_notice(*rows[0])
        if len(rows) > 1:
            places = collections.defaultdict(list)
            for page, e, s in rows: places[e['id']].append(str(s['offset']))
            notice += '; '+str(len(rows))+' places: '+', '.join(run+' offsets '+('/'.join(offsets)) for run, offsets in places.items())
        uncertain.append(notice)
    for (font,code,before,after,score),count in sorted(verified_counts.items()):
        if before == after:
            uncertain.append(f"font {font}, glyph {code}: claimed '{before}' fails shape verification in {count} places; "
                             f"similarity {score:.3f}; retained to preserve table/heading layout; unresolved, check the glyph crops")
        else:
            method = ('unconfirmed; shown as' if after == '\ufffd' else
                      'verified as' if (font,code) in shape_named else 'read by OCR as')
            uncertain.append(f"font {font}, glyph {code}: claimed '{before}' {method} '{after}' in {count} places; "
                             f"shape similarity {score:.3f}; check the glyph crops")
            alternative = alternatives.get((font,code))
            if alternative and (score >= VERIFY_THRESHOLDS.get(before,VERIFY_THRESHOLD) or before in OVERLAPPING_CLASSES):
                uncertain[-1] += (f"; competing '{alternative['character']}' shape at least "
                                  f"{alternative['minimum_similarity']:.3f}, margin {alternative['minimum_margin']:.3f}")


def check(folder, pdf, workers=4, binary=signs.shapes.TESSERACT, data=signs.shapes.TESSDATA,
          libs=signs.shapes.TESS_LIBS, report_path=None):
    started = time.perf_counter(); folder=Path(folder).resolve(); pdf=Path(pdf).resolve()
    pages,runs,unverified,outline_report = collect(folder,pdf)
    selected = sample_runs(runs); indices = sorted(set().union(*selected.values())) if selected else []
    with tempfile.TemporaryDirectory(dir=folder, prefix='.check-fonts-') as scratch:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda i:recognize(runs[i],scratch,binary,data,libs),indices))
        tasks = [dict(page=p['page'],pdf=str(pdf),boxes=p['_font_glyph_boxes'],
                      runs=[r for r in runs if r['file'] == filename and r['symbol_candidates']])
                 for filename,(_,p) in pages.items()]
        tasks = [t for t in tasks if t['runs']]
        def page_symbols(task):
            try: return recognize_symbol_page(task,scratch,binary,data,libs)
            except (ValueError,OSError,subprocess.SubprocessError) as exc:
                return [dict(page=task['page'],status='error',reason=f'{type(exc).__name__}: {exc}')]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            symbol_records = [r for batch in pool.map(page_symbols,tasks) for r in batch]
        evidence_dir = folder/'font-evidence'; evidence_dir.mkdir(exist_ok=True)
        verify_tasks = [dict(page=p['page'],pdf=str(pdf),boxes=p['_font_glyph_boxes'],
                            runs=[r for r in runs if r['file']==filename and r['verification_candidates']])
                        for filename,(_,p) in pages.items()]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            verification_records = [r for batch in pool.map(
                lambda t:measure_page(t,scratch,evidence_dir),[t for t in verify_tasks if t['runs']]) for r in batch]
    for index,result in zip(indices,results): runs[index].update(result)
    evidence = decide(runs,selected)
    named = {(g['font'], g['source_code']): g for g in outline_report.get('greek_named', [])}
    verification = decide_verification(verification_records,evidence,binary,data,libs,named)
    errors = sum(r['status']=='error' for r in results+symbol_records)
    substitutions = apply_results(pages,runs,evidence,symbol_records,verification_records,verification) if not errors else []
    report = dict(model=MODEL, pdf=str(pdf), seconds=time.perf_counter()-started,
                  fonts=len(selected), sampled_runs=len(indices), errors=errors, evidence=evidence,
                  substitutions=substitutions, unverified_runs=unverified, samples=[runs[i] for i in indices],
                  symbol_model=SYMBOL_MODEL,symbol_occurrences=symbol_records,
                  outline_verification=outline_report,
                  verification_model=VERIFY_MODEL,verification=verification,verification_occurrences=verification_records)
    Path(report_path or folder/'fonts-ocr.json').write_text(json.dumps(report,ensure_ascii=True,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('model','fonts','sampled_runs','errors')} | {'substitutions':len(substitutions)}))
    return int(bool(errors))


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path); parser.add_argument('pdf',type=Path)
    parser.add_argument('--report',type=Path); parser.add_argument('--workers',type=int,default=4,choices=range(1,9))
    parser.add_argument('--tesseract',type=Path,default=signs.shapes.TESSERACT)
    parser.add_argument('--tessdata',type=Path,default=signs.shapes.TESSDATA)
    parser.add_argument('--tesseract-libs',type=Path,default=signs.shapes.TESS_LIBS)
    args=parser.parse_args(argv)
    try: return check(args.folder,args.pdf,args.workers,args.tesseract,args.tessdata,args.tesseract_libs,args.report)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(f'check_fonts: {type(exc).__name__}: {exc}',file=sys.stderr); return 1

if __name__ == '__main__':
    if sys.argv[1:] == ['--build-symbol-shapes']:
        print(build_symbol_shapes(), 'Symbol-only reference characters written to', SYMBOL_SHAPES)
    elif sys.argv[1:] == ['--build-glyph-extents']:
        print(build_glyph_extents(), 'reference extents and extra Greek silhouettes written to', EXTENT_SHAPES)
    elif len(sys.argv) == 3 and sys.argv[1] == '--verify-task':
        task_path = Path(sys.argv[2])
        payload = json.loads(task_path.read_text())
        result = verify_page(**payload)
        task_path.with_suffix('.result.json').write_text(json.dumps(result))
    else: raise SystemExit(main())
