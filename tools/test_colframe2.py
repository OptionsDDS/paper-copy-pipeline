"""Synthetic regressions for lane colframe2 (2026-11-04): a table the grid cannot finish must not spill.
prose_witnesses: a prose-column block ends a captioned table beyond its connected drawn structure only
outside the table's gate (its own rules continuing past the structure) and when it does not stand beside
cells (runs of narrow blocks on its baselines). Every geometry here is invented; no line of any paper is quoted."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('colframe2_boxer', ROOT / 'standalone/element_boxer_sc.py')
boxer = importlib.util.module_from_spec(spec); spec.loader.exec_module(boxer)

SENTENCE = 'the quick brown fox jumps over the lazy dog and keeps running on.'


def run(name, text, box, size=10):
    return dict(id=name, text=text, box_px=list(box), kind='text', line=box[1], angle=0, size_px=size, run_size_px=size,
                font='', _faces={})


class ProseWitnesses(unittest.TestCase):
    SPAN = (90, 710)
    STRUCT = [[100, 100, 700, 101], [100, 140, 700, 141]]     # top rule and header rule, connected

    def column(self, texts, blocks, name, x0, x1, y0, rows=5):
        ms = []
        for r in range(rows):
            e = run(f'{name}{r}', SENTENCE, [x0, y0 + r * 14, x1, y0 + r * 14 + 10]); texts.append(e); ms.append(e['id'])
        blocks.append(dict(id=name, members=ms, text_lines=rows, box_px=[x0, y0, x1, y0 + (rows - 1) * 14 + 10]))

    def witnesses(self, texts, blocks, rules, captions=()):
        return boxer.prose_witnesses(texts, blocks, {b['id'] for b in blocks if b['id'].startswith('p')}, self.SPAN,
                                     self.STRUCT, rules, list(captions), 141, +1, 10)

    def test_block_inside_the_tables_own_rules_is_no_witness(self):
        texts, blocks = [], []
        self.column(texts, blocks, 'p1', 450, 690, 160)
        rules = self.STRUCT + [[100, 240, 700, 241], [100.5, 330, 699.5, 331]]   # row rule and bottom rule, same ends
        self.assertEqual(self.witnesses(texts, blocks, rules), frozenset())

    def test_block_past_the_last_own_rule_stays_a_witness(self):
        texts, blocks = [], []
        self.column(texts, blocks, 'p1', 100, 390, 360)
        self.column(texts, blocks, 'p2', 410, 700, 360)
        rules = self.STRUCT + [[100, 330, 700, 331]]
        self.assertEqual(self.witnesses(texts, blocks, rules), frozenset({'p1', 'p2'}))

    def test_a_rule_of_another_width_is_not_the_tables(self):
        texts, blocks = [], []
        self.column(texts, blocks, 'p1', 100, 390, 160)
        self.column(texts, blocks, 'p2', 410, 700, 160)
        rules = self.STRUCT + [[100, 400, 300, 401]]      # a short footnote rule further down
        self.assertEqual(self.witnesses(texts, blocks, rules), frozenset({'p1', 'p2'}))

    def test_another_caption_ends_the_gate(self):
        texts, blocks = [], []
        self.column(texts, blocks, 'p1', 100, 390, 160)
        self.column(texts, blocks, 'p2', 410, 700, 160)
        cap = run('cap2', 'Table 9. Something else.', [100, 260, 400, 270])
        rules = self.STRUCT + [[100, 290, 700, 291]]     # the next table's top rule
        self.assertEqual(self.witnesses(texts, blocks, rules, [cap]), frozenset({'p1', 'p2'}))

    def test_block_beside_narrow_cells_is_no_witness(self):
        texts, blocks = [], []
        self.column(texts, blocks, 'p1', 450, 690, 160)
        for i, (x0, x1) in enumerate(((110, 200), (220, 300), (420, 435))):   # a name cell, a value cell, an item number
            e = run(f'c{i}', 'cell', [x0, 160 + 28, x1, 170 + 28]); texts.append(e)
            blocks.append(dict(id=f'c{i}', members=[e['id']], text_lines=1, box_px=e['box_px']))
        self.assertEqual(self.witnesses(texts, blocks, self.STRUCT), frozenset())

    def test_body_column_beside_the_next_tables_cells_stays_a_witness(self):
        texts, blocks = [], []
        self.column(texts, blocks, 'p1', 450, 690, 160, rows=8)
        cap = run('cap2', 'Table 9.', [110, 188, 170, 198]); texts.append(cap)
        blocks.append(dict(id='cap', members=['cap2'], text_lines=1, box_px=cap['box_px']))
        for i, (x0, x1) in enumerate(((110, 200), (220, 300))):          # the next table's cells, under its caption
            e = run(f'c{i}', 'cell', [x0, 160 + 56, x1, 170 + 56]); texts.append(e)
            blocks.append(dict(id=f'c{i}', members=[e['id']], text_lines=1, box_px=e['box_px']))
        self.assertEqual(self.witnesses(texts, blocks, self.STRUCT, [cap]), frozenset({'p1'}))

    def test_two_body_columns_side_by_side_stay_witnesses(self):
        texts, blocks = [], []
        self.column(texts, blocks, 'p1', 100, 390, 160)
        self.column(texts, blocks, 'p2', 410, 700, 160)
        sup = run('sup', '7', [300, 158, 306, 164]); texts.append(sup)          # a superscript inside the column's width
        blocks.append(dict(id='s', members=['sup'], text_lines=1, box_px=sup['box_px']))
        self.assertEqual(self.witnesses(texts, blocks, self.STRUCT), frozenset({'p1', 'p2'}))

    def test_body_column_beside_a_bulleted_body_column_stays_a_witness(self):
        # round 2: the neighbouring column's list marker is a narrow block of its own, but its line also holds
        # that column's wide run on the same side, so the marker is a piece of a body column, not a cell
        texts, blocks = [], []
        self.column(texts, blocks, 'p1', 450, 690, 160)
        ms = []
        for r in range(5):
            e = run(f'q{r}', SENTENCE, [130, 160 + r * 14, 400, 170 + r * 14]); texts.append(e); ms.append(e['id'])
        blocks.append(dict(id='q', members=ms, text_lines=5, box_px=[130, 160, 400, 226]))
        for r in (1, 3):
            m = run(f'm{r}', '*', [104, 163 + r * 14, 110, 167 + r * 14]); m['line'] = 160 + r * 14; texts.append(m)
            blocks.append(dict(id=f'm{r}', members=[m['id']], text_lines=1, box_px=m['box_px']))
        self.assertEqual(self.witnesses(texts, blocks, self.STRUCT), frozenset({'p1'}))
        got = boxer.prose_witnesses(texts, blocks, {'p1'}, self.SPAN, [], [], [], 400, -1, 10)   # caption below, no drawing
        self.assertEqual(got, frozenset({'p1'}))

    def test_cells_beside_the_block_are_cells_even_with_a_marker_among_them(self):
        texts, blocks = [], []
        self.column(texts, blocks, 'p1', 450, 690, 160)
        for i, (x0, x1) in enumerate(((104, 110), (130, 200), (220, 300))):   # a marker and two narrow cells, nothing wide
            e = run(f'c{i}', 'cell', [x0, 160 + 28, x1, 170 + 28]); texts.append(e)
            blocks.append(dict(id=f'c{i}', members=[e['id']], text_lines=1, box_px=e['box_px']))
        self.assertEqual(self.witnesses(texts, blocks, self.STRUCT), frozenset())

    def test_upward_table_gate(self):
        texts, blocks = [], []
        self.column(texts, blocks, 'p1', 450, 690, 200)
        struct = [[100, 400, 700, 401], [100, 360, 700, 361]]
        rules = struct + [[100, 180, 700, 181]]
        got = boxer.prose_witnesses(texts, blocks, {'p1'}, self.SPAN, struct, rules, [], 360, -1, 10)
        self.assertEqual(got, frozenset())
        got = boxer.prose_witnesses(texts, blocks, {'p1'}, self.SPAN, struct, struct, [], 360, -1, 10)
        self.assertEqual(got, frozenset({'p1'}))


if __name__ == '__main__':
    unittest.main()
