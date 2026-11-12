"""Lane r2-divider: a body line holding one text run that starts inside the label column and runs on over the
next column's gutter, with value cells on the body lines above (or the header above) and below, is a divider row of its own (its text
is the label column's cell), never the wrapped line of the value cell its hull centre falls in; a wrapped text
cell whose second line starts in its own column still joins its cell. Fixtures are synthetic; no paper text."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('tablesub',Path(__file__).with_name('test_tablesub.py'))
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
c,run,page,grid,rule,fill=t.c,t.run,t.page,t.grid,t.rule,t.fill


def stats(divider_x=5, divider_width=150, label=True, opening=False):
    """Term | Est | SE | p with short labels; two divider lines run from the label column over the Est gutter
    (opening: a third divider opens the body, directly under the header)."""
    rs=[run('Term',5,0,24),run('Est',100,0,18),run('SE',170,0,12),run('p',250,0,6)]
    gr=[rule(-4,0,320),rule(12,0,320)]
    body=(['Opening group part'] if opening else [])+[('aa','1.25','0.11','0.02'),('bb','0.40','0.07','0.31'),'Upper group part',
          ('cc','2.10','0.15','0.01'),('dd','0.62','0.09','0.44'),'Spread parts',
          ('ee','0.83','0.20',None),('ff','0.14','0.02',None)]
    y=16
    for r in body:
        if isinstance(r,str): rs.append(run(r,divider_x,y,divider_width))
        else:
            if label: rs.append(run(r[0],5,y,12))
            rs+=[run(v,x,y,24) for v,x in zip(r[1:],(100,170,250)) if v]
        y+=12
    gr.append(rule(y,0,320))
    return rs,gr


class DividerRows(unittest.TestCase):
    def rows(self,**k):
        rs,gr=stats(**k); return grid(c.table_rows(rs,10,page(rs+gr))[0])

    def test_a_divider_over_the_value_gutter_is_a_row_of_its_own(self):
        g=self.rows()
        self.assertIn(['Upper group part','','',''],g)
        self.assertIn(['Spread parts','','',''],g)
        self.assertIn(['bb','0.40','0.07','0.31'],g)
        self.assertIn(['ee','0.83','0.20',''],g)

    def test_an_indented_divider_is_a_row_of_its_own(self):
        g=self.rows(divider_x=11)
        self.assertIn(['Upper group part','','',''],g)
        self.assertIn(['cc','2.10','0.15','0.01'],g)

    def test_a_divider_opening_the_body_is_a_row_of_its_own(self):
        g=self.rows(divider_x=11,opening=True)
        self.assertEqual(g[1],['Opening group part','','',''])
        self.assertEqual(g[2],['aa','1.25','0.11','0.02'])
        self.assertIn(['Upper group part','','',''],g)

    def test_a_short_divider_inside_the_label_column_stays_a_row(self):
        g=self.rows(divider_width=60)
        self.assertIn(['Upper group part','','',''],g)
        self.assertIn(['dd','0.62','0.09','0.44'],g)


def banded(divider='Upper group', face='Sans', size=10, step_below=12, label_face='Sans', bands=True):
    """Crew | n | Mean | p with body rows in alternate shaded bands; a label-column-only line after 'Beta'
    shares the shaded band of that row. face/size: how the line is set; step_below: its step to the next row
    (rows are 12 apart); label_face: the labels' face."""
    def lab(t,x,y,f=None,sz=10):
        r=run(t,x,y,6*len(t)); r['_faces']={(f or label_face):len(t)}; r['run_size_px']=sz; return r
    rs=[run('Crew',5,0,24),run('n',100,0,6),run('Mean',170,0,24),run('p',250,0,6)]
    gr=[rule(-4,0,320),rule(12,0,320)]
    y=16
    for k,(l,*vs) in enumerate([('Alpha boats','14','41.2','0.21'),('Beta','12','38.7','0.48')]):
        rs+=[lab(l,5,y)]+[run(v,x,y,24) for v,x in zip(vs,(100,170,250))]; y+=12
    rs.append(lab(divider,5,y,face,size)); y+=step_below
    for l,*vs in [('Gamma','9','44.0','0.09'),('Delta','7','36.1','0.62')]:
        rs+=[lab(l,5,y)]+[run(v,x,y,24) for v,x in zip(vs,(100,170,250))]; y+=12
    if bands: gr+=[fill(15,27,320),fill(16+12+12+step_below-1,16+12+12+step_below+11,320)]
    gr.append(rule(y,0,320))
    return rs,gr


class LabelColumnDividers(unittest.TestCase):
    def rows(self,**k):
        rs,gr=banded(**k); return grid(c.table_rows(rs,10,page(rs+gr))[0])

    def test_a_divider_set_smaller_than_the_labels_is_a_row_of_its_own(self):
        g=self.rows(size=8)
        self.assertIn(['Upper group','','',''],g); self.assertIn(['Beta','12','38.7','0.48'],g)
        self.assertIn(['Gamma','9','44.0','0.09'],g)

    def test_a_divider_in_capitals_is_a_row_of_its_own(self):
        g=self.rows(divider='UPPER GROUP')
        self.assertIn(['UPPER GROUP','','',''],g); self.assertIn(['Beta','12','38.7','0.48'],g)

    def test_a_divider_in_another_face_set_tight_to_the_row_below_is_a_row_of_its_own(self):
        g=self.rows(face='Sans-Bold',step_below=9)
        self.assertIn(['Upper group','','',''],g); self.assertIn(['Gamma','9','44.0','0.09'],g)

    def test_a_divider_set_like_the_labels_binding_to_the_row_below_is_a_row_of_its_own(self):
        # italic labels, italic divider: the face says nothing; the divider sits closer to the row below
        g=self.rows(face='Serif-Italic',label_face='Serif-Italic',step_below=9)
        self.assertIn(['Upper group','','',''],g); self.assertIn(['Beta','12','38.7','0.48'],g)

    def test_a_second_label_line_set_like_the_labels_at_the_row_pitch_joins_its_label(self):
        # a two-line label in one band: the second line is set like the labels, at the row pitch
        # (without bands the same line is split on BASE already: a separate fault, t4u)
        for kw in (dict(divider='Vessels'),
                   dict(divider='Vessels',face='Serif-Italic',label_face='Serif-Italic')):
            g=self.rows(**kw)
            self.assertIn(['Beta Vessels','12','38.7','0.48'],g,kw)
            self.assertNotIn(['Vessels','','',''],g,kw)

    def test_a_divider_in_capitals_after_a_wrapped_label_in_its_band(self):
        # Beta's label wraps onto a second line (no room above); a divider in capitals follows in the same band
        rs=[run('Crew',5,0,24),run('n',100,0,6),run('Mean',170,0,24),run('p',250,0,6)]
        for e in rs: e['_faces']={'Sans-Bold':4}
        gr=[rule(-4,0,320),rule(12,0,320),fill(15,27,320),fill(63,75,320),rule(88,0,320)]
        def lab(t,y,w): r=run(t,5,y,w); r['run_size_px']=10; return r
        rs+=[lab('Alpha boats',16,66)]+[run(v,x,16,24) for v,x in zip(('14','41.2','0.21'),(100,170,250))]
        rs+=[lab('Beta region of the',28,84)]+[run(v,x,28,24) for v,x in zip(('12','38.7','0.48'),(100,170,250))]
        rs+=[lab('bay',40,18),lab('UPPER GROUP',52,66)]
        rs+=[lab('Gamma',64,30)]+[run(v,x,64,24) for v,x in zip(('9','44.0','0.09'),(100,170,250))]
        rs+=[lab('Delta',76,30)]+[run(v,x,76,24) for v,x in zip(('7','36.1','0.62'),(100,170,250))]
        g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertIn(['Beta region of the bay','12','38.7','0.48'],g)
        self.assertIn(['UPPER GROUP','','',''],g)
        self.assertIn(['Gamma','9','44.0','0.09'],g)

    def test_a_line_set_like_an_opening_divider_is_a_divider_at_the_row_step(self):
        # the body opens with a divider set like the labels; a later line in the same setting and at
        # the same edge, at the full row step, is a divider too
        rs,gr=banded(divider='Lower')
        for e in rs:
            if e['box_px'][1]>=16: e['box_px'][1]+=12; e['box_px'][3]+=12
        gr=[g if g['kind']!='fill' else dict(g,box_px=[g['box_px'][0],g['box_px'][1]+12,g['box_px'][2],g['box_px'][3]+12]) for g in gr]
        op=run('Upper',5,16,30); op['_faces']={'Sans':5}; op['run_size_px']=10; rs.append(op)
        g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertEqual(g[1],['Upper','','',''])
        self.assertIn(['Lower','','',''],g); self.assertIn(['Beta','12','38.7','0.48'],g)

    def test_a_label_that_wrapped_into_the_line_below_still_joins(self):
        # the label above fills its column up to the next column's text: no room, so the line is its tail
        rs,gr=banded(divider='tail',step_below=9)
        rs=[dict(e,box_px=[e['box_px'][0],e['box_px'][1],88,e['box_px'][3]],text='Beta region of the bay') if e['text']=='Beta' else e for e in rs]
        g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertNotIn(['tail','','',''],g)
        self.assertTrue(any(r[0].startswith('Beta region of the bay') and r[0].endswith('tail') for r in g))


class WrappedTextCell(unittest.TestCase):
    def test_a_wrapped_text_cell_joins_its_cell(self):
        # Name | Description | Effect: the description's second line starts in its own column
        rs=[run('Name',5,0,24),run('Description',90,0,60),run('Effect',270,0,30)]
        gr=[rule(-4,0,320),rule(12,0,320)]
        rs+=[run('Alpha',5,16,30),run('Cut every second',90,16,96),run('0.42',270,16,24),
             run('branch in spring',90,28,96),
             run('Beta',5,40,24),run('Straw cover',90,40,66),run('0.18',270,40,24)]
        gr.append(rule(52,0,320))
        g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertIn(['Alpha','Cut every second branch in spring','0.42'],g)
        self.assertIn(['Beta','Straw cover','0.18'],g)


if __name__=='__main__':
    unittest.main()
