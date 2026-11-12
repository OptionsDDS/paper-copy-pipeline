"""Synthetic section/column regressions: /usr/bin/python3 -I tools/test_sections.py."""
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


paper = module('copy_paper', ROOT / 'copy_paper.py')
boxer = module('element_boxer_sc', ROOT / 'standalone/element_boxer_sc.py')


def block(name, box, text='Paragraph text'):
    return dict(id=name, box_px=box, text=text)


class Sections(unittest.TestCase):
    def test_body_columns_finish_before_reference_band(self):
        blocks = [block('left', [0, 0, 90, 80]), block('right', [110, 0, 200, 70]),
                  block('head', [0, 100, 50, 110], 'References'),
                  block('refs-left', [0, 130, 90, 220]), block('refs-right', [110, 130, 200, 220])]
        ordered, cuts = boxer.reading_order_bands(blocks, [[0, 90], [110, 200]], 10)
        self.assertEqual([b['id'] for b in ordered], ['left', 'right', 'head', 'refs-left', 'refs-right'])
        self.assertIn(100, cuts)

    def test_reference_heading_in_continuing_column_is_not_page_boundary(self):
        blocks = [block('left', [0, 0, 90, 220]), block('head', [110, 100, 160, 110], 'References'),
                  block('refs', [110, 130, 200, 220])]
        ordered, cuts = boxer.reading_order_bands(blocks, [[0, 90], [110, 200]], 10)
        self.assertEqual([b['id'] for b in ordered], ['left', 'head', 'refs'])
        self.assertEqual(cuts, [])

    def test_float_crossing_heading_vetoes_section_cut(self):
        blocks = [block('head', [0, 100, 50, 110], 'References'),
                  block('left', [0, 130, 90, 220]), block('right', [110, 130, 200, 220])]
        self.assertEqual(boxer.reference_section_cuts(blocks, [[0, 90], [110, 200]], 10,
                                                     [[110, 70, 200, 120]]), [])

    def test_reference_columns_ignore_subline_top_differences(self):
        blocks = [block('left', [0, 10.01, 90, 220]), block('right', [110, 10, 200, 220])]
        ordered, _ = boxer.reading_order_bands(blocks, [[0, 90], [110, 200]], 10)
        self.assertEqual([b['id'] for b in ordered], ['left', 'right'])

    def test_three_panel_columns_are_atomic_after_reference_columns(self):
        blocks = [block('refs-left', [0, 0, 90, 80]), block('refs-right', [110, 0, 200, 80]),
                  block('panel-left', [0, 100, 55, 180]), block('panel-middle', [70, 100, 125, 180]),
                  block('panel-right', [140, 100, 195, 180])]
        panel = dict(id='panel', box_px=[0, 95, 200, 185], columns=[[0, 55], [70, 125], [140, 195]],
                     blocks=['panel-left', 'panel-middle', 'panel-right'])
        ordered, _ = boxer.reading_order_bands(blocks, [[0, 90], [110, 200]], 10, panels=[panel])
        self.assertEqual([b['id'] for b in ordered], [b['id'] for b in blocks])

    def test_exclusion_reason_wraps_are_one_reference(self):
        b = dict(lines=['Able, A. (2001) A study.', 'Journal 1: 1-2.',
                        'Exclusion criteria: unavailable', 'measurements.',
                        'Baker, B. (2002) Another study.', 'Journal 2: 3-4.'],
                 lefts=[0, 10, 0, 0, 0, 10])
        class Join:
            def join(self, a, b): return a + ' ' + b
        parts = paper.split_references(b, Join())
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[0][0].endswith('unavailable measurements.'))
        self.assertTrue(parts[1][0].startswith('Baker,'))

    def test_exclusion_reason_continues_across_column(self):
        b = dict(lines=['measurements.', 'Baker, B. (2002) Another study.', 'Journal 2: 3-4.'], lefts=[0, 0, 10])
        class Join:
            def join(self, a, b): return a + ' ' + b
        parts = paper.split_references(b, Join(), continuing_note=True)
        self.assertEqual(parts[0], ['measurements.', False])
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[1][1])


if __name__ == '__main__':
    unittest.main()
