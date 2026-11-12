"""Re-ladder of lane claims: in a small face the glyph's place on the line (its outline box, bottom and top
in em) decides which Latin and Greek letters compete; a Latin and a Greek letter are different families; a
letter claim its place contradicts is not printed unless another character replaces it; a sign or Greek
claim under the floor is flagged only by a rival that itself reaches the floor. All numbers are invented.
/usr/bin/python3 -I tools/test_reladder_claims.py"""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fonts', TOOLS/'check_fonts.py')
fonts = importlib.util.module_from_spec(spec); spec.loader.exec_module(fonts)
sys.path.insert(0, str(TOOLS/'secondpass'))
r09 = importlib.import_module('r09_glyphs')
sys.path.pop(0)

DESCENDING = (-.22, .46)     # a letter that reaches below the baseline and stops at the x-height
X_HEIGHT = (0.0, .45)        # a letter that sits on the baseline and stops at the x-height
ASCENDING = (0.0, .70)       # a letter that rises above the x-height


class References(unittest.TestCase):
    def test_every_reference_letter_has_a_place_and_the_zones_hold(self):
        extents, shapes = fonts.glyph_extents()
        letters = [ch for ch in fonts.outline_references() if ch.isalpha()]
        self.assertTrue(letters and all(ch in extents for ch in letters))
        for ch in 'γχ':                        # descenders
            self.assertLess(extents[ch][1], -.1)
        self.assertLess(extents['y'][0], -.1)   # y takes Y's place too, as its silhouettes do
        for ch in 'xτκα':                      # on the baseline
            self.assertGreater(extents[ch][0], -.05)
        self.assertGreater(extents['t'][2], extents['τ'][2])   # the Latin t rises above the Greek tau
        self.assertEqual(set(shapes), set(fonts.EXTRA_GREEK))
        self.assertTrue(all(len(rows) == 8 for rows in shapes.values()))

    def test_extra_greek_competes_only_in_small_faces(self):
        self.assertTrue(set(fonts.EXTRA_GREEK) <= set(fonts.small_references()))
        self.assertFalse(set(fonts.EXTRA_GREEK) & set(fonts.sign_references()))
        self.assertFalse(set(fonts.EXTRA_GREEK) & set(fonts.outline_references()))


class Placement(unittest.TestCase):
    def test_letters_are_placed_by_their_zones(self):
        self.assertFalse(fonts.placed('x', DESCENDING))
        self.assertTrue(fonts.placed('χ', DESCENDING))
        self.assertFalse(fonts.placed('t', X_HEIGHT))
        self.assertTrue(fonts.placed('τ', X_HEIGHT))
        self.assertTrue(fonts.placed('t', ASCENDING))
        self.assertFalse(fonts.placed('τ', ASCENDING))

    def test_a_low_capital_keeps_its_letter(self):
        self.assertTrue(fonts.placed('P', (0.0, .59)))     # a design with capitals lower than the 17 faces'
        self.assertFalse(fonts.placed('p', (0.0, .59)) and fonts.placed_exactly('p', (0.0, .59)))

    def test_signs_and_unmeasured_glyphs_give_no_evidence(self):
        for ch in '<↑,±':
            self.assertTrue(fonts.placed(ch, (-.5, 1.5)))
        self.assertTrue(fonts.placed('x', None))

    def test_extent_from_a_box(self):
        self.assertEqual(fonts.outline_extent((20, 450, 500, -210)), (-.21, .45))
        self.assertIsNone(fonts.outline_extent((-1, -1, -1, -1)))
        self.assertIsNone(fonts.outline_extent(None))
        self.assertEqual(fonts.saved_extent([-.21, .45]), (-.21, .45))
        for bad in ([.5, .1], ['a', 1], [True, 1], [0.0], None):
            self.assertIsNone(fonts.saved_extent(bad))

    def test_small_family_splits_scripts(self):
        self.assertEqual(fonts.small_family('x'), 'xX')
        self.assertEqual(fonts.small_family('χ'), 'χΧ')
        self.assertEqual(fonts.small_family('×'), '×')
        self.assertEqual(set(fonts.small_family('µ')), set('μµ'))
        self.assertIn('x', fonts.sign_family('χ'))   # the sign family itself is unchanged


class SmallFaceDecision(unittest.TestCase):
    def test_a_descending_letter_claimed_as_x_is_chi(self):
        scores = {'x': .80, 'X': .80, 'χ': .66, 'λ': .50, 'y': .44, '\\': .52}
        self.assertEqual(fonts.sign_outline_decision('x', scores, small=True, extent=DESCENDING), ('replaced', 'χ'))
        # without a place the Latin claim still wins its own family
        self.assertEqual(fonts.sign_outline_decision('x', scores, small=True), ('confirmed', 'x'))
        # an x that sits on the baseline stays an x
        self.assertEqual(fonts.sign_outline_decision('x', scores, small=True, extent=X_HEIGHT), ('confirmed', 'x'))

    def test_an_x_height_letter_claimed_as_t_is_tau(self):
        scores = {'t': .72, 'T': .72, 'τ': .69, '7': .57, '↑': .58}
        self.assertEqual(fonts.sign_outline_decision('t', scores, small=True, extent=X_HEIGHT), ('replaced', 'τ'))
        self.assertEqual(fonts.sign_outline_decision('t', scores, small=True, extent=ASCENDING), ('confirmed', 't'))

    def test_a_contradicted_letter_claim_with_no_replacement_is_flagged(self):
        scores = {'t': .72, 'T': .72, 'τ': .50, '7': .48}   # tau placed but not separated: no replacement
        self.assertEqual(fonts.sign_outline_decision('t', scores, small=True, extent=X_HEIGHT), ('rejected', '�'))

    def test_a_greek_claim_under_the_floor_needs_a_rival_at_the_floor(self):
        scores = {'γ': .33, '7': .43, 'y': .37, 'τ': .38}
        self.assertEqual(fonts.sign_outline_decision('γ', scores, small=True, extent=DESCENDING), ('confirmed', 'γ'))
        self.assertEqual(fonts.sign_outline_decision('γ', scores, small=True), ('confirmed', 'γ'))
        rival = dict(scores, y=.49)
        self.assertEqual(fonts.sign_outline_decision('γ', rival, small=True, extent=DESCENDING), ('rejected', '�'))
        # a rival letter at the floor whose place the glyph does not take is no rival
        unplaced = dict(scores, k=.49)
        self.assertEqual(fonts.sign_outline_decision('γ', unplaced, small=True, extent=DESCENDING), ('confirmed', 'γ'))

    def test_a_greek_claim_its_place_contradicts_is_flagged(self):
        scores = {'γ': .60, 'v': .40}
        self.assertEqual(fonts.sign_outline_decision('γ', scores, small=True, extent=X_HEIGHT), ('rejected', '�'))

    def test_named_sign_faces_outside_small_faces_take_no_place(self):
        scores = {'x': .80, 'X': .80, 'χ': .66}
        self.assertEqual(fonts.sign_outline_decision('x', scores, extent=DESCENDING), ('confirmed', 'x'))

    def test_saved_proof_reproduces_the_placed_decision(self):
        proof = dict(before='x', scores={'x': .80, 'X': .80, 'χ': .66, 'λ': .50}, sign_claim='small face',
                     small_face=True, extent=list(DESCENDING))
        self.assertEqual(fonts.saved_outline_decision(proof), ('replaced', 'χ'))
        self.assertEqual(fonts.saved_outline_decision(dict(proof, extent=['bad', 1])), ('confirmed', 'x'))

    def test_notice_names_the_place(self):
        sub = dict(sign_claim='small face', status='rejected', before='t', after='�', extent=X_HEIGHT)
        text = fonts.sign_notice('F', 9, sub, 1, [3])
        self.assertIn('0.00 to 0.45 em', text)
        self.assertNotIn('scores', text)


def glyph(font, code, before, offset, char_id, box):
    return dict(font=font, source_code=code, before=before, offset=offset, char_id=char_id, box_px=box)


class CasesAndScripts(unittest.TestCase):
    def test_in_a_greek_face_each_case_scores_only_where_it_sits(self):
        cases = fonts.case_references()
        upper = cases['T'][0]                      # a capital T silhouette set at the x-height
        scores = {'t': 0.0, 'T': 0.0, 'τ': .5}
        low = fonts.case_scores(upper, scores, (0.0, .52))
        tall = fonts.case_scores(upper, scores, (0.0, .70))
        self.assertLess(low['t'], tall['t'])       # at the x-height the capital no longer scores the claim
        self.assertEqual(low['τ'], .5)             # other characters keep their scores
        self.assertIs(fonts.case_scores(upper, scores, None), scores)

    def test_other_case_counts_as_the_letter(self):
        self.assertTrue(fonts.placed('t', (0.0, .70)))
        self.assertTrue(fonts.placed('T', (0.0, .70)))
        self.assertFalse(fonts.placed_exactly('T', X_HEIGHT))
        self.assertFalse(fonts.placed('x', DESCENDING))

    def test_digits_are_rivals_by_their_place_but_never_displace_a_digit_claim(self):
        self.assertFalse(fonts.placed('8', X_HEIGHT))
        self.assertTrue(fonts.placed('8', (0.0, .70)))
        scores = {'7': .62, 'γ': .40}   # an old-style figure claimed as itself keeps its own score
        self.assertEqual(fonts.sign_outline_decision('7', scores, small=True, extent=DESCENDING), ('confirmed', '7'))
        rival = {'γ': .33, '7': .50, 'y': .30}   # a figure that does not reach below the baseline is no rival
        self.assertEqual(fonts.sign_outline_decision('γ', rival, small=True, extent=DESCENDING), ('confirmed', 'γ'))

    def test_in_a_greek_face_a_latin_claim_a_greek_letter_beats_clearly_is_flagged(self):
        scores = {'t': .58, 'T': .58, 'τ': .70, 'r': .66, 'R': .66}
        self.assertEqual(fonts.sign_outline_decision('t', scores, small=True, extent=(0.0, .52)), ('confirmed', 't'))
        self.assertEqual(fonts.sign_outline_decision('t', scores, small=True, extent=(0.0, .52), greek_face=True),
                         ('rejected', '\ufffd'))
        close = dict(scores, τ=.64)   # within the margin the Latin claim stands even there
        self.assertEqual(fonts.sign_outline_decision('t', close, small=True, extent=(0.0, .52), greek_face=True),
                         ('confirmed', 't'))
        latin = {'a': .56, 'A': .56, 'o': .70, 'O': .70}   # a Latin rival never flags a Latin claim this way
        self.assertEqual(fonts.sign_outline_decision('a', latin, small=True, extent=X_HEIGHT, greek_face=True),
                         ('confirmed', 'a'))
        proof = dict(before='t', scores=scores, sign_claim='small face', small_face=True, extent=[0.0, .52], greek_face=True)
        self.assertEqual(fonts.saved_outline_decision(proof), ('rejected', '\ufffd'))


class GreekFacePass(unittest.TestCase):
    """verify_outlines with patched outlines: a small face whose 'x' is a chi has its 't' decided again."""
    refs = {ch: [(ch,)] for ch in 'xXχtTτrR'}
    table = {(120, 'χ'): .69, (120, 'x'): .78, (120, 'X'): .78, (116, 'τ'): .70, (116, 't'): .58, (116, 'T'): .58,
             (116, 'r'): .60, (116, 'R'): .60, (121, 'x'): .80, (121, 'X'): .80}
    boxes = {120: (0, 450, 500, -210), 116: (0, 520, 450, 0), 121: (0, 450, 500, 0)}

    def run_outlines(self, small):
        body = [glyph('BODY', 100+i, 'etaoinsrh'[i], i, i, [i*10, 0, i*10+9, 10]) for i in range(7)]
        runs = [dict(page=1, id='run:0', source='etaoins', crop_xywh=[0, 0, 90, 10], font_glyphs=body),
                dict(page=1, id='run:1', source='a xt b', crop_xywh=[0, 20, 60, 10], font_glyphs=small)]
        box = lambda code: self.boxes[code]
        doc = SimpleNamespace(fonts={1: SimpleNamespace(basefont='BODY', base='StandardEncoding', cid=False, prog=None),
                                     2: SimpleNamespace(basefont='SMALL', base='StandardEncoding', cid=False, prog=None, bbox=box)})
        with patch.object(fonts, 'outline_references', return_value=self.refs), \
             patch.object(fonts, 'sign_references', return_value=self.refs), \
             patch.object(fonts, 'small_references', return_value=self.refs), \
             patch.object(fonts, 'case_references', return_value={ch: rs for ch, rs in self.refs.items() if ch.isascii()}), \
             patch.object(fonts, 'outline_shape', side_effect=lambda f, code: (code, 1.0, .5)), \
             patch.object(fonts, 'outline_similarity', side_effect=lambda a, b: self.table.get((a[0], b[0]), .1)):
            return fonts.verify_outlines(doc, runs)

    def test_latin_claim_of_a_face_that_draws_greek_is_flagged(self):
        result = self.run_outlines([glyph('SMALL', 120, 'x', 2, 20, [5, 20, 9, 30]), glyph('SMALL', 116, 't', 3, 21, [10, 20, 14, 30])])
        got = {r['before']: (r['after'], r['status'], r.get('greek_face', False), r.get('extent')) for r in result['records']}
        self.assertEqual(got['x'], ('χ', 'replaced', False, [-.21, .45]))
        self.assertEqual(got['t'], ('\ufffd', 'rejected', True, [0.0, .52]))

    def test_without_a_greek_letter_in_the_face_the_latin_claim_stands(self):
        result = self.run_outlines([glyph('SMALL', 121, 'x', 2, 20, [5, 20, 9, 30]), glyph('SMALL', 116, 't', 3, 21, [10, 20, 14, 30])])
        self.assertEqual(result['records'], [])


class RuleNine(unittest.TestCase):
    def test_rule_9_places_a_small_face_glyph_as_the_first_pass_does(self):
        font = SimpleNamespace(bbox=lambda code: (20, 460, 500, -220), width=lambda code: 520)
        shape = (1, .8, .5)
        seen = {}
        def decide(before, scores, **kw):
            seen.update(kw, references=set(scores)); return 'confirmed', before
        with patch.object(fonts, 'outline_shape', return_value=shape), \
                patch.object(fonts, 'outline_similarity', return_value=.5), \
                patch.object(fonts, 'sign_outline_decision', side_effect=decide):
            r09.sign_decision(fonts, {'F': [font]}, dict(font='F', source_code=7), 'x', small=True)
            self.assertEqual(seen['extent'], (-.22, .46))
            self.assertTrue(set(fonts.EXTRA_GREEK) <= seen['references'])
            r09.sign_decision(fonts, {'F': [font]}, dict(font='F', source_code=7), 'x', small=False)
            self.assertIsNone(seen['extent'])
            self.assertFalse(set(fonts.EXTRA_GREEK) & seen['references'])
            r09.sign_decision(fonts, {'F': [font]}, dict(font='F', source_code=7), 'x', small=True, greek_face=True)
            self.assertTrue(seen['greek_face'])


if __name__ == '__main__':
    unittest.main()
