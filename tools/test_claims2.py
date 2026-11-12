"""Lane claims2: a correct sign claim in a small symbol face must not be flagged.
(1) outline_plus_minus reads the joined design (the plus's stem runs down onto the lower bar, one connected
shape); (2) strokes that prove the claimed sign itself confirm it whatever the silhouettes say; (3) in a small
face a claim that is itself a sign or Greek letter is flagged only when a rival outside its family scores
above it; (4) a small face whose outline cannot be read abstains and is recorded as such.
/usr/bin/python3 -I tools/test_claims2.py"""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fonts', TOOLS/'check_fonts.py')
fonts = importlib.util.module_from_spec(spec); spec.loader.exec_module(fonts)


def silhouette(rows, aspect=1.0):
    """A 32x32 silhouette from (row range, column range) strokes, in outline_shape's bit layout."""
    mask = 0
    for ys, xs in rows:
        for y in ys:
            for x in xs: mask |= 1 << ((y+4)*40+x+4)
    return mask, aspect, mask.bit_count()/1024


FULL = range(32)
STEM = range(15, 17)
# Hairline plus over a bar, the stem meeting the bar (the drawing of CMSY10 glyph 6 at 1200 dpi, AQ24)
JOINED = silhouette([(range(0, 30), STEM), (range(15, 17), FULL), (range(30, 32), FULL)])
# The same with a gap between stem and bar (DejaVu's design, two components)
SEPARATE = silhouette([(range(0, 26), STEM), (range(12, 14), FULL), (range(30, 32), FULL)])
# Measured scores of AQ24's glyph against the references (rounded): '+' beats the claim in silhouette
AQ24_SCORES = {'+': .519, '±': .354, '1': .349, 'L': .322, 'l': .322, 'I': .315, 'T': .308, '∈': .305}


class JoinedPlusMinus(unittest.TestCase):
    def test_joined_and_separate_designs_are_plus_minus(self):
        self.assertTrue(fonts.outline_plus_minus(JOINED))
        self.assertTrue(fonts.outline_plus_minus(SEPARATE))
        self.assertTrue(fonts.outline_plus_minus([hex(JOINED[0]), JOINED[1], JOINED[2]]))   # a saved proof

    def test_lookalikes_stay_out(self):
        up_tack = silhouette([(range(0, 30), STEM), (range(30, 32), FULL)])                 # no crossbar
        minus_plus = silhouette([(range(0, 2), FULL), (range(2, 32), STEM), (range(16, 18), FULL)])
        off_centre = silhouette([(range(0, 30), range(3, 5)), (range(15, 17), FULL), (range(30, 32), FULL)])
        high_bar = silhouette([(range(0, 30), STEM), (range(2, 4), FULL), (range(30, 32), FULL)])
        thick_foot = silhouette([(range(0, 22), STEM), (range(10, 12), FULL), (range(22, 32), FULL)])
        for shape in (up_tack, minus_plus, off_centre, high_bar, thick_foot):
            self.assertFalse(fonts.outline_plus_minus(shape))

    def test_no_reference_silhouette_other_than_plus_minus_passes(self):
        refs = fonts.sign_references()
        self.assertEqual({ch for ch, rs in refs.items() if any(fonts.outline_plus_minus(r) for r in rs)}, {'±'})


class StrokesConfirmTheClaim(unittest.TestCase):
    def test_aq24_plus_minus_is_confirmed_in_a_small_face(self):
        self.assertEqual(fonts.sign_outline_decision('±', AQ24_SCORES, shape=JOINED, small=True), ('confirmed', '±'))
        self.assertEqual(fonts.sign_outline_decision('±', AQ24_SCORES, shape=JOINED), ('confirmed', '±'))

    def test_without_the_strokes_the_better_plus_is_a_rival(self):
        # silhouettes alone: '+' (.52) beats the claim (.35), under the sign floor: flagged
        self.assertEqual(fonts.sign_outline_decision('±', AQ24_SCORES, small=True), ('rejected', '�'))

    def test_strokes_replace_a_different_claim_only_with_silhouette_support(self):
        # the claim is a digit, the strokes say ±, its silhouette support (.354) is under the structure floor
        scores = dict(AQ24_SCORES, **{'4': .20})
        self.assertNotEqual(fonts.sign_outline_decision('4', scores, shape=JOINED, small=True), ('replaced', '±'))
        self.assertEqual(fonts.sign_outline_decision('4', dict(scores, **{'±': .45}), shape=JOINED, small=True),
                         ('replaced', '±'))

    def test_saved_proof_reproduces_the_confirmation(self):
        proof = dict(before='±', scores=AQ24_SCORES, sign_claim='symbolic encoding', small_face=True,
                     outline=[hex(JOINED[0]), JOINED[1], JOINED[2]])
        self.assertEqual(fonts.saved_outline_decision(proof), ('confirmed', '±'))


class RivalRule(unittest.TestCase):
    def test_best_scoring_sign_or_greek_claim_is_printed(self):
        self.assertEqual(fonts.sign_outline_decision('±', {'±': .35, '+': .30, '1': .29}, small=True), ('confirmed', '±'))
        self.assertEqual(fonts.sign_outline_decision('μ', {'μ': .42, 'u': .40, 'p': .30}, small=True), ('confirmed', 'μ'))
        self.assertEqual(fonts.sign_outline_decision('∼', {'∼': .30, '-': .25}, small=True), ('confirmed', '∼'))
        # a family member scoring higher is no rival (µ and μ are one family)
        self.assertEqual(fonts.sign_outline_decision('μ', {'μ': .40, 'µ': .43, 'u': .41}, small=True), ('confirmed', 'μ'))

    def test_a_rival_that_beats_the_claim_flags_it(self):
        self.assertEqual(fonts.sign_outline_decision('±', {'±': .30, '†': .46}, small=True), ('rejected', '�'))
        self.assertEqual(fonts.sign_outline_decision('μ', {'μ': .42, 'u': .50}, small=True), ('rejected', '�'))
        # re-ladder: a rival under SIGN_CLAIM_FLOOR is no evidence against the claim
        self.assertEqual(fonts.sign_outline_decision('±', {'±': .30, '†': .40}, small=True), ('confirmed', '±'))

    def test_latin_and_punctuation_claims_keep_the_floor(self):
        # R1 unchanged for claims outside the sign and Greek sets (AP01 'c' for gamma, AP24 ',' for '<')
        self.assertEqual(fonts.sign_outline_decision('c', {'c': .30, 'o': .20}, small=True), ('rejected', '�'))
        self.assertEqual(fonts.sign_outline_decision('c', {'c': .086, 'y': .52, 'γ': .47}, small=True), ('rejected', '�'))
        self.assertEqual(fonts.sign_outline_decision(',', {',': .16, '<': .59, 'c': .29}, small=True), ('replaced', '<'))

    def test_outside_small_faces_nothing_changes(self):
        self.assertEqual(fonts.sign_outline_decision('±', {'±': .30, '+': .20}), ('unchanged', '±'))
        self.assertEqual(fonts.sign_outline_decision('+', {'+': .30, '1': .20}), ('rejected', '�'))

    def test_membership(self):
        for ch in '±−+×<>=°μαβγδκσχω•′∼≈∞→':
            self.assertTrue(fonts.sign_or_greek(ch), ch)
        # glyphsigns re-ladder R-b: a non-symbol character of the Latin 8-bit encoding (dagger, section,
        # pilcrow, en and em dash) is a text claim, what a symbol face's code reads as, not a claimed sign
        for ch in 'acnx1,.;:*"\'`’“”Æăı†‡§¶–—':
            self.assertFalse(fonts.sign_or_greek(ch), ch)


def glyph(font, code, before, offset, char_id, box):
    return dict(font=font, source_code=code, before=before, offset=offset, char_id=char_id, box_px=box)


class UnreadableSmallFace(unittest.TestCase):
    def test_unreadable_outline_abstains_and_is_recorded(self):
        refs = {ch: [(ch,)] for ch in '±+etaoinsrh'}
        body = [glyph('BODY', 100+i, 'etaoinsrh'[i], i, i, [i*10, 0, i*10+9, 10]) for i in range(7)]
        runs = [dict(page=1, id='run:0', source='etaoins', crop_xywh=[0, 0, 90, 10], font_glyphs=body),
                dict(page=1, id='run:1', source='1 ± 2', crop_xywh=[0, 20, 60, 10],
                     font_glyphs=[glyph('SMALL', 6, '±', 2, 20, [5, 20, 9, 30])])]
        doc = SimpleNamespace(fonts={1: SimpleNamespace(basefont='BODY', base='StandardEncoding', cid=False, prog=None),
                                     2: SimpleNamespace(basefont='SMALL', base='StandardEncoding', cid=False, prog=None)})

        def shape(font, code):
            if font.basefont == 'SMALL': raise ValueError('missing selected glyph')
            return code, 1.0, .5
        with patch.object(fonts, 'outline_references', return_value=refs), \
             patch.object(fonts, 'sign_references', return_value=refs), \
             patch.object(fonts, 'outline_shape', side_effect=shape), \
             patch.object(fonts, 'outline_similarity', return_value=.9):
            result = fonts.verify_outlines(doc, runs)
        self.assertEqual(result['records'], [])
        self.assertEqual([(u['font'], u['source_code'], u['small_face']) for u in result['unavailable']], [('SMALL', 6, True)])


if __name__ == '__main__':
    unittest.main()
