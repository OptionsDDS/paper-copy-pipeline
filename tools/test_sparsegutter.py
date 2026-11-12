"""A sparse column's aligned word spaces never become a column gutter (synthetic, no corpus strings).

When only a few lines populate a column, the spaces between its words can line
up into a narrow white channel. If that channel, narrower than a line height,
ends within one line height of a channel at least a line height and twice as
wide, and the words on its two sides belong to one saved run on most lines, the
wider channel is the gutter: the words after the spaces stay in their cell at
every reading angle, including rotated tables. A narrow channel between
separate cells (different runs) stays a gutter.
"""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1] / 'copy_paper.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)

H = 16   # line box height (px): the table's line height


def build(cells):
    """cells: [(y, [(word, x0, x1), ...]), ...], one saved run per entry, with one character box per letter."""
    chars, runs = [], []
    for y, words in cells:
        ids = []
        for word, x0, x1 in words:
            step = (x1 - x0) / len(word)
            for k, ch in enumerate(word):
                ids.append(len(chars))
                chars.append(dict(x0=x0 + k*step, y0=y, x1=x0 + (k+1)*step, y1=y + H, text=ch, size=H))
        text = ' '.join(w for w, _, _ in words)
        runs.append(dict(id=f'run:{len(runs)}', kind='text', text=text, angle=0, line=len(runs),
                         box_px=[words[0][1], y, words[-1][2], y + H], char_ids=ids))
    return runs, chars


def rotate(runs, chars, angle):
    """Set the reading-frame layout on the page at this angle (text reads along the rotated frame)."""
    to_page = c.frame(-angle)
    runs, chars = copy.deepcopy(runs), copy.deepcopy(chars)
    for e in runs:
        e['box_px'] = list(to_page(e['box_px'])); e['angle'] = angle
    for ch in chars:
        ch['x0'], ch['y0'], ch['x1'], ch['y1'] = to_page([ch['x0'], ch['y0'], ch['x1'], ch['y1']])
    return runs, chars


def cell_texts(rows):
    return [' '.join(cell) for row in rows if row for cell in row]


class SparseColumnWordSpaces(unittest.TestCase):
    def layout(self):
        # Results column (x 100..195): its first words end at 141 and its second words start at 151
        # on five lines, a 10 px channel (narrower than H) ending 8 px before the gutter (159..220).
        results = {30: [('A1', 100, 112), ('and', 116, 141), ('have', 151, 177)],
                   50: [('similarity', 100, 141), ('ok', 151, 159)],
                   70: [('difference', 100, 141), ('no', 151, 159)],
                   90: [('betweenxyz', 100, 141), ('X1', 151, 159), ('and', 163, 181), ('Y2', 185, 195)],
                   250: [('synthesis', 100, 141), ('of', 151, 159)],
                   270: [('results', 100, 130)]}
        cells = [(0, [('Study', 0, 30)]), (0, [('Results', 100, 142)]), (0, [('Score', 220, 250)]),
                 (0, [('Comments', 300, 348)])]
        cells += [(30, [('Alpha', 0, 30)]), (50, [('2001', 0, 24)]), (250, [('Beta', 0, 24)]), (270, [('2002', 0, 24)])]
        cells += [(30, [('Q7', 220, 232)]), (50, [('L2', 220, 232)]), (250, [('Q5', 220, 232)]), (270, [('L3', 220, 232)])]
        cells += [(y, list(words)) for y, words in results.items()]
        for y in list(range(30, 230, 20)) + list(range(250, 430, 20)):
            cells.append((y, [('prose', 300, 330), ('words', 336, 366), ('here', 372, 396)]))
        return build(cells)

    def test_word_spaces_stay_in_their_cell_at_every_angle(self):
        for angle in (0, 90, 270):
            runs, chars = rotate(*self.layout(), angle)
            page = dict(page=1, elements=runs, _table_chars=chars)
            rows, notes = c.table_rows(runs, H, page)
            texts = cell_texts(rows)
            # The words stay in their columns; where "Alpha" / "2001" (a study and its
            # year) divide rows is the row rule's business (tablesub5: a year line
            # continues its citation), so the column contents are read across rows.
            column = lambda k: ' '.join(' '.join(row[k]) for row in rows[1:] if row and row[k])
            self.assertEqual(column(1), 'A1 and have similarity ok difference no betweenxyz X1 and Y2 synthesis of results', (angle, texts))
            self.assertEqual(column(2).split(), ['Q7', 'L2', 'Q5', 'L3'], (angle, texts))

    def test_narrow_gutter_between_separate_cells_is_kept(self):
        # A text column ends 10 px before a column of one-character values (cells of their own),
        # whose next channel is wide: the narrow channel separates different runs, so it stays a gutter.
        cells = [(0, [('Item', 0, 24)]), (0, [('Measure', 100, 141)]), (0, [('Y', 151, 157)]), (0, [('Note', 220, 244)])]
        for i, y in enumerate(range(30, 330, 20)):
            cells += [(y, [('row%02d' % i, 0, 30)]), (y, [('valuetextz', 100, 141)]), (y, [('N' if i % 2 else 'Y', 151, 157)]),
                      (y, [('text', 220, 244)])]
        runs, chars = build(cells)
        rows, notes = c.table_rows(runs, H, dict(page=1, elements=runs, _table_chars=chars))
        # (Whether the wide channel also separates the one-character column is outside this rule.)
        self.assertEqual(rows[1][:2], [['row00'], ['valuetextz']], rows)
        self.assertTrue(all(row[1] == ['valuetextz'] for row in rows[1:]), rows)


if __name__ == '__main__':
    unittest.main()
