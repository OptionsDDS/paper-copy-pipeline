"""Lane tablesub, re-ladder round 2 of the combined gate (tablesub7): a significance mark under a value stays in its
cell; a line of bracketed spreads under a label that fills its column goes on in the row; a bracketed sample size
under a column's name goes on with it; a repeated stub beside values starts its own sub-row; a drawn band holding
one entry keeps its wrapped label whole; a caption wrapped in a one-column grid stays one cell; the checks witness
a blank-label row under a drawn border and a repeated stub. Fixtures are synthetic; no paper text."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('tablesub',Path(__file__).with_name('test_tablesub.py'))
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
c,run,page,grid,rule,fill=t.c,t.run,t.page,t.grid,t.rule,t.fill


def checks(rs,p,rows,notes,caption='Table 1. Invented'):
    return c.table_structure_checks(rows,c.table_source(rs,p),caption,notes)


class Marks(unittest.TestCase):
    def test_a_significance_mark_under_each_value_stays_in_its_cell(self):
        rs=[run('Weight (kg)',90,0,60),run('Height (cm)',190,0,60),run('Visits',290,0,40)]
        rs+=[run('Early',5,15,30),run('61 (8.0)',90,15,48),run('170 (6.1)',190,15,54),run('4 (2)',290,15,30),
             run('NS',90,26,12),run('NS',190,26,12),run('NS',290,26,12),
             run('Late',5,40,24),run('63 (7.5)',90,40,48),run('168 (5.9)',190,40,54),run('5 (2)',290,40,30)]
        g=grid(c.table_rows(rs,10,page(rs+[rule(-4,0,340),rule(12,0,340),rule(54,0,340)]))[0])
        self.assertEqual(g[1:],[['Early','61 (8.0) NS','170 (6.1) NS','4 (2) NS'],['Late','63 (7.5)','168 (5.9)','5 (2)']])

    def test_a_line_of_bracketed_spreads_under_a_full_label_goes_on_in_its_row(self):
        # the label column is as wide as its widest label, which leaves no room before the next column; the label's second line carries the spreads of the
        # values above, one of them printed without its opening bracket
        rs=[run('Start',118,0,30),run('End',200,0,20),run('p',280,0,6)]
        rs+=[run('Clean outer sides',5,15,102),run('31%',118,15,24),run('48%',200,15,24),run('0.01',280,15,24),
             run('of molars',5,26,54),run('(22%)',118,26,30),run('24%)',200,26,24),
             run('Clean inner sides',5,37,102),run('17%',118,37,24),run('27%',200,37,24),run('0.08',280,37,24),
             run('of molars',5,48,54),run('(19%)',118,48,30),run('(16%)',200,48,30)]
        p=page(rs+[rule(-4,0,330),rule(12,0,330),rule(62,0,330)])
        rows,notes=c.table_rows(rs,10,p);g=grid(rows)
        self.assertEqual(g[1:],[['Clean outer sides of molars','31% (22%)','48% 24%)','0.01'],
                                ['Clean inner sides of molars','17% (19%)','27% (16%)','0.08']])
        self.assertFalse(checks(rs,p,rows,notes)['row_bands']['fired'])

    def test_a_bracketed_sample_size_under_a_column_name_stays_with_it(self):
        # a guard: here the header tier is found by its rule; the row witness must not undo it
        rs=[run('Rinse',150,0,30),run('Placebo',230,0,42),
            run('Event',5,11,30),run('(N = 40)',150,11,48),run('(N = 38)',230,11,48),
            run('Sore gums',5,26,54),run('4 (10.0)',150,26,48),run('5 (13.2)',230,26,48),
            run('Dry mouth',5,38,54),run('2 (5.0)',150,38,42),run('1 (2.6)',230,38,42)]
        g=grid(c.table_rows(rs,10,page(rs+[rule(-4,0,300),rule(23,0,300),rule(52,0,300)]))[0])
        self.assertIn(['Event','Rinse (N = 40)','Placebo (N = 38)'],g)
        self.assertEqual(g[-2:],[['Sore gums','4 (10.0)','5 (13.2)'],['Dry mouth','2 (5.0)','1 (2.6)']])


def stub_table(bands):
    """Group | Statistic | Arm A | Arm B: two groups, each a drawn band, the group's name wrapped over its first two
    lines beside a repeated stub column (n / Mean / Median / Range)."""
    rs=[run('Group',5,0,30),run('Statistic',100,0,50),run('Arm A',190,0,30),run('Arm B',260,0,30)]
    graphics=[rule(-4,0,320),rule(12,0,320)]
    y=16
    for k,(name,tail) in enumerate([('Sites treated','per mouth'),('Mean pocket','depth')]):
        top=y-2
        rs+=[run(name,5,y,72),run(tail,5,y+11,6*len(tail))]
        for i,(st,a,b) in enumerate([('n','40','38'),('Mean','21.4','23.0'),('Median','20','22'),('Range','(4-61)','(5-70)')]):
            rs+=[run(st,100,y+11*i,6*len(st)),run(a,190,y+11*i,6*len(a)),run(b,260,y+11*i,6*len(b))]
        y+=11*4+8
        if bands: graphics.append(fill(top,y-4))
    graphics.append(rule(y-2,0,320))
    return rs,graphics


class Stubs(unittest.TestCase):
    def test_a_repeated_stub_beside_bracketed_values_is_its_own_sub_row(self):
        rs,gr=stub_table(bands=True);p=page(rs+gr)
        rows,notes=c.table_rows(rs,10,p);g=grid(rows)
        self.assertEqual([r[1] for r in g[1:]],['n','Mean','Median','Range']*2)
        self.assertEqual(g[4][2:],['(4-61)','(5-70)'])
        self.assertFalse(checks(rs,p,rows,notes)['row_count']['fired'],checks(rs,p,rows,notes)['row_count'])

    def test_a_drawn_band_holding_one_entry_keeps_its_wrapped_label_whole(self):
        rs,gr=stub_table(bands=True);g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertEqual([r[0] for r in g[1:]],['Sites treated per mouth','','','','Mean pocket depth','','',''])

    def test_without_drawn_bands_the_label_lines_stay_as_the_witnesses_read_them(self):
        # no band edges: the band rule has no evidence and the label tail is not joined by it
        rs,gr=stub_table(bands=False);g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertNotIn('Sites treated per mouth',[r[0] for r in g])

    def test_a_band_with_two_entries_each_with_values_keeps_both_rows(self):
        # negative: two labelled lines with values of their own in one band, nothing stacked under them
        rs=[run('Arm A',190,0,30),run('Arm B',260,0,30)]
        gr=[rule(-4,0,320),rule(12,0,320)]
        rs+=[run('All reported events',5,16,114),run('43',190,16,12),run('51',260,16,12),
             run('Patients with events',5,27,120),run('15 (37.5)',190,27,54),run('19 (50.0)',260,27,54)]
        gr.append(fill(14,40))
        rs+=[run('Gum swelling',5,44,72),run('3 (7.5)',190,44,42),run('2 (5.3)',260,44,42)]
        gr+=[rule(58,0,320)]
        g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertEqual([r[0] for r in g[1:]],['All reported events','Patients with events','Gum swelling'])


class Bands(unittest.TestCase):
    def test_a_label_tail_alone_in_its_band_joins_its_label(self):
        # alternate rows shaded; the unshaded row's label wraps onto a line of its own
        rs=[run('Arm A',150,0,30),run('Arm B',230,0,30),run('p',330,0,6)]
        rs+=[run('Upper',5,16,30),run('0.31 ± 0.40',150,16,66),run('0.28 ± 0.33',230,16,66),run('.41',330,16,18),
             run('Lower',5,30,30),run('0.14 ± 0.15',150,30,66),run('0.19 ± 0.11',230,30,66),run('.07',330,30,18),
             run('Mean gap',5,44,48),run('0.22 ± 0.24',150,44,66),run('0.23 ± 0.18',230,44,66),run('.88',330,44,18),
             run('width',5,54,30),
             run('Overall p',5,70,54),run('0.170',150,70,30),run('0.260',230,70,30)]
        gr=[rule(-4,0,350),rule(12,0,350),fill(27,41,350),fill(67,82,350)]
        g=grid(c.table_rows(rs,10,page(rs+gr))[0])
        self.assertIn(['Mean gap width','0.22 ± 0.24','0.23 ± 0.18','.88'],g)


class OneColumn(unittest.TestCase):
    def test_a_caption_wrapped_in_a_one_column_grid_stays_one_cell(self):
        rs=[run('Fig. 4 A narrow band of',5,0,138),run('firm tissue around the implant crown',5,12,216),
            run('Fig. 5 The same site',5,60,120),run('after one year',5,72,84)]
        g=grid(c.table_rows(rs,10,page(rs))[0])
        self.assertEqual(g,[['Fig. 4 A narrow band of firm tissue around the implant crown'],['Fig. 5 The same site after one year']])


class Checks(unittest.TestCase):
    def test_a_blank_label_row_under_a_drawn_border_is_a_witnessed_row(self):
        # the first label spans two shaded rows; the second row's text cells start under the band edge
        rs=[run('KIND',5,0,30),run('GOOD',100,0,30),run('FAIR',200,0,30),
            run('SIGNS',5,16,36),run('NO LOSS OF',100,16,60),run('SOME LOSS',200,16,54),
            run('BONE',100,27,24),run('OF BONE',200,27,42),
            run('NO SWELLING',100,44,66),run('SWELLING',200,44,48),
            run('PRESENT',100,55,42),
            run('OUTLOOK',5,72,42),run('STABLE',100,72,36),run('UNSURE',200,72,36)]
        gr=[fill(-4,12,320),fill(41,68,90),fill(41,68,190),fill(41,68,320),rule(86,0,320)]
        gr[1]['box_px'][0]=0;gr[2]['box_px'][0]=90;gr[3]['box_px'][0]=190
        p=page(rs+gr);rows,notes=c.table_rows(rs,10,p);g=grid(rows)
        self.assertEqual([r[0] for r in g],['KIND','SIGNS','','OUTLOOK'])
        self.assertFalse(checks(rs,p,rows,notes)['row_count']['fired'],checks(rs,p,rows,notes)['row_count'])

    def test_text_running_on_across_a_band_edge_is_not_witnessed_by_the_edge(self):
        # the second drawn row's cell goes on from the cell above by a connector: the edge is no row witness
        rs=[run('KIND',5,0,30),run('GOOD',100,0,30),run('FAIR',200,0,30),
            run('SIGNS',5,16,36),run('LOSS SEEN BY',100,16,72),run('SOME LOSS',200,16,54),
            run('X-RAY ONLY',100,44,60),run('SWELLING',200,44,48),
            run('OUTLOOK',5,72,42),run('STABLE',100,72,36),run('UNSURE',200,72,36)]
        gr=[fill(-4,12,320),fill(41,68,90),fill(41,68,190),fill(41,68,320),rule(86,0,320)]
        gr[1]['box_px'][0]=0;gr[2]['box_px'][0]=90;gr[3]['box_px'][0]=190
        p=page(rs+gr);rows,notes=c.table_rows(rs,10,p);g=grid(rows)
        if len(g)==4 and not g[2][0]:
            self.assertTrue(checks(rs,p,rows,notes)['row_count']['fired'])


class StubGuard(unittest.TestCase):
    def test_wrapped_prose_lines_that_repeat_between_entries_are_no_stub(self):
        # a prose column whose two wrapped lines recur in two entries, beside text (not values) in the next column
        rs=[run('Ref',5,0,20),run('Health',90,0,40),run('Smoking',200,0,40),run('Teeth',300,0,30)]
        for k,(r,n) in enumerate([('Ames 2016','6 former'),('Baird 2017','4 former')]):
            y=15+30*k
            rs+=[run(r,5,y,55),run('Good general',90,y,72),run(n,200,y,48),run('Front: 5',300,y,48),
                 run('health',90,y+11,36),run('(smoked daily)',200,y+11,78),run('Side: 8',300,y+11,42)]
        g=grid(c.table_rows(rs,10,page(rs+[rule(-4,0,380),rule(12,0,380),rule(70,0,380)]))[0])
        self.assertEqual([r[1] for r in g[1:]],['Good general health','Good general health'])


if __name__=='__main__':
    unittest.main()
