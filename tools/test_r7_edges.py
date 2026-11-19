"""Round 7 lane r7-edges: rules TE2/TE6 (body look under the lowest rule), TE5 (gutter), TE3 (notes), TE10 (doubt).
Synthetic pages only; no corpus strings or IDs."""
import importlib.util, unittest
from pathlib import Path
spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1] / 'copy_paper.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)

BODY = 20.0


def run(t, x, y, w, size=BODY, rid=None):
    return dict(id=rid or f'{x}:{y}', kind='text', text=t, box_px=[x, y, x + w, y + size], angle=0, line=y,
                char_ids=[], run_size_px=size)


def rule(x0, x1, y):
    return dict(id=f'rule:{x0}:{y}', kind='rule', box_px=[x0, y, x1, y + 1])


def page(table_runs, other, rules, columns, caption='Table 1. Values'):
    cap = run(caption, columns[0][0], 40, 200, rid='cap')
    els = [cap] + table_runs + other + rules
    t = dict(id='t1', angle=0, members=[e['id'] for e in table_runs], box_px=c.hull(e['box_px'] for e in table_runs))
    return dict(page=3, elements=els, tables=[t], blocks=[dict(id='capb', members=['cap'], box_px=cap['box_px'])],
                floats=[dict(caption=caption, blocks=['capb', 't1'], box_px=c.hull([cap['box_px'], t['box_px']]))],
                region_box_px=[0, 0, 1000, 1400], main_text=dict(columns=columns, blocks=[]))


def cells(x0, y0, n, size=16.0):
    return [r for i in range(n) for r in (run('Label' + str(i), x0, y0 + 24 * i, 60, size, rid=f'a{i}'),
                                          run(str(10 + i) + '.5', x0 + 300, y0 + 24 * i, 30, size, rid=f'b{i}'))]


def prose(x0, y0, n, width=400, indent=0, prefix='p'):
    return [run('word ' * 12, x0 + (indent if i == 0 else 0), y0 + 25 * i, width - (indent if i == 0 else 0), rid=f'{prefix}{i}')
            for i in range(n)]


class BodyLook(unittest.TestCase):
    def setUp(self):
        c.doubt_list().reset()

    def test_body_rows_under_the_lowest_rule_leave_the_table(self):
        tab = cells(100, 100, 4)
        body = prose(100, 260, 4, indent=30)
        p = page(tab + body, [], [rule(100, 500, 90), rule(100, 500, 200)], [(100, 500), (540, 940)])
        c.table_body_look_bound(p, BODY)
        self.assertEqual(set(p['tables'][0]['members']), {e['id'] for e in tab})
        self.assertEqual(set(p['_copy_body_members']), {e['id'] for e in body})
        self.assertEqual(c.doubt_list().items(), [])

    def test_a_note_under_the_rule_stays_and_a_heading_goes_with_the_body(self):
        tab = cells(100, 100, 4)
        note = [run('* Note on the values', 100, 210, 300, 16.0, rid='n0')]
        head = [run('Next section', 100, 250, 160, 24.0, rid='h0')]
        body = prose(100, 290, 3)
        p = page(tab + note + head + body, [], [rule(100, 500, 90), rule(100, 500, 200)], [(100, 500), (540, 940)])
        c.table_body_look_bound(p, BODY)
        self.assertEqual(set(p['tables'][0]['members']), {e['id'] for e in tab + note})
        sizes = {b['id']: b['size_px'] for b in p['main_text']['blocks']}
        self.assertTrue(any(v == 24.0 for v in sizes.values()))   # the heading is a block of its own size

    def test_no_drawn_mark_no_change(self):
        tab = cells(100, 100, 4)
        body = prose(100, 260, 4)
        p = page(tab + body, [], [], [(100, 500), (540, 940)])
        c.table_body_look_bound(p, BODY)
        self.assertEqual(len(p['tables'][0]['members']), len(tab + body))

    def test_negative_cells_in_body_size_on_the_column_edge_stay(self):
        # the nearest look-alike: a stub column set in the body size on the column edge, under a header rule
        tab = [r for i in range(6) for r in (run('Item' + str(i), 100, 100 + 25 * i, 60, rid=f'a{i}'),
                                             run('value', 380, 100 + 25 * i, 60, rid=f'b{i}'))]
        p = page(tab, [], [rule(100, 500, 90), rule(100, 500, 95)], [(100, 500), (540, 940)])
        c.table_body_look_bound(p, BODY)
        self.assertEqual(len(p['tables'][0]['members']), len(tab))

    def test_marks_disagree_keeps_the_table_and_lists_the_place(self):
        tab = cells(100, 100, 4)
        body = prose(100, 260, 5)
        body[4]['text'] = 'Total 12.5 13.5 14.5'   # a label with values among the released rows: the marks disagree
        p = page(tab + body, [], [rule(100, 500, 90), rule(100, 500, 200)], [(100, 500), (540, 940)])
        c.table_body_look_bound(p, BODY)
        self.assertEqual(len(p['tables'][0]['members']), len(tab + body))
        self.assertEqual([d['rule'] for d in c.doubt_list().items()], ['TE10'])


class Gutter(unittest.TestCase):
    def setUp(self):
        c.doubt_list().reset()

    def test_body_column_beside_a_one_column_table_leaves_it(self):
        tab = cells(540, 100, 5)
        tab = [dict(e, box_px=[e['box_px'][0], e['box_px'][1], min(e['box_px'][2], 930), e['box_px'][3]]) for e in tab]
        beside = prose(100, 100, 5, width=400, prefix='s')
        p = page(tab + beside, [], [rule(540, 930, 90), rule(540, 930, 220)], [(100, 500), (540, 940)])
        c.table_gutter_bound(p, BODY)
        self.assertEqual(set(p['tables'][0]['members']), {e['id'] for e in tab})

    def test_negative_page_wide_rules_keep_both_columns(self):
        tab = cells(100, 100, 5) + cells(540, 100, 5)
        for i, e in enumerate(tab): e['id'] = 'c' + str(i)
        p = page(tab, [], [rule(100, 930, 90), rule(100, 930, 220)], [(100, 500), (540, 940)])
        c.table_gutter_bound(p, BODY)
        self.assertEqual(len(p['tables'][0]['members']), len(tab))


class Notes(unittest.TestCase):
    def lines(self, rows):
        return [dict(text=t, items=[dict(box=list(b), text=t, id=str(i))]) for i, (t, b) in enumerate(rows)]

    def test_note_lines_under_the_lowest_rule(self):
        src = dict(frame=[0, 0, 400, 140], graphics=[dict(kind='rule', box=[0, -5, 400, -4]), dict(kind='rule', box=[0, 75, 400, 76])],
                   lines=self.lines([('Head', [0, 0, 100, 10]), ('Alpha 1', [0, 20, 100, 30]), ('Beta 2', [0, 40, 100, 50]),
                                     ('Gamma 3', [0, 60, 100, 70]), ('* Note one', [0, 85, 300, 95]), ('goes on', [0, 100, 200, 110])]))
        notes, doubt = c.te3_table_notes(src)
        self.assertEqual([l['text'] for l in notes], ['* Note one', 'goes on'])
        self.assertFalse(doubt)

    def test_negative_a_row_with_cells_under_the_mark_is_a_doubt(self):
        src = dict(frame=[0, 0, 400, 140], graphics=[dict(kind='rule', box=[0, 75, 400, 76])],
                   lines=[dict(text='Head', items=[dict(box=[0, 0, 100, 10], text='Head', id='h')]),
                          dict(text='Alpha 1', items=[dict(box=[0, 20, 100, 30], text='Alpha 1', id='a')]),
                          dict(text='Beta 2', items=[dict(box=[0, 40, 100, 50], text='Beta 2', id='b')]),
                          dict(text='* x', items=[dict(box=[0, 85, 20, 95], text='*', id='m')]),
                          dict(text='Gamma 3 4', items=[dict(box=[0, 100, 50, 110], text='Gamma', id='g'),
                                                        dict(box=[200, 100, 250, 110], text='3 4', id='g2')])])
        notes, doubt = c.te3_table_notes(src)
        self.assertEqual(notes, [])
        self.assertTrue(doubt)

    def test_grid_rows_made_of_the_note_lines_leave_the_grid(self):
        src = dict(frame=[0, 0, 400, 140], graphics=[dict(kind='rule', box=[0, 75, 400, 76])],
                   lines=self.lines([('Head', [0, 0, 100, 10]), ('Alpha 1', [0, 20, 100, 30]), ('Beta 2', [0, 40, 100, 50]),
                                     ('Gamma 3', [0, 60, 100, 70]), ('* Note one two', [0, 85, 300, 95])]))
        rows = [[['Head'], []], [['Alpha'], ['1']], [['Beta'], ['2']], [['Gamma'], ['3']], [['* Note'], ['one two']]]
        r, notes, ev, doubt = c.te3_grid_notes(rows, src, [])
        self.assertEqual(len(r), 4); self.assertEqual(notes, ['* Note one two']); self.assertFalse(doubt)
        # the note already printed as a note: nothing moves, no doubt
        self.assertEqual(c.te3_grid_notes(rows[:4], src, ['* Note one two'])[2:], (None, False))
        # a bottom row holding other words: the grid stays, the place is a doubt
        rows2 = rows[:4] + [[['* Note'], ['one three']]]
        r2, notes2, ev2, doubt2 = c.te3_grid_notes(rows2, src, [])
        self.assertEqual(r2, rows2); self.assertTrue(doubt2)

    def test_no_rule_no_notes(self):
        src = dict(frame=[0, 0, 400, 140], graphics=[],
                   lines=self.lines([('Head', [0, 0, 100, 10]), ('Alpha 1', [0, 20, 100, 30]), ('* Note', [0, 40, 100, 50])]))
        self.assertEqual(c.te3_table_notes(src), ([], False))



class SendBack(unittest.TestCase):
    def setUp(self):
        c.doubt_list().reset()

    def test_released_heading_by_type_shape_and_white(self):
        p = dict(_body_face='Body-Regular')
        head = [dict(run('Results of the survey', 100, 300, 200, 24.0), _faces={'Body-Regular': 18})]
        self.assertEqual(c.released_heading_row(head, p, BODY, 30), 'heading')
        self.assertEqual(c.released_heading_row(head, p, BODY, 2), 'doubt')
        self.assertEqual(c.released_heading_row(head, p, BODY, 2, after_heading=True), 'heading')
        bold = [dict(run('DISCUSSION', 100, 300, 120), _faces={'Body-B': 10})]
        self.assertEqual(c.released_heading_row(bold, p, BODY, 40), 'heading')
        line = [dict(run('the values were compared with the earlier readings.', 100, 300, 380), _faces={'Body-Regular': 40})]
        self.assertEqual(c.released_heading_row(line, p, BODY, 40), '')

    def fill(self, x0, y0, x1, y1):
        return dict(id=f'fill:{x0}:{y0}', kind='fill', box_px=[x0, y0, x1, y1])

    def test_te1_stub_header_in_the_header_fill_joins(self):
        tab = cells(100, 140, 5)
        stub = run('Group name', 100, 105, 80, 16.0, rid='stub')
        p = page(tab + [stub], [], [self.fill(95, 100, 455, 130)], [(100, 500), (540, 940)])
        p['tables'][0]['members'] = [e['id'] for e in tab]
        c.table_top_bound(p, BODY)
        self.assertIn('stub', p['tables'][0]['members'])

    def test_te8_rows_under_the_part_inside_the_fills_join(self):
        tab = cells(100, 100, 4)
        more = [r for i in range(2) for r in (run('Label' + str(9 + i), 100, 196 + 24 * i, 60, 16.0, rid=f'm{i}'),
                                              run('7.5', 400, 196 + 24 * i, 30, 16.0, rid=f'n{i}'))]
        p = page(tab + more, [], [self.fill(95, 95, 500, 250)], [(100, 500), (540, 940)])
        p['tables'][0]['members'] = [e['id'] for e in tab]
        p['tables'][0]['box_px'] = c.hull(e['box_px'] for e in tab)
        p['floats'][0]['box_px'] = c.hull([p['elements'][0]['box_px'], p['tables'][0]['box_px']])
        c.table_drawn_growth(p, BODY)
        self.assertTrue({'m0', 'n1'} <= set(p['tables'][0]['members']))

    def test_te8_negative_body_lines_inside_the_reach_are_a_doubt(self):
        tab = cells(100, 100, 4)
        body = prose(100, 200, 3, prefix='q')
        p = page(tab + body, [], [self.fill(95, 95, 500, 290)], [(100, 500), (540, 940)])
        p['tables'][0]['members'] = [e['id'] for e in tab]
        p['tables'][0]['box_px'] = c.hull(e['box_px'] for e in tab)
        p['floats'][0]['box_px'] = c.hull([p['elements'][0]['box_px'], p['tables'][0]['box_px']])
        c.table_drawn_growth(p, BODY)
        self.assertEqual(set(p['tables'][0]['members']), {e['id'] for e in tab})
        self.assertEqual([d['rule'] for d in c.doubt_list().items()], ['TE10'])

if __name__ == '__main__':
    unittest.main()
