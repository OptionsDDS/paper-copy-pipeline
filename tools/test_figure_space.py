"""Lane r5-floatspace (rules F8 to F12): a figure's space runs from its caption to the nearest body text; the
off-grid words in it are the figure's, never body text or a heading. Invented pages, no paper text."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1] / 'copy_paper.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

N = [0]
WORDS = 'crew cliff record moss count which have ridge dune and signal plot shale season tide bank'.split()


def run(text, x, y, width=None, size=10):
    N[0] += 1
    return dict(id=f'run:{N[0]}', kind='text', text=text, angle=0, line=N[0], run_size_px=size, size_px=size,
                box_px=[x, y, x + (width or 6 * len(text)), y + size], char_ids=[])


def rule(box):
    N[0] += 1
    return dict(id=f'rule:{N[0]}', kind='rule', box_px=list(box))


def words(k, n=8):
    return ' '.join(WORDS[(k + i) % len(WORDS)] for i in range(n))


def paragraph(x, y, lines, width=300, last=120, indent=0):
    """body lines at 13 px spacing on the edge x: a first line indented, full lines, a short last line"""
    out = []
    for k in range(lines):
        w = last if k == lines - 1 else width - (indent if k == 0 else 0)
        out.append(run(words(k) if k < lines - 1 else words(k, 4), x + (indent if k == 0 else 0), y + 13 * k, w))
    return out


def caption(x, y, width=300, text='Figure 2. Counts of crews by season'):
    return run(text, x, y, width, size=9)


def floats_for(cap):
    b = cap['box_px']
    return [(b[1], 'figure', cap['text'], [], [], dict(caption_ids=[cap['id']], caption_box=list(b)))]


def page(es, columns):
    return dict(page=3, elements=es, region_box_px=[0, 0, 800, 1000], main_text=dict(columns=columns))


def runs_of(p):
    return {e['id']: e for e in p['elements'] if e['kind'] == 'text'}


class BodyGrid(unittest.TestCase):
    def test_paragraph_lines_are_body_and_chart_numbers_are_not(self):
        body = paragraph(40, 100, 8, indent=15)
        ticks = [run(str(30 - 5 * k), 420, 100 + 20 * k, 12) for k in range(6)]
        p = page(body + ticks, [[40, 340], [400, 700]])
        grid = c.body_grid_runs(runs_of(p), 10)
        self.assertEqual(grid, {e['id'] for e in body})          # the indented first and short last lines too
        self.assertFalse(grid & {e['id'] for e in ticks})

    def test_other_size_block_is_not_body(self):
        body = paragraph(40, 100, 8)
        small = [run(words(k), 400, 100 + 10 * k, 200, size=7) for k in range(6)]
        grid = c.body_grid_runs(runs_of(page(body + small, [[40, 340], [400, 700]])), 10)
        self.assertFalse(grid & {e['id'] for e in small})


class FigureSpace(unittest.TestCase):
    def chart_page(self):
        """left column: body text; right column: body text at the top, a chart (axis rule, tick numbers, an axis
        title) and its caption under it"""
        left = paragraph(40, 100, 30)
        top = paragraph(400, 100, 6)
        ticks = [run(str(30 - 5 * k), 420, 200 + 25 * k, 12, size=8) for k in range(6)]   # chart lettering in its own type
        axis = [rule([440, 200, 441, 350]), rule([440, 350, 690, 351])]
        title = run('Groups', 520, 360, 40, size=8)
        cap = caption(400, 390)
        below = paragraph(400, 420, 6)
        es = left + top + ticks + axis + [title, cap] + below
        return page(es, [[40, 340], [400, 700]]), cap, ticks + [title], left + top + below

    def test_chart_words_above_the_caption_are_the_figures(self):
        p, cap, fig, body = self.chart_page()
        got = c.figure_space_runs(p, runs_of(p), 10, floats_for(cap), set(), {e['id'] for e in fig + body})
        self.assertEqual(set(got), {e['id'] for e in fig})
        self.assertTrue(all(r['direction'] == 'above' for r in got.values()))

    def test_body_text_round_the_figure_is_never_taken(self):
        p, cap, fig, body = self.chart_page()
        got = c.figure_space_runs(p, runs_of(p), 10, floats_for(cap), set(), {e['id'] for e in fig + body})
        self.assertFalse(set(got) & {e['id'] for e in body})

    def test_taken_runs_stay_with_their_owner(self):
        p, cap, fig, body = self.chart_page()
        got = c.figure_space_runs(p, runs_of(p), 10, floats_for(cap), {fig[0]['id']}, {e['id'] for e in fig + body})
        self.assertNotIn(fig[0]['id'], got)

    def test_heading_on_the_column_edge_is_text(self):
        """a heading over the figure starts where the column's running text starts: it is not figure text"""
        top = paragraph(400, 100, 6)
        head = run('Results and survey', 400, 190, 120)
        ticks = [run(str(k), 460, 230 + 20 * k, 8) for k in range(4)]
        cap = caption(400, 330)
        below = paragraph(400, 360, 6)
        left = paragraph(40, 100, 30)
        p = page(left + top + [head] + ticks + [cap] + below, [[40, 340], [400, 700]])
        got = c.figure_space_runs(p, runs_of(p), 10, floats_for(cap), set(), {e['id'] for e in top + [head] + ticks + below + left})
        self.assertNotIn(head['id'], got)
        self.assertEqual(set(got), {e['id'] for e in ticks})

    def test_caption_over_its_figure_looks_below(self):
        """nothing above the caption: the figure is under it; a body paragraph under the figure ends the space"""
        left = paragraph(40, 60, 30)
        top = paragraph(400, 60, 6)
        cap = caption(400, 150)
        labels = [run('Stage ' + str(k), 450, 190 + 30 * k, 50) for k in range(3)]
        box = [rule([440, 180, 640, 181]), rule([440, 280, 640, 281])]
        below = paragraph(400, 300, 6)
        p = page(left + top + [cap] + labels + box + below, [[40, 340], [400, 700]])
        got = c.figure_space_runs(p, runs_of(p), 10, floats_for(cap), set(), {e['id'] for e in left + top + labels + below})
        self.assertEqual(set(got), {e['id'] for e in labels})
        self.assertTrue(all(r['direction'] == 'below' for r in got.values()))

    def test_figure_wider_than_its_caption_takes_the_free_neighbour_column(self):
        """a flowchart under the body text of both columns, its caption short in the left column"""
        left = paragraph(40, 60, 10)
        right = paragraph(360, 60, 10)
        boxes = [run('SCREENING', 120, 220, 70), run('TESTS', 410, 300, 40), run('PATIENTS', 430, 240, 60)]
        cap = caption(40, 360, 120, 'Fig. 1. Study plan.')
        p = page(left + right + boxes + [cap], [[40, 340], [360, 660]])
        got = c.figure_space_runs(p, runs_of(p), 10, floats_for(cap), set(), {e['id'] for e in left + right + boxes})
        self.assertEqual(set(got), {e['id'] for e in boxes})

    def test_reference_column_beside_the_figure_is_not_the_figures(self):
        """small-type running text going down the neighbour column from above (a reference list) bounds the figure"""
        left = paragraph(40, 60, 10)
        refs = [run(words(k, 7), 360, 60 + 9 * k, 280, size=7) for k in range(40)]
        ticks = [run(str(k), 120, 220 + 20 * k, 8) for k in range(4)]
        cap = caption(40, 360, 120, 'Fig. 3. Crew counts.')
        p = page(left + refs + ticks + [cap], [[40, 340], [360, 660]])
        got = c.figure_space_runs(p, runs_of(p), 10, floats_for(cap), set(), {e['id'] for e in left + refs + ticks})
        self.assertEqual(set(got), {e['id'] for e in ticks})

    def test_display_heading_in_the_space_is_kept(self):
        left = paragraph(40, 100, 30)
        top = paragraph(400, 100, 6)
        head = run('Survey', 470, 190, 60, size=13)
        ticks = [run(str(k), 460, 230 + 20 * k, 8) for k in range(4)]
        cap = caption(400, 330)
        p = page(left + top + [head] + ticks + [cap], [[40, 340], [400, 700]])
        got = c.figure_space_runs(p, runs_of(p), 10, floats_for(cap), set(), {e['id'] for e in left + top + [head] + ticks})
        self.assertNotIn(head['id'], got)

    def test_unplaced_line_that_goes_on_from_a_note_is_kept(self):
        """a free run directly under a line a note owns belongs to that note, not to the next figure"""
        left = paragraph(40, 100, 30)
        top = paragraph(400, 100, 6)
        note = run('CR = crew record; SB = shale bank;', 400, 200, 250, size=9)
        tail = run('TB = tide bank.', 400, 210, 90, size=9)
        ticks = [run(str(k), 460, 240 + 20 * k, 8) for k in range(3)]
        cap = caption(400, 330)
        p = page(left + top + [note, tail] + ticks + [cap], [[40, 340], [400, 700]])
        got = c.figure_space_runs(p, runs_of(p), 10, floats_for(cap), {note['id']}, {e['id'] for e in left + top + ticks})
        self.assertNotIn(tail['id'], got)
        self.assertEqual(set(got), {e['id'] for e in ticks})

    def indented_line_page(alone=False):
        """memo floatspace-holdback-1: body lines (or none) on a column top, then the indented first line of a new
        paragraph, a white gap, a raster picture and its caption; the paragraph goes on in the next column"""
        col1 = [] if alone else paragraph(40, 60, 4)
        first = run(words(3, 6), 50, 60 + 13 * len(col1), 290)          # set in by a paragraph indent, full measure
        pic = dict(id='image:1', kind='image', box_px=[40, 140, 340, 280])
        cap = caption(40, 290)
        col2 = paragraph(360, 60, 30, width=300, indent=0)
        return page(col1 + [first, pic, cap] + col2, [[40, 340], [360, 660]]), cap, first, col1 + col2

    def test_indented_first_line_above_a_picture_is_body_text(self):
        p, cap, first, body = FigureSpace.indented_line_page()
        got = c.figure_space_runs(p, runs_of(p), 10, floats_for(cap), set(), {e['id']: 'b' for e in body + [first]})
        self.assertNotIn(first['id'], got)

    def test_indented_line_alone_on_the_column_top_is_body_text(self):
        p, cap, first, body = FigureSpace.indented_line_page(alone=True)
        got = c.figure_space_runs(p, runs_of(p), 10, floats_for(cap), set(), {e['id']: 'b' for e in body + [first]})
        self.assertNotIn(first['id'], got)

    def test_output_check_keeps_a_body_type_neighbour_of_body_text(self):
        """a body-type run under a body line at the body spacing is never lettering, whatever took it"""
        left = paragraph(40, 100, 30)
        top = paragraph(400, 100, 6, last=300)
        stray = run('crew bank', 470, 100 + 13 * 6, 60)                # body type, one line under the body text
        ticks = [run(str(k), 460, 230 + 20 * k, 8, size=8) for k in range(3)]
        cap = caption(400, 330)
        p = page(left + top + [stray] + ticks + [cap], [[40, 340], [400, 700]])
        ids = {e['id']: 'b%d' % i for i, e in enumerate(left + top + [stray] + ticks)}
        got = c.figure_space_runs(p, runs_of(p), 10, floats_for(cap), set(), ids)
        self.assertNotIn(stray['id'], got)
        self.assertEqual(set(got), {e['id'] for e in ticks})

    def test_output_check_never_splits_a_main_text_block(self):
        """a block of main text keeps all its lines or gives up none"""
        p, cap, fig, body = self.chart_page()
        ids = {e['id']: 'b%d' % i for i, e in enumerate(body)}
        for e in fig:
            ids[e['id']] = 'chart'
        ids[body[-1]['id']] = 'chart'                                 # a block that also holds a body line
        got = c.figure_space_runs(p, runs_of(p), 10, floats_for(cap), set(), ids)
        self.assertEqual(got, {})

    def test_pool_p1_side_caption_takes_only_its_picture(self):
        """memo floatspace-pool-1 P1: a caption beside a page-wide picture; under it two body columns, the right one
        with two body lines, a heading in body-size capitals, a two-line paragraph and a reference list"""
        pic = [dict(id='image:1', kind='image', box_px=[95, 96, 800, 332]), dict(id='fill:1', kind='fill', box_px=[95, 96, 1145, 332])]
        cap = run('Figure 1. Crew cliffs and survey plots by season', 828, 97, 293, size=14)
        left = [run(words(k), 96, 381 + 27 * k, 504, size=16.7) for k in range(12)]
        right = [run(words(1), 640, 381, 505, size=16.7), run(words(2, 4), 640, 409, 200, size=16.7),
                 run('CREW AND TIDE RECORDS', 640, 463, 223, size=16.7), run(words(3), 639, 490, 506, size=16.7),
                 run('season.', 640, 517, 76, size=16.7)] + [run(words(k, 9), 640, 599 + 20 * k, 505, size=13) for k in range(6)]
        p = dict(page=5, elements=pic + [cap] + left + right, region_box_px=[0, 0, 1240, 1650],
                 main_text=dict(columns=[[96, 600], [640, 1145]]))
        got = c.figure_space_runs(p, runs_of(p), 16.7, floats_for(cap), set(), {e['id']: e['id'] for e in left + right})
        self.assertEqual(got, {})

    def test_pool_p2_list_beside_a_picture_stays(self):
        """memo floatspace-pool-1 P2: a picture with its caption under it in the right column; beside it in the left
        column a short line, a heading, a short line and a bulleted list in large type"""
        pic = dict(id='image:1', kind='image', box_px=[615, 127, 1151, 589])
        cap = run('Figure 2. Plots of the crew records', 615, 594, 493, size=20)
        left = [run('The survey recorded these three:', 59, 135, 331, size=23), run('Crew records', 59, 170, 200, size=33.5)]
        for k in range(9):
            left += [run('•', 98, 230 + 26 * k, 8, size=23), run(words(k, 3), 134, 230 + 26 * k, 200, size=23)]
        body = [run(words(k), 59, 900 + 30 * k, 1090, size=23) for k in range(8)]
        p = dict(page=2, elements=[pic, cap] + left + body, region_box_px=[0, 0, 1240, 1650],
                 main_text=dict(columns=[[59, 1151]]))
        got = c.figure_space_runs(p, runs_of(p), 23, floats_for(cap), set(), {e['id']: e['id'] for e in left + body})
        self.assertEqual(got, {})

    def test_no_body_text_on_the_page_no_change(self):
        cap = caption(400, 390)
        ticks = [run(str(k), 420, 200 + 25 * k, 12) for k in range(3)]
        p = page(ticks + [cap], [[400, 700]])
        self.assertEqual(c.figure_space_runs(p, runs_of(p), 10, floats_for(cap), set(), {e['id'] for e in ticks}), {})


if __name__ == '__main__':
    unittest.main()
