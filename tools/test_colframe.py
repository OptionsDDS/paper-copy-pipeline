"""Synthetic regressions for lane colframe (born-digital columns and reading order, 2026-11-04):
C1 a drawn object frames text only when the text stays inside it, a free-form curve never;
C2 column cuts inside a block from the sort's gutter threshold (layout/rules.py SPLIT_EM);
C3 a labelled-row list read row by row under its heading, a key never a heading;
C4 a margin label prefixes its entry and opens it in the reference splitter even when bare;
C5 the no-line-spans-a-gutter invariant as a copy check (paper gutters, gutter cut);
table extent: lines of a body prose column beyond a caption table's drawn structure are prose.
Every geometry here is invented; no line of any paper is quoted."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


paper = module('colframe_copy', 'copy_paper.py')
boxer = module('colframe_boxer', 'standalone/element_boxer_sc.py')
RL = module('colframe_rules', 'layout/rules.py')


def run(name, text, box, size=10, line=None, font=''):
    return dict(id=name, text=text, box_px=list(box), kind='text', line=box[1] if line is None else line, angle=0,
                size_px=size, run_size_px=size, font=font, _faces={})


SENTENCE = 'the quick brown fox jumps over the lazy dog and keeps running on.'


class FramesOverrun(unittest.TestCase):
    """C1 part 1: a Poppler block of column_min_lines lines each running past the box by more than an em."""
    def block(self, lines, x0, x1, y0, pitch=12):
        boxes = [[x0, y0 + i * pitch, x1, y0 + i * pitch + 10] for i in range(lines)]
        return dict(source='poppler', lines=lines, line_boxes=boxes,
                    box_px=[x0, y0, x1, y0 + lines * pitch])

    def test_column_running_past_the_bottom_is_not_framed(self):
        fill = [100, 100, 400, 200]
        past = self.block(12, 110, 390, 110)          # runs to y 254, far past 200
        self.assertEqual(boxer.frames_overrun(fill, [past], 10), 4)   # lines wholly below 210: 4 of 12
        self.assertEqual(boxer.frames_overrun(fill, [past], 10) >= boxer.PARAMS['column_min_lines'], True)

    def test_text_inside_the_box_keeps_the_frame(self):
        fill = [100, 100, 400, 300]
        inside = self.block(8, 110, 390, 110)         # ends at y 206
        self.assertEqual(boxer.frames_overrun(fill, [inside], 10), 0)

    def test_two_lines_past_are_not_enough(self):
        fill = [100, 100, 400, 140]
        short = self.block(5, 110, 390, 110)          # lines at 110,122,134,146,158: three past 150 by more than an em? 158,146 only
        self.assertEqual(boxer.frames_overrun(fill, [short], 10), 0)

    def test_sideways_overrun_counts(self):
        fill = [100, 100, 300, 400]
        wide = self.block(6, 110, 340, 110)           # every line reaches x 340 > 300 + em
        self.assertEqual(boxer.frames_overrun(fill, [wide], 10), 6)

    def test_page_wide_block_touching_a_figure_corner_is_not_an_overrun(self):
        image = [100, 100, 400, 300]
        page = self.block(40, 110, 900, 110)          # a 40-line page-wide block; 16 lines centred inside the image? no: centres at x 505, outside
        self.assertEqual(boxer.frames_overrun(image, [page], 10), 0)
        under = self.block(40, 110, 390, 110)         # the same lines centred inside sideways, 16 of 40 inside vertically: under half
        self.assertEqual(boxer.frames_overrun(image, [under], 10), 0)


class CurveFrames(unittest.TestCase):
    """C1 part 2: only a box-like curve (path points on its bounding box) frames text."""
    def test_rounded_box_is_boxlike(self):
        o = dict(x0=0, top=0, x1=100, bottom=50, pts=[(0, 10), (0, 40), (10, 50), (90, 50), (100, 40), (100, 10), (90, 0), (10, 0)])
        self.assertEqual(boxer.curve_box_share(o), 1.0)
        self.assertTrue(boxer.boxlike(dict(source='curve', curve_box_share=1.0, box_px=[0, 0, 900, 800]), 10))

    def test_swoosh_is_not(self):
        o = dict(x0=0, top=0, x1=100, bottom=50, pts=[(0, 25), (30, 10), (50, 30), (70, 20), (100, 25), (60, 45), (40, 15), (20, 35), (80, 5)])
        share = boxer.curve_box_share(o)
        self.assertLess(share, boxer.PARAMS['curve_box_share'])
        self.assertFalse(boxer.boxlike(dict(source='curve', curve_box_share=share, box_px=[0, 0, 900, 800]), 10))   # page scale: 80 em
        self.assertTrue(boxer.boxlike(dict(source='curve', curve_box_share=share, box_px=[0, 0, 70, 60]), 10))     # a flow-diagram shape: 6 em

    def test_rects_and_images_frame(self):
        self.assertTrue(boxer.boxlike(dict(source='rect', box_px=[0, 0, 900, 800]), 10))
        self.assertTrue(boxer.boxlike(dict(source='image', box_px=[0, 0, 900, 800]), 10))


class ProseColumnBlocks(unittest.TestCase):
    """Table extent: a block of column_min_lines lines at the modal body width with sentences is body prose."""
    def test_body_columns_found_and_cells_not(self):
        texts, blocks = [], []
        for c, x0 in enumerate((100, 420)):
            ms = []
            for r in range(5):
                e = run(f'c{c}r{r}', SENTENCE, [x0, 300 + r * 14, x0 + 280, 310 + r * 14], size=10)
                texts.append(e); ms.append(e['id'])
            blocks.append(dict(id=f'col{c}', members=ms, text_lines=5, box_px=[x0, 300, x0 + 280, 370]))
        cells = []
        for r in range(4):
            e = run(f'cell{r}', f'{r} 12.5 ok', [100, 100 + r * 14, 160, 110 + r * 14], size=10); texts.append(e); cells.append(e['id'])
        blocks.append(dict(id='cells', members=cells, text_lines=4, box_px=[100, 100, 160, 160]))
        found = boxer.prose_column_blocks(texts, blocks, 10)
        self.assertEqual(found, {'col0', 'col1'})

    def test_wrapped_cell_column_narrower_than_the_modal_line_is_not_prose(self):
        texts, blocks = [], []
        ms = []
        for r in range(6):
            e = run(f'b{r}', SENTENCE, [100, 300 + r * 14, 380, 310 + r * 14]); texts.append(e); ms.append(e['id'])
        blocks.append(dict(id='body', members=ms, text_lines=6, box_px=[100, 300, 380, 390]))
        ns = []
        for r in range(4):
            e = run(f'n{r}', 'a longer description cell that wraps. yes', [420, 100 + r * 14, 560, 110 + r * 14]); texts.append(e); ns.append(e['id'])
        blocks.append(dict(id='note', members=ns, text_lines=4, box_px=[420, 100, 560, 160]))
        self.assertEqual(boxer.prose_column_blocks(texts, blocks, 10), {'body'})


class ColumnGutters(unittest.TestCase):
    """C2: a white strip through every row, at least SPLIT_EM em wide, with text on both sides in three rows."""
    def columns(self, gap, rows=4, crossing=False):
        runs = {}
        for r in range(rows):
            runs[f'l{r}'] = run(f'l{r}', SENTENCE, [100, 20 * r, 300, 20 * r + 10])
            runs[f'r{r}'] = run(f'r{r}', SENTENCE, [300 + gap, 20 * r, 500 + gap, 20 * r + 10])
        if crossing: runs['x'] = run('x', 'a line across both columns of text here.', [100, 20 * rows, 500 + gap, 20 * rows + 10])
        return runs

    def test_gap_at_the_sort_threshold_cuts(self):
        runs = self.columns(gap=10)                                    # 1.0 em at size 10, above SPLIT_EM 0.9
        groups = paper.prose_column_groups(list(runs), runs, 10)
        self.assertEqual(groups, [[f'l{r}' for r in range(4)], [f'r{r}' for r in range(4)]])

    def test_narrower_than_a_word_gap_does_not_cut(self):
        runs = self.columns(gap=8)                                     # 0.8 em: a word space by the sort's rule
        self.assertEqual(paper.prose_column_groups(list(runs), runs, 10), [list(runs)])

    def test_a_crossing_line_closes_the_strip(self):
        runs = self.columns(gap=12, crossing=True)
        self.assertEqual(paper.prose_column_groups(list(runs), runs, 10), [list(runs)])

    def test_three_rows_needed_on_each_side(self):
        runs = self.columns(gap=12, rows=2)
        self.assertEqual(paper.prose_column_groups(list(runs), runs, 10), [list(runs)])
        self.assertEqual(RL.SPLIT_EM, 0.9)


class LabelledRowList(unittest.TestCase):
    """C3: keys at one edge, each level with a definition at a second edge, under a one-word bold heading."""
    def page(self, heading=True, bold_head=True, punctuated=False, wrap=True):
        es = []
        if heading: es.append(run('h', 'Glossaryish', [100, 80, 160, 92], size=8, font='Myriad-Bold' if bold_head else 'Myriad'))
        keys = ['AAA', 'BB-C', 'DDD', 'EE']
        for i, k in enumerate(keys):
            y = 100 + i * 24
            es.append(run(f'k{i}', k + ('.' if punctuated else ''), [100, y, 130, y + 9], size=8, font='Myriad'))
            es.append(run(f'd{i}', 'expansion words for the key here', [180, y, 420, y + 9], size=8, font='Myriad'))
            if wrap and i == 0: es.append(run('d0w', 'and its wrapped tail', [180, y + 11, 300, y + 20], size=8, font='Myriad'))
        es.append(run('ref0', 'Some reference text in the other column 2019.', [600, 100, 900, 109], size=8, font='Myriad'))
        es.append(run('ref1', '12.', [580, 124, 592, 133], size=8, font='Myriad'))
        return sorted(es, key=lambda e: (e['box_px'][1], e['box_px'][0]))

    def bold(self, e): return 'Bold' in e.get('font', '')

    def test_rows_under_a_bold_one_word_heading(self):
        head, rows = paper.labelled_row_list(self.page(), 10, self.bold)
        self.assertEqual(head['id'], 'h')
        self.assertEqual([(k['id'], [d['id'] for d in ds]) for k, ds in rows],
                         [('k0', ['d0', 'd0w']), ('k1', ['d1']), ('k2', ['d2']), ('k3', ['d3'])])

    def test_no_heading_no_list(self):
        self.assertIsNone(paper.labelled_row_list(self.page(heading=False), 10, self.bold))
        self.assertIsNone(paper.labelled_row_list(self.page(bold_head=False), 10, self.bold))

    def test_punctuated_keys_are_not_a_list(self):
        self.assertIsNone(paper.labelled_row_list(self.page(punctuated=True), 10, self.bold))


class MarginLabelsOpenEntries(unittest.TestCase):
    """C4 (copier): a row opened by a margin label begins a reference entry even when its number is bare."""
    def block(self, label_rows):
        lines = ['18 AB Carr, JA Gibb', 'Imaging of the joint', 'J Example, 1 (1987), pp. 1-9', '19 CD Dawson', 'A second entry title']
        lefts = [92, 168, 168, 92, 168]
        boxes = [[l, 100 + i * 14, 500, 110 + i * 14] for i, l in enumerate(lefts)]
        return dict(lines=lines, lefts=lefts, row_boxes=boxes, meta=dict(size_px=10, id='block:1'), page=3, _label_rows=label_rows)

    def test_labelled_rows_begin_entries(self):
        parts = paper.split_references(self.block([0, 3]), paper.Joiner([]))
        self.assertEqual([begins for _, begins in parts], [True, True])
        self.assertTrue(parts[0][0].startswith('18 AB Carr'))
        self.assertTrue(parts[1][0].startswith('19 CD Dawson'))

    def test_without_label_evidence_the_hanging_indent_rule_stands(self):
        parts = paper.split_references(self.block([]), paper.Joiner([]))
        self.assertEqual([begins for _, begins in parts], [True, True])   # hanging indent still splits here
        block = self.block([]); block['lefts'] = [168] * 5; block['row_boxes'] = [[168, b[1], 500, b[3]] for b in block['row_boxes']]
        parts = paper.split_references(block, paper.Joiner([]))
        self.assertEqual(len(parts), 1)                                    # flush rows, bare numbers: one entry
        block['_label_rows'] = [0, 3]
        parts = paper.split_references(block, paper.Joiner([]))
        self.assertEqual(len(parts), 2)                                    # the margin labels open the entries


class GutterCut(unittest.TestCase):
    """C5: rows assembled across a paper gutter are cut into their columns; a spanning run forbids the cut."""
    def rows(self, crossing=False):
        runs = {}
        for r in range(3):
            runs[f'l{r}'] = run(f'l{r}', 'left column words', [100, 20 * r, 290, 20 * r + 10])
            runs[f'r{r}'] = run(f'r{r}', 'right column words', [330, 20 * r, 520, 20 * r + 10])
        if crossing: runs['h'] = run('h', 'A heading across the columns', [150, 60, 470, 70])
        return runs

    def test_cut_into_columns_with_a_finding(self):
        runs = self.rows()
        groups, findings = paper.gutter_cut(list(runs), runs, 10, [(300, 320)], lambda b: b)
        self.assertEqual(groups, [[f'l{r}' for r in range(3)], [f'r{r}' for r in range(3)]])
        self.assertEqual([f['kind'] for f in findings], ['cut'])
        self.assertEqual(findings[0]['rows'], 3)

    def test_spanning_line_forbids_the_cut(self):
        runs = self.rows(crossing=True)
        groups, findings = paper.gutter_cut(list(runs), runs, 10, [(300, 320)], lambda b: b)
        self.assertIsNone(groups)
        self.assertEqual([f['kind'] for f in findings], ['spans'])

    def test_no_gutter_no_finding(self):
        runs = self.rows()
        self.assertEqual(paper.gutter_cut(list(runs), runs, 10, [], lambda b: b), (None, []))


class PaperGutters(unittest.TestCase):
    """C5: the majority gutter from the pages' columns, frame-relative; dropped where main text runs through it."""
    def page(self, n, cols, through=False):
        es = [run(f'p{n}m{r}', SENTENCE, [cols[0][0], 100 + 14 * r, cols[0][1], 110 + 14 * r]) for r in range(4)]
        if through: es += [run(f'p{n}t{r}', SENTENCE, [cols[0][0], 200 + 14 * r, cols[-1][1], 210 + 14 * r]) for r in range(3)]
        return dict(page=n, elements=es, region_box_px=[0, 0, 1000, 1400],
                    blocks=[dict(id='b', members=[e['id'] for e in es])],
                    main_text=dict(columns=[list(c) for c in cols], blocks=[dict(id='b', cls='main', lines=len(es))]))

    def test_majority_gutter_mapped_by_frame_left(self):
        pages = [self.page(1, [[100, 400], [430, 730]]), self.page(2, [[150, 450], [480, 780]]), self.page(3, [[100, 400]])]
        paper._TRACE.pop('gutters_evaluated', None)
        gutters = paper.paper_gutters(pages, 10)
        self.assertEqual(gutters, [(300, 330)])
        self.assertEqual(pages[0]['_gutters'], [(400, 430)])
        self.assertEqual(pages[1]['_gutters'], [(450, 480)])
        self.assertEqual(pages[2]['_gutters'], [(400, 430)])        # the frame moves; the gutter follows

    def test_gutter_dropped_where_main_text_runs_through(self):
        pages = [self.page(1, [[100, 400], [430, 730]]), self.page(2, [[100, 400], [430, 730]]), self.page(3, [[100, 730]], through=True)]
        paper.paper_gutters(pages, 10)
        self.assertEqual(pages[0]['_gutters'], [(400, 430)])
        self.assertEqual(pages[2]['_gutters'], [])


if __name__ == '__main__':
    unittest.main()
