"""Round 8 lane r8-box: finding and boxing a table (TF1, TF4, TF7, TF8, TK1, TK2, TK6, TK8, TK9).
Synthetic pages only; no corpus strings or IDs."""
import importlib.util, unittest
from pathlib import Path
spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1] / 'copy_paper.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)

BODY = 20.0
NORMAL = dict(size=BODY, face='Serif', pitch=25.0)
COLS = [(100, 500), (540, 940)]


def run(t, x, y, w, size=BODY, rid=None, face='Serif'):
    return dict(id=rid or f'{x}:{y}', kind='text', text=t, box_px=[x, y, x + w, y + size], angle=0, line=y,
                char_ids=[], run_size_px=size, _faces={face: 40})


def prose(x0, y0, n, prefix='p', width=400):
    return [run('alpha beta gamma delta epsilon zeta eta theta', x0, y0 + 25 * i, width, rid=f'{prefix}{i}') for i in range(n)]


def cells(x0, y0, n, size=16.0, prefix='c'):
    return [r for i in range(n) for r in (run('Item ' + str(i), x0, y0 + 22 * i, 60, size, rid=f'{prefix}a{i}', face='Sans'),
                                          run(str(10 + i) + '.5', x0 + 200, y0 + 22 * i, 30, size, rid=f'{prefix}b{i}', face='Sans'),
                                          run(str(20 + i) + '.1', x0 + 330, y0 + 22 * i, 30, size, rid=f'{prefix}c{i}', face='Sans'))]


def page(elements, tables=(), floats=(), blocks=(), mt_blocks=(), num=3):
    return dict(page=num, elements=list(elements), tables=list(tables), floats=list(floats), blocks=list(blocks),
                region_box_px=[0, 0, 1000, 1400], main_text=dict(columns=COLS, blocks=list(mt_blocks)), _r8_normal=NORMAL,
                _body_face='Serif')


class Labels(unittest.TestCase):
    def test_wide_list(self):
        for t in ('Table 1 – Values', 'TABLE 2 Reasons', 'Appendix Table 1 Terms', 'Table A2. Search', 'Tables 3 and 4',
                  'T A B L E 5', 'Table 1 (Continued)', 'eTable 2.', 'Table IV'):
            self.assertTrue(c.r8_label_line(t), t)

    def test_sentences_are_not_captions(self):
        for t in ('Table 1 shows the values', 'Table 2 summarises the', 'Tablets were given'):
            self.assertFalse(c.r8_label_line(t), t)


class Normal(unittest.TestCase):
    def test_normal_column_from_the_prose_blocks(self):
        body = prose(100, 100, 6)
        tab = cells(100, 400, 12)
        p = dict(page=1, elements=body + tab, blocks=[dict(id='b1', members=[e['id'] for e in body])],
                 main_text=dict(columns=COLS, blocks=[dict(id='b1', order=1, lines=6, size_px=BODY, cls='main', text='alpha')]),
                 _body_face='Serif')
        nm = c.r8_paper_normal([p])
        self.assertEqual(nm['size'], BODY)
        self.assertAlmostEqual(nm['pitch'], 25.0)


class Unlabelled(unittest.TestCase):
    def setUp(self):
        c.doubt_list().reset()

    def area(self, members):
        return dict(id='t1', angle=0, members=[e['id'] for e in members], box_px=c.hull(e['box_px'] for e in members))

    def test_prose_area_without_label_is_released(self):
        body = prose(100, 100, 6)
        p = page(body, tables=[self.area(body)])
        c.r8_unlabelled_not_table(p, BODY)
        self.assertEqual(p['tables'], [])
        self.assertEqual(set(p['_copy_body_members']), {e['id'] for e in body})
        self.assertEqual([d['reason'] for d in c.doubt_list().items()], ['unlabelled_area_not_table:TK2'])

    def test_cells_without_label_stay(self):
        tab = cells(100, 100, 6)
        p = page(tab, tables=[self.area(tab)])
        c.r8_unlabelled_not_table(p, BODY)
        self.assertEqual(len(p['tables']), 1)
        self.assertEqual(c.doubt_list().items(), [])

    def test_prose_area_with_label_stays(self):
        body = prose(100, 100, 6)
        lab = run('Table 3. Notes', 100, 60, 150, rid='lab')
        p = page(body + [lab], tables=[self.area(body)])
        c.r8_unlabelled_not_table(p, BODY)
        self.assertEqual(len(p['tables']), 1)

    def test_run_on_from_the_page_before_stays(self):
        body = prose(100, 100, 6)
        p = page(body, tables=[self.area(body)])
        p['_r8_prev_table'] = True
        c.r8_unlabelled_not_table(p, BODY)
        self.assertEqual(len(p['tables']), 1)


class WideCaption(unittest.TestCase):
    def setUp(self):
        c.doubt_list().reset()

    def test_label_above_an_uncaptioned_part_becomes_its_caption(self):
        tab = cells(100, 140, 6)
        lab = run('Appendix Table 1 Terms', 100, 100, 300, rid='lab')
        t = dict(id='t1', angle=0, members=[e['id'] for e in tab], box_px=c.hull(e['box_px'] for e in tab))
        p = page(tab + [lab], tables=[t], blocks=[dict(id='lb', members=['lab'], box_px=lab['box_px'])])
        c.r8_wide_label_caption(p, BODY)
        self.assertEqual(len(p['floats']), 1)
        self.assertEqual(p['floats'][0]['blocks'][1], 't1')
        self.assertEqual(p['floats'][0]['_caption_ids'], ['lab'])
        self.assertNotIn('lab', p['blocks'][0]['members'])

    def test_label_far_from_the_part_is_not_taken(self):
        tab = cells(100, 400, 6)
        lab = run('Table A1. Terms', 100, 100, 300, rid='lab')
        t = dict(id='t1', angle=0, members=[e['id'] for e in tab], box_px=c.hull(e['box_px'] for e in tab))
        p = page(tab + [lab], tables=[t])
        c.r8_wide_label_caption(p, BODY)
        self.assertEqual(p['floats'], [])


class LabelledPart(unittest.TestCase):
    def setUp(self):
        c.doubt_list().reset()

    def body_page(self, under):
        lab = run('Table 2 – Values', 100, 100, 200, rid='lab')
        els = [lab] + under
        blk = dict(id='b1', members=[e['id'] for e in els], box_px=c.hull(e['box_px'] for e in els))
        return page(els, blocks=[blk], mt_blocks=[dict(id='b1', order=1, cls='main', lines=10, size_px=BODY)])

    def test_label_printed_as_body_with_cells_becomes_a_part(self):
        tab = cells(100, 140, 7)
        p = self.body_page(tab)
        c.r8_labelled_part(p, BODY)
        self.assertEqual(len(p['tables']), 1)
        self.assertEqual(set(p['tables'][0]['members']), {e['id'] for e in tab})
        self.assertEqual(p['floats'][0]['_caption_ids'], ['lab'])
        self.assertEqual(p['blocks'][0]['members'], [])

    def test_label_over_prose_stays_body_with_a_doubt(self):
        p = self.body_page(prose(100, 140, 7))
        c.r8_labelled_part(p, BODY)
        self.assertEqual(p['tables'], [])
        self.assertEqual(len(p['blocks'][0]['members']), 8)

    def test_label_inside_a_sentence_is_not_read(self):
        lead = run('alpha beta gamma delta epsilon as listed in', 100, 75, 400, rid='lead')
        p = self.body_page(cells(100, 140, 7))
        p['elements'].append(lead); p['blocks'][0]['members'].append('lead')
        c.r8_labelled_part(p, BODY)
        self.assertEqual(p['tables'], [])


class PictureMarks(unittest.TestCase):
    def setUp(self):
        c.doubt_list().reset()

    def test_part_with_plot_marks_is_listed(self):
        tab = cells(100, 140, 4); plot = cells(100, 300, 4, prefix='g')
        marks = [dict(id=f'o{i}', kind='outline', box_px=[700, 300 + 22 * i, 708, 308 + 22 * i]) for i in range(4)]
        t1 = dict(id='t1', angle=0, members=[e['id'] for e in tab], box_px=c.hull(e['box_px'] for e in tab))
        t2 = dict(id='t2', angle=0, members=[e['id'] for e in plot], box_px=c.hull([e['box_px'] for e in plot] + [m['box_px'] for m in marks]))
        p = page(tab + plot + marks, tables=[t1, t2], floats=[dict(caption='Table 1. Values', blocks=['t1', 't2'], box_px=[100, 140, 720, 400])])
        c.r8_figure_part(p, BODY)
        self.assertEqual([d['reason'] for d in c.doubt_list().items()], ['table_part_picture_marks:TK6'])
        self.assertEqual(len(p['tables']), 2)

    def test_closing_line_grid_end_and_figure_label_agree_the_drawing_leaves(self):
        tab = cells(100, 140, 4); plot = cells(100, 300, 4, prefix='g')
        marks = [dict(id=f'o{i}', kind='outline', box_px=[700, 300 + 22 * i, 708, 308 + 22 * i]) for i in range(4)]
        closing = dict(id='r1', kind='rule', box_px=[100, 230, 500, 231])
        fig = run('Figure 2. A plot', 100, 400, 200, rid='fig')
        t1 = dict(id='t1', angle=0, members=[e['id'] for e in tab], box_px=c.hull(e['box_px'] for e in tab))
        t2 = dict(id='t2', angle=0, members=[e['id'] for e in plot], box_px=c.hull([e['box_px'] for e in plot] + [m['box_px'] for m in marks]))
        p = page(tab + plot + marks + [closing, fig], tables=[t1, t2],
                 floats=[dict(caption='Table 1. Values', blocks=['t1', 't2'], box_px=[100, 140, 720, 400])])
        c.r8_figure_part(p, BODY)
        self.assertEqual([t['id'] for t in p['tables']], ['t1'])
        self.assertEqual(p['floats'][0]['blocks'], ['t1'])
        self.assertEqual(p['floats'][1]['_caption_ids'], ['fig'])
        self.assertEqual(set(p['floats'][1]['_r8_figure_text']), {e['id'] for e in plot})
        self.assertEqual(c.doubt_list().items(), [])


if __name__ == '__main__':
    unittest.main()
