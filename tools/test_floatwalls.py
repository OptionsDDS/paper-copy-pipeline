"""Lane r5-floatwalls (round 5): where one float ends and the next begins, continuation labels, and the checks across
all floats.

Rules: F20 a continuation form after a table label's number ("Table 3 (Continued)") is a table label, the further
part of that table; F23 the body sentence open before a float continues after it: a piece ending in a decimal number
is open, and with a float between the two pieces and a layout witness they join (list item or not); F33 a missing
number in the copy's figure or table numbers and F34 a mentioned number without a float are listed in the doubt list
(copy.doubts.json, doubts.py), never changing the copy.  Fixtures are invented: synthetic geometry and words.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); mod.__dict__['__file__'] = str(path); spec.loader.exec_module(mod)
    return mod


copy = module('floatwalls_copy', ROOT/'copy_paper.py')


class ContinuedLabel(unittest.TestCase):
    """F20: the continuation forms of section 1e after a table label's number."""
    def test_forms(self):
        for text in ('Table 3 (Continued)', 'TABLE 2. (continued)', 'Table 4 (cont.)', "Table 1 cont'd",
                     'Table 5 Continued', 'T A B L E 2 (Continued) Group means', 'Table IV (continued)'):
            self.assertIsNotNone(copy.continued_table_label(text), text)
        self.assertEqual(copy.continued_table_label('Table 12 (Continued)'), '12')

    def test_look_alikes(self):
        for text in ('Table 3 shows the counts', 'Table 3. Results by group', 'Table 3', 'Figure 2 (continued)',
                     'The table continued on', 'Table 2 lists continued visits'):
            self.assertIsNone(copy.continued_table_label(text), text)


class AroundFloat(unittest.TestCase):
    """F23: a sentence open at a column foot goes on at the next column head after a float."""
    def items(self, tail, head, float_above=True, as_list=True):
        a = dict(kind='para', text=tail, page=1, box=[200, 1200, 1060, 1222], size=20.8, col=(200, 1060),
                 flow_start=(1, 0, True), flow_end=(1, 0, True), list=as_list)
        b = dict(kind='para', text=head, page=1, box=[1100, 620, 1560, 900], size=20.8, col=(1100, 1560),
                 flow_start=(1, 1, True), flow_end=(1, 1, True))
        out = [a, b]
        if float_above:
            out.append(dict(kind='figure', page=1, box=[1100, 60, 1560, 600], caption='Figure 1. A drawn plate'))
        return out

    def join(self, items):
        return [it for it in copy.rejoin_paragraphs(items, copy.Joiner([]), 20.8) if it['kind'] == 'para']

    def test_decimal_end_before_a_float_joins(self):
        out = self.join(self.items('- the dose was set between 4.5', 'Gy and 9.0 Gy for each plate.'))
        self.assertEqual(len(out), 1)
        self.assertIn('4.5 Gy and 9.0', out[0]['text'])

    def test_decimal_end_without_a_float_keeps_the_ordinary_decision(self):
        out = self.join(self.items('- the dose was set between 4.5', 'Gy and 9.0 Gy for each plate.', float_above=False))
        self.assertEqual(len(out), 2)

    def test_sentence_stop_before_a_float_does_not_join(self):
        out = self.join(self.items('- the dose was set for each plate.', 'Gy values were read later.'))
        self.assertEqual(len(out), 2)

    def test_float_between_pieces_geometry(self):
        it = dict(page=1, box=[200, 1200, 1060, 1222])
        nxt = dict(page=1, box=[1100, 620, 1560, 900])
        self.assertTrue(copy.float_between_pieces(it, nxt, {1: [[1100, 60, 1560, 600]]}, 20.8))
        self.assertTrue(copy.float_between_pieces(it, nxt, {1: [[200, 1240, 1060, 1500]]}, 20.8))
        self.assertFalse(copy.float_between_pieces(it, nxt, {1: [[200, 60, 1060, 600]]}, 20.8))
        self.assertFalse(copy.float_between_pieces(it, nxt, {1: [[1100, 950, 1560, 1300]]}, 20.8))


class NumberDoubts(unittest.TestCase):
    """F33 and F34: the doubt list, the copy unchanged."""
    def paper(self, ids, body_text):
        d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, d)
        floats = [dict(id=i, kind='figure', captions=[dict(page=2, box=[100, 100 + 50 * k, 500, 120 + 50 * k])],
                       parts=[dict(page=2, box=[100, 100 + 50 * k, 500, 140 + 50 * k])]) for k, i in enumerate(ids)]
        with open(os.path.join(d, 'copy.floats.json'), 'w') as f:
            json.dump(dict(floats=floats), f)
        md = ['# A title', '', body_text, ''] + ['**%s. A drawn plate**' % i for i in ids] + \
             ['', '---', '## Places the program is not sure of', '- none']
        with open(os.path.join(d, 'copy.md'), 'w') as f:
            f.write('\n'.join(md) + '\n')
        pages = [dict(page=1, elements=[dict(id='run:1', kind='text', text=body_text, box_px=[100, 300, 900, 320])],
                      blocks=[dict(id='block:1', members=['run:1'])],
                      main_text=dict(blocks=[dict(id='block:1', cls='main', order=1)]))]
        return d, pages

    def doubts(self, ids, body_text):
        d, pages = self.paper(ids, body_text)
        D = copy.doubt_list(); D.reset()
        before = Path(d, 'copy.md').read_text()
        copy.float_number_doubts(d, pages, os.path.join(d, 'copy.md'))
        self.assertEqual(Path(d, 'copy.md').read_text(), before)
        return D.items()

    def test_gap_in_the_numbers_is_listed(self):
        got = self.doubts(['Figure 1', 'Figure 2', 'Figure 4'], 'The plates are shown in Figure 1.')
        self.assertEqual([(x['rule'], x['reason']) for x in got], [('F33', 'number_gap:figure:3')])
        self.assertEqual(got[0]['page'], 2)
        self.assertEqual(got[0]['line'], 7)

    def test_mention_without_a_float_is_listed(self):
        got = self.doubts(['Figure 1', 'Figure 2'], 'As Figures 1-3 and Table 2 show, the plates differ.')
        self.assertEqual(sorted(x['reason'] for x in got), ['mention_without_float:figure:3', 'mention_without_float:table:2'])
        self.assertTrue(all(x['rule'] == 'F34' and x['page'] == 1 and x['line'] == 3 for x in got))

    def test_complete_numbers_and_mentions_list_nothing(self):
        self.assertEqual(self.doubts(['Figure 1', 'Figure 2', 'Figure 2b'], 'See Fig. 1 and Figs. 2a, b.'), [])

    def test_mentions_read_ranges_and_pairs(self):
        self.assertEqual([(k, n) for k, n, _ in copy.float_mentions('Figs. 2-4, Table 1 and 3, and Figure 10A')],
                         [('figure', 2), ('figure', 3), ('figure', 4), ('table', 1), ('table', 3), ('figure', 10)])
        self.assertEqual(copy.float_mentions('in section 2.3 of the tables'), [])
        self.assertEqual([(k, n) for k, n, _ in copy.float_mentions('Figure 3, 1,250 records; Table 2.3')], [('figure', 3)])
        self.assertEqual([(k, n) for k, n, _ in copy.float_mentions('see supplementary Figures 2 and 3, and Fig. 4')],
                         [('figure', 4)])
        self.assertEqual(copy.float_mentions('(see sup- plementary Table 7 online) and Table 2'), [('table', 2, 41)])


if __name__ == '__main__':
    unittest.main()
