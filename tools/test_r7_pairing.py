#!/usr/bin/env python3
"""Lane r7-pairing (round 7): rules TP1 (pair the orphans), TP2 (one table, one block) and TP3 (no text layer) on the
page floats read_page returns; the doubtful places and their copy lines."""
import os, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import copy_paper as copy

W, H, BODY = 1240, 1650, 18


def run(i, box, text='cell', angle=0):
    return dict(id=f'run:{i}', kind='text', box_px=list(box), text=text, angle=angle)


def page(elements, unpaired=(), blocks=()):
    return dict(page=3, region_box_px=[0, 0, W, H], params=dict(dpi=150), elements=list(elements),
                unpaired=list(unpaired), blocks=[dict(id=b, members=list(m)) for b, m in blocks],
                main_text=dict(body_size_px=BODY))


def lines_source(runs, caption_ids=()):
    return dict(angle=0, caption_ids=list(caption_ids), lines=[dict(text=e['text'], items=[dict(id=e['id'], text=e['text'], box=e['box_px'])])
                                                               for e in runs])


def caption_float(label, cap_box, region, cap_ids=('run:1',), rows=(), source=None, **extra):
    return (cap_box[1], 'table', label, list(rows), [], dict(id='block:1', box=list(region), caption_box=list(cap_box),
            caption_ids=list(cap_ids), table_source=source or dict(lines=[], caption_ids=list(cap_ids)),
            image_only=False, outline_art=0, graphic_box=None, **extra))


def orphan_float(region, runs, rows=(('a', 'b'),), number=3):
    return (region[1], 'table', f'Table (no caption on page {number})', [list(r) for r in rows], [],
            dict(id='table:1', box=list(region), table_source=lines_source(runs), after_block='block:0'))


class PairOrphans(unittest.TestCase):
    def setUp(self):
        del copy._PAIRING_PENDING[:]

    def read(self, p, floats, uncertain=()):
        per_page = [([], list(floats), [])]
        unc = [list(uncertain)]
        copy.pair_orphan_tables([p], per_page, BODY, unc)
        return per_page[0][1], unc[0]

    def test_tp1_caption_with_no_lines_takes_the_uncaptioned_table_under_it(self):
        cells = [run(2, [120, 260, 400, 280]), run(3, [500, 260, 800, 280])]
        p = page([run(1, [120, 200, 600, 220], 'Table 1. Title')] + cells)
        cap = caption_float('Table 1. Title', [120, 200, 600, 220], [110, 200, 1140, 600])
        orphan = orphan_float([110, 250, 1140, 600], cells)
        floats, unc = self.read(p, [cap, orphan], [f"page 3: Table 1: its rows could not be read (table, layout uncertain)"])
        self.assertEqual(len(floats), 1)
        top, kind, caption, rows, notes, placement = floats[0]
        self.assertEqual(caption, 'Table 1. Title')
        self.assertEqual(rows, [['a', 'b']])
        self.assertEqual(top, 200)                      # printed at the caption's place
        self.assertNotIn('after_block', placement)
        self.assertEqual(placement['table_source']['caption_ids'], ['run:1'])
        self.assertEqual({x['id'] for l in placement['table_source']['lines'] for x in l['items']}, {'run:2', 'run:3'})
        self.assertEqual(placement['tp_paired'], 'TP1')
        self.assertEqual(unc, [])                       # the stale "rows could not be read" note goes
        self.assertEqual(copy._PAIRING_PENDING, [])

    def test_tp1_not_when_another_caption_stands_between(self):
        cells = [run(2, [120, 460, 400, 480])]
        p = page([run(1, [120, 200, 600, 220], 'Table 1. Title')] + cells)
        cap = caption_float('Table 1. Title', [120, 200, 600, 220], [110, 200, 1140, 900])
        other = caption_float('Figure 2. A picture', [120, 400, 600, 420], [110, 230, 1140, 420])
        other = (other[0], 'figure') + other[2:]
        orphan = orphan_float([110, 450, 1140, 600], cells)
        floats, _ = self.read(p, [cap, other, orphan])
        self.assertIn(orphan, floats)
        self.assertEqual([d[:2] + (d[3],) for d in copy._PAIRING_PENDING], [('TP1', 3, 'caption_without_lines')])

    def test_tp1_not_when_the_table_lies_outside_the_captions_region(self):
        cells = [run(2, [120, 960, 400, 980])]
        p = page([run(1, [120, 200, 600, 220], 'Table 1. Title')] + cells)
        cap = caption_float('Table 1. Title', [120, 200, 600, 220], [110, 200, 1140, 600])
        orphan = orphan_float([110, 950, 1140, 1100], cells)
        floats, _ = self.read(p, [cap, orphan])
        self.assertIn(orphan, floats)

    def test_tp1_not_for_a_table_in_the_other_column(self):
        cells = [run(2, [700, 260, 1100, 280])]
        p = page([run(1, [80, 200, 560, 220], 'Table 1. Title')] + cells)
        cap = caption_float('Table 1. Title', [80, 200, 560, 220], [70, 200, 580, 600])
        orphan = orphan_float([690, 250, 1140, 600], cells)
        floats, _ = self.read(p, [cap, orphan])
        self.assertIn(orphan, floats)

    def test_tp1_not_for_a_table_above_its_caption(self):
        cells = [run(2, [120, 260, 400, 280])]
        p = page([run(1, [120, 700, 600, 720], 'Table 1. Title')] + cells)
        cap = caption_float('Table 1. Title', [120, 700, 600, 720], [110, 700, 1140, 900])
        orphan = orphan_float([110, 250, 1140, 600], cells)
        floats, _ = self.read(p, [cap, orphan])
        self.assertIn(orphan, floats)

    def test_tp2_two_lists_of_one_table_become_one_list_in_page_order(self):
        data = [run(2, [120, 300, 400, 320], 'Row one 53'), run(3, [120, 340, 400, 360], 'Row two 33')]
        part = [run(4, [120, 260, 900, 280], 'Header line p'), run(5, [820, 340, 900, 360], 'p = 0.01')]
        p = page([run(1, [120, 200, 600, 220], 'Table 2. Title')] + data + part)
        cap = caption_float('Table 2. Title', [120, 200, 600, 220], [110, 200, 1000, 380], source=lines_source(data, ['run:1']))
        orphan = orphan_float([110, 255, 1000, 380], part, rows=())
        floats, _ = self.read(p, [cap, orphan])
        self.assertEqual(len(floats), 1)
        source = floats[0][5]['table_source']
        self.assertEqual(floats[0][3], [])
        self.assertEqual([l['text'] for l in source['lines']], ['Header line p', 'Row one 53', 'Row two 33 p = 0.01'])
        self.assertEqual(floats[0][5]['tp_paired'], 'TP2')

    def test_tp2_a_grid_keeps_its_grid_and_the_split_is_doubtful(self):
        data = [run(2, [120, 300, 400, 320], 'Row one 53')]
        part = [run(4, [120, 260, 900, 280], 'Header line p')]
        p = page([run(1, [120, 200, 600, 220], 'Table 2. Title')] + data + part)
        cap = caption_float('Table 2. Title', [120, 200, 600, 220], [110, 200, 1000, 380], rows=[['Row one', '53']],
                            source=lines_source(data, ['run:1']))
        orphan = orphan_float([110, 255, 1000, 380], part, rows=())
        floats, _ = self.read(p, [cap, orphan])
        self.assertEqual(floats, [cap, orphan])
        self.assertEqual([d[0] + ':' + d[3] for d in copy._PAIRING_PENDING], ['TP2:table_split_over_two_blocks'])

    def test_tp3_outline_table_keeps_its_caption_takes_no_lines_and_is_doubtful(self):
        cells = [run(2, [120, 260, 400, 280])]
        p = page([run(1, [120, 200, 600, 220], 'Table 1. Title')] + cells)
        cap = caption_float('Table 1. Title', [120, 200, 600, 220], [110, 200, 1140, 600])
        cap = cap[:5] + (dict(cap[5], outline_art=40),)
        orphan = orphan_float([110, 250, 1140, 600], cells)
        floats, _ = self.read(p, [cap, orphan])
        self.assertEqual(floats, [cap, orphan])
        self.assertEqual([d[0] + ':' + d[3] for d in copy._PAIRING_PENDING], ['TP3:table_without_text_layer'])

    def test_tp1_an_unpaired_label_printed_inside_the_table_names_it(self):
        cells = [run(1, [120, 200, 300, 220], 'Table 1'), run(2, [120, 260, 400, 280])]
        p = page(cells, unpaired=[dict(kind='caption without a graphic on this page', caption='Table 1', block='block:7')],
                 blocks=[('block:7', ['run:1'])])
        orphan = orphan_float([110, 200, 1140, 600], cells)
        floats, _ = self.read(p, [orphan])
        self.assertEqual(floats[0][2], 'Table 1')
        self.assertTrue(floats[0][5]['tp_label'])

    def test_tp1_an_unpaired_label_not_printed_in_the_table_leaves_it(self):
        cells = [run(2, [120, 260, 400, 280])]
        p = page([run(1, [120, 200, 300, 220], 'Table 1')] + cells,
                 unpaired=[dict(kind='caption without a graphic on this page', caption='Table 1', block='block:7')],
                 blocks=[('block:7', ['run:1'])])
        orphan = orphan_float([110, 250, 1140, 600], cells)
        floats, _ = self.read(p, [orphan])
        self.assertEqual(floats, [orphan])

    def test_tp1_a_table_whose_first_printed_line_is_its_label_line_takes_that_label(self):
        cells = [run(1, [120, 200, 700, 220], 'Table 3 – Distances to the gauge.'), run(2, [120, 260, 400, 280])]
        floats, _ = self.read(page(cells), [orphan_float([110, 200, 1140, 600], cells)])
        self.assertEqual(floats[0][2], 'Table 3')
        self.assertTrue(floats[0][5]['tp_label'])

    def test_tp1_a_first_line_that_cites_a_table_in_a_sentence_names_nothing(self):
        cells = [run(1, [120, 200, 700, 220], 'Table 3 shows the distances'), run(2, [120, 260, 400, 280])]
        orphan = orphan_float([110, 200, 1140, 600], cells)
        floats, _ = self.read(page(cells), [orphan])
        self.assertEqual(floats, [orphan])

    def test_tp1_a_label_another_float_of_the_page_names_is_not_taken_again(self):
        cells = [run(3, [120, 700, 700, 720], 'Table 1. Repeated head'), run(4, [120, 760, 400, 780])]
        p = page([run(1, [120, 100, 600, 120], 'Table 1. Title'), run(2, [120, 160, 400, 180])] + cells)
        cap = caption_float('Table 1. Title', [120, 100, 600, 120], [110, 100, 1140, 300],
                            rows=[['a']], source=lines_source([run(2, [120, 160, 400, 180])], ['run:1']))
        orphan = orphan_float([110, 690, 1140, 900], cells)
        floats, _ = self.read(p, [cap, orphan])
        self.assertIn(orphan, floats)

    def test_turned_table_pairs_in_its_reading_frame(self):
        # read bottom to top: the caption stands left of the table on the page
        cells = [run(2, [300, 200, 320, 900], 'cell', 90)]
        p = page([run(1, [200, 200, 220, 900], 'Table 1. Title', 90)] + cells)
        cap = caption_float('Table 1. Title', [200, 200, 220, 900], [200, 150, 900, 950])
        orphan = orphan_float([290, 150, 900, 950], cells)
        orphan[5]['table_source']['angle'] = 90
        floats, _ = self.read(p, [cap, orphan])
        self.assertEqual(len(floats), 1)


class Doubts(unittest.TestCase):
    def test_lines_found_by_label(self):
        del copy._PAIRING_PENDING[:]
        copy._PAIRING_PENDING.append(('TP1', 3, [1, 2, 3, 4], 'caption_without_lines', 'Table 1'))
        copy._PAIRING_PENDING.append(('TP3', 4, [1, 2, 3, 4], 'table_without_text_layer', 'Table 10'))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'copy.md')
            with open(path, 'w') as f:
                f.write('# Title\n\n**Table 10. Ten**\n\ntext Table 1\n\n**Table 1. One**\n')
            copy.doubt_list().reset()
            copy.pairing_doubts(path)
            items = copy.doubt_list().items()
        self.assertEqual([(d['rule'], d['line']) for d in items], [('TP1', 7), ('TP3', 3)])
        self.assertEqual(copy._PAIRING_PENDING, [])


if __name__ == '__main__':
    unittest.main()
