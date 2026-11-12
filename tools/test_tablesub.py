"""Lane tablesub: one printed row is one Markdown row (R1), every table is declared with its gate (R2),
body prose never enters a table's line list (R3); tablesub2: a spanner header stays in its table (T1), a header
row and a data row are never one band (T2), lines the grid cannot place never form a paragraph (T3), a caption
without a float region takes its aligned cell lines (T4); tablesub3: that fallback is the last resort and
its gate is complete; tablesub4: a line of a table's gate is released as body prose only when it reads as prose
outside the table's drawn structure. Fixtures are synthetic; no paper text."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('cellblocks',Path(__file__).with_name('test_cellblocks.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
c,run,fill=m.c,m.run,m.fill


def rule(y,x0=0,x1=320):
    return dict(id=f'rule:{y}',kind='rule',box_px=[x0,y,x1,y+.5])


def page(es,columns=((0,320),)):
    for i,e in enumerate(es):
        e.setdefault('id',f'{e["kind"]}:{i}')
        if e['kind']=='text':e.setdefault('run_size_px',10);e.setdefault('size_px',10)
    return dict(page=1,elements=es,tables=[],floats=[],blocks=[],art=[],region_box_px=[0,0,700,900],
                main_text=dict(blocks=[],columns=[list(cc) for cc in columns],body_size_px=10))


def grid(rows):
    return [[' '.join(cell) for cell in r] for r in rows if r is not None]


class PrintedRows(unittest.TestCase):
    """R1 in the row assembler."""

    def labelled_values(self):
        rs=[run('Test group',150,0,80),run('Control group',250,0,80)]
        for y,label,a,b in [(15,'subjects','35 (19 females)','80 (42 females)'),(30,'drop-outs','7','19'),
                            (45,'age (years)','41.2 (24–60)','42.1 (23–66)'),(60,'Plaque (%)','33','28')]:
            rs+=[run(label,5,y,100),run(a,150,y,80),run(b,250,y,80)]
        return rs

    def test_lower_case_label_with_its_own_value_is_a_row(self):
        rs=self.labelled_values();p=page(rs)
        rows,notes=c.table_rows(rs,10,p)
        self.assertEqual([r[0] for r in grid(rows)],['','subjects','drop-outs','age (years)','Plaque (%)'])
        self.assertEqual(grid(rows)[2][1:],['7','19'])
        checks=c.table_structure_checks(rows,c.table_source(rs,p),'Table 1. Baseline',notes)
        self.assertFalse(checks['split_first_cell']['fired'])
        self.assertFalse(checks['row_bands']['fired'])

    def test_group_label_over_lower_case_children_with_values(self):
        rs=[run('Variable',5,0,60),run('Estimate',150,0,60),run('P-value',250,0,60)]
        for i,(a,b,d) in enumerate([('Sex (male)','0.24','0.54'),('Age','−0.002','0.89'),('Smoking','−0.77','0.03'),('Diabetes','−0.95','0.28')]):
            rs+=[run(a,5,15+15*i,60),run(b,150,15+15*i,40),run(d,250,15+15*i,40)]
        rs+=[run('Horizontal component – ref: none',5,84,200),
             run('degree 2',15,102,60),run('−0.684',150,102,40),run('0.1',250,102,40),
             run('degree 3',15,120,60),run('−0.184',150,120,40),run('0.82',250,120,40)]
        rows,_=c.table_rows(rs,10,page(rs))
        g=grid(rows)
        self.assertEqual([r[0] for r in g][-4:],['Diabetes','Horizontal component – ref: none','degree 2','degree 3'])
        self.assertTrue(rows[-3].group)
        self.assertEqual(g[-1][1:],['−0.184','0.82'])

    def test_hanging_indented_label_lines_stay_one_wrapped_label(self):
        rs=[run('sP-selectin, P-selectin,',5,0,120),run('Plasma levels elevated',150,0,120),run('Papapanagiotou et al. 2009,',300,0,120),
            run('CD18, activated glycoprotein',13,12,120),run('periodontitis, reversed',158,12,120),run('Fredman et al. 2011, Fredman &',308,12,120),
            run('IIb/IIIa (platelet markers)',13,24,120),run('Serhan 2011',308,24,120)]
        rows,_=c.table_rows(rs,10,page(rs,((0,450),)))
        self.assertEqual(len(rows),1)
        self.assertEqual(' '.join(rows[0][0]),'sP-selectin, P-selectin, CD18, activated glycoprotein IIb/IIIa (platelet markers)')
        self.assertEqual(' '.join(rows[0][2]),'Papapanagiotou et al. 2009, Fredman et al. 2011, Fredman & Serhan 2011')

    def observations(self):
        return [run('Fibrinogen',5,0,120),run('Serum levels increased in CP',150,0,120),run('Kweider et al. 1993,',300,0,120),
                run('Schwahn et al. 2004,',308,12,120),
                run('Serum levels in patients with CVD',150,24,120),run('Taylor et al. 2006,',300,24,120),
                run('Buhlin et al. 2009,',308,36,120),
                run('Serum levels decreased',150,48,120),run('Vidal et al. 2009,',300,48,120),
                run('von Willebrand factor',5,60,120),run('Significant association',150,60,120),run('Montebugnoli 2005',300,60,120)]

    def test_fresh_cells_under_a_label_are_rows_and_the_next_label_is_a_row(self):
        rs=self.observations();p=page(rs,((0,450),))
        rows,notes=c.table_rows(rs,10,p)
        g=grid(rows)
        self.assertEqual([r[0] for r in g],['Fibrinogen','','','von Willebrand factor'])
        self.assertEqual(g[0][2],'Kweider et al. 1993, Schwahn et al. 2004,')
        self.assertEqual(g[1],['','Serum levels in patients with CVD','Taylor et al. 2006, Buhlin et al. 2009,'])
        self.assertEqual(g[2],['','Serum levels decreased','Vidal et al. 2009,'])
        checks=c.table_structure_checks(rows,c.table_source(rs,p),'Table 2. Markers',notes)
        for name in ('row_count','split_phrase','split_first_cell','row_bands'):
            self.assertFalse(checks[name]['fired'],name)

    def test_closing_rule_is_not_a_header_end_and_a_marked_short_note_is_a_note(self):
        rs=[run('grade I',5,0,60),run('distinct change in CEJ contour',100,0,200),
            run('grade II',5,12,60),run('CEP approaching the furcation',100,12,200),
            run('grade III',5,24,60),run('CEP extending into the furcation',100,24,200),
            run('* Masters & Hoskins (1964).',5,42,120)]
        p=page(rs);p['elements']=p['elements']+[rule(-6),rule(37)]
        rows,notes=c.table_rows(rs,10,p)
        self.assertEqual([r[0] for r in grid(rows)],['grade I','grade II','grade III'])
        self.assertEqual(notes,['* Masters & Hoskins (1964).'])

    def test_a_wrapped_header_line_is_not_a_witnessed_subrow_and_case_is_no_witness(self):
        rs=[run('Test',5,0,60),run('Groups',100,0,60),run('Groups',200,0,60),
            run('Columns',5,12,60),run('112.7',100,12,40),run('1',200,12,20),
            run('Sum of',100,24,60),run('Degrees of',200,24,60),
            run('Friedman test',5,36,80),run('squares',100,36,60),run('freedom',200,36,60),
            run('Error',5,48,60),run('1.1',100,48,40),run('48',200,48,20)]
        p=page(rs)
        rows=[c.TableRow([['Test'],['Groups'],['Groups']],header=True),c.TableRow([['Columns'],['112.7'],['1']]),
              c.TableRow([[],['Sum of'],['Degrees of']]),c.TableRow([['Friedman test'],['squares'],['freedom']]),
              c.TableRow([['Error'],['1.1'],['48']])]
        checks=c.table_structure_checks(rows,c.table_source(rs,p),'Table 2.',[])
        self.assertTrue(checks['row_count']['fired'])
        rs2=[run('Test',5,0,60),run('Groups',100,0,60),run('Groups',200,0,60),
             run('Columns',5,12,60),run('112.7',100,12,40),run('1',200,12,20),
             run('Mean',100,24,60),run('Total',200,24,60),
             run('Friedman test',5,36,80),run('Squares',100,36,60),run('Freedom',200,36,60),
             run('Error',5,48,60),run('1.1',100,48,40),run('48',200,48,20)]
        rows=[c.TableRow([['Test'],['Groups'],['Groups']],header=True),c.TableRow([['Columns'],['112.7'],['1']]),
              c.TableRow([[],['Mean'],['Total']]),c.TableRow([['Friedman test'],['Squares'],['Freedom']]),
              c.TableRow([['Error'],['1.1'],['48']])]
        checks=c.table_structure_checks(rows,c.table_source(rs2,page(rs2)),'Table 2.',[])
        # tablesub5: the case of a letter is no witness; capitalised text alone does not make a sub-row.
        self.assertTrue(checks['row_count']['fired'])
        # Values restarting in two columns on one baseline do.
        rs3=[dict(e) for e in rs2];rs3[6]=run('2.5',100,24,30);rs3[7]=run('3',200,24,20)
        rows=[c.TableRow([['Test'],['Groups'],['Groups']],header=True),c.TableRow([['Columns'],['112.7'],['1']]),
              c.TableRow([[],['2.5'],['3']]),c.TableRow([['Friedman test'],['Squares'],['Freedom']]),
              c.TableRow([['Error'],['1.1'],['48']])]
        checks=c.table_structure_checks(rows,c.table_source(rs3,page(rs3)),'Table 2.',[])
        self.assertFalse(checks['row_count']['fired'])


def prose(text,x,y,size=10):
    e=run(text,x,y,290);e['run_size_px']=size;e['size_px']=size;return e


class BodyProse(unittest.TestCase):
    """R3: body prose never enters a table's line list."""

    def seed_page(self):
        cells=[run('A. Downregulation of antigen-specific proliferation.',5,0,250),
               run('B. Reduction of the ratio at the protein level.',5,15,250),
               run('C. Reduction of normalized ratios at both levels.',5,30,250)]
        for e in cells:e['run_size_px']=9;e['size_px']=9
        body=[prose('the effects of interfering with antigen specific cells were',0,60+15*i) for i in range(4)]
        body+=[prose('channels have been demonstrated to be involved in a wide',350,60+15*i) for i in range(4)]
        es=cells+body+[fill(-2,40,300),rule(44,0,300)]
        p=page(es,((0,300),(350,650)))
        t=dict(id='table:1',angle=0,members=[e['id'] for e in cells+body],box_px=c.hull(e['box_px'] for e in cells+body))
        p['tables']=[t];p['floats']=[dict(id='float:1',caption='Table 3.',blocks=['table:1'],box_px=list(t['box_px']))]
        return p,cells,body

    def test_closing_border_as_wide_as_the_cell_rows_releases_the_body_columns(self):
        p,cells,body=self.seed_page()
        c.bound_table_before_body(p,10)
        self.assertEqual(sorted(p['tables'][0]['members']),sorted(e['id'] for e in cells))
        released={b['id'] for b in p['main_text']['blocks'] if b['id'].startswith('copy:released:')}
        self.assertEqual(len(released),2)

    def test_prose_seed_beside_another_table_part_is_released(self):
        p,cells,body=self.seed_page()
        p['tables']=[dict(id='table:cells',angle=0,members=[e['id'] for e in cells],box_px=c.hull(e['box_px'] for e in cells)),
                     dict(id='table:prose',angle=0,members=[e['id'] for e in body],box_px=c.hull(e['box_px'] for e in body))]
        p['floats']=[dict(id='float:1',caption='Table 4.',blocks=['table:cells','table:prose'],box_px=[0,0,650,120])]
        c.release_body_column_seeds(p,10)
        self.assertEqual([t['id'] for t in p['tables']],['table:cells'])
        self.assertEqual(p['floats'][0]['blocks'],['table:cells'])
        self.assertTrue(any(b['id'].startswith('copy:released:') for b in p['main_text']['blocks']))

    def test_prose_block_inside_a_table_float_returns_to_the_columns(self):
        p,cells,body=self.seed_page()
        p['tables']=[dict(id='table:cells',angle=0,members=[e['id'] for e in cells],box_px=c.hull(e['box_px'] for e in cells))]
        p['floats']=[dict(id='float:1',caption='Table 4.',blocks=['table:cells'],box_px=[0,0,650,120])]
        p['blocks']=[dict(id='block:9',members=[e['id'] for e in body],box_px=c.hull(e['box_px'] for e in body))]
        c.release_body_column_seeds(p,10)
        self.assertTrue(any(b['id'].startswith('copy:released:block:9') for b in p['main_text']['blocks']))
        self.assertEqual(len(p['tables']),1)


class GateExtent(unittest.TestCase):
    """R2: rows aligned to the table tracks below the detector box join its gate."""

    def test_aligned_small_type_rows_below_the_box_join_the_table(self):
        cells=[]
        for i,(a,b,d) in enumerate([('CRP','Serum levels increased','Ebersole 1997,'),('IL-6','Serum levels decreased','Buhlin 2009,'),
                                    ('IL-1','Serum levels unchanged','Ide 2003,')]):
            cells+=[run(a,5,i*12,60),run(b,100,i*12,120),run(d,220,i*12,80)]
        tail=[run('IL-18',5,48,60),run('Serum levels decreased in CP',100,48,120),
              run('Serum amyloid A, alpha 1 anti-',5,60,80),run('Serum levels increased in patients',100,60,120),run('Glurich 2002,',220,60,80),
              run('chymotrypsin',12,70,60),run('CP compared to periodontitis alone',108,70,120)]
        body=[prose('as CRP and haptoglobin are elevated in chronic and aggressive patients compared',5,100)]
        for e in cells+tail:e['run_size_px']=8;e['size_px']=8
        es=cells+tail+body;p=page(es)
        t=dict(id='table:1',angle=0,members=[e['id'] for e in cells],box_px=c.hull(e['box_px'] for e in cells))
        p['tables']=[t];p['floats']=[dict(id='float:1',caption='Table 1.',blocks=['table:1'],box_px=list(t['box_px']))]
        c.recover_table_aligned_tail(p,10)
        self.assertTrue(p['tables'][0].get('_copy_tail_recovered'))
        self.assertEqual(sorted(p['tables'][0]['members']),sorted(e['id'] for e in cells+tail))
        self.assertNotIn(body[0]['id'],p['tables'][0]['members'])

    def test_a_tail_without_separated_cells_is_not_taken(self):
        cells=[run(a,5,i*12,60) for i,a in enumerate(['CRP','IL-6','IL-1'])]+[run(v,100,i*12,60) for i,v in enumerate(['1','2','3'])]
        for e in cells:e['run_size_px']=8;e['size_px']=8
        notes=[run('Values are means of three measurements',5,40,200)];notes[0]['run_size_px']=8;notes[0]['size_px']=8
        es=cells+notes;p=page(es)
        t=dict(id='table:1',angle=0,members=[e['id'] for e in cells],box_px=c.hull(e['box_px'] for e in cells))
        p['tables']=[t];p['floats']=[dict(id='float:1',caption='Table 1.',blocks=['table:1'],box_px=list(t['box_px']))]
        c.recover_table_aligned_tail(p,10)
        self.assertFalse(p['tables'][0].get('_copy_tail_recovered'))


def small(text,x,y,width=60,size=8):
    e=run(text,x,y,width);e['run_size_px']=size;e['size_px']=size;e['box_px'][3]=y+size;return e


class SpannerHeader(unittest.TestCase):
    """T1: a column-group spanner above the header row is a table line, never released as prose."""

    def spanner_page(self):
        cap=[run('Table 1. Change by month after treatment',5,0,300)]
        spanner=run('Mean decrease in probing depth (mm), month:',162,20,138)   # body size, fills the second column
        header=[run('Study',5,40,40),run('Depth',80,40,40)]+[run(m,x,40,15) for m,x in zip(['1','3','6','9','12'],[170,200,230,260,290])]
        rows=[]
        for i,(name,depth) in enumerate([('Alpha (1990)','5.0'),('Beta (1992)','4.3'),('Gamma (1995)','6.1')]):
            y=55+15*i
            rows+=[run(name,5,y,60),run(depth,80,y,20)]+[run(v,x,y,15) for v,x in zip(['1.1','0.9','0.7','0.6','0.5'],[170,200,230,260,290])]
        after=run('These values were pooled across the studies listed.',162,130,138)
        es=cap+[spanner]+header+rows+[after]
        p=page(es,((0,150),(160,310)))
        cells=header+rows
        t=dict(id='table:1',angle=0,members=[e['id'] for e in cells],box_px=c.hull(e['box_px'] for e in cells))
        p['tables']=[t]
        p['blocks']=[dict(id='block:cap',members=[cap[0]['id'],spanner['id']],box_px=c.hull([cap[0]['box_px'],spanner['box_px']])),
                     dict(id='block:after',members=[after['id']],box_px=after['box_px'])]
        p['main_text']['blocks']=[dict(id='block:after',cls='main',order=1,lines=1,size_px=10,box_px=after['box_px'],text=after['text'])]
        p['floats']=[dict(id='float:1',caption=cap[0]['text'],blocks=['block:cap','table:1'],box_px=c.hull([t['box_px'],cap[0]['box_px']]))]
        return p,spanner,after

    def test_spanner_line_stays_in_the_table_and_prose_below_stays_body(self):
        p,spanner,after=self.spanner_page()
        self.assertTrue(c.body_prose_line(p,spanner,10,[0,0,310,120]))   # the prose test alone would release it
        body,floats,side=c.read_page(p,10,[])
        source=floats[0][5]['table_source']
        owned={x['id'] for l in source['lines'] for x in l['items']}
        self.assertIn(spanner['id'],owned)
        self.assertNotIn(after['id'],owned)
        self.assertEqual(side,[])
        self.assertEqual([b['lines'] for b in body],[[after['text']]])


class HeaderBand(unittest.TestCase):
    """T2: cell shading under the column labels is the first data row's, not the header's."""

    def test_header_row_and_first_data_row_are_separate_rows(self):
        rs=[run('Group',5,0,40),run('Initial',110,0,40),run('6 mo',215,0,30),
            run('Test',5,15,30),run('6.1 ± 0.8 mm',110,15,70),run('1.6 ± 1.4 mm',215,15,70),
            run('Control',5,30,40),run('6.7 ± 0.9 mm',110,30,70),run('5.0 ± 1.1 mm',215,30,70)]
        for e in rs[:3]:e['_faces']={'Sans-Medium':len(e['text'])}
        fills=[dict(id=f'fill:{y}:{x}',kind='fill',box_px=[x,y,x+105,y+15]) for y in (-3,12,27) for x in (0,105,210)]
        rules=[rule(-3,0,315),rule(12,0,315),rule(42,0,315)]
        p=page(rs+fills+rules)
        rows,notes=c.table_rows(rs,10,p)
        self.assertEqual(grid(rows),[['Group','Initial','6 mo'],['Test','6.1 ± 0.8 mm','1.6 ± 1.4 mm'],['Control','6.7 ± 0.9 mm','5.0 ± 1.1 mm']])
        self.assertEqual(notes,[])


    def test_a_stub_on_the_lower_header_tier_is_the_first_header_rows_first_cell(self):
        rs=[run('Change',185,0,50),
            run('Group',5,15,40),run('mm',150,15,20),run('%',255,15,10),
            run('Test',5,30,30),run('-5.2 ± 1.1',150,30,60),run('75 ± 20',255,30,50),
            run('Control',5,45,40),run('-3.2 ± 1.4',150,45,60),run('28 ± 8',255,45,50)]
        for e in rs[:4]:e['_faces']={'Sans-Medium':len(e['text'])}
        fills=[dict(id=f'fill:{i}',kind='fill',box_px=b) for i,b in enumerate([[0,-3,105,27],[105,-3,315,12],[105,12,210,27],[210,12,315,27],
                                                                                [0,27,105,42],[105,27,210,42],[210,27,315,42],[0,42,105,57],[105,42,210,57],[210,42,315,57]])]
        p=page(rs+fills+[rule(-3,0,315),rule(12,105,315),rule(27,0,315),rule(57,0,315)])
        rows,_=c.table_rows(rs,10,p)
        g=grid(rows)
        self.assertEqual((g[0][0],g[1][0]),('Group',''))
        self.assertEqual(set(g[0][1:]),{'Change'});self.assertEqual([x for x in g[1][1:] if x],['mm','%'])
        self.assertEqual([x for x in g[2] if x],['Test','-5.2 ± 1.1','75 ± 20'])


class ListLines(unittest.TestCase):
    """T3: a rule inside a shaded panel is not the closing rule; value lines never become a note paragraph."""

    def test_numbered_steps_and_equations_below_an_interior_rule_stay_table_lines(self):
        texts=['1. Calculate the dose from each drug for the patient.','Weight/150 lb adult x adult dose = patient dose',
               'Adult dose:','Drug A: 500 mg','Drug A: 50/150 x 500 mg = 166 mg',
               '2. Determine the number of cartridges from the dose.','Drug A: 166 mg ÷ 36 mg/cartridge =',
               '4.62a cartridges','Drug B: 133 mg ÷ 54 mg/cartridge = 2.46b cartridges',
               'aIn clinical terms, 4.5 cartridges.','Abbreviation: MRD, maximum recommended dose.']
        ys=[0,29,58,87,116,160,189,210,239,272,290]
        rs=[small(t,0 if i>=9 else 9,y,300,16) for i,(t,y) in enumerate(zip(texts,ys))]
        panel=[dict(id='fill:panel',kind='fill',box_px=[-20,-40,340,330]),rule(-20,-20,340),rule(150,0,320)]
        p=page(rs+panel,((0,340),));p['main_text']['body_size_px']=16
        rows,notes=c.table_rows(rs,16,p)
        self.assertEqual([r[0] for r in grid(rows)],texts[:9])
        self.assertEqual(notes,texts[9:])


class CaptionWithoutRegion(unittest.TestCase):
    """T4: a table caption with no recovered float region takes its aligned cell lines; nothing aligned, a declared empty table."""

    def caption_page(self,cells=True,angle=0,seed=False):
        cap=[small('Table 1 Intensity of',5,0,80),small('inflammation of tissue',5,12,80)]
        rows=[small('Number of cells',140,0,70),small('Scores',230,0,40)]
        for i,(a,b) in enumerate([('0–3','Grade 1'),('4–19','Grade 2'),('20–99','Grade 3')]):
            rows+=[small(a,140,22+12*i,30),small(b,230,22+12*i,40)]
        body=[run('The cells were counted in every section of the sample taken.',5,120,290)]
        es=cap+(rows if cells else [])+body
        p=page(es,((0,310),))
        p['blocks']=[dict(id='block:cap',members=[e['id'] for e in cap],box_px=c.hull(e['box_px'] for e in cap))]
        p['unpaired']=[dict(kind='caption without a graphic on this page',caption='Table 1 Intensity of',block='block:cap')]
        if seed:
            p['tables']=[dict(id='table:9',angle=0,members=[body[0]['id']],box_px=list(body[0]['box_px']))]
        if angle:
            for e in p['elements']+p['blocks']+p['tables']:
                e['box_px']=list(c.frame(-angle)(e['box_px']))
                if 'angle' in e:e['angle']=angle
            p['region_box_px']=list(c.frame(-angle)(p['region_box_px']))
            p['main_text']['columns']=[]
        return p,cap,rows,body

    def test_aligned_cell_lines_beside_and_below_the_caption_are_its_gate(self):
        for angle in (0,90):
            p,cap,rows,body=self.caption_page(angle=angle)
            c.recover_caption_aligned_region(p,[],10)
            self.assertEqual(len(p['floats']),1,angle)
            f=p['floats'][0]
            self.assertEqual(f['caption'],'Table 1. Intensity of inflammation of tissue')
            t=next(t for t in p['tables'] if t['id'] in f['blocks'])
            self.assertEqual(sorted(t['members']),sorted(e['id'] for e in rows))
            self.assertTrue(t.get('_copy_printed_lines'))
            self.assertNotIn(body[0]['id'],t['members'])

    def test_nothing_aligned_declares_the_caption_alone(self):
        p,cap,rows,body=self.caption_page(cells=False)
        c.recover_caption_aligned_region(p,[],10)
        self.assertEqual(len(p['floats']),1)
        self.assertEqual(p['floats'][0]['blocks'],['copy:caption:'+cap[0]['id']])
        self.assertEqual(p['tables'],[])

    def test_a_bare_label_with_nothing_aligned_is_not_declared(self):
        p,cap,rows,body=self.caption_page(cells=False)
        p['elements']=[e for e in p['elements'] if e is not cap[1]];p['blocks'][0]['members']=[cap[0]['id']]
        cap[0]['text']='Table 1'
        c.recover_caption_aligned_region(p,[],10)
        self.assertEqual(p['floats'],[])

    def test_an_unclaimed_seed_leaves_the_caption_to_the_later_pairing(self):
        p,cap,rows,body=self.caption_page(seed=True)
        c.recover_caption_aligned_region(p,[],10)
        self.assertEqual(p['floats'],[])



class LastResortCaption(unittest.TestCase):
    """tablesub3: the caption fallback runs last, only on a page without table parts, and only with a complete gate."""

    caption_page=CaptionWithoutRegion.caption_page

    def aligned(self,p):
        return [f for f in p['floats'] if any(str(b).startswith('copy:aligned:') for b in f['blocks'])]

    def test_it_runs_after_every_other_recovery_of_the_page(self):
        p,cap,rows,body=self.caption_page()
        out=c.table_float_regions(copy.deepcopy(p),10)
        self.assertEqual(len(self.aligned(out)),1)
        # A later recovery (here the printed-border frames) that finds a table
        # part keeps the page: the fallback no longer pre-empts it.
        real=c.recover_bordered_table_regions
        def border(q,labs,body):
            real(q,labs,body)
            q['tables'].append(dict(id='copy:border:1',angle=0,members=[e['id'] for e in rows],
                                    box_px=c.hull(e['box_px'] for e in rows)))
        c.recover_bordered_table_regions=border
        try: out=c.table_float_regions(copy.deepcopy(p),10)
        finally: c.recover_bordered_table_regions=real
        self.assertEqual(self.aligned(out),[])

    def test_cell_lines_beside_kept_lines_in_another_column_stop_it(self):
        p,cap,rows,body=self.caption_page()
        beside=[small(t,330,y,60) for t,y in [('Outcome',0),('none',22),('mild',34),('severe',46)]]
        p['elements']+=beside
        for i,e in enumerate(beside): e['id']=f'text:beside{i}'
        p['main_text']['columns']=[[0,310],[320,700]]
        c.recover_caption_aligned_region(p,[],10)
        self.assertEqual(p['floats'],[])
        self.assertEqual(p['tables'],[])

    def test_a_line_past_the_caption_end_widens_the_frame(self):
        cap=[small('Table 1 Assessment scores',5,0,90)]
        rows=[small('Grade',5,14,30),small('Score',60,14,30)]
        texts=['Score 0: no cells around the material','Score 1: cells under a quarter of the area',
               'Score 2: cells under half of the area']
        rows+=[small(t,5,26+12*i,200) for i,t in enumerate(texts)]
        es=cap+rows
        p=page(es,());p['main_text']['columns']=[]
        p['blocks']=[dict(id='block:cap',members=[cap[0]['id']],box_px=list(cap[0]['box_px']))]
        p['unpaired']=[dict(kind='caption without a graphic on this page',caption=cap[0]['text'],block='block:cap')]
        c.recover_caption_aligned_region(p,[],10)
        t=next(t for t in p['tables'] if t['id'].startswith('copy:aligned:'))
        self.assertEqual(sorted(t['members']),sorted(e['id'] for e in rows))

    def test_an_empty_label_declaration_is_replaced_by_the_aligned_lines(self):
        p,cap,rows,body=self.caption_page()
        bid='copy:caption:'+cap[0]['id']
        p['blocks'].append(dict(id=bid,members=[e['id'] for e in cap],box_px=c.hull(e['box_px'] for e in cap)))
        p['floats'].append(dict(caption='Table 1 Intensity of',blocks=[bid],_line_fallback_ids=[],box_px=list(cap[0]['box_px'])))
        c.recover_caption_aligned_region(p,[],10)
        self.assertEqual(len(p['floats']),1)
        t=next(t for t in p['tables'] if t['id'] in p['floats'][0]['blocks'])
        self.assertEqual(sorted(t['members']),sorted(e['id'] for e in rows))
        self.assertEqual([b['id'] for b in p['blocks']].count(bid),1)

    def test_a_declaration_with_lines_or_a_rule7_list_is_left_alone(self):
        p,cap,rows,body=self.caption_page()
        bid='copy:caption:'+cap[0]['id']
        p['blocks'].append(dict(id=bid,members=[e['id'] for e in cap],box_px=c.hull(e['box_px'] for e in cap)))
        p['floats'].append(dict(caption='Table 1 Intensity of',blocks=[bid],_line_fallback_ids=[rows[0]['id']],box_px=list(cap[0]['box_px'])))
        c.recover_caption_aligned_region(p,[],10)
        self.assertEqual(len(p['floats']),1);self.assertEqual(p['tables'],[])
        p,cap,rows,body=self.caption_page()
        p['main_text']['captioned_lists']=[dict(members=[e['id'] for e in cap+rows])]
        c.recover_caption_aligned_region(p,[],10)
        self.assertEqual(p['floats'],[])


class ReleasedLines(unittest.TestCase):
    """tablesub4: a printed line inside a table's gate that reads as prose is released only outside the table's
    drawn structure; a label-plus-values line, a note line under the table or a line between its rules stays."""

    def table_page(self):
        cap=[run('Table 2. Outcome by group after treatment',5,0,300)]
        header=[run('Group',5,30,40),run('Baseline',150,30,50),run('Final',250,30,40)]
        rows=[]
        for i,(name,a,d) in enumerate([('Alpha','4.1','3.2'),('Beta','4.4','3.0'),('Gamma','4.0','2.9')]):
            rows+=[run(name,5,48+15*i,60),run(a,150,48+15*i,20),run(d,250,48+15*i,20)]
        # below the detector box, inside the rules: a group line and a label-plus-values line, both one
        # body-size run filling the column (the prose test alone would release them)
        group=prose('Patients treated with the adjunctive systemic antibiotic regimen',0,95)
        values=prose('Total number of implants with marginal bone loss 25 30',0,110)
        notes=[prose('Abbreviations: BOP, bleeding on probing; PD, probing depth; CAL,',0,132),
               prose('clinical attachment level; SD, standard deviation of the mean.',0,144)]
        after=prose('The results in the second group were compared with those of the first',0,175)
        rules=[rule(26,0,300),rule(42,0,300),rule(125,0,300)]
        es=cap+header+rows+[group,values]+notes+[after]+rules
        p=page(es,((0,320),))
        cells=header+rows
        t=dict(id='table:1',angle=0,members=[e['id'] for e in cells],box_px=c.hull(e['box_px'] for e in cells))
        p['tables']=[t]
        p['blocks']=[dict(id='block:cap',members=[cap[0]['id']],box_px=cap[0]['box_px']),
                     dict(id='block:after',members=[after['id']],box_px=after['box_px'])]
        p['main_text']['blocks']=[dict(id='block:after',cls='main',order=1,lines=1,size_px=10,box_px=after['box_px'],text=after['text'])]
        p['floats']=[dict(id='float:1',caption=cap[0]['text'],blocks=['block:cap','table:1'],box_px=c.hull([t['box_px'],cap[0]['box_px']]))]
        return p,group,values,notes,after

    def test_label_values_lines(self):
        self.assertTrue(c.label_values_line('Total number of implants with marginal bone loss 25 30'))
        self.assertTrue(c.label_values_line('Peri-implant mucositis cases 12 (34.3) 8 (22.9)'))
        self.assertFalse(c.label_values_line('score showed improvement from 11.57 ± 4.02 to 9.63 ± 3.52'))
        self.assertFalse(c.label_values_line('while the gain was 0.67 ± 0.33 and 0.8 ± 0.4 mm, respectively.'))

    def test_lines_of_the_gate_stay_and_prose_after_the_table_is_body(self):
        p,group,values,notes,after=self.table_page()
        for e in [group,values]+notes:self.assertTrue(c.body_prose_line(p,e,10,[0,0,320,200]))
        body,floats,side=c.read_page(p,10,[])
        source=floats[0][5]['table_source']
        owned={x['id'] for l in source['lines'] for x in l['items']}
        for e in [group,values]+notes:self.assertIn(e['id'],owned)
        self.assertNotIn(after['id'],owned)
        self.assertEqual([b['lines'] for b in body],[[after['text']]])

    def test_reasons(self):
        p,group,values,notes,after=self.table_page()
        region=[0,30,300,90]
        self.assertEqual(c.table_line_stays(p,values,10,region),'label and values')
        self.assertEqual(c.table_line_stays(p,group,10,region),'drawn structure')
        self.assertEqual(c.table_line_stays(p,notes[0],10,[0,30,300,125]),'note')
        self.assertEqual(c.table_line_stays(p,notes[1],10,[0,30,300,125],notes=[notes[0]['id']]),'note')
        self.assertEqual(c.table_line_stays(p,after,10,[0,30,300,150]),'')

    def test_a_caption_or_three_prose_rows_end_the_ruled_set(self):
        es=[rule(0,0,300),rule(40,0,300)]+[prose('the effects of interfering with antigen specific cells were',0,50+12*i) for i in range(3)]+[rule(100,0,300)]
        p=page(es)
        spans=[g[1:4:2] for g in c.table_ruled_extents(p,[0,0,300,40],10)]
        self.assertIn([0,40.5],spans);self.assertFalse(any(g[1]>=99 for g in spans))
        es=[rule(0,0,300),rule(40,0,300),run('Table 3. Second table',0,50,200),rule(70,0,300)]
        p=page(es)
        self.assertFalse(any(g[1]>=69 for g in c.table_ruled_extents(p,[0,0,300,40],10)))

    def seed_page(self,second):
        cells=[run('Variable',5,0,60),run('Test',150,0,40),run('Control',250,0,40)]
        cells+=[run('Age',5,15,60),run('41',150,15,20),run('43',250,15,20)]
        p=page(cells+second+[rule(-3,0,300),rule(12,0,300)],((0,320),))
        p['tables']=[dict(id='table:cells',angle=0,members=[e['id'] for e in cells],box_px=c.hull(e['box_px'] for e in cells)),
                     dict(id='table:second',angle=0,members=[e['id'] for e in second],box_px=c.hull(e['box_px'] for e in second))]
        p['floats']=[dict(id='float:1',caption='Table 4.',blocks=['table:cells','table:second'],box_px=[0,-10,320,200])]
        return p

    def test_a_part_holding_label_values_lines_is_not_released(self):
        second=[prose('Patients with at least one implant showing bone loss 12 14',0,40+12*i) for i in range(3)]
        second+=[prose('the effects of interfering with antigen specific cells were',0,80+12*i) for i in range(5)]
        p=self.seed_page(second)
        c.release_body_column_seeds(p,10)
        self.assertEqual([t['id'] for t in p['tables']],['table:cells','table:second'])
        second=[prose('the effects of interfering with antigen specific cells were',0,80+12*i) for i in range(8)]
        p=self.seed_page(second)
        c.release_body_column_seeds(p,10)
        self.assertEqual([t['id'] for t in p['tables']],['table:cells'])

    def test_a_block_holding_a_note_under_the_table_is_not_released(self):
        cells=[run('Variable',5,0,60),run('Test',150,0,40),run('Control',250,0,40),run('Age',5,15,60),run('41',150,15,20),run('43',250,15,20)]
        block=[prose('Abbreviations: BOP, bleeding on probing; PD, probing depth and more',0,30)]
        block+=[prose('clinical attachment level; SD, standard deviation of the mean here',0,39+9*i) for i in range(4)]
        p=page(cells+block,((0,320),))
        p['tables']=[dict(id='table:cells',angle=0,members=[e['id'] for e in cells],box_px=c.hull(e['box_px'] for e in cells))]
        p['floats']=[dict(id='float:1',caption='Table 4.',blocks=['table:cells'],box_px=[0,0,320,90])]
        p['blocks']=[dict(id='block:9',members=[e['id'] for e in block],box_px=c.hull(e['box_px'] for e in block))]
        c.release_body_column_seeds(p,10)
        self.assertFalse(any(b['id'].startswith('copy:released:') for b in p['main_text']['blocks']))

    def boundary_page(self,released):
        cells=[small('Variable',5,0,60,9),small('Test',150,0,40,9),small('Control',250,0,40,9)]
        for i in range(3):cells+=[small('Item',5,12+12*i,60,9),small('4.1',150,12+12*i,20,9),small('3.2',250,12+12*i,20,9)]
        es=cells+released+[rule(-3,0,300),rule(50,0,300)]
        p=page(es,((0,320),))
        t=dict(id='table:1',angle=0,members=[e['id'] for e in cells+released],box_px=c.hull(e['box_px'] for e in cells+released))
        p['tables']=[t];p['floats']=[dict(id='float:1',caption='Table 3.',blocks=['table:1'],box_px=list(t['box_px']))]
        return p,cells

    def test_the_body_boundary_does_not_release_table_lines(self):
        p,cells=self.boundary_page([prose('Total number of implants with marginal bone loss 25 30',0,60+12*i) for i in range(3)])
        c.bound_table_before_body(p,10)
        self.assertNotIn('_copy_body_bottom',p['tables'][0])
        p,cells=self.boundary_page([prose('the effects of interfering with antigen specific cells were',0,60+12*i) for i in range(3)])
        c.bound_table_before_body(p,10)
        self.assertEqual(sorted(p['tables'][0]['members']),sorted(e['id'] for e in cells))
        p,cells=self.boundary_page([prose('the effects of interfering with antigen specific cells were',0,60+12*i) for i in range(2)])
        p['elements'].append(dict(id='rule:x',kind='rule',box_px=[0,85,300,85.5]))
        c.bound_table_before_body(p,10)
        self.assertNotIn('_copy_body_bottom',p['tables'][0])


if __name__=='__main__':
    unittest.main()
