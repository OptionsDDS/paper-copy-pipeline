"""Fail-safe decisions from independent printed evidence, in every reading frame."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('gate',Path(__file__).with_name('test_table_gate.py'))
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
c,run,source,checks=gate.c,gate.run,gate.source,gate.checks


class Safe(unittest.TestCase):
    def test_assembly_warning_gates_an_otherwise_rectangular_table(self):
        rs=[run(t,x,y) for y,pair in [(0,('Name','Value')),(20,('Alpha','12'))]
            for x,t in zip((0,120),pair)]
        src=source(rs);src['assembly_warnings']=['pieces joined; rows unverified']
        it=dict(kind='table',page=1,caption='Table 1. Example',
                rows=[[['Name'],['Value']],[['Alpha'],['12']]],notes=[],table_source=src)
        warnings=[]
        rec=c.gate_tables([it],[dict(page=1,elements=rs)],warnings)[0]
        self.assertEqual(rec['fired'],['assembly_evidence'])
        self.assertEqual(rec['printed_lines'],['Name Value','Alpha 12'])
        self.assertIn('assembly_evidence',warnings[0])
        self.assertIn('2 printed lines',c.table_gate_markdown(rec['printed_lines'])[1])

    def test_empty_first_cell_cannot_hide_a_split_phrase(self):
        rows=[[['Group'],['Result']],[['Alpha'],['A measured response']],
              [[],['continued below']]]
        rs=[run(t,x,y) for y,pair in zip((0,20,35),rows)
            for x,parts in zip((0,120),pair) for t in parts]
        self.assertTrue(checks(rows,rs)['split_phrase']['fired'])
        rows[2][1]=['• Independent item'];rs[-1]['text']='• Independent item'
        self.assertFalse(checks(rows,rs)['split_phrase']['fired'])

    def test_continued_first_cell_is_not_a_new_entry(self):
        rs=[run('Name',0,0),run('Value',120,0),run('A long entry',0,20),
            run('12',120,20),run('with continuation',0,35)]
        rows=[[['Name'],['Value']],[['A long entry'],['12']],
              [['with continuation'],[]]]
        self.assertTrue(checks(rows,rs)['split_first_cell']['fired'])
        rows[2][0]=['lowerCaseVariable'];rs[4]['text']='lowerCaseVariable'
        self.assertFalse(checks(rows,rs)['split_first_cell']['fired'])
        # R1 (lane tablesub): a lower-case label beside its own value, under a
        # label with its own value, is a printed row, not a continuation.
        rs2=rs[:4]+[run('with continuation',0,35),run('24',120,35)]
        rows2=[[['Name'],['Value']],[['A long entry'],['12']],[['with continuation'],['24']]]
        self.assertFalse(checks(rows2,rs2)['split_first_cell']['fired'])
        rows[2][0]=['de Beta et al. (2014)'];rs[4]['text']='de Beta et al. (2014)'
        self.assertFalse(checks(rows,rs)['split_first_cell']['fired'])

    def test_unfinished_cell_checks_only_the_final_fragment(self):
        rs=[run('Name',0,0),run('Value',120,0),run('Alpha',0,20),run('non-',120,20)]
        rows=[[['Name'],['Value']],[['Alpha'],['non-']]]
        self.assertTrue(checks(rows,rs)['unfinished_cell']['fired'])
        for text in ('range (','range [','range {'):
            rows[1][1]=[text];rs[-1]['text']=text
            self.assertTrue(checks(rows,rs)['unfinished_cell']['fired'])
        rows[1][1]=['non-','linear'];rs[-1]['text']='non-';rs.append(run('linear',120,35))
        self.assertFalse(checks(rows,rs)['unfinished_cell']['fired'])
        rows[1][1]=['-'];self.assertFalse(checks(rows,rs)['unfinished_cell']['fired'])

    def test_surplus_unlabelled_rows_are_recorded(self):
        rows=[[['Name'],['Value']],[['Alpha'],['12']],[[],['24']],[['Beta'],['36']]]
        rs=[run(t,x,y) for y,row in zip((0,20,35,60),rows)
            for x,parts in zip((0,120),row) for t in parts]
        result=checks(rows,rs)['row_count']
        self.assertTrue(result['fired'])
        self.assertEqual(result['evidence'][0]['unlabelled_rows'],[3])

    def test_numeric_header_and_data_above_header(self):
        rs=[run(t,x,y) for y,row in [(0,('Alpha','12','24')),(20,('Beta','36','48'))]
            for x,t in zip((0,120,240),row)]
        rows=[[['Alpha'],['12'],['24']],[['Beta'],['36'],['48']]]
        self.assertTrue(checks(rows,rs)['header_data']['fired'])
        rows=[[['Name'],['Count'],['Rate']]]+rows
        rs.extend([run(t,x,40) for x,t in zip((0,120,240),('Name','Count','Rate'))])
        self.assertTrue(checks(rows,rs)['header_data']['fired'])

    def test_sample_sizes_in_arm_headers_are_not_data(self):
        rows=[[['A (n = 20)'],['B (n = 30)'],['P']],[['12'],['24'],['0.3']]]
        rs=[run(t,x,y) for y,row in zip((0,20),rows)
            for x,parts in zip((0,120,240),row) for t in parts]
        self.assertFalse(checks(rows,rs)['header_data']['fired'])
        for labels,expected in [(('E18','E20','P'),False),(('1e-8','2.4E+3','P'),True)]:
            rows=[[ [t] for t in labels],[['12'],['24'],['0.3']]]
            rs=[run(t,x,y) for y,row in zip((0,20),rows)
                for x,parts in zip((0,120,240),row) for t in parts]
            self.assertEqual(checks(rows,rs)['header_data']['fired'],expected)

    def test_data_above_a_later_panel_header_is_checked(self):
        rows=[[['Name'],['Value']],[['Alpha'],['12']],None,
              [['Kind'],['Count']],[['Beta'],['24']]]
        rs=[run(t,x,y) for y,pair in [(0,('Name','Value')),(20,('Alpha','12')),
                                    (80,('Kind','Count')),(60,('Beta','24'))]
            for x,t in zip((0,120),pair)]
        self.assertTrue(checks(rows,rs)['header_data']['fired'])

    def test_repeated_header_word_does_not_place_data_above_header(self):
        rows=[[['Name'],['Measurement type']],[['Alpha'],['Measurement','result']]]
        rs=[run('Name',0,0),run('Measurement',120,-20),run('type',120,0),
            run('Alpha',0,20),run('Measurement',120,20),run('result',120,35)]
        self.assertFalse(checks(rows,rs)['header_data']['fired'])

    def test_spanning_category_before_first_entry_is_not_a_surplus_data_row(self):
        rows=[[['Name'],['Result']],[[],['A category heading']],
              [['Alpha'],['12']],[['Beta'],['24']]]
        rs=[run(t,x,y) for y,row in zip((0,20,40,60),rows)
            for x,parts in zip((0,120),row) for t in parts]
        self.assertFalse(checks(rows,rs)['row_count']['fired'])

    def test_multilevel_header_units_are_not_a_split_data_phrase(self):
        rows=[[[],['Outcome']],[[],['Change']],[[],['(mm)']],
              [['Alpha'],['12']],[['Beta'],['24']]]
        rs=[run(t,x,y) for y,row in zip((0,20,40,60,80),rows)
            for x,parts in zip((0,120),row) for t in parts]
        self.assertFalse(checks(rows,rs)['split_phrase']['fired'])

    def test_repeated_statistical_units_inside_a_table_are_not_data(self):
        rows=[[['Age'],['A'],['B']],[['Average'],['12'],['24']],
              [[],['n (%)'],['n (%)']],[['Younger'],['10 (20)'],['20 (40)']]]
        rs=[run(t,x,y) for y,row in zip((0,20,40,60),rows)
            for x,parts in zip((0,120,240),row) for t in parts]
        result=checks(rows,rs)
        self.assertFalse(result['split_phrase']['fired'])
        self.assertFalse(result['row_count']['fired'])

    def test_three_header_tiers_end_at_a_segmented_rule(self):
        rows=[[[],[],['Later']],[['Treatment'],['Early'],[]],
              [[],[],['female']],[['Alpha'],['12'],['24']],[['Beta'],['36'],['48']]]
        rs=[run(t,x,y) for y,row in zip((0,15,30,60,80),rows)
            for x,parts in zip((0,120,240),row) for t in parts]
        rules=[dict(kind='rule',box_px=[x,50,x+95,51]) for x in (0,95,190)]
        result=checks(rows,rs,graphics=rules)
        self.assertFalse(result['row_count']['fired'])
        self.assertFalse(result['split_phrase']['fired'])
        self.assertTrue(checks(rows,rs)['row_count']['fired'])
        rows[1][1]=['72'];rs[2]['text']='72'
        self.assertTrue(checks(rows,rs,graphics=rules)['row_count']['fired'])

    def test_visible_column_gap_gates_in_every_rotation(self):
        for angle in (0,90,180,270):
            rs=[run(t,x,y) for y,pair in [(0,('Name','Value')),(20,('Alpha','12'))]
                for x,t in zip((0,120),pair)]
            for r in rs:r.update(angle=angle,box_px=c.frame(-angle)(r['box_px']))
            self.assertTrue(checks([[['Name Value']],[['Alpha 12']]],rs)['cell_contiguity']['fired'])

    def test_failed_grid_keeps_inferred_notes_inside_counted_payload(self):
        rs=[run(t,0,y) for y,t in [(0,'Header'),(20,'First row'),(40,'Last row'),(60,'Note line')]]
        it=dict(kind='table',page=1,caption='Table 1. Example',rows=[],
                notes=['Last row','Note line'],table_source=source(rs))
        rec=c.gate_tables([it],[dict(page=1,elements=rs)],[])[0]
        self.assertEqual(rec['printed_lines'],[r['text'] for r in rs])
        self.assertEqual(rec['notes'],[])
        self.assertEqual(rec['region_coverage']['missing_output_line_count'],0)

    def test_one_fused_data_cell_contradicts_an_established_column(self):
        rs=[run(t,x,y) for y,pair in [(0,('Name','Value')),(20,('Alpha','12')),(40,('Beta','24'))]
            for x,t in zip((0,120),pair)]
        rows=[[['Name'],['Value']],[['Alpha 12'],[]],[['Beta'],['24']]]
        self.assertTrue(checks(rows,rs)['cell_contiguity']['fired'])

    def test_sparse_rotated_island_retains_header_and_notes(self):
        for angle in (90,270):
            cap=run('Table 3 Clinical categories',0,0,120)
            rs=[cap]+[run(t,x,y,45) for y in (30,60,90,120)
                     for x,t in ((0,'Group'),(200,'Value'),(400,'Other'))]
            rs += [run('The explanatory note belongs to this table.',0,145,460)]
            for r in rs:r.update(angle=angle,box_px=c.frame(-angle)(r['box_px']),run_size_px=10)
            # Upright prose is outside the rotated island's native x span.
            prose=run('A long upright prose line outside the table.',500,0,400)
            p=dict(page=1,elements=rs+[prose],tables=[],floats=[],blocks=[])
            c.recover_rotated_table_lines([p],10)
            self.assertEqual(set(p['tables'][0]['members']),{r['id'] for r in rs[1:]})
            self.assertEqual(p['floats'][0]['_caption_ids'],[cap['id']])

    def test_ruled_seed_owns_interior_and_small_type_tail_before_prose(self):
        cap=run('Table 3 Example',0,-30,120)
        rs=[run(t,x,y) for y in (10,35,60,85) for x,t in ((0,'Label'),(120,'Value'))]
        for r in rs:r['run_size_px']=10
        # Body type only ten percent larger is still a real table boundary.
        prose=run('Following body text remains outside the table.',0,110,180);prose['run_size_px']=11
        t=dict(id='t',angle=0,members=[r['id'] for r in rs[:3]],box_px=[0,0,180,45])
        rules=[dict(kind='rule',box_px=[0,y,180,y+.1]) for y in (0,25)]
        p=dict(elements=[cap]+rs+[prose]+rules,tables=[t],blocks=[],
               floats=[dict(caption=cap['text'],blocks=['t'])])
        c.recover_table_small_type_tail(p,10)
        self.assertEqual(set(p['tables'][0]['members']),{r['id'] for r in rs})
        # Ordinary assembly can already collect omitted runs inside a
        # complete region; that alone is not evidence of a missing tail.
        interior_only=dict(t,box_px=[0,0,180,100])
        p['tables']=[interior_only]
        c.recover_table_small_type_tail(p,10)
        self.assertIs(p['tables'][0],interior_only)
        complete=dict(t,members=[r['id'] for r in rs],box_px=[0,0,180,100])
        p['tables']=[complete]
        note=run('An ordinary note after a complete table.',0,101,170);note['run_size_px']=8
        p['elements'].append(note)
        c.recover_table_small_type_tail(p,10)
        self.assertIs(p['tables'][0],complete)


if __name__=='__main__':unittest.main()
