"""Round 5, rules O16 and O29-O31: display formulas found from the page, simple or stacked."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('formula_blocks', Path(__file__).resolve().parents[1]/'copy_paper.py')
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)

BODY = 10.0


def run(name, text, x, y, size=BODY, step=5.0, base=None):
    """a run of characters set left to right from x, baseline y (top-left page units)"""
    base = y if base is None else base
    chars = [dict(text=ch, x0=x+i*step, x1=x+i*step+step-1, y0=base-size*.75, y1=base+size*.2,
                  origin=(x+i*step, base), size=size) for i, ch in enumerate(text)]
    box = f.hull([c['x0'], c['y0'], c['x1'], c['y1']] for c in chars) if chars else [x, y-size, x, y]
    return dict(id=name, kind='text', text=text, angle=0, _chars=chars, box_px=box)


def prose(name, y, x=50, width=50):
    """a full line of running text in a column from x (width characters of 5 units)"""
    words = ('lorem ipsum dolor sit amet ' * 20)[:width]
    return run(name, words, x, y)


def page(runs, rules=()):
    return dict(page=1, elements=[dict(id='r%d' % i, kind='rule', box_px=list(b)) for i, b in enumerate(rules)], art=[]), \
        {e['id']: e for e in runs}


def column(top=100, n=4, x=50):
    return [prose('p%d' % i, top+i*12, x) for i in range(n)]


class Zones(unittest.TestCase):
    def test_numbered_formula_on_one_baseline_is_simple(self):
        runs = column(100, 3) + [run('f', 'a=b+c', 100, 160), run('n', '(1)', 284, 160)] + column(180, 3)
        runs = runs[:3] + runs[3:5] + [dict(r, id='q%s' % r['id']) for r in runs[5:]]
        p, rs = page(runs)
        zones = f.display_formula_zones(p, rs, set(rs), BODY)
        self.assertEqual(len(zones), 1)
        self.assertEqual(set(zones[0]['ids']), {'f', 'n'})
        self.assertFalse(zones[0]['stacked'])
        self.assertEqual(zones[0]['number'], 'n')

    def test_unread_bracket_sign_counts_as_bracket(self):
        runs = column(100, 3) + [run('f', 'a=b', 100, 160), run('n', '�2�', 284, 160)] + \
            [dict(r, id='q%s' % r['id']) for r in column(180, 3)]
        p, rs = page(runs)
        zones = f.display_formula_zones(p, rs, set(rs), BODY)
        self.assertEqual(len(zones), 1)
        self.assertTrue(zones[0]['unread'])

    def test_bar_with_text_above_and_below_is_stacked(self):
        runs = column(100, 3) + [run('h', 'x =', 60, 166), run('t', 'a+b+c', 90, 160), run('d', 'a-b', 95, 174)] + \
            [dict(r, id='q%s' % r['id']) for r in column(195, 3)]
        p, rs = page(runs, rules=[(88, 163, 118, 163.5)])
        zones = f.display_formula_zones(p, rs, set(rs), BODY)
        self.assertEqual(len(zones), 1)
        self.assertEqual(set(zones[0]['ids']), {'h', 't', 'd'})
        self.assertTrue(zones[0]['stacked'])
        self.assertIn('bar', zones[0]['reasons'])

    def test_prose_lines_close_to_the_formula_stay_out(self):
        runs = column(100, 3) + [run('f', 'a=b', 100, 136), run('n', '(3)', 284, 136)] + \
            [dict(r, id='q%s' % r['id']) for r in column(148, 3)]
        p, rs = page(runs)
        zones = f.display_formula_zones(p, rs, set(rs), BODY)
        self.assertEqual(len(zones), 1)
        self.assertEqual(set(zones[0]['ids']), {'f', 'n'})

    def test_two_rows_of_full_size_characters_are_stacked(self):
        runs = column(100, 3) + [run('f1', 'a=b+c+d', 100, 160), run('f2', '+e+f+g', 110, 172), run('n', '(4)', 284, 166)] + \
            [dict(r, id='q%s' % r['id']) for r in column(195, 3)]
        p, rs = page(runs)
        zones = f.display_formula_zones(p, rs, set(rs), BODY)
        self.assertEqual(len(zones), 1)
        self.assertEqual(zones[0]['reasons'], ['baselines'])

    def test_a_number_in_running_text_is_no_formula(self):
        runs = column(100, 6)
        runs[2] = run('p2', 'lorem ipsum dolor sit amet lorem ipsum dolor (5)', 50, 124)
        p, rs = page(runs)
        self.assertEqual(f.display_formula_zones(p, rs, set(rs), BODY), [])

    def test_table_ruling_drawn_cell_by_cell_is_no_bar(self):
        runs = column(100, 3) + [run('h1', 'ab', 60, 156), run('h2', 'cd', 120, 156), run('v1', '1.5', 60, 172), run('v2', '2.5', 120, 172)] + \
            [dict(r, id='q%s' % r['id']) for r in column(195, 3)]
        p, rs = page(runs, rules=[(50, 163, 110, 163.5), (110, 163, 170, 163.5), (170, 163, 300, 163.5)])
        self.assertEqual(f.display_formula_zones(p, rs, set(rs), BODY), [])

    def test_no_formula_without_number_or_bar(self):
        runs = column(100, 3) + [run('f', 'a=b+c', 100, 160)] + [dict(r, id='q%s' % r['id']) for r in column(180, 3)]
        p, rs = page(runs)
        self.assertEqual(f.display_formula_zones(p, rs, set(rs), BODY), [])

    def test_short_rule_without_level_text_is_no_bar(self):
        # a short rule between two short lines (a column-head rule of a small unruled table): nothing level with it
        runs = column(100, 3) + [run('t', 'a+b+c', 90, 160), run('d', 'a-b', 95, 174)] + \
            [dict(r, id='q%s' % r['id']) for r in column(195, 3)]
        p, rs = page(runs, rules=[(88, 163, 118, 163.5)])
        self.assertEqual(f.display_formula_zones(p, rs, set(rs), BODY), [])

    def test_inline_fraction_in_a_line_of_running_text_is_listed_not_lifted(self):
        # hold-back memo 1: a small bar mid-line, prose on both sides on the same line, no number, no gaps
        runs = column(100, 3) + [run('l', 'lorem ipsum dolor sit amet ratio', 50, 136), run('t', 'a+b+c', 214, 132, size=7),
                                 run('d', 'n+m', 216, 141, size=7), run('r', 'of each vessel was kept', 245, 136)] + \
            [dict(r, id='q%s' % r['id']) for r in column(148, 3)]
        p, rs = page(runs, rules=[(212, 134.5, 240, 135)])
        zones = f.display_formula_zones(p, rs, set(rs), BODY)
        self.assertEqual([(z.get('inline'), z['ids']) for z in zones], [(True, [])])

    def test_display_fraction_with_a_short_left_hand_side_is_no_inline_fraction(self):
        runs = column(100, 3) + [run('h', 'Drift (%) =', 60, 166), run('t', 'a+b+c', 120, 160), run('d', 'a-b', 125, 174)] + \
            [dict(r, id='q%s' % r['id']) for r in column(195, 3)]
        p, rs = page(runs, rules=[(118, 163, 148, 163.5)])
        zones = f.display_formula_zones(p, rs, set(rs), BODY)
        self.assertEqual(len(zones), 1)
        self.assertFalse(zones[0].get('inline'))
        self.assertEqual(set(zones[0]['ids']), {'h', 't', 'd'})

    def test_rule_inside_a_filled_box_with_word_lines_is_no_bar(self):
        # pool memo 1: a shaded key-points box, a divider under its title, short list lines under it
        runs = column(100, 3) + [run('h', 'Key points', 60, 160), run('t', 'of the work', 60, 172), run('w', 'lorem ipsum dolor sit', 60, 196),
                                 run('l1', '1. Loss 3 %', 60, 186)] + [dict(r, id='q%s' % r['id']) for r in column(215, 3)]
        p, rs = page(runs, rules=[(58, 176, 120, 176.4)])
        p['elements'].append(dict(id='fill', kind='fill', box_px=[52, 148, 200, 200]))
        self.assertEqual([z for z in f.display_formula_zones(p, rs, set(rs), BODY) if not z.get('inline')], [])

    def test_a_line_across_the_page_does_not_merge_the_columns(self):
        # two columns under a wide line; a numbered formula in the left column takes nothing of the right one
        left = [prose('a%d' % i, 100+i*12, 50) for i in range(4)]
        right = [prose('b%d' % i, 100+i*12, 320) for i in range(8)]
        wide = [run('w', ('lorem ipsum dolor sit amet ' * 20)[:104], 50, 80)]
        runs = wide + left + right + [run('f', 'a=b+c', 100, 160), run('n', '(1)', 284, 160)] + \
            [prose('c%d' % i, 180+i*12, 50) for i in range(3)]
        p, rs = page(runs)
        zones = f.display_formula_zones(p, rs, set(rs), BODY)
        self.assertEqual(len(zones), 1)
        self.assertEqual(set(zones[0]['ids']), {'f', 'n'})


class Writing(unittest.TestCase):
    def test_stacked_block_keeps_its_rows_no_one_line_fraction(self):
        top, bottom = run('top', 'a+b', 20, 29), run('bottom', '2', 25, 39)
        p = dict(page=1, tables=[], floats=[], elements=[dict(id='bar', kind='rule', box_px=[19, 30, 35, 30.5])])
        rows = f.prose_text_rows([top, bottom], p, fractions=False)
        self.assertEqual([[e['id'] for e in r] for r in rows], [['top'], ['bottom']])
        self.assertNotIn('copy_formulas', p)

    def test_doubt_list_is_the_shared_module(self):
        import json, tempfile, os
        d = f.doubts_list(); d.reset()
        d.add('O30', 2, [1, 2, 3, 4], 'stacked_formula:bar')
        with tempfile.TemporaryDirectory() as tmp:
            d.write(tmp)
            with open(os.path.join(tmp, 'copy.doubts.json')) as fh: items = json.load(fh)
        self.assertEqual(items, [dict(rule='O30', page=2, box=[1.0, 2.0, 3.0, 4.0], reason='stacked_formula:bar')])
        d.reset()


if __name__ == '__main__':
    unittest.main()
