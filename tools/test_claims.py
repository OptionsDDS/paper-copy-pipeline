"""Lane claims: R1 small faces (sign_outline_decision among the sign and Greek sets), R2 a Greek letter inside a
word named by its outline and its raster, R3 white text overprinted by later glyphs, and the copier's two
follow-ups (a flagged glyph in front-row deduplication, the Greek hyphen rule).
/usr/bin/python3 -I tools/test_claims.py"""
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fonts', TOOLS/'check_fonts.py')
fonts = importlib.util.module_from_spec(spec); spec.loader.exec_module(fonts)
paper = fonts.signs.copy
sys.path.insert(0, str(TOOLS/'secondpass'))   # rule 9 imports its folder's common module (before the reader's import guard)
r09 = importlib.import_module('r09_glyphs')
sys.path.pop(0)
if '_copy_table_reader' not in sys.modules:   # the copier's own reader module, as table_characters loads it
    spec = importlib.util.spec_from_file_location('_copy_table_reader', TOOLS.parent/'standalone'/'element_boxer_sc.py')
    module = importlib.util.module_from_spec(spec); sys.modules['_copy_table_reader'] = module; spec.loader.exec_module(module)
reader = sys.modules['_copy_table_reader']


class SmallFaceDecision(unittest.TestCase):
    def test_comparison_signs_claimed_as_comma_and_period(self):
        # AP24: '<' and '>' outlines whose text layer says ',' and '.'
        self.assertEqual(fonts.sign_outline_decision(',', {',': .16, '<': .59, 'c': .29}, small=True), ('replaced', '<'))
        self.assertEqual(fonts.sign_outline_decision('.', {'.': .18, '>': .59, ')': .31}, small=True), ('replaced', '>'))

    def test_gamma_claimed_as_c_is_flagged(self):
        # AP01: the best reference is the Latin 'y', gamma under the sign floor: neither is printed
        self.assertEqual(fonts.sign_outline_decision('c', {'c': .086, 'y': .52, 'γ': .47}, small=True), ('rejected', '�'))

    def test_greek_letters_compete_and_the_best_family_member_is_printed(self):
        # AP24: chi claimed as 'v'; the cross family holds × and χ, chi scores higher
        scores = {'v': .30, 'χ': .75, 'x': .61, 'X': .61, '×': .45, 'o': .40}
        self.assertEqual(fonts.sign_outline_decision('v', scores, small=True), ('replaced', 'χ'))
        # without the small-face rule the sign set alone decides: the claim is only rejected
        # (glyphsigns re-ladder R-a: the cross's own score .45 is under the sign floor; chi is no ×)
        self.assertEqual(fonts.sign_outline_decision('v', scores), ('rejected', '\ufffd'))
        self.assertEqual(fonts.sign_outline_decision('b', {'b': .34, 'β': .67, 'f': .48}, small=True), ('replaced', 'β'))

    def test_claim_above_the_floor_is_kept_and_a_measured_sign_under_it_is_rejected(self):
        self.assertEqual(fonts.sign_outline_decision('a', {'a': .50, 'α': .60}, small=True), ('confirmed', 'a'))
        # a measured non-ASCII claim under the floor: kept by the sign-face rule, rejected in a small face
        self.assertEqual(fonts.sign_outline_decision('±', {'±': .30, '†': .40}), ('unchanged', '±'))
        # (re-ladder: in a small face the rival must itself reach the floor to flag a sign claim)
        self.assertEqual(fonts.sign_outline_decision('±', {'±': .30, '†': .46}, small=True), ('rejected', '�'))
        self.assertEqual(fonts.sign_outline_decision('±', {'±': .30, '†': .40}, small=True), ('confirmed', '±'))
        # an unmeasured claim (no reference of its family) is never rejected by the floor
        self.assertEqual(fonts.sign_outline_decision('Δ', {'A': .50, '±': .30}, small=True), ('unchanged', 'Δ'))

    def test_saved_proof_reproduces_the_small_face_decision(self):
        proof = dict(before='v', scores={'v': .30, 'χ': .75, 'x': .61, 'X': .61, 'o': .40}, sign_claim='small face',
                     small_face=True)
        self.assertEqual(fonts.saved_outline_decision(proof), ('replaced', 'χ'))
        # outside the small face only the sign set competes, on the sign's own score (glyphsigns R-a): rejected
        self.assertEqual(fonts.saved_outline_decision(dict(proof, small_face=False)), ('rejected', '\ufffd'))

    def test_notice_names_font_code_score_count_and_pages(self):
        sub = dict(sign_claim='small face', status='rejected', before='c', after='�', claim_score=.086)
        text = fonts.sign_notice('JPIOBH+AdvPSMP13', 99, sub, 2, [8, 19])
        for part in ('JPIOBH+AdvPSMP13', 'glyph 99', "'c'", '0.09', '2 places', 'pages 8, 19', '�'):
            self.assertIn(part, text)
        named = fonts.sign_notice('X', 44, dict(sign_claim='sign face', status='replaced', before=',', after='<'), 1, [2])
        self.assertNotIn('scores', named)


def glyph(font, code, before, offset, char_id, box):
    return dict(font=font, source_code=code, before=before, offset=offset, char_id=char_id, box_px=box)


class SmallFaceSelection(unittest.TestCase):
    """verify_outlines with patched outlines: a face of <= 5 used codes beside a body face of more."""
    refs = {ch: [(ch,)] for ch in ',<c.>fγy'}
    table = {(44, ','): .16, (44, '<'): .59, (44, 'c'): .29, (3, 'f'): .40, (7, 'c'): .09, (7, 'y'): .52, (7, 'γ'): .47}

    def run_outlines(self, runs, body_codes=7):
        body = [glyph('BODY', 100+i, 'etaoinsrh'[i], i, i, [i*10, 0, i*10+9, 10]) for i in range(body_codes)]
        runs = [dict(page=1, id='run:0', source='etaoinsrh'[:body_codes], crop_xywh=[0, 0, 90, 10], font_glyphs=body)] + runs
        doc = SimpleNamespace(fonts={1: SimpleNamespace(basefont='BODY', base='StandardEncoding', cid=False, prog=None),
                                     2: SimpleNamespace(basefont='SMALL', base='StandardEncoding', cid=False, prog=None)})
        with patch.object(fonts, 'outline_references', return_value=self.refs), \
             patch.object(fonts, 'sign_references', return_value=self.refs), \
             patch.object(fonts, 'outline_shape', side_effect=lambda f, code: (code, 1.0, .5)), \
             patch.object(fonts, 'outline_similarity', side_effect=lambda a, b: self.table.get((a[0], b[0]), .1)):
            return fonts.verify_outlines(doc, runs)

    def test_comma_of_a_small_face_becomes_less_than(self):
        runs = [dict(page=1, id='run:1', source='p,0.015', crop_xywh=[0, 20, 60, 10],
                     font_glyphs=[glyph('SMALL', 44, ',', 1, 20, [5, 20, 9, 30])])]
        result = self.run_outlines(runs)
        record = result['records'][0]
        self.assertEqual((record['after'], record['status'], record['sign_claim'], record['small_face']),
                         ('<', 'replaced', 'small face', True))

    def test_letter_inside_a_word_of_a_small_face_is_rejected(self):
        runs = [dict(page=1, id='run:1', source='Fcc receptors', crop_xywh=[0, 20, 60, 10],
                     font_glyphs=[glyph('SMALL', 7, 'c', 2, 20, [5, 20, 9, 30])])]
        record = self.run_outlines(runs)['records'][0]
        self.assertEqual((record['after'], record['status']), ('�', 'rejected'))

    def test_no_body_contrast_no_small_face(self):
        runs = [dict(page=1, id='run:1', source='p,0.015', crop_xywh=[0, 20, 60, 10],
                     font_glyphs=[glyph('SMALL', 44, ',', 1, 20, [5, 20, 9, 30])])]
        self.assertEqual(self.run_outlines(runs, body_codes=5)['records'], [])

    def test_ligature_glyph_is_exempt(self):
        # one 'ff' glyph: the reader gives both characters the glyph's own box
        runs = [dict(page=1, id='run:1', source='effects', crop_xywh=[0, 20, 60, 10],
                     font_glyphs=[glyph('SMALL', 3, 'f', 1, 20, [5, 20, 15, 30]), glyph('SMALL', 3, 'f', 2, 21, [5, 20, 15, 30])])]
        result = self.run_outlines(runs)
        self.assertEqual(result['records'], [])
        self.assertNotIn('small face', result['selected'])

    def test_claim_without_its_own_silhouette_is_exempt(self):
        runs = [dict(page=1, id='run:1', source='“Iuliu”', crop_xywh=[0, 20, 60, 10],
                     font_glyphs=[glyph('SMALL', 147, '“', 0, 20, [5, 20, 9, 30])])]
        result = self.run_outlines(runs)
        self.assertEqual(result['records'], [])
        self.assertNotIn('small face', result['selected'])


class SecondPassSmallFaces(unittest.TestCase):
    def test_rule_9_selects_the_same_small_faces(self):
        def c(font, code, text, x): return dict(font=font, source_code=code, text=text, x0=x, y0=0, x1=x+5, y1=10)
        body = [c('BODY', 100+i, 'etaoinsrh'[i], i*10) for i in range(7)]
        pages = [(1, body + [c('SMALL', 44, ',', 200), c('LIG', 3, 'f', 300), c('LIG', 3, 'f', 300)])]
        self.assertEqual(r09.small_faces(fonts, pages), {('SMALL', 44)})
        self.assertEqual(r09.small_faces(fonts, [(1, body[:5] + [c('SMALL', 44, ',', 200)])]), set())


class GreekInWords(unittest.TestCase):
    def test_outline_names_a_greek_letter(self):
        self.assertEqual(fonts.outline_greek('a', {'a': .36, 'α': .65, 'σ': .50}), 'α')
        self.assertIsNone(fonts.outline_greek('a', {'a': .36, 'α': .61, 'σ': .52}))     # runner-up within .10
        self.assertIsNone(fonts.outline_greek('a', {'a': .46, 'α': .70}))               # the claim passes the floor
        self.assertIsNone(fonts.outline_greek('w', {'w': .32, 'ω': .54, 'm': .30}))     # under the sign floor
        self.assertIsNone(fonts.outline_greek('5', {'5': .10, 'α': .80}))               # not a Latin letter

    def record(self, offset, alone):
        return dict(font='F', source_code=97, before='a', status='measured', similarity=.30, crop=f'c{offset}.png',
                    alternatives={'α': .75, 'σ': .40}, source='TNFa receptor', offset=offset, alone=alone,
                    legacy_selected=False, raster_symbols=[])

    def test_raster_and_outline_agree_alone_in_its_face(self):
        named = {('F', 97): dict(before='a', character='α', scores={'a': .36, 'α': .65, 'σ': .50})}
        d = fonts.decide_verification([self.record(3, True)], {}, None, None, None, named)['F']['97']
        self.assertEqual((d['status'], d['after']), ('rejected', 'α'))
        self.assertTrue(fonts.valid_verification(d, 'a', 'α'))
        self.assertFalse(fonts.valid_verification(dict(d, proof=dict(d['proof'], outline_greek=dict(
            character='α', scores={'a': .50, 'α': .65}))), 'a', 'α'))

    def test_a_letter_of_its_own_face_inside_a_word_is_not_replaced(self):
        # Korinna-Kursiv 'w' resembles omega; its neighbours are in its own face
        named = {('F', 97): dict(before='a', character='α', scores={'a': .36, 'α': .65, 'σ': .50})}
        d = fonts.decide_verification([self.record(3, False)], {}, None, None, None, named)['F']['97']
        self.assertNotEqual(d.get('after'), 'α')
        d = fonts.decide_verification([self.record(3, True)], {}, None, None, None, {})['F']['97']
        self.assertNotEqual(d.get('after'), 'α')


def char(text, x, order, colour=(0, 0, 0), space='DeviceRGB', y=100, size=14):
    return dict(text=text, x0=x, y0=y-10, x1=x+6, y1=y, origin=(x, y), size=size, paint_order=(order, x),
                fill_color=colour, fill_space=space, render_mode=0, fill_alpha=1, hidden=False)


class OverprintedLayers(unittest.TestCase):
    texts = [dict(paint_serial=1), dict(paint_serial=2), dict(paint_serial=5)]

    def test_white_layer_under_later_black_glyphs_is_hidden(self):
        white = [char(t, 100+7*i, 0, (1, 1, 1), 'ICCBased') for i, t in enumerate('https://doi')]
        black = [char(t, 100+7*i, 1) for i, t in enumerate('DOI: 10.117')]
        self.assertEqual(reader.sc_overprinted_layers(white+black, self.texts, []), [0])

    def test_white_banner_text_that_nothing_overprints_stays(self):
        white = [char(t, 100+7*i, 0, (1, 1, 1)) for i, t in enumerate('REVIEW')]
        black = [char(t, 100+7*i, 1, y=200) for i, t in enumerate('Title')]
        self.assertEqual(reader.sc_overprinted_layers(white+black, self.texts, []), [])

    def test_white_text_on_an_earlier_coloured_fill_stays(self):
        white = [char(t, 100+7*i, 0, (1, 1, 1)) for i, t in enumerate('https://doi')]
        black = [char(t, 100+7*i, 1) for i, t in enumerate('DOI: 10.117')]
        self.assertEqual(reader.sc_overprinted_layers(white+black, self.texts, [((90, 80, 300, 110), 0.5)]), [])
        # a fill painted after the white text is not its background
        self.assertEqual(reader.sc_overprinted_layers(white+black, self.texts, [((90, 80, 300, 110), 3.5)]), [0])

    def test_coloured_or_mostly_uncovered_layers_stay(self):
        grey = [char(t, 100+7*i, 0, (.5, .5, .5)) for i, t in enumerate('https://doi')]
        black = [char(t, 100+7*i, 1) for i, t in enumerate('DOI: 10.117')]
        self.assertEqual(reader.sc_overprinted_layers(grey+black, self.texts, []), [])
        white = [char(t, 100+7*i, 0, (1, 1, 1)) for i, t in enumerate('https://doi.org/10.1177')]
        short = [char(t, 100+7*i, 1) for i, t in enumerate('DOI:')]
        self.assertEqual(reader.sc_overprinted_layers(white+short, self.texts, []), [])

    def test_white_in_device_and_icc_spaces(self):
        self.assertTrue(reader.sc_white_fill((1, 1, 1), 'ICCBased'))
        self.assertTrue(reader.sc_white_fill(1, 'DeviceGray'))
        self.assertTrue(reader.sc_white_fill([0, 0, 0, 0], 'DeviceCMYK'))
        self.assertFalse(reader.sc_white_fill((1, 1, 1), 'Separation'))
        self.assertFalse(reader.sc_white_fill((0, 0, 0), 'DeviceRGB'))

    def test_copier_lists_each_hidden_layer_once_with_its_text(self):
        pages = [dict(page=1, hidden_layers=[dict(evidence=reader.SC_OVERPRINT_REASON, dropped_glyphs=40,
                                                  text='https://doi.org/10.1177/0022034519842510'),
                                             dict(evidence='outside text clip', dropped_glyphs=5, text='Draft')])]
        uncertain = []
        paper.list_overprinted_layers(pages, uncertain)
        self.assertEqual(len(uncertain), 1)
        self.assertIn('https://doi.org/10.1177/0022034519842510', uncertain[0])
        self.assertIn('page 1', uncertain[0])


class CopierFollowUps(unittest.TestCase):
    def test_flagged_glyph_matches_its_native_character_in_front_rows(self):
        self.assertTrue(paper.compact_in('� Interleukin Genetics, Waltham, MA.', ['i Interleukin Genetics, Waltham, MA.']))
        self.assertTrue(paper.compact_in('Interleukin Genetics', ['interleukin genetics']))
        self.assertFalse(paper.compact_in('� Interleukin Genetics, Boston', ['i Interleukin Genetics, Waltham, MA.']))

    def test_flagged_glyph_is_ordered_in_place_and_an_unreadable_code_abstains(self):
        def c(t, x, code=1, **k): return dict(text=t, x0=x, x1=x+6, y0=90, y1=100, origin=(x, 100), size=12,
                                             adv_x1=x+6, source_code=code, font='F', **k)
        word = dict(id='run:1', angle=0, text='Mendonca', _chars=[c(t, 100+6*i) for i, t in enumerate('Mendonca')])
        mark = dict(id='run:2', angle=0, text='\ufffd', _chars=[dict(c('\ufffd', 139, 120), x1=142, y0=100, y1=104)])
        self.assertEqual(paper.positioned_prose_text([word, mark], {}), 'Mendonc\ufffda')
        unreadable = dict(mark, _chars=[dict(c('\ufffd', 139, 2, dropped_control=True), x1=142, y0=100, y1=104)])
        self.assertIsNone(paper.positioned_prose_text([word, unreadable], {}))

    def test_greek_letter_keeps_its_hyphen_unless_the_joined_word_is_printed(self):
        j = paper.Joiner(['without altering μopioid receptors'])
        self.assertEqual(j.lines(['the number of μopi-', 'oid receptors']), 'the number of μopioid receptors')
        j = paper.Joiner(['no closed form here'])
        self.assertEqual(j.lines(['the β-', 'blocking agents']), 'the β-blocking agents')


if __name__ == '__main__':
    unittest.main()
