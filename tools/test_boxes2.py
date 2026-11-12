"""Synthetic regressions for boxes2: panel columns, bylines beside display type,
headings attached below, and figure panel titles (AUDIT-AH: AH04, AH01)."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

paper = module('boxes2_copy', 'copy_paper.py')
boxer = module('boxes2_boxer', 'standalone/element_boxer_sc.py')


def run(name, text, box, size=10, faces=None):
    return dict(id=name, text=text, box_px=box, kind='text', line=box[1], angle=0,
                size_px=size, run_size_px=size, _faces=faces or {})


class PanelColumns(unittest.TestCase):
    def panel(self, texts):
        es = {}
        for c, rows in enumerate(texts):
            for r, t in enumerate(rows):
                x = 130*c
                es[f'c{c}r{r}'] = run(f'c{c}r{r}', t, [x, 15*r, x+100, 15*r+10])
        return es

    def test_flowing_panel_columns_are_read_in_turn(self):
        runs = self.panel([['Clinical Relevance', 'Based on the current scientific evi-', 'dence, as outlined in the original'],
                           ['papers, this consensus report is of', 'crucial importance for clinical prac-'],
                           ['tice in the diagnosis and treatment of', 'peri-implant diseases.']])
        ms = list(runs)
        self.assertEqual(paper.prose_column_groups(ms, runs, 10), [ms])   # not a panel: row order kept
        self.assertEqual(paper.prose_column_groups(ms, runs, 10, panel=True),
                         [['c0r0', 'c0r1', 'c0r2'], ['c1r0', 'c1r1'], ['c2r0', 'c2r1']])

    def test_boxed_cells_that_do_not_continue_keep_row_order(self):
        runs = self.panel([['Group one receives treatment.', 'Followed for two years.'],
                           ['Group two receives placebo here.', 'Followed for one year.']])
        ms = list(runs)
        self.assertEqual(paper.prose_column_groups(ms, runs, 10, panel=True), [ms])

    def test_unequal_or_staggered_groups_keep_row_order(self):
        runs = self.panel([['A label', 'of the first part of the'], ['next column starts here with', 'more words to read on']])
        runs['c1r0']['box_px'] = [130, 40, 230, 50]; runs['c1r1']['box_px'] = [130, 55, 230, 65]
        self.assertEqual(paper.prose_column_groups(list(runs), runs, 10, panel=True), [list(runs)])


class BylineBesideTitle(unittest.TestCase):
    def chars(self):
        cs = []; order = 0
        def word(text, x, base, size, font):
            nonlocal order
            for ch in text:
                w = .55*size
                cs.append(dict(text=ch, x0=x, x1=x+w, y0=base-.7*size, y1=base, origin=(x, base), size=size,
                               font=font, angle=0, paint_order=(order, len(cs))))
                x += w
            order += 1
            return x
        word('Peri-implant', 0, 330, 45, 'T')        # display title line ending left of the byline
        word('Jan Lindhe', 320, 310, 18, 'B')         # byline row 1
        word('of Group D', 320, 333, 18, 'B')         # byline row 2, inside the title's tolerance
        for i, c in enumerate(cs): c['id'] = i
        return cs

    def test_rows_of_one_size_keep_their_own_baselines(self):
        to_read, baseline_v = boxer.frame(0)
        lines, runs, _ = boxer.lines_and_runs(self.chars(), 0, [], to_read, baseline_v)
        joined = [''.join(c['text'] for c in cs).strip() for _, cs in runs]
        self.assertTrue(any(t.endswith('Jan Lindhe') for t in joined), joined)   # the region split separates the title later
        self.assertIn('of Group D', joined)
        self.assertFalse(any('Joa' in t for t in joined), joined)


class FigureBand(unittest.TestCase):
    def page(self):
        es = [dict(id='image:1', kind='image', box_px=[100, 100, 600, 500]),
              run('para1', 'This body paragraph above the figure has many ordinary words in it.', [100, 40, 600, 50], 10),
              run('para2', 'It continues for a second line of ordinary prose words here.', [100, 54, 600, 64], 10),
              run('title', 'Beta Diversity Principal Coordinates Analysis Via Aitchison Distance', [200, 80, 500, 92], 10),
              run('letter', '(B)', [300, 96, 315, 106], 10),   # a panel letter rising above the ink
              run('cap', 'Figure 3 Salivary microbial diversity analysis.', [100, 510, 600, 520], 10)]
        blocks = [dict(id='b1', members=['para1', 'para2'], box_px=[100, 40, 600, 64]),
                  dict(id='b2', members=['title'], box_px=[200, 80, 500, 92]),
                  dict(id='b3', members=['letter'], box_px=[300, 96, 315, 106]),
                  dict(id='b4', members=['cap'], box_px=[100, 510, 600, 520])]
        return dict(page=1, elements=es, blocks=blocks, region_box_px=[0, 0, 700, 900],
                    main_text=dict(body_size_px=10))

    def test_panel_title_and_lettering_belong_to_the_figure(self):
        p = self.page(); runs = {e['id']: e for e in p['elements'] if e['kind'] == 'text'}
        band, letters = paper.figure_band_lettering(p, runs, ['cap'], 10)
        self.assertEqual(sorted(letters), ['letter', 'title'])
        self.assertLessEqual(band[1], 80)

    def test_sentence_line_above_a_figure_stays_body(self):
        p = self.page(); runs = {e['id']: e for e in p['elements'] if e['kind'] == 'text'}
        runs['title']['text'] = 'The results are shown in the figure below.'
        band, letters = paper.figure_band_lettering(p, runs, ['cap'], 10)
        self.assertEqual(letters, ['letter'])


if __name__ == '__main__':
    unittest.main()
