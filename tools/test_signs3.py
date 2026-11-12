"""Two-part punctuation claimed for a sign, and stacked fractions with word operands.

Run: /usr/bin/python3 -I tools/test_signs3.py
"""
import copy
import importlib.util
import math
from pathlib import Path
import unittest

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('signs3_fonts', root/'tools/check_fonts.py')
fonts = importlib.util.module_from_spec(spec); spec.loader.exec_module(fonts)
spec = importlib.util.spec_from_file_location('signs3_copy', root/'copy_paper.py')
cp = importlib.util.module_from_spec(spec); spec.loader.exec_module(cp)


def bitmap(width, height, points):
    return width, height, b''.join(b'\0\0\0' if (x, y) in points else b'\xff\xff\xff'
                                   for y in range(height) for x in range(width))


def wave(width=28, amplitude=3, top=10):
    """A tilde: low left end, crest, trough, high right end; two pixels thick."""
    points = set()
    for x in range(width):
        y = round(top+amplitude-amplitude*math.sin(2*math.pi*x/(width-1)))
        points |= {(x+2, y), (x+2, y+1)}
    return points


class Tilde(unittest.TestCase):
    def test_wave_above_baseline_is_a_tilde(self):
        self.assertIn('∼', fonts.raster_symbols(bitmap(34, 30, wave()), 40, 26))

    def test_dash_semicolon_and_baseline_wave_are_not(self):
        dash = {(x, y) for x in range(2, 30) for y in (12, 13)}
        self.assertNotIn('∼', fonts.raster_symbols(bitmap(34, 30, dash), 40, 26))
        semicolon = {(x, y) for x in (5, 6, 7) for y in (4, 5, 6)} | {(x, y) for x in (5, 6, 7) for y in (14, 15, 16)} | {(5, 17), (4, 18)}
        self.assertNotIn('∼', fonts.raster_symbols(bitmap(12, 22, semicolon), 40, 17))
        # The same wave hanging below the baseline is not an operator on the math axis.
        self.assertNotIn('∼', fonts.raster_symbols(bitmap(34, 30, wave()), 40, 12))


class Selection(unittest.TestCase):
    def test_punctuation_needs_other_face_and_number(self):
        self.assertTrue(fonts.sign_verification_eligible('for ;50 years', 4, 'X+Sign', 'X+Body'))
        self.assertFalse(fonts.sign_verification_eligible('for ;50 years', 4, 'X+Body', 'X+Body'))
        self.assertFalse(fonts.sign_verification_eligible('one; two', 3, 'X+Sign', 'X+Body'))
        self.assertFalse(fonts.sign_verification_eligible('1.5', 1, 'X+Sign', 'X+Body'))
        # Signs keep their earlier rule: another face alone selects them.
        self.assertTrue(fonts.sign_verification_eligible('a – b', 2, 'X+Sign', 'X+Body'))


def row(parts=1, similarity=.13, shapes=('∼',), tilde=.43, other=.36):
    return dict(before=';', similarity=similarity, ink_parts=parts, raster_symbols=list(shapes),
                alternatives={'∼': tilde, '←': other, '−': .34})


class Structure(unittest.TestCase):
    def test_one_part_tilde_is_named(self):
        self.assertEqual(fonts.punctuation_structure(';', [row(), row()]), '~')

    def test_two_parts_or_confirmed_template_keep_the_claim(self):
        self.assertIsNone(fonts.punctuation_structure(';', [row(), row(parts=2)]))
        self.assertIsNone(fonts.punctuation_structure(';', [row(similarity=.40)]))
        self.assertIsNone(fonts.punctuation_structure('-', [row()]))
        self.assertIsNone(fonts.punctuation_structure(';', [dict(row(), ink_parts=None)]))

    def test_unnamed_or_contested_shape_is_flagged(self):
        self.assertEqual(fonts.punctuation_structure(';', [row(shapes=())]), '�')
        self.assertEqual(fonts.punctuation_structure(';', [row(other=.50)]), '�')
        self.assertEqual(fonts.punctuation_structure(';', [row(tilde=.30)]), '�')
        self.assertEqual(fonts.punctuation_structure(';', [row(), row(shapes=('−',))]), '�')

    def test_alternative_evidence_respects_two_parts(self):
        rows = [dict(row(parts=2), alternatives={'∼': .9})]
        self.assertIsNone(fonts.alternative_evidence(rows))

    def test_saved_decision_is_revalidated(self):
        rows = [row()]
        proof = dict(model=fonts.VERIFY_MODEL, before=';', after='~', similarity=.13,
                     threshold=fonts.VERIFY_THRESHOLD, status='rejected', proof=dict(structure_rows=rows))
        self.assertTrue(fonts.valid_verification(proof, ';', '~'))
        self.assertFalse(fonts.valid_verification(dict(proof, after='∼'), ';', '∼'))
        forged = copy.deepcopy(proof); forged['proof']['structure_rows'][0]['ink_parts'] = 2
        self.assertFalse(fonts.valid_verification(forged, ';', '~'))


def text_run(name, text, x, baseline, size=19, big=()):
    chars = []; offset = x
    for i, ch in enumerate(text):
        if ch == ' ': offset += 5; continue
        tall = i in big
        chars.append(dict(text=ch, x0=offset, x1=offset+8, y0=baseline-(18 if tall else 13), y1=baseline+(5 if tall else 0),
                          origin=(offset, baseline), size=size, adv_x1=offset+9))
        offset += 9
    return dict(id=name, kind='text', text=text, angle=0, _chars=chars, char_ids=list(range(len(chars))),
                box_px=cp.hull([c[k] for k in ('x0', 'y0', 'x1', 'y1')] for c in chars), run_size_px=size)


def tail_run(name, text, tail, x, baseline, rule_y):
    e = text_run(name, text+' '+tail, x, baseline)
    n = len(text.replace(' ', ''))
    for c in e['_chars'][n:]:
        c['y0'], c['y1'] = rule_y-6, rule_y+5
    e['box_px'] = cp.hull([c[k] for k in ('x0', 'y0', 'x1', 'y1')] for c in e['_chars'])
    return e


def fraction_page(intro='Bone fill =', tail='× 100', rule_width=None, wrapped='(base level) −'):
    runs = [text_run('intro', intro, 100, 100)] if intro else []
    if wrapped: runs.append(text_run('wrapped', wrapped, 100, 125))
    runs.append(tail_run('top', '(month level)', tail, 100, 150, 156) if tail else text_run('top', '(month level)', 100, 150))
    runs.append(text_run('bottom', '(base level)', 104, 177))
    runs.append(text_run('next', 'where the level is the distance between two marks of the tooth', 100, 215))
    width = rule_width or max(r['box_px'][2] for r in runs if r['id'] in ('wrapped', 'top', 'bottom') and r['id'] != 'top') - 99
    width = max(width, 120)
    rule = dict(id='rule:9', kind='rule', box_px=[99, 156, 99+width, 157])
    page = dict(page=6, tables=[], floats=[], elements=[], art=[rule], main_text=dict(columns=[[90, 700]]))
    return runs, page


class WordFractions(unittest.TestCase):
    def test_wrapped_numerator_is_grouped_and_divided(self):
        runs, page = fraction_page(); original = copy.deepcopy(runs)
        result = cp.display_formula_runs(runs, page)
        texts = [e['text'] for e in result]
        self.assertEqual(texts[1], '[(base level) − (month level)] / (base level) × 100')
        self.assertEqual([e['id'] for e in result], ['intro', 'wrapped', 'next'])
        self.assertEqual(set(page['copy_formulas'][0]['runs']), {'wrapped', 'top', 'bottom'})
        self.assertEqual({e['id'] for e in result[1]['_formula_sources']}, {'wrapped', 'top', 'bottom'})
        self.assertEqual(runs, original)

    def test_single_line_operands_keep_their_brackets(self):
        runs, page = fraction_page(wrapped=None)
        self.assertEqual(cp.display_formula_runs(runs, page)[1]['text'], '(month level) / (base level) × 100')

    def test_without_introducer_or_operator_it_stays_prose(self):
        runs, page = fraction_page(intro='Bone fill', tail=None, wrapped=None)
        self.assertEqual(cp.display_formula_runs(runs, page), runs)
        self.assertFalse(page.get('copy_formulas'))

    def test_prose_beside_the_operands_stops_the_grouping(self):
        runs, page = fraction_page(wrapped=None)
        bottom = next(e for e in runs if e['id'] == 'bottom')
        longer = text_run('bottom', '(base level) and the following words of the sentence', 104, 177)
        runs[runs.index(bottom)] = longer
        self.assertEqual(cp.display_formula_runs(runs, page), runs)

    def test_column_wide_rule_and_table_frame_abstain(self):
        runs, page = fraction_page(wrapped=None)
        page['main_text']['columns'] = [[95, 225]]
        self.assertEqual(cp.display_formula_runs(runs, page), runs)
        runs, page = fraction_page(wrapped=None)
        page['tables'] = [dict(box_px=[0, 0, 800, 400])]
        self.assertEqual(cp.display_formula_runs(runs, page), runs)

    def test_operand_grouping(self):
        self.assertEqual(cp.formula_operand('( a + b )'), '(a + b)')
        self.assertEqual(cp.formula_operand('(a) − (b)'), '[(a) − (b)]')
        self.assertEqual(cp.formula_operand('a'), '[a]')
        self.assertEqual(cp.formula_operand('(a'), '[(a]')


if __name__ == '__main__':
    unittest.main()
