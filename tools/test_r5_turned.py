"""Lane r5-turned (rule F17): turned side text is set apart and read in its own turned frame; no corpus strings or IDs."""
import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1] / 'copy_paper.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def run(t, box, angle=0):
    return dict(id='r:%s:%s' % (box[0], box[1]), kind='text', text=t, box_px=list(box), angle=angle, line=0, char_ids=[])


class TurnedSide(unittest.TestCase):
    def test_turned_group_is_turned(self):
        self.assertTrue(c.turned_side_text([run('Alpha beta gamma', [10, 100, 20, 300], 90)]))
        self.assertTrue(c.turned_side_text([run('Alpha beta gamma', [10, 100, 20, 300], 270)]))

    def test_upright_group_is_not_turned(self):
        self.assertFalse(c.turned_side_text([run('Alpha beta gamma', [10, 100, 200, 112])]))
        self.assertFalse(c.turned_side_text([]))

    def test_majority_of_characters_decides(self):
        rs = [run('Alpha beta gamma delta', [10, 100, 200, 112]), run('ab', [300, 100, 310, 120], 90)]
        self.assertFalse(c.turned_side_text(rs))
        rs = [run('xy', [10, 100, 30, 112]), run('Alpha beta gamma', [300, 100, 310, 300], 90)]
        self.assertTrue(c.turned_side_text(rs))

    def test_quarter_turn_reads_left_to_right_across_lines(self):
        # 90 degrees: a line reads bottom to top; the next line lies to its right
        a = c.TurnedSide(['first'], [run('first', [10, 100, 20, 300], 90)])
        b = c.TurnedSide(['second'], [run('second', [22, 150, 32, 300], 90)])
        self.assertLess(a.frame_key, b.frame_key)

    def test_three_quarter_turn_reads_right_to_left_across_lines(self):
        # 270 degrees: a line reads top to bottom; the next line lies to its left
        a = c.TurnedSide(['first'], [run('first', [40, 100, 50, 300], 270)])
        b = c.TurnedSide(['second'], [run('second', [28, 100, 38, 250], 270)])
        self.assertLess(a.frame_key, b.frame_key)

    def test_turned_side_is_still_a_list_of_rows(self):
        t = c.TurnedSide(['one', 'two'], [run('one two', [10, 100, 20, 300], 90)])
        self.assertEqual(list(t), ['one', 'two'])
        self.assertIsInstance(t, list)


def page(texts, tables=(), floats=()):
    return dict(page=3, elements=list(texts), tables=list(tables), floats=list(floats))


class TurnedFloatPage(unittest.TestCase):
    """F18 (round 5b/5c): a page where most text is turned is a float page; the float of its table label owns the
    whole turned area from the label on (caption zone = the label's own block); captionless table parts at that turn
    join it; what still stays outside gives one doubt entry for the page."""

    def cells(self, xs):
        return [run('x' * 50, [x, 100, x + 8, 400], 90) for x in xs]

    def test_turned_page_angle_needs_most_characters_turned(self):
        turned = self.cells([10 * i for i in range(6)])
        self.assertEqual(c.turned_page_angle(page(turned + [run('y' * 20, [0, 20, 200, 30])])), 90)
        self.assertIsNone(c.turned_page_angle(page(turned[:1] + [run('y' * 400, [0, 20, 200, 30])])))
        self.assertIsNone(c.turned_page_angle(page([run('x' * 50, [0, 100, 8, 400], 90)])))   # under 200 characters

    def setup_strip(self):
        # label at the turned top (small x), a recorded strip in the middle, turned lines on both sides of it
        label = run('Table 3 (continued)', [20, 300, 28, 400], 90)
        strip = self.cells([200, 210, 220])
        before = self.cells([60, 70]); after = self.cells([300, 310])
        tables = {'copy:part': dict(id='copy:part', angle=90, box_px=[200, 100, 228, 400], members=[e['id'] for e in strip])}
        floats = [dict(id='f:label', blocks=['copy:caption:l'], _caption_ids=[label['id']]),
                  dict(id='f:part', blocks=['copy:part'])]
        p = page([label] + strip + before + after, tables.values(), floats)
        p['blocks'] = [dict(id='copy:caption:l', members=[label['id']])]
        side = [c.TurnedSide(['b'], [e]) for e in before + after]
        return p, tables, side, label, strip, before, after

    def test_lines_on_both_sides_of_a_middle_strip_join_the_label_float(self):
        p, tables, side, label, strip, before, after = self.setup_strip()
        src = {}
        c.turned_float_leftovers(p, src, side, tables, 10)
        offer = src['_turned_float_offer']
        self.assertEqual(offer['caption'], [label['id']])
        self.assertIsNone(offer['table'])
        self.assertEqual(offer['merge'], ['copy:part'])
        self.assertEqual(sorted(offer['ids']), sorted(e['id'] for e in before + after))
        self.assertEqual(len(src['_turned_float_left']), 4)
        src['_turned_float_runs'] = offer
        c.extend_turned_float(p, src)
        made = [t for t in p['tables'] if t['id'].startswith('copy:turned:')]
        self.assertEqual(len(made), 1)
        self.assertEqual(set(made[0]['members']), {e['id'] for e in strip + before + after})
        self.assertEqual(made[0]['layout'], 'unstructured')
        self.assertTrue(made[0]['_copy_printed_lines'])
        self.assertNotIn('copy:part', [t['id'] for t in p['tables']])
        self.assertEqual([f['id'] for f in p['floats']], ['f:label'])
        self.assertIn(made[0]['id'], p['floats'][0]['blocks'])

    def test_one_table_part_without_a_label_takes_the_leftovers(self):
        cells = self.cells([100 + 10 * i for i in range(6)])
        left = run('a left out cell', [60, 120, 68, 300], 90)
        tables = {'table:1': dict(id='table:1', angle=90, box_px=[90, 90, 200, 410], members=[e['id'] for e in cells])}
        p = page(cells + [left], tables.values(), [dict(id='float:1', blocks=['table:1'])])
        src = {}
        c.turned_float_leftovers(p, src, [c.TurnedSide(['x'], [left])], tables, 10)
        self.assertEqual(src['_turned_float_offer']['table'], 'table:1')
        self.assertEqual(src['_turned_float_offer']['ids'], [left['id']])   # before the table's top too
        src['_turned_float_runs'] = src['_turned_float_offer']
        c.extend_turned_float(p, src)
        self.assertIn(left['id'], p['tables'][0]['members'])

    def test_title_on_the_label_line_joins_the_caption(self):
        label = run('Table 2.', [20, 340, 28, 400], 90)
        title = run('A title on the label line', [20, 100, 28, 320], 90)
        cells = self.cells([100 + 10 * i for i in range(6)])
        tables = {'table:1': dict(id='table:1', angle=90, box_px=[90, 90, 200, 410], members=[e['id'] for e in cells])}
        p = page([label, title] + cells, tables.values(), [dict(id='float:1', blocks=['table:1'], _caption_ids=[label['id']])])
        src = {}
        c.turned_float_leftovers(p, src, [c.TurnedSide(['t'], [title])], tables, 10)
        self.assertEqual(src['_turned_float_offer']['title'], [title['id']])
        self.assertEqual(src['_turned_float_offer']['ids'], [])
        src['_turned_float_runs'] = src['_turned_float_offer']
        c.extend_turned_float(p, src)
        self.assertIn(title['id'], p['floats'][0]['_caption_ids'])
        self.assertNotIn(title['id'], p['tables'][0]['members'])

    def test_two_labels_are_not_guessed(self):
        l1 = run('Table 1.', [20, 300, 28, 400], 90); l2 = run('Table 2.', [250, 300, 258, 400], 90)
        left = run('a left out cell', [300, 120, 308, 300], 90)
        cells = self.cells([100 + 10 * i for i in range(6)])
        p = page([l1, l2, left] + cells, [], [dict(id='a', blocks=[], _caption_ids=[l1['id']]),
                                             dict(id='b', blocks=[], _caption_ids=[l2['id']])])
        src = {}
        c.turned_float_leftovers(p, src, [c.TurnedSide(['x'], [left])], {}, 10)
        self.assertNotIn('_turned_float_offer', src)
        self.assertEqual(src.get('_turned_float_left'), [left['box_px']])

    def test_continuation_mark_is_left_to_the_flow_cleanup(self):
        cells = self.cells([100 + 10 * i for i in range(6)])
        mark = run('(Continues)', [300, 120, 308, 200], 90)
        tables = {'table:1': dict(id='table:1', angle=90, box_px=[90, 90, 200, 410], members=[])}
        p = page(cells + [mark], tables.values(), [dict(id='float:1', blocks=['table:1'])])
        src = {}
        c.turned_float_leftovers(p, src, [c.TurnedSide(['(Continues)'], [mark])], tables, 10)
        self.assertEqual(src, {})

    def test_upright_page_is_left_alone(self):
        p = page([run('y' * 400, [0, 20, 200, 30]), run('x' * 30, [300, 120, 308, 300], 90)])
        src = {}
        c.turned_float_leftovers(p, src, [c.TurnedSide(['x'], [p['elements'][1]])], {}, 10)
        self.assertEqual(src, {})

if __name__ == '__main__':
    unittest.main()
