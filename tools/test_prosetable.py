"""Synthetic regressions for lane r2-prosetable (2026-11-06): equal columns of body prose (justified or ragged,
partner beside, across a panel or elsewhere on the page; not table rows opening together) are the page's
columns, never table cells (prose_column_tracks), in the grid finder (tables_from_grid), the bordered-caption route
(bounded_caption_tables) and the caption-anchored route (tables_from_caption).
Every geometry and word here is invented; no line of any paper is quoted."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prosetable_boxer', ROOT / 'standalone/element_boxer_sc.py')
boxer = importlib.util.module_from_spec(spec); spec.loader.exec_module(boxer)

SIZE = 10          # letter height (px)
LEAD = 13          # line pitch (px)
WORDS = 'alder brook cinder dune ember fallow glade heath inlet juniper knoll larch'.split()


def run(name, text, box, line, size=SIZE):
    font = 'AAAAAA+Body-Regular'
    return dict(id=name, text=text, box_px=[float(v) for v in box], kind='text', line=line, angle=0, size_px=size,
                run_size_px=size, font=font, font_spans=[dict(font=font, start=0, end=len(text))], char_ids=[], region=None)


def prose_line(k, n=7):
    words = [WORDS[(k * 5 + i) % len(WORDS)] for i in range(n)]
    return ' '.join(words) + ('.' if k % 3 == 2 else '')


def columns(xs, width, top, lines, start=0, ragged=False, rows=False):
    """one run per column per line. A prose column fills its width on every line but each paragraph's last, or
    ends its lines short by varying amounts when ragged; paragraphs open (indented) at different lines in
    different columns. rows=True sets table rows instead: cells of three lines opening on shared baselines,
    a row gap under each"""
    out = []
    for c, x in enumerate(xs):
        y = top
        for k in range(lines):
            if rows and k and k % 3 == 0: y += 0.6 * LEAD
            opens = (k % 3 == 0) if rows else ((k + 2 * c) % 5 == 0)
            indent = 1.5 * SIZE if opens and not rows else 0
            if ragged or rows: w = width - (((k * 7 + c * 3) % 5) * 2.2 * SIZE + 1.5 * SIZE)
            else: w = width - (0.4 * width if (k + 2 * c) % 5 == 4 else 0)
            out.append(run(f'run:{start + len(out)}', prose_line(k + 11 * c), (x + indent, y, x + w, y + SIZE), line=k))
            y += LEAD
    return out


def pairs(runs): return [(r['box_px'], r) for r in runs]


class ProseColumnTracks(unittest.TestCase):
    def test_three_equal_filled_columns_are_prose(self):
        rs = columns([100, 400, 700], 270, 100, 20)
        got = boxer.prose_column_tracks(pairs(rs), {r['id'] for r in rs}, SIZE)
        self.assertEqual(len(got), 3)

    def test_ragged_prose_columns_are_prose(self):
        rs = columns([100, 400, 700], 270, 100, 20, ragged=True)
        self.assertEqual(len(boxer.prose_column_tracks(pairs(rs), {r['id'] for r in rs}, SIZE)), 3)

    def test_table_rows_opening_together_are_not_prose(self):
        rs = columns([100, 400, 700], 270, 100, 21, rows=True)
        self.assertEqual(boxer.prose_column_tracks(pairs(rs), {r['id'] for r in rs}, SIZE), [])

    def test_value_cells_are_not_prose(self):
        rs = []
        for c, x in enumerate((100, 400)):
            for k in range(12):
                rs.append(run(f'run:{len(rs)}', f'{k + 3}.{c} ({k % 4}.{k % 7}) {k * 11}', (x, 100 + k * LEAD, x + 270, 110 + k * LEAD), line=k))
        self.assertEqual(boxer.prose_column_tracks(pairs(rs), {r['id'] for r in rs}, SIZE), [])

    def test_a_partner_across_a_panel_counts(self):
        both = columns([100, 650], 270, 100, 20)
        left, right = both[:20], both[20:]
        panel = [run(f'run:{100 + k}', 'alder brook', (420, 100 + k * LEAD, 600, 110 + k * LEAD), line=k) for k in range(20)]
        got = boxer.prose_column_tracks(pairs(left + panel + right), {r['id'] for r in left + right}, SIZE)
        self.assertEqual(len(got), 2)

    def test_columns_smaller_than_the_body_are_not_prose(self):
        body = columns([100, 400], 270, 600, 40, start=500)        # the page's body text elsewhere, at SIZE
        small = [dict(r, run_size_px=0.8 * SIZE, size_px=0.8 * SIZE) for r in columns([100, 400], 270, 100, 20)]
        got = boxer.prose_column_tracks(pairs(small), set(), SIZE, pairs(small + body), {})
        self.assertEqual(got, [])

    def test_a_lone_prose_column_has_no_partner(self):
        prose = columns([100], 270, 100, 20)
        cells = []
        for c, x in enumerate((400, 560)):
            for k in range(20):
                cells.append(run(f'run:{100 + len(cells)}', f'{k}.{c}', (x, 100 + k * LEAD, x + 40, 110 + k * LEAD), line=k))
        got = boxer.prose_column_tracks(pairs(prose + cells), {r['id'] for r in prose + cells}, SIZE)
        self.assertEqual(got, [])

    def test_unequal_widths_are_not_one_measure(self):
        rs = columns([100], 270, 100, 20) + columns([400], 420, 100, 20, start=100)
        self.assertEqual(boxer.prose_column_tracks(pairs(rs), {r['id'] for r in rs}, SIZE), [])

    def test_justified_lines_split_at_wide_word_spaces_still_fill(self):
        rs = []
        for c, x in enumerate((100, 400)):
            for k in range(12):
                cut = 60 + (k * 37) % 150     # the wide word space falls at a different place on every line
                rs.append(run(f'run:{len(rs)}', 'alder brook', (x, 100 + k * LEAD, x + cut, 110 + k * LEAD), line=k))
                rs.append(run(f'run:{len(rs)}', 'cinder dune ember.', (x + cut + 30, 100 + k * LEAD, x + 270, 110 + k * LEAD), line=k))
        self.assertEqual(len(boxer.prose_column_tracks(pairs(rs), {r['id'] for r in rs}, SIZE)), 2)


def fill(name, box): return dict(id=name, kind='fill', box_px=[float(v) for v in box], angle=0)
def rule(name, box): return dict(id=name, kind='rule', box_px=[float(v) for v in box], angle=0)


def block(name, runs):
    bs = [r['box_px'] for r in runs]
    return dict(id=name, members=[r['id'] for r in runs], box_px=[min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)],
                text_lines=len({r['line'] for r in runs}), text=' '.join(r['text'] for r in runs)[:80], kinds=['text'])


class GridFinder(unittest.TestCase):
    """three prose columns beside a shaded panel, a page-wide rule over and under the column band"""
    def page(self, ragged=False, rows=False):
        cols = columns([400, 700, 1000], 270, 120, 30, start=100, ragged=ragged, rows=rows)
        panel = []
        for k in range(30):
            panel.append(run(f'run:{k}', prose_line(k, 3), (110, 120 + k * LEAD, 330, 130 + k * LEAD), line=k))
        drawn = [fill('fill:1', (100, 113, 340, 512)), rule('rule:2', (100, 113, 1270, 114)), rule('rule:3', (100, 511, 1270, 512))]
        blocks = [block('block:1', panel)] + [block(f'block:{2 + c}', [r for r in cols if abs(r['box_px'][0] - x) < 1])
                                              for c, x in enumerate((400, 700, 1000))]
        return panel + cols + drawn, blocks, cols

    def test_prose_columns_are_not_cells(self):
        elements, blocks, cols = self.page()
        decisions = []
        tables = boxer.tables_from_grid(elements, blocks, decisions)
        ids = {r['id'] for r in cols}
        self.assertFalse(any(ids.intersection(t['members']) for t in tables))
        self.assertTrue(any("page's columns" in d['why'] for d in decisions))

    def test_ragged_prose_columns_are_not_cells(self):
        elements, blocks, cols = self.page(ragged=True)
        decisions = []
        tables = boxer.tables_from_grid(elements, blocks, decisions)
        self.assertFalse(any({r['id'] for r in cols}.intersection(t['members']) for t in tables))

    def test_table_rows_keep_their_grid(self):
        elements, blocks, cols = self.page(rows=True)
        decisions = []
        boxer.tables_from_grid(elements, blocks, decisions)
        self.assertFalse(any("page's columns" in d['why'] for d in decisions))


class BorderedCaption(unittest.TestCase):
    """a Table caption over a page-wide rule, a matching rule under the column band: the table is the panel only"""
    def test_bordered_caption_keeps_only_the_panel(self):
        cols = columns([400, 700, 1000], 270, 130, 24, start=100)
        panel = [run(f'run:{k}', prose_line(k, 3), (110, 130 + k * LEAD, 330, 140 + k * LEAD), line=k) for k in range(24)]
        cap = run('run:99', 'Table 1. Points', (100, 100, 260, 110), line=-1)
        drawn = [rule('rule:2', (100, 118, 1270, 119)), rule('rule:3', (100, 450, 1270, 451))]
        blocks = [block('block:0', [cap]), block('block:1', panel)] + [block(f'block:{2 + c}', [r for r in cols if abs(r['box_px'][0] - x) < 1])
                                                                     for c, x in enumerate((400, 700, 1000))]
        elements = [cap] + panel + cols + drawn
        decisions = []
        out = boxer.bounded_caption_tables(elements, blocks, [], decisions, fallback=True)
        self.assertEqual(len(out), 1)
        self.assertLessEqual(out[0]['box_px'][2], 340)
        self.assertFalse({r['id'] for r in cols}.intersection(out[0]['members']))


if __name__ == '__main__':
    unittest.main()


class TableRowsAsBlocks(unittest.TestCase):
    """cells of one row are rule-2 blocks starting on one line in every track: rows, not columns"""
    def test_side_by_side_cell_blocks_are_rows(self):
        rs, blocks = [], {}
        for c, x in enumerate((100, 400)):
            y = 100
            for r in range(4):
                n = 4 if c else 2          # the left cells are shorter: white under them
                ids = []
                for k in range(n):
                    e = run(f'run:{len(rs)}', prose_line(k + 3 * r + 7 * c), (x, y + k * LEAD, x + 270, y + k * LEAD + SIZE), line=int(y / LEAD) + k)
                    rs.append(e); ids.append(e['id'])
                blk = dict(id=f'block:{c}:{r}', members=ids)
                for m in ids: blocks[m] = blk
                y += 4 * LEAD + 6
        got = boxer.prose_column_tracks(pairs(rs), {r['id'] for r in rs}, SIZE, pairs(rs), blocks)
        self.assertEqual(got, [])


class UnequalMeasures(unittest.TestCase):
    """two prose columns of different measures: partners across a drawn panel, or when each opens its own units"""
    def cols(self):
        a = columns([100], 300, 100, 24)                      # opens at lines 0, 5, 10, ...
        b = [dict(r, id=f'run:{500 + i}') for i, r in enumerate(columns([0, 600], 220, 100, 24)[24:])]   # opens at 3, 8, ...
        return a, b

    def test_independent_openings_make_partners(self):
        a, b = self.cols()
        got = boxer.prose_column_tracks(pairs(a + b), {r['id'] for r in a + b}, SIZE)
        self.assertEqual(len(got), 2)

    def test_a_panel_between_makes_partners(self):
        rs = []   # two filled prose columns of different measures with no openings: no independence evidence
        for c, (x, w) in enumerate(((100, 300), (620, 220))):
            for k in range(20):
                rs.append(run(f'run:{len(rs)}', prose_line(k + 9 * c) + '.', (x, 100 + k * LEAD, x + w, 110 + k * LEAD), line=k))
        self.assertEqual(boxer.prose_column_tracks(pairs(rs), {r['id'] for r in rs}, SIZE), [])
        got = boxer.prose_column_tracks(pairs(rs), {r['id'] for r in rs}, SIZE, drawn=[[430, 95, 590, 380]])
        self.assertEqual(len(got), 2)

    def test_unequal_cells_without_openings_stay_cells(self):
        rs = []
        for c, (x, w) in enumerate(((100, 300), (450, 200))):
            for k in range(20):
                rs.append(run(f'run:{len(rs)}', prose_line(k + 9 * c), (x, 100 + k * LEAD, x + w - (k % 4) * SIZE, 110 + k * LEAD), line=k))
        self.assertEqual(boxer.prose_column_tracks(pairs(rs), {r['id'] for r in rs}, SIZE), [])
