"""Study ownership and narrow cell gaps, with synthetic source geometry."""
import copy
import unittest
from test_cellblocks import c, run, fill


class StudyOwnership(unittest.TestCase):
    def example(self):
        rs=[run(t,x,0,110) for t,x in [('Study',5),('Treatment',165),('Comments',325)]]
        first=[(25,'Alpha et al12'),(40,'2010'),(55,'RCT'),(70,'6 months'),(85,'Country'),
               (104,'Beta et al13'),(119,'2011'),(134,'RCT'),(149,'also reported in:'),
               (164,'Beta et al14'),(179,'2012'),(194,'Beta et al15'),(209,'2013'),
               (250,'Gamma et al16'),(265,'2014'),(280,'RCT')]
        rs += [run(t,5,y,110) for y,t in first]
        rs += [run(t,165,y,110) for y,t in [(25,'First arm'),(70,'Second arm'),
                                           (104,'Third arm'),(179,'Fourth arm'),(250,'Last arm')]]
        rs += [run(t,325,y,130) for y,t in [(25,'• First comment'),(85,'• Country comment'),
                  (104,'• Second comment'),(164,'• Continued comment'),(194,'• Final comment'),
                  (250,'• Third comment'),(280,'• Last comment')]]
        return dict(elements=rs+[fill(-5,18,480)])

    def test_primary_studies_own_countries_arms_and_secondary_citations(self):
        for angle in (0,90,180,270):
            p=copy.deepcopy(self.example())
            for e in p['elements']:
                e['box_px']=c.frame(-angle)(e['box_px'])
                if e['kind']=='text':e['angle']=angle
            rs=p['elements'][:-1]
            rows,notes=c.table_rows(rs,10,p)
            self.assertEqual(len(rows),4)
            self.assertEqual(rows[1][0][-1],'Country')
            self.assertEqual(rows[1][1],['First arm','Second arm'])
            self.assertEqual(rows[1][2][-1],'• Country comment')
            self.assertEqual(rows[2][0],['Beta et al13','2011','RCT','also reported in:',
                                        'Beta et al14','2012','Beta et al15','2013'])
            self.assertEqual(rows[2][1],['Third arm','Fourth arm'])
            self.assertEqual(rows[2][2][-1],'• Final comment')
            checks=c.table_structure_checks(rows,c.table_source(rs,p),'Table 1. Studies',notes)
            self.assertFalse(checks['study_row_ownership']['fired'],checks)

    def test_verifier_rejects_country_and_each_secondary_citation_row(self):
        p=self.example();rs=p['elements'][:-1]
        rows=[c.TableRow([['Study'],['Treatment'],['Comments']]),
              c.TableRow([['Alpha et al12','2010','RCT','6 months'],['First arm','Second arm'],['• First comment']]),
              c.TableRow([['Country'],[],['• Country comment']]),
              c.TableRow([['Beta et al13','2011','RCT','also reported in:'],['Third arm'],['• Second comment']]),
              c.TableRow([['Beta et al14','2012'],['Fourth arm'],['• Continued comment']]),
              c.TableRow([['Beta et al15','2013'],[],['• Final comment']]),
              c.TableRow([['Gamma et al16','2014','RCT'],['Last arm'],['• Third comment','• Last comment']])]
        for row in rows:row.cell_band=(0,400);row.study_band=True
        check=c.table_structure_checks(rows,c.table_source(rs,p),'Table 1. Studies',[])['study_row_ownership']
        self.assertTrue(check['fired'])
        self.assertEqual([e['row'] for e in check['evidence']],[3,5,6])

    def test_nonbibliographic_study_labels_are_not_rejected(self):
        rs=[run(t,x,y,100) for y,labels in [(0,('Study','Result')),
              (25,('First experiment','Earlier result')),(50,('Second experiment','Later result'))]
              for x,t in zip((5,165),labels)]
        rows=[[[a],[b]] for a,b in [('Study','Result'),('First experiment','Earlier result'),
                                   ('Second experiment','Later result')]]
        self.assertFalse(c.table_structure_checks(rows,c.table_source(rs,dict(elements=rs)),
                         'Table 1. Experiments',[])['study_row_ownership']['fired'])

    def test_first_data_row_cannot_be_a_continuation_or_explicit_secondary_citation(self):
        for label in ('Country','also reported in: Alpha et al12'):
            rs=[run(t,x,y,120) for y,labels in [(0,('Study','Comments')),
                (25,(label,'• Previous comment')),(70,('Beta et al13','• Next comment'))]
                for x,t in zip((5,165),labels)]
            rows=[[[a],[b]] for a,b in [('Study','Comments'),(label,'• Previous comment'),
                                       ('Beta et al13','• Next comment')]]
            check=c.table_structure_checks(rows,c.table_source(rs,dict(elements=rs)),
                         'Table 1. Studies',[])['study_row_ownership']
            self.assertEqual([e['row'] for e in check['evidence']],[2])

    def test_reflow_retains_productive_adjectival_compound(self):
        j=c.Joiner(['The energy-dependent pathway.'])
        self.assertEqual(j.lines(['energy-','dependent pathway']),'energy-dependent pathway')
        j=c.Joiner([])
        j.prose=False
        self.assertEqual(j.lines(['oxygen-','dependent pathway']),'oxygen-dependent pathway')
        # A witnessed closed spelling still wins over the productive suffix.
        j=c.Joiner(['The independent pathway.'])
        self.assertEqual(j.lines(['in-','dependent pathway']),'independent pathway')

    def test_table_suffix_rule_does_not_change_prose_or_reference_reflow(self):
        self.assertEqual(c.Joiner([]).lines(['oxygen-','dependent pathway']),'oxygendependent pathway')

    def test_closed_dependent_words_need_no_unbroken_witness(self):
        for prefix in ('in','inter','co'):
            j=c.Joiner([]);j.prose=False
            self.assertEqual(j.lines([prefix+'-','dependent pathway']),
                             prefix+'dependent pathway')

    def test_labelled_spanning_section_is_not_a_study_continuation(self):
        labels=[('Study','Result'),('Alpha et al12','Earlier result'),
                ('(A) Human studies',''),('Beta et al13','Later result')]
        rs=[run(t,x,y,130) for y,pair in zip((0,25,50,75),labels)
            for x,t in zip((5,165),pair) if t]
        rows=[c.TableRow([[a],[b] if b else []]) for a,b in labels]
        check=c.table_structure_checks(rows,c.table_source(rs,dict(elements=rs)),
                                      'Table 1. Studies',[])['study_row_ownership']
        self.assertFalse(check['fired'],check)

    def test_single_and_paired_authors_with_numbered_citations_start_studies(self):
        labels=[('Study','Result'),('Alpha et al12','Earlier result'),
                ('Beta and Gamma13','Next result'),('Delta14','Later result'),
                ('Epsilon et, al15','Last result'),('International- Research-Consortium (16)','Group result'),
                ('Zeta and Eta17 Country A descriptive study','Paired result'),
                ('Theta18 Country Another descriptive study','Single result')]
        rs=[run(t,x,y,140) for y,pair in zip((0,30,60,90,120,150,180,210),labels)
            for x,t in zip((5,180),pair)]
        rows=[[[a],[b]] for a,b in labels]
        check=c.table_structure_checks(rows,c.table_source(rs,dict(elements=rs)),
                                      'Table 1. Studies',[])['study_row_ownership']
        self.assertFalse(check['fired'],check)

    def test_unlabelled_category_attaches_to_next_study_but_country_to_previous(self):
        labels=[('Reference','Result'),('Alpha et al12','Earlier result'),
                ('Country',''),('Respiratory disease',''),('Beta et al13','Later result')]
        rs=[run(t,x,y,130) for y,pair in zip((0,25,40,85,110),labels)
            for x,t in zip((5,180),pair) if t]
        rows=[[[a],[b] if b else []] for a,b in labels]
        check=c.table_structure_checks(rows,c.table_source(rs,dict(elements=rs)),
                                      'Table 1. Studies',[])['study_row_ownership']
        self.assertEqual([e['row'] for e in check['evidence']],[3])

    def test_outdented_category_can_touch_the_previous_study(self):
        labels=[('Study','Result'),('Alpha et al12','Earlier result'),
                ('Control versus treatment',''),('Beta et al13','Later result')]
        rs=[run(t,x,y,130) for y,pair in zip((0,25,40,80),labels)
            for x,t in zip((5 if y in (0,40) else 15,180),pair) if t]
        rows=[[[a],[b] if b else []] for a,b in labels]
        check=c.table_structure_checks(rows,c.table_source(rs,dict(elements=rs)),
                                      'Table 1. Studies',[])['study_row_ownership']
        self.assertFalse(check['fired'],check)

    def test_study_title_can_precede_its_numbered_author_citation(self):
        labels=[('Studies performed','Result'),('Alpha et al12','Earlier result'),
                ('A review of 42 cases. Beta B, Gamma C, & Delta D13','Later result')]
        rs=[run(t,x,y,150) for y,pair in zip((0,25,50),labels)
            for x,t in zip((5,180),pair)]
        rows=[[[a],[b]] for a,b in labels]
        check=c.table_structure_checks(rows,c.table_source(rs,dict(elements=rs)),
                                      'Table 1. Studies',[])['study_row_ownership']
        self.assertFalse(check['fired'],check)

    def test_measurement_strata_are_distinct_numeric_observations(self):
        labels=[('Study','Result'),('Alpha et al12','Procedure'),
                ('1–3 mm','20%'),('≤ 3 mm','35%'),('Country','40%'),
                ('Study','Later assessment'),('Beta et al13','Second procedure')]
        rs=[run(t,x,y,120) for y,pair in zip((0,30,60,90,120,150,180),labels)
            for x,t in zip((5,180),pair)]
        rows=[[[a],[b]] for a,b in labels]
        check=c.table_structure_checks(rows,c.table_source(rs,dict(elements=rs)),
                                      'Table 1. Studies',[])['study_row_ownership']
        self.assertEqual([e['row'] for e in check['evidence']],[5])


class CellStarts(unittest.TestCase):
    def example(self, text, words, close_gap=False):
        # The header and two unindented body lines witness the second cell's
        # start, even though most lines start at its hanging indent instead.
        rs=[run('Label',5,0,45),run('Definition',105,0,50),run('Treatment',205,0,65)]
        rs += [run('Alpha',5,25,45),run('First definition',105,25,85),run('Action',205,25,50)]
        rs += [run('wrapped action',211,y,90) for y in (40,55,70,85,100)]
        rs += [run('Last action',205,115,60),run('Beta',5,140,45)]
        joined=run(text,105,140,150)
        chars=[]
        for word,x in words:
            for j,ch in enumerate(word):chars.append(dict(text=ch,x0=x+j*4,x1=x+(j+1)*4,y0=140,y1=150))
        # End the first phrase near the second column; its ordinary-looking
        # gap alone cannot identify two cells.
        if close_gap:
            for ch in chars[7:14]:ch['x0']+=30;ch['x1']+=30
        joined['char_ids']=list(range(len(chars)));rs.append(joined)
        graphics=[fill(-5,18,320),dict(kind='fill',box_px=[100,20,200,160]),
                  dict(kind='fill',box_px=[200,20,320,160])]
        p=dict(elements=rs+graphics,_table_chars=chars)
        rows,_=c.table_rows(rs,10,p)
        return rows

    def test_unindented_start_splits_a_joined_run_when_hanging_indent_is_modal(self):
        rows=self.example('Signs of illness Action',
                          [('Signs',105),('of',130),('illness',140),('Action',205)],True)
        self.assertEqual(rows[-1],[['Beta'],['Signs of illness'],['Action']])

    def test_alternate_start_does_not_split_a_unit_expression(self):
        rows=self.example('Range (% [limits])',[('Range',105),('(%',190),('[limits])',205)])
        self.assertEqual(rows[-1],[['Beta'],['Range (% [limits])'],[]])


if __name__=='__main__':unittest.main()
