"""Floatplace lane (AUDIT-AI): floats at sentence boundaries, boxes as floats,
column-major reading around partial-width floats, a table header's reference
word, and body prose freed from a recovered table seed. Synthetic, keyless.

Run: /usr/bin/python3 -I tools/test_floatplace.py
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


copy = module('floatplace_copy', 'copy_paper.py')
boxer = module('floatplace_boxer', 'standalone/element_boxer_sc.py')


def block(bid, box, text, lines=1, size=10):
    return dict(id=bid, box_px=list(box), text=text, lines=lines, size=size, size_px=size, cls='main')


class HeaderRowReference(unittest.TestCase):
    """A reference word set as a table column header is not a bibliography heading."""

    def test_header_cell_beside_two_header_cells(self):
        cells = [block('a', [0, 100, 60, 110], 'Genetic variant'),
                 block('b', [80, 90, 200, 110], 'Association with\ncardiovascular diseases', lines=2),
                 block('c', [220, 100, 270, 110], 'Reference')]
        boxer.mark_header_row_references(cells, lambda b: b['text'])
        self.assertTrue(cells[2].get('table_header_cell'))
        self.assertFalse(cells[0].get('table_header_cell'))

    def test_real_heading_beside_body_columns(self):
        blocks = [block('body', [0, 80, 150, 400], 'Long body text\n' * 20, lines=20),
                  block('head', [180, 100, 260, 110], 'References'),
                  block('refs', [180, 120, 330, 400], '1. Smith J.\n' * 20, lines=20)]
        boxer.mark_header_row_references(blocks, lambda b: b['text'])
        self.assertFalse(blocks[1].get('table_header_cell'))

    def test_one_neighbour_is_not_a_header_row(self):
        blocks = [block('a', [0, 100, 60, 110], 'Study'),
                  block('c', [220, 100, 270, 110], 'References')]
        boxer.mark_header_row_references(blocks, lambda b: b['text'])
        self.assertFalse(blocks[1].get('table_header_cell'))


class ColumnMajorAroundFloats(unittest.TestCase):
    """Rule 7: a float over some columns beside a running column does not cut the page."""
    cols = [[0, 100], [120, 220], [240, 340]]

    def test_third_column_beside_a_top_float_is_read_last(self):
        floats = [[0, 0, 220, 200]]
        blocks = [block('c3top', [240, 0, 340, 300], 'third column top', lines=20),
                  block('c1', [0, 320, 100, 700], 'first column', lines=25),
                  block('c2', [120, 320, 220, 700], 'second column', lines=25),
                  block('c3low', [240, 330, 340, 700], 'third column below', lines=25)]
        ordered, cuts = boxer.reading_order_bands(blocks, self.cols, 10, floats)
        self.assertEqual([b['id'] for b in ordered], ['c1', 'c2', 'c3top', 'c3low'])
        self.assertEqual(cuts, [])

    def test_float_across_every_column_still_cuts(self):
        floats = [[0, 310, 340, 400]]
        blocks = [block('c1a', [0, 0, 100, 300], 'a', lines=20), block('c2a', [120, 0, 220, 300], 'b', lines=20),
                  block('c3a', [240, 0, 340, 300], 'c', lines=20),
                  block('c1b', [0, 420, 100, 700], 'd', lines=20), block('c2b', [120, 420, 220, 700], 'e', lines=20),
                  block('c3b', [240, 420, 340, 700], 'f', lines=20)]
        ordered, cuts = boxer.reading_order_bands(blocks, self.cols, 10, floats)
        self.assertEqual([b['id'] for b in ordered], ['c1a', 'c2a', 'c3a', 'c1b', 'c2b', 'c3b'])

    def test_mid_column_float_with_text_above_and_below_still_cuts(self):
        floats = [[0, 310, 220, 400]]
        blocks = [block('c1a', [0, 0, 100, 300], 'a', lines=20), block('c2a', [120, 0, 220, 300], 'b', lines=20),
                  block('c3a', [240, 0, 340, 300], 'c', lines=20), block('c3b', [240, 420, 340, 700], 'f', lines=20),
                  block('c1b', [0, 420, 100, 700], 'd', lines=20), block('c2b', [120, 420, 220, 700], 'e', lines=20)]
        ordered, cuts = boxer.reading_order_bands(blocks, self.cols, 10, floats)
        self.assertEqual([b['id'] for b in ordered], ['c1a', 'c2a', 'c3a', 'c1b', 'c2b', 'c3b'])


def text(rid, value, box, size=10):
    return dict(id=rid, kind='text', text=value, box_px=list(box), angle=0, line=box[1],
                size_px=size, run_size_px=size, char_ids=[])


class LabelledBox(unittest.TestCase):
    """A shaded frame led by a "Box N" label is one float: caption rows, then item rows."""

    def page(self, label='Box 1'):
        runs = [text('r1', label, [105, 105, 140, 115]),
                text('r2', 'Adverse effects as defined', [150, 105, 300, 115]),
                text('r3', 'for the purpose of this study', [105, 118, 300, 128]),
                text('r4', '▸ The first item', [105, 150, 250, 160]),
                text('r5', '▸ The second item', [105, 165, 250, 175])]
        fill = dict(id='fill:1', kind='fill', box_px=[100, 100, 320, 190])
        return dict(page=2, elements=runs + [fill], tables=[], floats=[]), {r['id']: r for r in runs}

    def test_caption_and_items(self):
        p, runs = self.page()
        found = copy.labelled_box_regions(p, runs, 10)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]['caption_ids'], ['r1', 'r2', 'r3'])
        self.assertEqual([[r['id'] for r in row] for row in found[0]['item_rows']], [['r4'], ['r5']])

    def test_a_citation_is_not_a_label(self):
        p, runs = self.page('box 1')
        self.assertEqual(copy.labelled_box_regions(p, runs, 10), [])

    def test_no_frame_no_box(self):
        p, runs = self.page()
        p['elements'] = [e for e in p['elements'] if e['kind'] != 'fill']
        self.assertEqual(copy.labelled_box_regions(p, runs, 10), [])


class BoxPlacement(unittest.TestCase):
    """A box float waits for the paragraph whose sentence it interrupts, like a table."""

    def test_box_follows_its_citing_paragraph(self):
        first = dict(kind='para', text='Earlier text.', page=1, box=[0, 10, 100, 50])
        citing = dict(kind='para', text='The safety endpoints are listed (box 1).', page=1, box=[0, 60, 100, 90])
        box = dict(kind='box', caption='Box 1. Effects', rows=[], notes=[], page=1, top=5, left=0,
                   text_lines=['▸ one'])
        records = [dict(page=1, elements=[], tables=[], region_box_px=[0, 0, 300, 500])]
        self.assertEqual(copy.arrange_floats([first, citing, box], records, []), [first, citing, box])

    def test_rejoin_skips_a_box_inside_a_sentence(self):
        first = dict(kind='para', text='Success was defined by a', page=1, box=[0, 10, 100, 50])
        box = dict(kind='box', caption='Box 1. Effects', rows=[], notes=[], page=1, top=60, left=0)
        rest = dict(kind='para', text='reduction in the index.', page=2, box=[0, 10, 100, 50])
        joined = copy.rejoin_paragraphs([first, box, rest], copy.Joiner([]))
        self.assertEqual([it['kind'] for it in joined], ['para', 'box'])
        self.assertIn('defined by a reduction', joined[0]['text'])


if __name__ == '__main__':
    unittest.main()
