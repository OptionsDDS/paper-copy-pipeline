"""Lane r3-labelrows: in a table structured by row strips at one pitch (label-only rows one full-width strip,
data rows two strips split at the value column) with hierarchy shown by indent, a label-only line one body row
pitch below the line above it, starting at a body indent level and indented from that line or set in a face it
does not use, opens the body: the header band never takes it, whatever the strips do. A label wrapped at the
line pitch and a units line under a header label stay in their cell. Fixtures are synthetic; no paper text."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('tablesub',Path(__file__).with_name('test_tablesub.py'))
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
c,run,page,grid,rule=t.c,t.run,t.page,t.grid,t.rule


def strip(y0,y1,x0=0,x1=320):
    return dict(kind='fill',box_px=[x0,y0,x1,y1])


def lab(text,x,y,face='Sans'):
    r=run(text,x,y,6*len(text)); r['_faces']={face:len(text)}; return r


P=20; V=230; SPLIT=220


def strips(rows, shade=lambda k,grp,label_only: ('full' if label_only else 'split') if grp%2==0 else None, y=0):
    """rows: (indent, label, value or None, face, group); one row per pitch, text centred in its strip."""
    rs=[];gr=[]
    for k,(ind,text,val,face,grp) in enumerate(rows):
        rs.append(lab(text,5+ind,y+5,face))
        if val: rs.append(run(val,V,y+5,60))
        mode=shade(k,grp,val is None)
        if mode=='full': gr.append(strip(y,y+P))
        elif mode=='split': gr+=[strip(y,y+P,0,SPLIT),strip(y,y+P,SPLIT,320)]
        y+=P
    return rs,gr,y


THREE=[(0,'Group one (n = 40)',None,'Sans',0),(10,'First kind',None,'Sans',0),(20,'aa','12 (30.0)','Sans',0),
       (20,'bb','28 (70.0)','Sans',0),(10,'Second kind',None,'Sans',1),(20,'cc','9 (22.5)','Sans',1),
       (20,'dd','31 (77.5)','Sans',1),(10,'Third kind',None,'Sans',2),(20,'ee','20 (50.0)','Sans',2),
       (20,'ff','20 (50.0)','Sans',2)]


def rows_of(rs,gr,angle=0):
    p=page(rs+gr)
    if angle:
        p=copy.deepcopy(p)
        for e in p['elements']:
            e['box_px']=c.frame(-angle)(e['box_px'])
            if e['kind']=='text': e['angle']=angle
        rs=[e for e in p['elements'] if e['kind']=='text']
    return grid(c.table_rows(rs,10,p)[0])


class LabelOnlyRows(unittest.TestCase):
    def test_an_indented_label_row_under_the_first_label_row_is_a_row_of_its_own(self):
        rs,gr,_=strips(THREE)
        g=rows_of(rs,gr)
        self.assertEqual(g[0],['Group one (n = 40)',''])
        self.assertEqual(g[1],['First kind',''])
        self.assertEqual(g[2],['aa','12 (30.0)'])
        self.assertIn(['Second kind',''],g)

    def test_a_single_nested_group_at_one_or_two_em_is_a_row_of_its_own(self):
        # the subheading's indent occurs nowhere else in the body: the indent under a label-only line suffices
        for step in (10,20):
            rows=[(0,'Group one (n = 40)',None,'Sans',0),(step,'First kind',None,'Sans',0),(step+10,'Third level',None,'Sans',0),
                  (step+20,'aa','12 (30.0)','Sans',0),(step+20,'bb','28 (70.0)','Sans',0),(0,'cc','9 (22.5)','Sans',1),
                  (0,'dd','31 (77.5)','Sans',1)]
            g=rows_of(*strips(rows)[:2])
            self.assertEqual(g[:2],[['Group one (n = 40)',''],['First kind','']],step)
            self.assertIn(['Third level',''],g)

    def test_a_single_subgroup_in_another_face_at_the_same_edge_is_a_row_of_its_own(self):
        # italic under regular, regular under bold; the face occurs nowhere else in the body
        for top,sub in (('Sans','Sans-Italic'),('Sans-Bold','Sans')):
            rows=[(0,'Group one (n = 40)',None,top,0),(0,'First kind',None,sub,0),(10,'aa','12 (30.0)','Sans',0),
                  (10,'bb','28 (70.0)','Sans',0),(0,'cc','9 (22.5)','Sans',1),(0,'dd','31 (77.5)','Sans',1)]
            g=rows_of(*strips(rows)[:2])
            self.assertEqual(g[:3],[['Group one (n = 40)',''],['First kind',''],['aa','12 (30.0)']],(top,sub))
            g=rows_of(*unshaded(rows))
            self.assertEqual(g[:3],[['Group one (n = 40)',''],['First kind',''],['aa','12 (30.0)']],('unshaded',top,sub))

    def test_the_rule_holds_at_every_angle(self):
        rs,gr,_=strips(THREE)
        for angle in (90,270):
            g=rows_of(copy.deepcopy(rs),copy.deepcopy(gr),angle)
            self.assertEqual(g[:3],[['Group one (n = 40)',''],['First kind',''],['aa','12 (30.0)']],angle)

    def test_whatever_the_strips_do(self):
        # the second row shaded as a split strip, or not shaded at all
        for mode in ('split',None):
            rs,gr,_=strips(THREE,shade=lambda k,grp,l,mode=mode: mode if k==1 else ('full' if l else 'split') if grp%2==0 else None)
            g=rows_of(rs,gr)
            self.assertEqual(g[:3],[['Group one (n = 40)',''],['First kind',''],['aa','12 (30.0)']],mode)

    def test_a_subgroup_row_in_another_face_at_the_same_indent_is_a_row_of_its_own(self):
        rows=[(0,'Group one (n = 40)',None,'Sans',0),(0,'First kind',None,'Sans-Italic',0),(10,'aa','12 (30.0)','Sans',0),
              (10,'bb','28 (70.0)','Sans',0),(0,'Second kind',None,'Sans-Italic',1),(10,'cc','9 (22.5)','Sans',1),
              (10,'dd','31 (77.5)','Sans',1),(0,'Third kind',None,'Sans-Italic',2),(10,'ee','20 (50.0)','Sans',2)]
        g=rows_of(*strips(rows)[:2])
        self.assertEqual(g[:3],[['Group one (n = 40)',''],['First kind',''],['aa','12 (30.0)']])

    def test_a_label_only_row_directly_under_a_bold_header_row_opens_the_body(self):
        rs=[lab('Heading',5,5,'Sans-Bold'),run('n (%)',V,5,30)];rs[1]['_faces']={'Sans-Bold':5}
        gr=[strip(0,P)]
        more,gr2,_=strips([(0,'First kind',None,'Sans',0),(10,'aa','12 (30.0)','Sans',0),(10,'bb','28 (70.0)','Sans',0),
                           (0,'Second kind',None,'Sans',1),(10,'cc','9 (22.5)','Sans',1),(10,'dd','31 (77.5)','Sans',1),
                           (0,'Third kind',None,'Sans',2),(10,'ee','20 (50.0)','Sans',2)],y=P)
        g=rows_of(rs+more,gr+gr2)
        self.assertEqual(g[:3],[['Heading','n (%)'],['First kind',''],['aa','12 (30.0)']])


def unshaded(rows):
    rs,gr,y=strips(rows,shade=lambda k,g,l:None)
    return rs,[rule(-2),rule(y)]


class UnshadedLabelRows(unittest.TestCase):
    def test_a_single_nested_group_without_strips_is_a_row_of_its_own(self):
        for step in (10,20):
            rows=[(0,'Group one (n = 40)',None,'Sans',0),(step,'First kind',None,'Sans',0),(step+10,'aa','12 (30.0)','Sans',0),
                  (step+10,'bb','28 (70.0)','Sans',0),(0,'cc','9 (22.5)','Sans',1),(0,'dd','31 (77.5)','Sans',1)]
            g=rows_of(*unshaded(rows))
            self.assertEqual(g[:3],[['Group one (n = 40)',''],['First kind',''],['aa','12 (30.0)']],step)

    def test_a_long_label_hung_onto_a_second_line_stays_one_cell(self):
        # the line above runs up to the value column: the next word could not have fitted there
        rows=[(0,'Group one treated by staged care',None,'Sans',0),(10,'with delay',None,'Sans',0),(20,'aa','12 (30.0)','Sans',0),
              (20,'bb','28 (70.0)','Sans',0),(0,'cc','9 (22.5)','Sans',1),(0,'dd','31 (77.5)','Sans',1)]
        g=rows_of(*unshaded(rows))
        self.assertEqual(g[0],['Group one treated by staged care with delay',''])


class StaysOneCell(unittest.TestCase):
    def test_a_label_wrapped_at_the_line_pitch_inside_one_strip_stays_one_cell(self):
        rs=[lab('Group one treated by the staged',5,5),lab('approach (n = 40)',15,17)]
        gr=[strip(0,P+12)]
        more,gr2,_=strips(THREE[2:],y=P+12)
        g=rows_of(rs+more,gr+gr2)
        self.assertEqual(g[0],['Group one treated by the staged approach (n = 40)',''])
        self.assertEqual(g[1],['aa','12 (30.0)'])

    def test_an_italic_qualifier_line_under_a_label_stays_with_the_label(self):
        # "(mean (SD))" set in italic under the label, at the row pitch in its own strip or at the line step
        for step,own_strip in ((P,True),(12,False)):
            rs=[lab('Group one (n = 40)',5,5),lab('(mean (SD))',15,5+step,'Sans-Italic')]
            gr=[strip(0,P),strip(P,2*P)] if own_strip else [strip(0,P+12)]
            more,gr2,_=strips([(10,'aa','4.1 (1.2)','Sans',0),(10,'bb','6.8 (1.9)','Sans',0),(0,'cc','8.2 (2.0)','Sans',1),
                               (0,'dd','1.3 (0.6)','Sans',1)],y=2*P if own_strip else P+12)
            g=rows_of(rs+more,gr+gr2)
            self.assertEqual(g[0],['Group one (n = 40) (mean (SD))',''],step)

    def test_a_units_line_under_the_header_label_stays_in_the_header(self):
        rs=[lab('Measure',5,5,'Sans-Bold'),run('Value',V,5,30),lab('(mm)',15,17,'Sans-Bold')]
        rs[1]['_faces']={'Sans-Bold':5}
        gr=[strip(0,P+12)]
        more,gr2,_=strips([(0,'aa','4.1 (1.2)','Sans',1),(0,'bb','6.8 (1.9)','Sans',1),(0,'cc','8.2 (2.0)','Sans',2),
                           (0,'dd','1.3 (0.6)','Sans',2),(0,'ee','1.9 (0.7)','Sans',3)],y=P+12)
        g=rows_of(rs+more,gr+gr2)
        self.assertEqual(g[0],['Measure (mm)','Value'])
        self.assertEqual(g[1],['aa','4.1 (1.2)'])

    def test_a_wrapped_header_line_at_the_body_line_pitch_stays_in_the_header(self):
        # a dense table of wrapped cells: the body's common step is the line step, which the wrapped
        # (centred) second line of the label header shares; no white beyond a line's leading sets it
        # apart, so it is no body row even though it starts at the body labels' indent
        rs=[lab('Medium (first',5,0,'Sans-Bold'),lab('Assay',170,0,'Sans-Bold'),lab('Size',250,0,'Sans-Bold'),
            lab('vs. second)',15,10,'Sans-Bold')]
        gr=[rule(-4,0,320),rule(22,0,320),strip(-4,22)]
        y=26
        for k in ('fluid aa','fluid bb','fluid cc','fluid dd'):
            rs+=[lab(k,15,y),lab('plate',170,y),run('3.1',250,y,18),lab('one',15,y+10),lab('bead',170,y+10)]
            y+=24
        gr.append(rule(y,0,320))
        g=rows_of(rs,gr)
        self.assertEqual(g[0][0],'Medium (first vs. second)',g)

    def test_a_second_label_row_at_the_same_indent_and_face_is_left_to_the_strips(self):
        # neither indented nor in another face: this rule does not speak
        rows=[(0,'Group one (n = 40)',None,'Sans',0),(0,'First kind',None,'Sans',0)]+THREE[2:]
        a=rows_of(*strips(rows)[:2])
        self.assertEqual(a[0],['Group one (n = 40) First kind',''])


def studies(sub_x=12, sub_step=17, sub_face='Sans', wrapped_heading=False):
    """Authors (year) | Design | Result: citations wrap over two lines (12 apart); a group heading flush left,
    then an indented comparison label one row step under it, then the studies (indented further).
    wrapped_heading: the heading instead wraps onto a hanging-indented second line at the line step."""
    rs=[lab('Authors (year)',5,0,'Sans-Bold'),run('Design',130,0,36),run('Result',220,0,36)]
    gr=[rule(-4,0,320),rule(12,0,320)]
    y=18
    def study(name,year,design,result):
        nonlocal y
        rs.extend([lab(name,20,y),run(design,130,y,60),run(result,220,y,80),lab(year,20,y+12),run('12 months',130,y+12,54)])
        y+=40
    study('Aa et al.','(2010)1','RCT','Gain 2.1')
    study('Bb et al.','(2012)2','RCT','Gain 1.7')
    rs.append(lab('Group two: membrane',5,y)); 
    if wrapped_heading: rs.append(lab('and the graft',12,y+12)); y+=38
    else: rs.append(lab('(3) First vs. second',sub_x,y+sub_step,sub_face)); y+=sub_step+26
    study('Cc et al.','(2014)3','RCT','Gain 2.4')
    study('Dd et al.','(2016)4','CCT','Gain 0.9')
    study('Ee et al.','(2018)5','RCT','Gain 1.1')
    gr.append(rule(y,0,320))
    return rs,gr


class StudyGroupRows(unittest.TestCase):
    def test_a_group_heading_and_its_indented_subheading_are_two_rows(self):
        g=rows_of(*studies())
        self.assertIn(['Group two: membrane','',''],g)
        self.assertIn(['(3) First vs. second','',''],g)
        self.assertIn(['Cc et al. (2014)3','RCT 12 months','Gain 2.4'],g)

    def test_a_subheading_in_another_face_is_a_row_of_its_own(self):
        g=rows_of(*studies(sub_x=5,sub_face='Sans-Italic'))
        self.assertIn(['(3) First vs. second','',''],g)

    def test_a_heading_over_its_indented_subheading_is_no_study_continuation(self):
        rs,gr=studies(); p=page(rs+gr)
        rows,notes=c.table_rows(rs,10,p)
        checks=c.table_structure_checks(rows,c.table_source(rs,p),'Table 1. Studies',notes)
        self.assertFalse(checks['study_row_ownership']['fired'],checks['study_row_ownership'])

    def test_a_heading_wrapped_at_the_line_step_stays_one_cell(self):
        g=rows_of(*studies(wrapped_heading=True))
        self.assertIn(['Group two: membrane and the graft','',''],g)


if __name__=='__main__':
    unittest.main()
