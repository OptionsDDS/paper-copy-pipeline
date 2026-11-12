"""Synthetic regressions for lane stream (no main-text run leaves the body, 2026-11-04):
R1 main text ends a table's outward walk and bars a block from a float's strip chain (main_text_runs);
R2 a free-form path in a colour no character, rect or line of the page uses is overlay ink, never table structure;
R3 columns recur as a pattern at a per-page offset, the title page included (paper_column_pattern, place_column_pattern);
R4 a fallback region under an orphan caption takes a boxer block whole or not at all (whole_block_region).
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


paper = module('stream_copy', 'copy_paper.py')
boxer = module('stream_boxer', 'standalone/element_boxer_sc.py')

WORDS = 'the quick brown fox jumps over the lazy dog and keeps on running'


def run(name, text, box, size=10, line=None, font='AAAAAA+Body-Regular'):
    return dict(id=name, text=text, box_px=list(box), kind='text', line=box[1] if line is None else line, angle=0,
                size_px=size, run_size_px=size, font=font, font_spans=[dict(font=font, start=0, end=len(text))], _faces={})


def ident(b): return list(b)


class WholeBlockRegion(unittest.TestCase):
    """R4: completing the boxer blocks a fallback walk entered."""
    def page(self, extra=()):
        rs = [run(f'run:{i}', f'Row {i} cell text', (100 + (15 if i % 2 else 0), 200 + 14 * i, 300 + 60 * (i % 3), 210 + 14 * i))
              for i in range(8)] + list(extra)
        runs = {e['id']: e for e in rs}
        blocks = [dict(id='block:2', members=[f'run:{i}' for i in range(8)] + [e['id'] for e in extra])]
        return dict(blocks=blocks, elements=rs), runs

    def test_walk_cut_short_takes_the_whole_block(self):
        p, runs = self.page()
        got = paper.whole_block_region(p, runs, ['run:0', 'run:1', 'run:2'], [], set(), [100, 150, 300, 190], ident, 10)
        self.assertEqual(got, [f'run:{i}' for i in range(8)])

    def test_a_run_of_another_size_returns_no_lines(self):
        p, runs = self.page([run('run:9', 'larger prose line', (100, 330, 400, 342), size=13)])
        got = paper.whole_block_region(p, runs, ['run:0', 'run:1'], [], set(), [100, 150, 300, 190], ident, 10)
        self.assertEqual(got, [])

    def test_a_run_off_every_taken_edge_returns_no_lines(self):
        p, runs = self.page([run('run:9', 'indented far', (180, 330, 400, 340))])
        got = paper.whole_block_region(p, runs, ['run:0', 'run:1'], [], set(), [100, 150, 300, 190], ident, 10)
        self.assertEqual(got, [])

    def test_a_run_of_another_float_returns_no_lines(self):
        p, runs = self.page()
        got = paper.whole_block_region(p, runs, ['run:0', 'run:1'], [], {'run:5'}, [100, 150, 300, 190], ident, 10)
        self.assertEqual(got, [])

    def test_a_complete_walk_is_unchanged(self):
        p, runs = self.page()
        taken = [f'run:{i}' for i in (2, 0, 1, 3, 4, 5, 6, 7)]
        self.assertEqual(paper.whole_block_region(p, runs, taken, [], set(), [100, 150, 300, 190], ident, 10), taken)

    def test_copier_blocks_are_not_boxer_blocks(self):
        p, runs = self.page()
        p['blocks'] = [dict(id='copy:caption:x', members=[f'run:{i}' for i in range(8)])]
        self.assertEqual(paper.whole_block_region(p, runs, ['run:0'], [], set(), [100, 150, 300, 190], ident, 10), ['run:0'])


class FakePage:
    def __init__(self, chars=(), rects=(), lines=()):
        self.chars, self.rects, self.lines = list(chars), list(rects), list(lines)


class OverlayInk(unittest.TestCase):
    """R2: layout palette and overlay ink."""
    def test_palette_from_characters_rects_and_lines(self):
        page = FakePage(chars=[dict(non_stroking_color=(0, 0, 0, 1))],
                        rects=[dict(fill=True, non_stroking_color=(0.1, 0, 0.05, 0), stroke=False, stroking_color=None)],
                        lines=[dict(fill=False, non_stroking_color=None, stroke=True, stroking_color=0.5)])
        self.assertEqual(boxer.layout_palette(page), {(0.0, 0.0, 0.0, 1.0), (0.1, 0.0, 0.05, 0.0), (0.5,)})

    def test_off_palette_curve_is_overlay(self):
        pal = {(0.0, 0.0, 0.0, 1.0)}
        self.assertTrue(boxer.overlay_ink(dict(fill=True, non_stroking_color=(1.0, 1.0, 0.0)), pal))
        self.assertFalse(boxer.overlay_ink(dict(fill=True, non_stroking_color=(0, 0, 0, 1)), pal))

    def test_stroked_path_uses_its_stroke_colour(self):
        pal = {(0.2, 0.3, 0.4)}
        self.assertFalse(boxer.overlay_ink(dict(fill=False, non_stroking_color=(1, 0, 0), stroking_color=(0.2, 0.3, 0.4)), pal))
        self.assertTrue(boxer.overlay_ink(dict(fill=False, non_stroking_color=(0.2, 0.3, 0.4), stroking_color=(1, 0, 0)), pal))

    def test_unset_or_pattern_colour_is_layout_ink(self):
        self.assertFalse(boxer.overlay_ink(dict(fill=True, non_stroking_color=None), set()))
        self.assertFalse(boxer.overlay_ink(dict(fill=True, non_stroking_color='P0'), set()))


def grid_page(extra_objs=(), body_rows=True):
    """A four-track ruled table (rules above, under its head and at its foot) over two body columns."""
    es = []; line = 0
    xs = [(100, 180), (220, 300), (340, 420), (460, 540)]
    for r in range(5):
        line += 1; y = 120 + 20 * r
        for k, (a, b) in enumerate(xs):
            es.append(run(f'run:c{r}{k}', f'c{r}{k}', (a, y, b, y + 9), size=9, line=line, font='AAAAAA+Cell'))
    es += [dict(id='rule:1', kind='rule', source='rect', box_px=[95, 112, 545, 114]),
           dict(id='rule:2', kind='rule', source='rect', box_px=[95, 133, 545, 135]),
           dict(id='rule:3', kind='rule', source='rect', box_px=[95, 212, 545, 214])]
    if body_rows:
        for r in range(6):
            line += 1; y = 222 + 14 * r
            es.append(run(f'run:L{r}', WORDS + ('.' if r == 5 else ''), (95, y, 315, y + 11), size=11, line=line))
            es.append(run(f'run:R{r}', WORDS + ('.' if r == 5 else ''), (330, y, 545, y + 11), size=11, line=line))
    es += list(extra_objs)
    return es


class TableWalk(unittest.TestCase):
    """R1/R2 in tables_from_grid."""
    def table(self, es):
        blocks = boxer.larger_boxes(es)
        ts = boxer.tables_from_grid(es, blocks)
        self.assertEqual(len(ts), 1)
        return ts[0]

    def test_overlay_fill_covering_no_text_never_grows_the_table(self):
        pen = dict(id='fill:9', kind='fill', source='curve', curve_box_share=0.4, overlay=True, box_px=[300, 205, 330, 220])
        t = self.table(grid_page([pen]))
        self.assertLessEqual(t['box_px'][3], 215)
        self.assertNotIn('fill:9', t['members'])

    def test_layout_fill_covering_no_text_still_joins(self):
        cell = dict(id='fill:9', kind='fill', source='rect', box_px=[300, 205, 330, 222])
        t = self.table(grid_page([cell], body_rows=False))
        self.assertIn('fill:9', t['members'])

    def test_overlay_highlight_is_no_spanning_rule(self):
        pen = dict(id='fill:9', kind='fill', source='curve', curve_box_share=0.6, overlay=True, box_px=[150, 292, 500, 304])
        t = self.table(grid_page([pen]))
        self.assertTrue(all(not m.startswith('run:L') and not m.startswith('run:R') for m in t['members']))
        self.assertLessEqual(t['box_px'][3], 215)

    def test_body_prose_ends_the_walk_under_a_rule_beyond_it(self):
        # a layout rule drawn under the body paragraph would let the walk take the lines before it
        far = dict(id='rule:8', kind='rule', source='rect', box_px=[95, 318, 545, 320])
        t = self.table(grid_page([far]))
        self.assertTrue(all(not m.startswith('run:L') and not m.startswith('run:R') for m in t['members']))


def note_page(note_size=9, opening=True):
    """grid_page without its body rows: a two-line note under the foot rule, then (opening) two body-size
    lines in each column, a white gap wider than a block's stack gap, and a six-line paragraph in each column."""
    es = grid_page(body_rows=False); line = 100
    for r in range(2):
        line += 1; y = 222 + 12 * r
        es.append(run(f'run:N{r}', 'note ' + WORDS, (95, y, 545, y + note_size), size=note_size, line=line, font='AAAAAA+Note'))
    top = 254
    if opening:
        for r in range(2):
            line += 1; y = top + 14 * r
            es.append(run(f'run:OL{r}', WORDS, (95, y, 315, y + 11), size=11, line=line))
            es.append(run(f'run:OR{r}', WORDS, (330, y, 545, y + 11), size=11, line=line))
        top += 2 * 14 + 9   # white of 12 under the last opening line: two blocks, inside the note gap
    for r in range(6):
        line += 1; y = top + 14 * r
        es.append(run(f'run:L{r}', WORDS + ('.' if r == 5 else ''), (95, y, 315, y + 11), size=11, line=line))
        es.append(run(f'run:R{r}', WORDS + ('.' if r == 5 else ''), (330, y, 545, y + 11), size=11, line=line))
    return es


class NoteBeforeMainText(unittest.TestCase):
    """R1 (stream2): main text ending the walk also ends the note at its first body-size line larger than it."""
    def table(self, es):
        ts = boxer.tables_from_grid(es, boxer.larger_boxes(es))
        self.assertEqual(len(ts), 1)
        return ts[0]

    def test_short_column_openings_above_the_main_text_leave_the_note(self):
        t = self.table(note_page())
        self.assertIn('run:N0', t['members']); self.assertIn('run:N1', t['members'])
        self.assertFalse([m for m in t['members'] if m.startswith(('run:O', 'run:L', 'run:R'))])
        self.assertLess(t["box_px"][3], 254)

    def test_note_without_openings_is_unchanged(self):
        t = self.table(note_page(opening=False))
        self.assertIn('run:N1', t['members'])
        self.assertFalse([m for m in t['members'] if m.startswith(('run:L', 'run:R'))])

    def test_helper_keeps_a_note_set_at_the_note_size(self):
        part = {1: [((0, 0, 10, 9), dict(run_size_px=9))], 2: [((0, 12, 10, 21), dict(run_size_px=9.2))]}
        pend = [('line', (0, 0, 10, 9), 1), ('line', (0, 12, 10, 21), 2)]
        self.assertEqual(boxer.note_before_main_text(pend, part, 9, 11), pend)

    def test_helper_cuts_at_the_first_body_size_line(self):
        part = {1: [((0, 0, 10, 9), dict(run_size_px=9))], 2: [((0, 12, 10, 23), dict(run_size_px=11))],
                3: [((0, 26, 10, 35), dict(run_size_px=9))]}
        pend = [('line', None, 1), ('line', None, 2), ('line', None, 3)]
        self.assertEqual(boxer.note_before_main_text(pend, part, 9, 11), pend[:1])

    def test_helper_keeps_a_note_when_cells_are_body_size(self):
        part = {1: [((0, 0, 10, 11), dict(run_size_px=11))]}
        pend = [('line', None, 1)]
        self.assertEqual(boxer.note_before_main_text(pend, part, 11, 11), pend)


class MainTextRuns(unittest.TestCase):
    """R1: the page's main-text runs."""
    def page(self):
        es = []
        for r in range(6):
            es.append(run(f'run:{r}', WORDS + ('.' if r % 2 else ''), (100, 100 + 14 * r, 400, 111 + 14 * r), size=11, line=r))
        es.append(run('run:near', 'a short cut-off body line.', (100, 300, 260, 311), size=11, line=20))
        es.append(run('run:above', 'its previous body line', (100, 286, 400, 297), size=11, line=19))
        es.append(run('run:far', 'a lone body-face label', (100, 400, 260, 411), size=11, line=30))
        es.append(run('run:face', 'another face nearby', (100, 314, 260, 325), size=11, line=21, font='BBBBBB+Display'))
        return es

    def test_columns_and_pitch_continuous_lines(self):
        es = self.page()
        got = boxer.main_text_runs(es, boxer.larger_boxes(es))
        self.assertTrue({f'run:{r}' for r in range(6)} <= got)
        self.assertIn('run:near', got); self.assertIn('run:above', got)
        self.assertNotIn('run:far', got); self.assertNotIn('run:face', got)

    def test_no_prose_column_no_main_text(self):
        es = [run('run:1', 'label', (100, 100, 140, 111), line=1), run('run:2', 'label', (100, 114, 140, 125), line=2)]
        self.assertEqual(boxer.main_text_runs(es, boxer.larger_boxes(es)), set())


class ColumnPattern(unittest.TestCase):
    """R3: a recurring column pattern at a per-page offset."""
    def test_alternating_margins_form_one_pattern_with_page_one(self):
        own = {1: [[131, 447], [132, 1130], [479, 793], [826, 1141]], 2: [], 3: [[131, 440], [477, 779], [823, 1143]],
               4: [[150, 469], [496, 815], [842, 1163]], 5: []}
        pat = boxer.paper_column_pattern(own, 17.5)
        self.assertEqual(sorted(pat['pages']), [1, 3, 4])
        self.assertEqual(len(pat['pattern']), 3)
        cols = boxer.place_column_pattern(pat, 5, [], [], 17.5)
        self.assertEqual([round(c[0]) for c in cols], [131, 479, 826])
        cols = boxer.place_column_pattern(pat, 2, [], [], 17.5)
        self.assertEqual(round(cols[0][0]), 150)

    def test_rule_outside_a_gutter_refuses_the_pattern(self):
        pat = boxer.paper_column_pattern({1: [[100, 400], [430, 730]], 3: [[100, 400], [430, 730]], 5: []}, 15)
        self.assertTrue(boxer.place_column_pattern(pat, 5, [[414, 200, 415, 800]], [], 15))
        self.assertEqual(boxer.place_column_pattern(pat, 5, [[300, 200, 301, 800]], [], 15), [])

    def test_block_across_a_gutter_refuses_the_pattern(self):
        pat = boxer.paper_column_pattern({1: [[100, 400], [430, 730]], 3: [[100, 400], [430, 730]], 5: []}, 15)
        self.assertEqual(boxer.place_column_pattern(pat, 5, [], [[100, 200, 730, 400]], 15), [])

    def test_one_page_is_no_pattern(self):
        self.assertIsNone(boxer.paper_column_pattern({1: [[100, 400], [430, 730]], 2: []}, 15))

    def test_different_widths_are_different_patterns(self):
        self.assertIsNone(boxer.paper_column_pattern({1: [[100, 400], [430, 730]], 3: [[100, 300], [330, 730]]}, 15))


if __name__ == '__main__':
    unittest.main()


def chart_beside_tail_page(tail_end=405):
    """Re-ladder 3 (R1): a paragraph tail carried over from the previous page in the left column (five lines, no
    sentence ended near the chart but the last, short line; then more of the column), and in the right column a
    framed chart on two background fills under a top rule, with a y-axis rule, a rule between its panels, and axis
    numbers and an asterisk set on the tail's own baselines (the same text lines)."""
    es = []
    for r in range(5):
        y = 120 + 14 * r
        text = WORDS if r < 4 else 'over the dog (data not shown).'
        es.append(run(f'run:T{r}', text, (100, y, tail_end if r < 4 else 200, y + 11), size=11, line=r + 1))
    for r in range(8):
        y = 206 + 14 * r   # white under the tail: the tail is a block of its own
        es.append(run(f'run:B{r}', WORDS + ('.' if r >= 5 else ''), (100, y, tail_end, y + 11), size=11, line=r + 10))
    es.append(run('run:n10', '10', (420, 121, 432, 129), size=8, line=1, font='AAAAAA+Sans'))
    es.append(run('run:n9', '9', (424, 149, 432, 157), size=8, line=3, font='AAAAAA+Sans'))
    es.append(run('run:ast', '*', (600, 149, 606, 155), size=8, line=3, font='AAAAAA+Sans'))
    es.append(run('run:n8', '8', (424, 177, 432, 185), size=8, line=5, font='AAAAAA+Sans'))
    es += [dict(id='rule:1', kind='rule', source='line', box_px=[410, 113, 700, 114]),
           dict(id='rule:2', kind='rule', source='line', box_px=[440, 116, 441, 300]),
           dict(id='rule:3', kind='rule', source='line', box_px=[410, 163, 700, 164]),
           dict(id='fill:1', kind='fill', source='rect', box_px=[411, 115, 700, 310]),
           dict(id='fill:2', kind='fill', source='rect', box_px=[411, 115, 701, 312])]
    return es


class MainTextBesideGrid(unittest.TestCase):
    """R1 (re-ladder 3): main text beyond the drawn grid sideways is never a grid cell."""
    def test_tail_lines_on_axis_baselines_are_no_cells(self):
        es = chart_beside_tail_page()
        ts = boxer.tables_from_grid(es, boxer.larger_boxes(es))
        self.assertFalse([m for t in ts for m in t['members'] if m.startswith(('run:T', 'run:B'))])
        self.assertTrue(all(t['box_px'][0] >= 405 for t in ts))

    def test_decision_names_the_main_text(self):
        es = chart_beside_tail_page(); dec = []
        boxer.tables_from_grid(es, boxer.larger_boxes(es), dec)
        self.assertTrue(any(d['why'] == 'bounded: main text beside the drawn grid' for d in dec))

    def test_a_ruled_table_beside_body_columns_keeps_its_cells(self):
        t = TableWalk.table(self, grid_page())
        self.assertTrue(any(m.startswith('run:c') for m in t['members']))
        self.assertFalse([m for m in t['members'] if m.startswith(('run:L', 'run:R'))])


def number_grid_page(label_words=False):
    """Two ruled rows of four aligned short labels (a chart's x-axis numbers drawn twice), or with a word label
    column (label_words: an ordinary small table)."""
    es = []
    xs = [(100, 120), (220, 240), (340, 360), (460, 490)]
    for r in range(3):
        y = 130 + 20 * r
        for k, (a, b) in enumerate(xs):
            text = (('row label', '1.2', '3.4', '5.6')[k] if label_words else ('0', '3', '6', '12')[k])
            es.append(run(f'run:x{r}{k}', text, (a, y, b + (60 if label_words and k == 0 else 0), y + 9), size=9, line=r + 1, font='AAAAAA+Sans'))
    es += [dict(id='rule:1', kind='rule', source='line', box_px=[95, 124, 545, 125]),
           dict(id='rule:2', kind='rule', source='line', box_px=[95, 182, 545, 183])]
    return es


class WordlessGrid(unittest.TestCase):
    """R1 (re-ladder 3): a grid of bare numbers, single letters and signs only is a chart's lettering, not a table."""
    def test_axis_numbers_make_no_table(self):
        es = number_grid_page(); dec = []
        self.assertEqual(boxer.tables_from_grid(es, boxer.larger_boxes(es), dec), [])
        self.assertTrue(any(d['why'].startswith('refused: every cell a bare number') for d in dec))

    def test_a_table_with_a_word_column_stays(self):
        es = number_grid_page(label_words=True)
        self.assertEqual(len(boxer.tables_from_grid(es, boxer.larger_boxes(es))), 1)
