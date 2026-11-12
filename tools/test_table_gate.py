"""Independent counterexamples for source-based gating; no corpus strings or IDs."""
import importlib.util,unittest,copy
from pathlib import Path
spec=importlib.util.spec_from_file_location('copy_paper',Path(__file__).resolve().parents[1] / 'copy_paper.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
def run(t,x,y,w=40):return dict(id=f'{x}:{y}:{t}',kind='text',text=t,box_px=[x,y,x+w,y+10],angle=0,line=y,char_ids=[])
def source(rs,graphics=()):return c.table_source(rs,dict(elements=rs+list(graphics)))
def checks(rows,rs,cap='Table 1. Measurements',notes=(),graphics=()):return c.table_structure_checks(rows,source(rs,graphics),cap,notes)
class Gate(unittest.TestCase):
 def test_names_after_sparse_ordinal_column_have_ten_starts(self):
  names=['ABC'+str(i) for i in range(10)]
  rs=[run('No.',0,0,10),run('Name',40,0),run('Result',120,0)]+[r for i,n in enumerate(names) for r in [run(n,40,20+i*20),run(str(i+20),120,20+i*20)]]
  rows=[[['No.'],['Name'],['Result']],[['1'],names,[str(i+20) for i in range(10)]]]
  result=checks(rows,rs)['first_column_entries']
  self.assertTrue(result['fired']);self.assertEqual(result['evidence'][0]['entry_count'],10)
 def test_identifiers_in_independent_rows_are_valid(self):
  rs=[r for i in range(4) for r in [run('ABC'+str(i),0,i*20),run(str(i+20),120,i*20)]]
  self.assertFalse(checks([[['ABC'+str(i)],[str(i+20)]] for i in range(4)],rs)['first_column_entries']['fired'])
 def test_caption_phrase_below_top_border_is_a_header(self):
  phrase='Counts recorded during the trial'
  rs=[run(phrase,0,20,150),run('Group',200,20)]
  self.assertFalse(checks([[[phrase],['Group']]],rs,cap='Table 1. '+phrase,graphics=[dict(kind='rule',box_px=[0,10,250,10])])['header_caption']['fired'])
 def test_unstructured_table_is_never_silent(self):
  result=c.table_structure_checks([],source([run('Alpha',0,0)]),'Table 1. Example',[])
  self.assertTrue(result['missing_grid']['fired'])
 def test_column_sequence_list_is_gated(self):
  rs=[run(t,x,y) for x,labels in [(0,['Alpha','Beta','Gamma']),(120,['12','24','36'])] for y,t in zip([0,20,40],labels)]
  src=source(rs);src.update(output_run_ids=[r['id'] for r in rs],faithful_list=True)
  self.assertTrue(c.table_structure_checks([],src,'Table 1. Example',[])['cell_contiguity']['fired'])
  src['output_run_ids']=[r['id'] for r in sorted(rs,key=lambda r:(r['box_px'][1],r['box_px'][0]))]
  self.assertFalse(any(v['fired'] for v in c.table_structure_checks([],src,'Table 1. Example',[]).values()))
 def test_supplemental_segmented_borders_exclude_references(self):
  cap=run('SUPPLEMENTARY TABLE S2 Sample list',0,0,230)
  rs=[run(t,x,y,30) for y in [30,50,70] for x,t in [(0,'ABC'+str(y)),(100,'Description'),(200,'Source')]]
  refs=run('References',0,110,80)
  rules=[dict(id=f'r{x}:{y}',kind='rule',box_px=[x,y,x+80,y+1]) for y in [20,90] for x in [0,80,160]]
  blocks=[dict(id='b'+r['id'],members=[r['id']],box_px=r['box_px']) for r in [cap]+rs+[refs]]
  p=dict(page=1,elements=[cap]+rs+[refs]+rules,blocks=blocks,tables=[dict(id='t',angle=0,box_px=[0,20,240,120],members=[r['id'] for r in rs]+[refs['id']])],floats=[],region_box_px=[0,0,250,500],main_text=dict(blocks=[]))
  c.recover_supplemental_tables([p],10)
  self.assertEqual(p['floats'][0]['caption'],'Supplementary Table S2. Sample list')
  self.assertEqual(set(p['tables'][0]['members']),{r['id'] for r in rs})
  self.assertTrue(p['tables'][0]['_copy_exact'])
 def test_orphan_caption_stops_before_body_paragraph(self):
  cap=run('TABLE 1 Example',0,0,100)
  rs=[run('Left',0,20),run('Right',120,20),run('Value',0,40),run('12',120,40),run('The next body paragraph starts with several ordinary words here.',0,60,200)]
  for e in rs+[cap]: e['run_size_px']=10
  p=dict(elements=[cap]+rs,main_text=dict(columns=[[0,200]]),floats=[],blocks=[])
  self.assertEqual(c.caption_fallback_runs(p,cap,[cap['id']],10),[r['id'] for r in rs[:4]])
 def test_rule7_faithful_list_is_not_reclaimed_as_a_missing_grid(self):
  cap=run('TABLE 1 (Continued)',0,0,130);rs=[run('Independent item',0,y,100) for y in [20,40,60]]
  p=dict(elements=[cap]+rs,tables=[],blocks=[],floats=[],main_text=dict(captioned_lists=[dict(members=[r['id'] for r in [cap]+rs])]))
  self.assertEqual(c.table_float_regions(p,10)['floats'],[])
 def test_orphan_side_caption_uses_repeated_row_bands(self):
  cap=run('TABLE 1 Example',250,0,100)
  rs=[run(t,x,y,30) for y in [5,25,45] for x,t in [(0,'Label'),(120,'Value')]]
  bands=[dict(kind='fill',box_px=[x,y,x+115,y+20]) for y in [0,40] for x in [0,115]]
  p=dict(elements=[cap]+rs+bands,main_text=dict(columns=[[0,200],[250,400]]),floats=[],blocks=[])
  self.assertEqual(set(c.caption_fallback_runs(p,cap,[cap['id']],10)),{r['id'] for r in rs})
 def test_empty_fallback_leaves_existing_orphan_table_attachment_available(self):
  cap=run('TABLE 1 Example',250,0,100);rs=[run('Value',0,100)]
  p=dict(elements=[cap]+rs,main_text=dict(columns=[[0,200],[250,400]]),floats=[],blocks=[],
         tables=[dict(id='table',angle=0,box_px=[0,100,200,200],members=[r['id'] for r in rs])])
  self.assertEqual(c.table_float_regions(p,10)['floats'],[])
 def test_fallback_does_not_steal_loose_headers_from_an_orphan_grid(self):
  cap=run('TABLE 1',0,0,60);rs=[run('Heading',0,20),run('Entry',0,40)]
  p=dict(elements=[cap]+rs,main_text=dict(columns=[[0,200]]),floats=[],blocks=[],
         tables=[dict(id='table',angle=0,box_px=[300,100,500,200],members=[])])
  self.assertEqual(c.table_float_regions(p,10)['floats'],[])
 def test_font_change_does_not_turn_a_body_reference_into_an_orphan_caption(self):
  cap=dict(run('Table 2 describes the observations in this study',0,0,200),label_font=True)
  p=dict(elements=[cap,run('More body text',0,20)],tables=[],blocks=[],floats=[],main_text={})
  self.assertEqual(c.table_float_regions(p,10)['floats'],[])
 def test_touching_header_cells_recover_all_columns_in_sideways_frames(self):
  for angle in [90,270]:
   cap=run('TABLE 1 (Continued)',0,0,80)
   rs=[run(t,x,y,30) for y in [25,45,65] for x,t in [(5,'Label'),(105,'Value'),(205,'Other')]]
   fills=[dict(id='f'+str(x),kind='fill',box_px=[x,20,x+100,40]) for x in [0,100,200]]
   es=[dict(e,angle=angle,box_px=c.frame(-angle)(e['box_px'])) for e in [cap]+rs+fills]
   p=c.table_float_regions(dict(elements=es,tables=[],blocks=[],floats=[],main_text={}),10)
   self.assertEqual(set(p['tables'][0]['members']),{r['id'] for r in rs})
 def test_table_reference_inside_figure_caption_stays_in_that_caption(self):
  cap=run('Table 1.',0,0,50);b=dict(id='caption',members=[cap['id']],box_px=cap['box_px'])
  f=dict(caption='Figure 2. Measurements are listed in Table 1.',blocks=['caption'],box_px=cap['box_px'])
  p=dict(elements=[cap],tables=[],blocks=[b],floats=[f],main_text={})
  self.assertEqual(c.table_float_regions(p,10)['floats'],[f])
 def test_shaded_fallback_stops_at_its_final_row_and_keeps_small_notes(self):
  cap=run('TABLE 1 Example',0,0,100)
  rs=[run(t,x,y,30) for y in [25,45,65] for x,t in [(5,'Label'),(105,'Value')]]
  note=dict(run('A small explanatory note',0,82,190),run_size_px=8)
  body=dict(run('A following body paragraph has several ordinary words here.',0,98,200),run_size_px=10)
  fills=[dict(kind='fill',box_px=[x,y,x+100,y+20]) for y in [20,40,60] for x in [0,100]]
  rules=[dict(kind='rule',box_px=[0,y,200,y+.1]) for y in [15,80]]
  p=dict(elements=[cap]+rs+[note,body]+fills+rules)
  self.assertEqual(set(c.caption_shaded_lines(p,cap,10)),{r['id'] for r in rs+[note]})
  p['elements']=[cap]+rs+fills[:2]+rules
  self.assertEqual(c.caption_shaded_lines(p,cap,10),[])
 def test_existing_grid_inference_precedes_shaded_line_fallback(self):
  cap=run('TABLE 1 Example',0,0,100)
  rs=[run(t,x,y,30) for y in [25,45,65] for x,t in [(5,'Label'),(105,'Value')]]
  fills=[dict(id='f'+str(y),kind='fill',box_px=[0,y,200,y+20]) for y in [20,40,60]]
  rules=[dict(id='r'+str(y),kind='rule',box_px=[0,y,200,y+.1]) for y in [15,40,80]]
  p=c.table_float_regions(dict(elements=[cap]+rs+fills+rules,tables=[],blocks=[],floats=[],main_text={}),10)
  self.assertNotEqual(p['tables'][0].get('layout'),'unstructured')
 def test_valid_wrapped_cells(self):
  rs=[run('Name',0,0),run('Result',100,0),run('Smith and',0,20),run('12',100,20),run('Jones',0,35),run('(2020)',0,50)]
  rows=[[['Name'],['Result']],[['Smith and','Jones','(2020)'],['12']]]
  self.assertFalse(any(v['fired'] for v in checks(rows,rs).values()))
 def test_separate_numbered_entries(self):
  rs=[run('1. First',0,0),run('2. Second',0,20)]
  self.assertTrue(checks([[['1. First','2. Second']]],rs)['first_column_entries']['fired'])
 def test_author_year_entries(self):
  rs=[run('Able (2001)',0,0),run('de Boer (2002)',0,20)]
  self.assertTrue(checks([[['Able (2001)','de Boer (2002)']]],rs)['first_column_entries']['fired'])
 def test_numeric_total_is_a_row(self):
  rs=[run('12',0,0),run('30 (total)',0,20)]
  self.assertTrue(checks([[['12','30 (total)']]],rs)['first_column_entries']['fired'])
 def test_fused_columns(self):
  rs=[run('Label',0,0),run('Value',100,0),run('Alpha',0,20),run('12',100,20)]
  cs=checks([[['Label Value']],[['Alpha 12']]],rs)
  self.assertTrue(cs['cell_contiguity']['fired']);self.assertTrue(cs['column_count']['fired'])
 def test_list_label_gap_is_not_a_column(self):
  rs=[run('1.1',0,0,10),run('First',30,0),run('1.2',0,20,10),run('Second',30,20)]
  cs=checks([[['1.1 First']],[['1.2 Second']]],rs)
  self.assertFalse(any(v['fired'] for v in cs.values()))
 def test_parenthesized_statistic_is_one_cell(self):
  rs=[run('1.2',0,0,10),run('(0.3)',30,0),run('2.4',0,20,10),run('(0.6)',30,20)]
  cs=checks([[['Mean'],['SD']],[['1.2 (0.3)']],[['2.4 (0.6)']]],rs)
  self.assertFalse(cs['cell_contiguity']['fired'])
 def test_header_crossing_drawn_boundary(self):
  rs=[run('Name',0,0),run('Count',100,0),run('Alpha',0,20),run('12',100,20)]
  cs=checks([[['Name','Alpha'],['Count','12']]],rs,graphics=[dict(kind='fill',box_px=[0,-2,150,14])])
  self.assertTrue(cs['header_fragments']['fired'])
 def test_caption_tail_in_header(self):
  tail='the second year of observation.'
  rs=[run(tail,0,0,120),run('Count',100,20)]
  cs=checks([[[tail],[]],[[],['Count']]],rs,cap='Table 1. Events during')
  self.assertTrue(cs['header_caption']['fired'])
 def test_caption_text_repeated(self):
  tail='Participants at the last visit'
  self.assertTrue(checks([[[tail]]],[run(tail,0,0)],cap='Table 1. '+tail)['header_caption']['fired'])
 def test_rotated_source_preserves_order(self):
  rs=[run('Left',0,0),run('Right',100,0),run('Next',0,20)]
  for ang in [0,90,180,270]:
   turned=[dict(r,angle=ang,box_px=c.frame(-ang)(r['box_px'])) for r in rs]
   self.assertEqual([l['text'] for l in source(turned)['lines']],['Left Right','Next'])
 def test_duplicate_geometry_and_missing_caption(self):
  rs=[run('Alpha',0,0),run('Beta',0,20),run('Gamma',0,40)]
  src=source(rs); label=run('TABLE 3',0,-30)
  items=[dict(kind='table',caption=cap,page=1,rows=[[[r['text']]] for r in rs],notes=[],table_source=copy.deepcopy(src)) for cap in ['Table 1. Results','Table (no caption)']]
  saved=copy.deepcopy(items);records=c.gate_tables(items,[dict(page=1,elements=rs+[label])],[])
  self.assertTrue(all(r['checks']['duplicate_cells']['fired'] for r in records))
  self.assertTrue(records[1]['checks']['unassigned_caption']['fired'])
  self.assertEqual(items[0]['rows'],saved[0]['rows'])
 def test_repeated_values_on_other_pages_not_duplicates(self):
  rs=[run('1',0,0),run('2',0,20),run('3',0,40)]
  items=[dict(kind='table',caption=f'Table {p}. Counts',page=p,rows=[[[r['text']]] for r in rs],notes=[],table_source=source(rs)) for p in [1,2]]
  recs=c.gate_tables(items,[dict(page=p,elements=rs) for p in [1,2]],[])
  self.assertFalse(any(r['checks']['duplicate_cells']['fired'] for r in recs))
 def test_category_heading_is_not_the_previous_rows_second_label(self):
  rs=[run('Measure',0,0),run('12',100,0),run('Category',0,20),run('Category description',0,40),run('Result',100,40)]
  rows=[[['Measure','Category'],['12']],[['Category description'],['Result']]]
  self.assertTrue(checks(rows,rs)['first_column_entries']['fired'])
 def test_identical_data_and_note_lines_are_not_all_removed(self):
  src=source([run('Same text',0,0),run('Same text',0,20)])
  self.assertEqual(len(c.table_printed_lines(src,['Same text'])),1)
 def test_spanning_caption_tail_is_not_nine_independent_headers(self):
  tail='the final period of observation'
  rs=[run(tail,0,0,180),run('Group',0,25),run('Value',120,25)]
  cs=checks([[[tail] for _ in range(3)],[['Group'],['Value'],[]]],rs,cap='Table 7. Measurements during')
  self.assertTrue(cs['header_caption']['fired'])
 def test_internal_header_does_not_turn_lower_cells_into_notes(self):
  rs=[run(t,x,y) for y,labels in [(0,('First','Second')),(20,('Alpha','Beta')),(40,('Lower','Panel')),(60,('Gamma','Delta')),(80,('Epsilon','Zeta'))] for x,t in zip([0,120],labels)]
  borders=[dict(kind='rule',box_px=[0,y,170,y+.2]) for y in [-5,15,35,55,95]]
  notes=['Gamma Delta','Epsilon Zeta']
  src=source(rs,borders)
  it=dict(kind='table',page=1,caption='Table 7. Applications',rows=[[['First'],['Second']],[['Alpha'],['Beta']],[['Lower'],['Panel']]],notes=notes,table_source=src)
  rec=c.gate_tables([it],[dict(page=1,elements=rs+borders)],[])[0]
  self.assertIn('note_cells',rec['fired']);self.assertEqual(rec['notes'],[])
  self.assertEqual(len(rec['printed_lines']),5)
  self.assertEqual(rec['region_coverage']['missing_output_line_count'],0)
 def test_real_notes_below_closing_rule_stay_notes(self):
  rs=[run('Group',0,0),run('Value',120,0),run('Alpha',0,20),run('12',120,20),run('Note: first definition',0,60,70),run('second definition',120,60,70),run('another definition',0,80,70),run('final definition',120,80,70)]
  cs=checks([[['Group'],['Value']],[['Alpha'],['12']]],rs,notes=['Note: first definition second definition','another definition final definition'],graphics=[dict(kind='rule',box_px=[0,40,200,40.2])])
  self.assertFalse(cs['note_cells']['fired'])
 def test_region_audit_finds_an_omitted_interior_line(self):
  rs=[run('First',0,0),run('Omitted',0,20),run('Last',0,40)]
  it=dict(kind='table',page=1,caption='Table 7. Example',rows=[],notes=[],table_source=source([rs[0],rs[2]]))
  rec=c.gate_tables([it],[dict(page=1,elements=rs)],[])[0]
  self.assertEqual(rec['region_coverage']['missing_frame_line_count'],1)
  self.assertEqual(rec['region_coverage']['missing_frame_lines'][0]['ids'],[rs[1]['id']])
 def test_two_same_text_baselines_are_not_duplicate_output(self):
  rs=[run('Repeated value',0,y) for y in [0,20]]
  it=dict(kind='table',page=1,caption='Table 7. Example',rows=[],notes=[],table_source=source(rs))
  rec=c.gate_tables([it],[dict(page=1,elements=rs)],[])[0]
  self.assertEqual(rec['region_coverage']['duplicate_output_line_count'],0)
  self.assertEqual(rec['region_coverage']['missing_output_line_count'],0)
if __name__=='__main__':unittest.main()
