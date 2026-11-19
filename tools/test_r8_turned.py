"""Round 8, lane r8-turned: a turned table read in one upright frame (the user's rule of 2026-11-16).

A table set sideways needs no special rules: its positions are turned upright by arithmetic, then every table rule
applies unchanged. Every page here is made up: an upright page is built, then turned a quarter turn by the inverse
of the program's own frame() (the direction a PDF records for text set sideways), and the rule must do on the turned
page exactly what it does on the upright one.
"""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('copy_paper', ROOT / 'copy_paper.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
BODY = 16.0


def run(i, x, y, text, w=None, size=BODY * .8, angle=0):
    w = w or .5 * size * len(text)
    return dict(id='run:%d' % i, kind='text', angle=angle, text=text, box_px=[x, y, x + w, y + size],
                run_size_px=size, size_px=size)


def rule(i, x0, x1, y):
    return dict(id='rule:%d' % i, kind='rule', box_px=[x0, y, x1, y + 1.0])


def upright_table_page(header_outside=True):
    """a captioned table under a top rule, its header line outside the part the detector found (rule TE1's case)"""
    els = [run(1, 100, 100, 'Table 1. Made-up values', size=BODY)]
    els.append(dict(id='fill:2', kind='fill', box_px=[100, 124, 470, 149]))   # a shaded header band under the caption
    els.append(run(3, 100, 130, 'Group'))
    els.append(run(4, 300, 130, 'Count'))
    els.append(run(5, 450, 130, 'Share'))
    members = []
    y, i = 152, 10
    for k in range(6):
        for x, t in ((100, 'Item %d' % k), (300, str(10 + k)), (450, '%d.5' % k)):
            els.append(run(i, x, y, t)); members.append('run:%d' % i); i += 1
        y += 18
    els.append(rule(99, 100, 470, y + 2))
    if not header_outside: members += ['run:3', 'run:4', 'run:5']
    tb = c.hull(e['box_px'] for e in els if e['id'] in members)
    p = dict(page=3, elements=els,
             tables=[dict(id='t1', angle=0, members=members, box_px=tb)],
             blocks=[dict(id='cap1', members=['run:1'], box_px=list(els[0]['box_px'])),
                     dict(id='b2', members=['run:3', 'run:4', 'run:5'], box_px=c.hull(e['box_px'] for e in els[2:5]))],
             floats=[dict(caption='Table 1. Made-up values', blocks=['cap1', 't1'], box_px=c.hull([els[0]['box_px'], tb]))],
             main_text=dict(columns=[(90, 610)], blocks=[dict(id='b2', order=1, box_px=c.hull(e['box_px'] for e in els[2:5]))]))
    return p


def turned(p, angle):
    """the same page set sideways: every box turned back by the inverse of frame(angle), text at that angle"""
    back = c.frame_box_back(angle)
    q = copy.deepcopy(p)
    for e in q['elements']:
        e['box_px'] = back(e['box_px'])
        if e['kind'] == 'text': e['angle'] = angle
    for k in ('tables', 'blocks', 'floats'):
        for x in q[k]:
            x['box_px'] = back(x['box_px'])
            if 'angle' in x: x['angle'] = angle
    for b in q['main_text']['blocks']: b['box_px'] = back(b['box_px'])
    q['main_text']['columns'] = []   # a turned page has no upright column of prose
    return q


class Frame(unittest.TestCase):
    def test_point_back_inverts_frame(self):
        for a in (0, 90, 180, 270):
            fr, back = c.frame(a), c.frame_point_back(a)
            for x, y in ((10.5, 20.25), (-3, 7), (400, 0)):
                u0, v0, _, _ = fr((x, y, x, y))
                self.assertEqual(back(u0, v0), (x, y))

    def test_box_back_inverts_frame(self):
        b = [10.0, 20.0, 30.5, 45.25]
        for a in (0, 90, 180, 270):
            self.assertEqual(c.frame_box_back(a)(list(c.frame(a)(b))), b)

    def test_render_point_upright_is_the_crop_shift(self):
        k = 150 / 72; crop = (12, 30, 600, 800); height = crop[3] - crop[1]
        f = c.r8_render_point(0, 0, height, crop, k)
        x, y = f(100.0, 200.0)
        self.assertAlmostEqual(x, 100 - 12 * k); self.assertAlmostEqual(y, 200 + 30 * k)

    def test_render_point_turned_text_lands_on_its_page_place(self):
        # text set at 90 degrees on an unflagged page: the upright point (u, v) is the record point (v, -u)
        k = 150 / 72; crop = (0, 0, 600, 800)
        f = c.r8_render_point(90, 0, 800, crop, k)
        x, y = f(-250.0, 120.0)
        self.assertAlmostEqual(x, 120.0); self.assertAlmostEqual(y, 250.0)


class Notes(unittest.TestCase):
    def source(self, angle):
        """a table source in its upright frame (as table_source() records any table): rows, the lowest long rule, then a
        note line under it opening with a note mark"""
        lines = []
        for k, y in enumerate((100, 118, 136, 154)):
            items = [dict(box=[100, y, 160, y + 12], text='Row%d' % k, id='a%d' % k),
                     dict(box=[300, y, 330, y + 12], text=str(k), id='b%d' % k)]
            lines.append(dict(text='Row%d %d' % (k, k), items=items))
        lines.append(dict(text='* made-up note', items=[dict(box=[100, 180, 260, 192], text='* made-up note', id='n')]))
        return dict(angle=angle, frame=[100, 100, 400, 192], lines=lines,
                    graphics=[dict(kind='rule', box=[100, 172, 400, 173])])

    def test_turned_part_reads_its_notes_as_upright(self):
        up, _ = c.te3_table_notes(self.source(0))
        tu, _ = c.te3_table_notes(self.source(90))
        self.assertEqual([l['text'] for l in up], ['* made-up note'])
        self.assertEqual([l['text'] for l in tu], [l['text'] for l in up])

    def test_doubt_box_of_a_turned_part_is_a_page_box(self):
        s = self.source(90)
        self.assertEqual(c.r8_page_box(s), c.frame_box_back(90)(s['frame']))
        self.assertEqual(c.r8_page_box(self.source(0)), [100, 100, 400, 192])


def oline(y, cells, k=150 / 72, ch=5.0):
    """a printed line for the overlay: cells [(x_pt, text)], each word its own item"""
    items = []
    for x, text in cells:
        x = x * k
        for w in text.split():
            b = [x, y * k, x + ch * k * len(w), (y + 8) * k]
            items.append((b, w, dict(id='%d:%d:%s' % (x, y, w), text=w, angle=0, box_px=b)))
            x += ch * k * (len(w) + 1)
    return dict(items=items, top=y * k, bot=(y + 8) * k, vc=(y + 4) * k, h=8 * k)


class WrappedLineTG12(unittest.TestCase):
    """send-back of lane r8-turned (AX10 p16): a lower line whose groups each go on the cell above in their column (a
    bracketed number under a name, a lower-case word under a sentence) is a continuation; with a mark for a new row the
    boundary is undecided and the part is not printed from the overlay"""
    def grid(self, second):
        k = 150 / 72
        lines = [oline(100, [(50, 'Author'), (180, 'Country'), (260, 'Year'), (320, 'Test result')]),
                 oline(112, [(50, 'Brun and Hunziker'), (180, 'Switzerland'), (260, '1980'), (320, 'Patch tests with metal')]),
                 oline(124, second),
                 oline(136, [(50, 'Peters et al. (172)'), (180, 'USA'), (260, '1984'), (320, 'Positive patch test')]),
                 oline(148, [(50, 'Abdallah et al. (173)'), (180, 'USA'), (260, '1994'), (320, 'Positive patch test')])]
        ov = c.overlay_module(); fit = ov.fit(lines, [], k)
        return c.overlay_grid(fit, lines, {0}, [], k)

    def test_bracket_and_lower_case_under_a_row_is_not_a_new_row(self):
        g = self.grid([(50, '(171)'), (320, 'negative')])
        d = g['cellrows'][0]
        self.assertNotEqual(d['decision'], 'new')   # a continuation, or undecided where a new-row mark stands too
        self.assertTrue(any(m.startswith('continues') for m in d['marks']))
        if d['decision'] is None: self.assertFalse(g['decided'])
        else: self.assertEqual(len([r for r in g['rows'] if not r['header']]), 3)   # the wrapped line stays in its row

    def test_a_row_with_its_own_values_stays_a_row(self):
        g = self.grid([(50, 'Clark et al. (171)'), (180, 'France'), (260, '1990'), (320, 'Negative test')])
        self.assertEqual(g['cellrows'][0]['decision'], 'new')


class CaptionedGridCheck(unittest.TestCase):
    def test_overlay_cell_rows_of_a_source(self):
        # five printed lines with values in two columns; from the third line on, each first-column label would have
        # fitted after the one above (the first label is the column's widest): the overlay starts a cell row there in
        # two columns (four cell rows in all); a grid of two rows joins lines it parts
        lines = []
        for k, y in enumerate((100, 118, 136, 154, 172)):
            lines.append(dict(text='x', items=[dict(box=[100, y, 150 if k == 0 else 120, y + 12], text='Name%d' % k, id='a%d' % k),
                                               dict(box=[300, y, 330, y + 12], text='%d.5' % k, id='b%d' % k)]))
        src = dict(angle=90, frame=[100, 100, 330, 184], lines=lines, graphics=[])
        fit = c.r8_source_fit(src, dict(params=dict(dpi=150)))
        self.assertEqual(fit['counts']['cell_rows'], 4)
        self.assertIsNone(c.r8_source_fit(dict(src, lines=lines[:1]), {}))


class TurnedView(unittest.TestCase):
    def test_upright_page_untouched(self):
        p = upright_table_page()
        before = copy.deepcopy(p); objs = [id(x) for x in p['tables'] + p['blocks'] + p['floats']]
        self.assertEqual(c.r8_turned_angles(p), [])
        c.r8_turned_rule(p, BODY, c.table_top_bound)
        self.assertEqual(p, before)
        self.assertEqual([id(x) for x in p['tables'] + p['blocks'] + p['floats']], objs)

    def test_view_round_trip_keeps_unchanged_objects(self):
        p = turned(upright_table_page(), 90)
        objs = [id(x) for x in p['tables'] + p['blocks'] + p['floats']]
        before = copy.deepcopy(p)
        v, origin = c.r8_turned_view(p, 90)
        c.r8_turned_back(p, v, 90, origin)
        self.assertEqual(p, before)
        self.assertEqual([id(x) for x in p['tables'] + p['blocks'] + p['floats']], objs)

    def test_view_reads_turned_runs_upright_and_upright_runs_turned(self):
        p = turned(upright_table_page(), 90)
        p['elements'].append(run(500, 20, 20, 'Running head', angle=0))
        v, _ = c.r8_turned_view(p, 90)
        ang = {e['id']: round(e['angle']) % 360 for e in v['elements'] if e['kind'] == 'text'}
        self.assertEqual(ang['run:3'], 0)
        self.assertEqual(ang['run:500'], 270)   # an upright leftover keeps its own frame: the rules skip it
        self.assertEqual(v['main_text']['columns'], [])

    def check_same_as_upright(self, angle):
        up = upright_table_page()
        c.table_top_bound(up, BODY)
        self.assertEqual(sorted(up['tables'][0]['members'])[:3], ['run:10', 'run:11', 'run:12'])
        self.assertIn('run:3', up['tables'][0]['members'])   # TE1 takes the header line in (upright, as BASE)
        tp = turned(upright_table_page(), angle)
        c.table_top_bound(tp, BODY)   # BASE: a turned part is skipped
        self.assertNotIn('run:3', tp['tables'][0]['members'])
        c.r8_turned_rule(tp, BODY, c.table_top_bound)
        self.assertEqual(sorted(tp['tables'][0]['members']), sorted(up['tables'][0]['members']))
        self.assertEqual(tp['tables'][0]['angle'], angle)
        self.assertEqual(tp['tables'][0]['box_px'], c.frame_box_back(angle)(up['tables'][0]['box_px']))
        # the header runs left their body block, in page coordinates
        b2 = next(b for b in tp['blocks'] if b['id'] == 'b2')
        self.assertEqual(b2['members'], [])

    def test_top_bound_turned_90(self):
        self.check_same_as_upright(90)

    def test_top_bound_turned_270(self):
        self.check_same_as_upright(270)

    def test_labelled_part_not_run_on_a_turned_float_page(self):
        # most text at the turn: F18 gives the page's turned label to the turned float, so TF7's labelled part (a label
        # BASE prints as body) has no label there; the rule is not called in the turned frame
        p = turned(upright_table_page(), 90)
        p['elements'].append(run(600, 700, 100, 'A made-up note line set at the turn under the table, ' * 4, angle=90))
        self.assertEqual(c.turned_page_angle(p), 90)
        called = []
        saved = c.r8_labelled_part
        try:
            c.r8_labelled_part = lambda v, body: called.append(v)
            c.r8_turned_rule(p, BODY, c.r8_labelled_part)
            self.assertEqual(called, [])
            c.r8_turned_rule(p, BODY, lambda v, body: called.append(v))   # any other rule runs in the turned frame
            self.assertEqual(len(called), 1)
        finally:
            c.r8_labelled_part = saved

    def test_doubt_places_map_to_the_page(self):
        class L(list):
            def add(self, rule, page, box, reason): self.append(dict(rule=rule, page=page, box=box, reason=reason))
            def items(self): return list(self)
        found = L(); saved = c.doubt_list
        c.doubt_list = lambda: found
        try:
            c._R8_VIEW_BACK[0] = c.frame_box_back(90)
            c.edges_doubt(4, [10, 20, 30, 40], 'x')
        finally:
            c._R8_VIEW_BACK[0] = None; c.doubt_list = saved
        self.assertEqual(found[0]['box'], [round(float(v), 1) for v in c.frame_box_back(90)([10, 20, 30, 40])])


if __name__ == '__main__':
    unittest.main()
