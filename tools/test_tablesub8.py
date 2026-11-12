"""Lane tablesub, re-ladder round 3 (tablesub8): a group line and its sub-group line in a drawn band stay two
rows while a label that wrapped for lack of room still joins; a wrapped label beside values set on its first
line stays whole in a value matrix while a group label after a gap stays a row; title lines under a label that
stands alone are the caption's, not header cells; a shaded header band over a ruled body holds one header per
column when its words stand clear of the body's walls. Fixtures are synthetic; no paper text."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('tablesub',Path(__file__).with_name('test_tablesub.py'))
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
c,run,page,grid,rule,fill=t.c,t.run,t.page,t.grid,t.rule,t.fill


def banded(sub,sub_width,first,first_width):
    """Name | Arm A | Arm B: a drawn band opening with two label-only lines, then indented entries."""
    rs=[run('Name',5,0,24),run('Arm A',150,0,30),run('Arm B',230,0,30)]
    gr=[rule(-4,0,320),rule(12,0,320)]
    rs+=[run(first,5,26,first_width),run(sub,5,38,sub_width)]
    for i,(n,a,b) in enumerate([('Upper molar','12','14'),('Lower molar','9','11'),('Upper incisor','20','18')]):
        y=50+12*i
        rs+=[run(n,15,y,66),run(a,150,y,12),run(b,230,y,12)]
    gr.append(fill(24,86,320))
    rs+=[run('Second group',5,90,72),run('Lower incisor',15,102,78),run('7',150,102,6),run('8',230,102,6)]
    gr+=[fill(88,114,320),rule(116,0,320)]
    return rs,gr


class GroupLines(unittest.TestCase):
    def test_a_group_line_and_its_sub_group_line_stay_two_rows(self):
        rs,gr=banded('Nil',18,'Graft material',84)
        g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        firsts=[r[0] for r in g]
        self.assertIn('Graft material',firsts); self.assertIn('Nil',firsts)
        self.assertNotIn('Graft material Nil',firsts)

    def test_a_label_that_wrapped_for_lack_of_room_still_joins(self):
        # the first line runs to the next column's text: the second line is its tail
        rs,gr=banded('tail',24,'Graft material from a donor',138)
        g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertIn('Graft material from a donor tail',[r[0] for r in g])


def matrix(gap_before_group=True,label_edge=True):
    """Label | n | % : rows at a pitch of 20, one label wrapped with its values on its first line; the label
    column is a drawn (shaded) column whose right edge the wrapped label reaches."""
    rs=[run('Group',5,0,30),run('n',150,0,6),run('%',230,0,6)]
    gr=[rule(-4,0,320),rule(12,0,320)]
    y=16
    for label,a,b,tail in [('Alpha',  '120','40.0',None),('Beta region','95','31.7','eastern'),
                           ('Gamma',  '85','28.3',None)]:
        rs+=[run(label,5,y,6*len(label)),run(a,150,y,18),run(b,230,y,24)]
        if tail: rs.append(run(tail,5,y+11,6*len(tail)))
        y+=20
    y+=12 if gap_before_group else 0
    rs.append(run('Sex',5,y,18)); y+=20
    for label,a,b in [('Female','160','53.3'),('Male','140','46.7')]:
        rs+=[run(label,5,y,6*len(label)),run(a,150,y,18),run(b,230,y,24)]; y+=20
    gr.append(rule(y,0,320))
    if label_edge: gr.append(fill(14,y-1,76))
    return rs,gr


class WrappedLabels(unittest.TestCase):
    def test_a_wrapped_label_beside_values_on_its_first_line_stays_whole(self):
        rs,gr=matrix();g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertIn(['Beta region eastern','95','31.7'],g)
        self.assertNotIn('eastern',[r[0] for r in g])

    def test_a_second_line_that_would_have_fitted_stays_a_row(self):
        # no drawn label column: the first line leaves room before the next column, so the
        # second line is a label of its own (a coded category under its first code)
        rs,gr=matrix(label_edge=False);g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertNotIn('Beta region eastern',[r[0] for r in g])

    def test_a_group_label_after_a_gap_stays_a_row(self):
        rs,gr=matrix();g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertIn('Sex',[r[0] for r in g])
        self.assertIn(['Female','160','53.3'],g)


def titled(label='Table 3.',title_size=13,header_gap=False):
    lab=run(label,5,0,50); lab['run_size_px']=lab['size_px']=10
    title=[run('Invented Outcomes of Two Imaginary',5,14,240),run('Treatments in a Made-up Trial',5,30,200)]
    for e in title: e['run_size_px']=e['size_px']=title_size
    head=[run('Arm',5,52,20),run('Mean',150,52,30),run('SD',230,52,16)]
    body=[]
    for i,(a,m,s) in enumerate([('First','1.2','0.4'),('Second','1.6','0.5'),('Third','0.9','0.3')]):
        body+=[run(a,5,66+12*i,36),run(m,150,66+12*i,18),run(s,230,66+12*i,18)]
    for e in head+body: e['run_size_px']=e['size_px']=9
    if header_gap: title=[run('Invented',5,14,60),run('Outcomes',150,14,60)]; [e.update(run_size_px=13,size_px=13) for e in title]
    return lab,title,head+body


class Titles(unittest.TestCase):
    def test_title_lines_under_a_label_alone_are_the_captions(self):
        lab,title,cells=titled()
        self.assertEqual([e['id'] for e in c.table_title_runs(lab,[lab],title+cells)],[e['id'] for e in title])

    def test_a_continued_label_alone_takes_its_title_too(self):
        lab,title,cells=titled('Table 3. (continued)')
        self.assertEqual(len(c.table_title_runs(lab,[lab],title+cells)),2)

    def test_a_label_with_its_own_title_takes_no_lines(self):
        lab,title,cells=titled('Table 3. Invented outcomes')
        self.assertEqual(c.table_title_runs(lab,[lab],title+cells),[])

    def test_a_line_in_the_tables_own_size_is_no_title(self):
        lab,title,cells=titled(title_size=9)
        self.assertEqual(c.table_title_runs(lab,[lab],title+cells),[])

    def test_a_large_line_with_a_column_gap_is_no_title(self):
        lab,title,cells=titled(header_gap=True)
        self.assertEqual(c.table_title_runs(lab,[lab],title+cells),[])

    def test_the_title_rows_are_marked_and_the_rows_are_otherwise_unchanged(self):
        # the title lines are read with the table (its checks see them as before) and marked, so
        # that a written grid leaves them to the caption
        lab,title,cells=titled()
        p=page(title+cells+[rule(48,0,320),rule(62,0,320),rule(104,0,320)])
        state=dict(ids={e['id'] for e in title},dropped=False)
        marked=c.table_rows(title+cells,10,dict(p,_table_title=state))[0]
        plain=c.table_rows(title+cells,10,p)[0]
        self.assertTrue(state['dropped'])
        self.assertEqual(grid(marked),grid(plain))
        kept=grid([r for r in marked if r is None or not r.title])
        self.assertFalse(any('Invented' in cell for r in kept for cell in r))
        self.assertTrue(all(any('Invented' in cell for cell in r) for r in grid([r for r in marked if r is not None and r.title])))
        self.assertTrue(any('First' in cell for r in kept for cell in r))

    def test_a_row_mixing_title_and_table_text_keeps_the_title(self):
        lab,title,cells=titled()
        p=page(title+cells)
        state=dict(ids={title[0]['id'],cells[0]['id']},dropped=False)
        rows=c.table_rows(title+cells,10,dict(p,_table_title=state))[0]
        self.assertFalse(state['dropped'])
        self.assertFalse(any(r is not None and r.title for r in rows))


def ruled(header):
    """A shaded header band with no walls of its own over a body ruled into three columns."""
    rs=list(header)
    gr=[dict(kind='fill',box_px=[0,0,300,26]),rule(26,0,300)]
    for x in (100,200): gr.append(dict(kind='rule',box_px=[x,26,x+.5,90]))
    for i,(a,b,d) in enumerate([('Row one','4','5'),('Row two','6','7'),('Row three','8','9')]):
        y=32+20*i
        rs+=[run(a,5,y,54),run(b,140,y,6),run(d,240,y,6)]; gr.append(rule(y+16,0,300))
    gr+=[dict(kind='rule',box_px=[0,0,.5,90]),dict(kind='rule',box_px=[300,0,300.5,90])]
    return rs,gr


class HeaderBands(unittest.TestCase):
    def test_header_words_clear_of_the_walls_are_one_header_per_column(self):
        rs,gr=ruled([run('Site',20,4,24),run('Test',120,4,24),run('Control',215,4,42)])
        g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertEqual(g[0],['Site','Test','Control'])

    def test_a_header_across_a_wall_still_spans(self):
        rs,gr=ruled([run('Measured at both visits',130,4,140)])
        g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertEqual(g[0][1:],['Measured at both visits']*2)


if __name__=='__main__':
    unittest.main()
