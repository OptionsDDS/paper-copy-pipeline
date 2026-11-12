"""Independent cell-island, caption, and released-prose counterexamples."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('gate',Path(__file__).with_name('test_table_gate.py'))
g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
c,run=g.c,g.run


def page(texts, fills=(), tables=(), floats=(), columns=((0,200),(220,420))):
    for e in texts:e.update(run_size_px=10,size_px=10)
    return dict(page=2,elements=texts+list(fills),tables=list(tables),floats=list(floats),blocks=[],
                region_box_px=[0,0,440,600],main_text=dict(body_size_px=10,columns=list(columns),blocks=[]))


def shaded_rows(ys=(30,60,90), xs=(0,100,200)):
    rs=[run(t,x+5,y+5,40) for y in ys for x,t in zip(xs,('Label','12 mo','NR'))]
    fills=[dict(kind='fill',box_px=[x,y,x+100,y+20]) for y in ys for x in xs]
    return rs,fills


class Ownership(unittest.TestCase):
    def test_swallowed_recurring_footer_is_excluded_before_prose_release(self):
        pages=[]
        for number in range(1,4):
            footer=run('Journal issue information',5,570,160)
            p=page([footer]);p['page']=number
            if number<3:
                p['main_text']['furniture']=[dict(members=[footer['id']])]
            pages.append(p)
        c.recover_table_frame_furniture(pages)
        self.assertIn(pages[2]['elements'][0]['id'],c.table_furniture(pages[2]))

    def test_mixed_font_first_prose_line_stays_with_released_body(self):
        cap=run('TABLE 2',0,0,60);rs,fs=shaded_rows((20,40,60))
        prose=[run('A sentence about several species continues in this column.',0,y,195)
               for y in (110,125,140)]
        p=page([cap]+rs+prose,fs+[dict(kind='rule',box_px=[0,85,300,85])],
               [dict(id='t',angle=0,box_px=[0,20,300,155],members=[e['id'] for e in rs+prose])],
               [dict(caption='Table 2',blocks=['t'],box_px=[0,0,300,155])])
        p['_body_face']='regular';prose[0]['_faces']={'regular':5,'italic':5}
        for e in rs:e['run_size_px']=9
        c.bound_table_before_body(p,10)
        self.assertEqual(set(p['tables'][0]['members']),{e['id'] for e in rs})
        self.assertTrue({e['id'] for e in prose}<={m for b in p['blocks'] for m in b['members']})

    def test_recurring_footer_does_not_extend_a_nearby_table(self):
        rs,fs=shaded_rows((450,480,510))
        footer=run('Volume 12, Number 3, 2020',5,550,180)
        p=page(rs+[footer],fs)
        p['copy_conservation']=dict(excluded=[dict(id=footer['id'],
            reason='same text up to digits at the same position on 5 pages')])
        regions=list(c.shaded_cell_regions(p,10))
        self.assertEqual({e['id'] for e in regions[0][2]},{e['id'] for e in rs})

    def test_one_off_prose_fragments_do_not_widen_numeric_columns(self):
        rs=[run(t,x,y,40) for y in (30,60,90)
            for x,t in ((0,'Analyte'),(100,'12'),(200,'24'))]
        stray=[run('profile.',320,30,50),run('DISCUSSION',320,60,80)]
        regions=list(c.unruled_cell_regions(page(rs+stray),10))
        self.assertEqual({e['id'] for e in regions[0][2]},{e['id'] for e in rs})

    def test_short_body_sentence_stops_shaded_tail(self):
        rs,fs=shaded_rows()
        prose=[run('Patients exhibit inflammation consistent with infection',0,125,195),
               run('Other symptoms include pain and swelling',0,140,195)]
        regions=list(c.shaded_cell_regions(page(rs+prose,fs),10))
        self.assertEqual({e['id'] for e in regions[0][2]},{e['id'] for e in rs})

    def test_another_mixed_case_caption_cannot_enter_a_gate(self):
        rs,fs=shaded_rows()
        extra=run('Table 2 Other measurements',5,70,160)
        p=page(rs+[extra],fs)
        placed=(30,'table','Table 1 Measurements',[],[],
                dict(id='t',box=[0,30,300,110],table_source=c.table_source(rs,p)))
        self.assertEqual(c.recover_unowned_table_parts([p],[([], [placed], [])],10),set())

    def test_abbreviation_paragraph_does_not_destroy_complete_grid(self):
        rs,fs=shaded_rows();note=run('Abbreviations: NR, not reported.',5,125,250)
        p=page(rs+[note],fs)
        grid=[[['Label'],['Value']],[['Entry'],['12']]]
        placed=(30,'table','Table 1 Measurements',grid,[],
                dict(id='t',box=[0,30,300,110],table_source=c.table_source(rs,p)))
        per_page=[([], [placed], [])]
        self.assertEqual(c.recover_unowned_table_parts([p],per_page,10),set())
        self.assertEqual(per_page[0][1][0][3],grid)

    def test_continuation_furniture_does_not_rebuild_a_complete_grid(self):
        rs,fs=shaded_rows();note=run('Continued',205,125,50)
        p=page(rs+[note],fs)
        p['copy_conservation']=dict(excluded=[dict(id=note['id'],reason='standalone continuation at the column foot')])
        grid=[[['Label'],['Value']],[['Entry'],['12']]]
        placed=(30,'table','Table 1 Measurements',grid,[],
                dict(id='t',box=[0,30,300,110],table_source=c.table_source(rs,p)))
        per_page=[([], [placed], [])]
        self.assertEqual(c.recover_unowned_table_parts([p],per_page,10),set())
        self.assertEqual(per_page[0][1][0][3],grid)

    def test_furniture_counters_are_not_numeric_columns_but_headers_can_return(self):
        rs=[run(t,x,y,40) for y in (30,60,90)
            for x,t in ((0,str(y//30)),(100,'Analyte'),(200,'12'))]
        p=page(rs)
        p['copy_conservation']=dict(excluded=[dict(id=e['id'],reason='same text up to digits at the same position on 5 pages')
                                             for e in rs if e['box_px'][0]==0])
        self.assertEqual(list(c.unruled_cell_regions(p,10)),[])
        rs,fs=shaded_rows();p=page(rs,fs)
        p['copy_conservation']=dict(excluded=[dict(id=rs[0]['id'],reason='inside the recurring header band')])
        self.assertIn(rs[0],list(c.shaded_cell_regions(p,10))[0][2])

    def test_two_partial_tables_receive_distinct_replacement_ids(self):
        first,fills=shaded_rows();second,more=shaded_rows((220,250,280))
        groups=[first,second]
        tables=[dict(id='t'+str(i),angle=0,members=[e['id'] for e in rs[:3]],
                     box_px=c.hull(e['box_px'] for e in rs)) for i,rs in enumerate(groups)]
        floats=[dict(id='f'+str(i),caption='Table '+str(i+1)+' Measurements',blocks=[t['id']],
                     _caption_ids=[],box_px=t['box_px']) for i,t in enumerate(tables)]
        p=page(first+second,fills+more,tables,floats)
        placed=[(f['box_px'][1],'table',f['caption'],[],[],
                 dict(id=f['id'],box=f['box_px'],table_source=c.table_source(rs[:3],p)))
                for f,rs in zip(floats,groups)]
        pages=[p]
        self.assertEqual(c.recover_unowned_table_parts(pages,[([],placed,[])],10),{0})
        ids=[t['id'] for t in pages[0]['tables'] if t['id'].startswith('copy:loose:')]
        self.assertEqual(len(ids),2)
        self.assertEqual(len(set(ids)),2)

    def test_one_orphan_payload_with_two_islands_is_named_once_without_rebuilding(self):
        rs,fs=shaded_rows((30,60,90));other,more=shaded_rows((220,250,280))
        first=page([],[]);first['page']=1
        second=page(rs+other,fs+more)
        prior=(0,'table','Table 2 Measurements',[[['Label'],['Value']]],[],dict(id='prior',box=[0,0,300,300]))
        orphan=(30,'table','Table (no caption on page 2)',[[['Label'],['12']]],[],
                dict(id='t',box=[0,30,300,300],table_source=c.table_source(rs+other,second)))
        per_page=[([], [prior], []),([], [orphan], [])]
        self.assertEqual(c.recover_unowned_table_parts([first,second],per_page,10),set())
        self.assertEqual(per_page[1][1][0][2],'Table 2 (continued)')
        self.assertEqual(per_page[1][1][0][3],orphan[3])

    def test_inferred_part_top_is_its_printed_region_not_page_zero(self):
        a=[run('Alpha',0,30,40),run('12',100,30,20)]
        b=[run('Beta',0,130,40),run('24',100,130,20)]
        tables=[dict(id=tid,angle=0,box_px=c.hull(e['box_px'] for e in rs),members=[e['id'] for e in rs],
                     _copy_exact=True,layout='unstructured') for tid,rs in [('a',a),('b',b)]]
        floats=[dict(id=t['id'],blocks=[t['id']],caption='Table '+str(i+1)+' (continued)',
                     box_px=t['box_px'],_caption_ids=[]) for i,t in enumerate(tables)]
        p=page(a+b,[],tables,floats);p['_copy_parts_prepared']=True
        self.assertEqual([f[0] for f in c.read_page(p,10,[])[1]],[30,130])

    def test_unruled_measurements_need_three_repeated_columns(self):
        rs=[run(t,x,y,40) for y in (30,60,90) for x,t in ((0,'Analyte'),(100,'12 ± 2'),(200,'NR'))]
        rs += [run(t,x,10,40) for x,t in ((0,'Marker'),(100,'Healthy'),(200,'Treated'))]
        regions=list(c.unruled_cell_regions(page(rs),10))
        self.assertEqual(len(regions),1)
        self.assertEqual({e['id'] for e in regions[0][2]},{e['id'] for e in rs})

    def test_numbered_prose_and_two_column_bibliographies_are_not_numeric_islands(self):
        rs=[run(t,x,y,150) for y in (30,60,90) for x,t in ((0,'12. A complete sentence in a numbered list.'),(220,'24. Another complete bibliographic entry.'))]
        self.assertEqual(list(c.unruled_cell_regions(page(rs),10)),[])

    def test_side_caption_does_not_clip_header_with_missing_empty_first_cell(self):
        rs,fs=shaded_rows(xs=(200,300,400))
        cap=run('TABLE 2 Example',0,0,150)
        header=[run('First',305,5,40),run('Second',405,5,40)]
        fs.extend(dict(kind='fill',box_px=[x,0,x+100,20]) for x in (300,400))
        p=page([cap]+header+rs,fs)
        regions=list(c.shaded_cell_regions(p,10))
        self.assertEqual(len(regions),1)
        self.assertEqual({e['id'] for e in regions[0][2]},{e['id'] for e in header+rs})

    def test_staggered_baselines_still_form_three_cell_columns(self):
        rs,fs=shaded_rows()
        for e in rs:
            if e['box_px'][1]>40 and e['box_px'][0]<100:e['box_px'][1]+=5;e['box_px'][3]+=5
        regions=list(c.shaded_cell_regions(page(rs,fs),10))
        self.assertEqual({e['id'] for e in regions[0][2]},{e['id'] for e in rs})

    def test_prose_below_and_beside_is_not_owned(self):
        rs,fs=shaded_rows()
        prose=[run('The following sentence continues in the ordinary body column.',0,130,195),
               run('Another sentence on the next baseline is ordinary prose.',0,145,195),
               run('The neighbouring column is independent body prose.',320,35,195)]
        regions=list(c.shaded_cell_regions(page(rs+prose,fs),10))
        self.assertEqual({e['id'] for e in regions[0][2]},{e['id'] for e in rs})

    def test_short_chart_axis_labels_cannot_extend_a_table_tail(self):
        rs,fs=shaded_rows()
        axes=[run(t,x,y,20) for y in (125,145,165)
              for x,t in ((5,'2'),(105,'4'),(205,'6'))]
        p=page(rs+axes,fs,floats=[dict(id='fig',caption='Fig 2',
               box_px=[0,120,300,200],blocks=[],lettering=[e['id'] for e in axes])])
        regions=list(c.shaded_cell_regions(p,10))
        self.assertEqual({e['id'] for e in regions[0][2]},{e['id'] for e in rs})

    def test_shaded_prose_panels_do_not_establish_cells(self):
        rs=[run('Ordinary prose extends across the complete body column.',x,y+5,190)
            for y in (0,20,40) for x in (0,220)]
        fs=[dict(kind='fill',box_px=[x,0,x+200,70]) for x in (0,220)]
        self.assertEqual(list(c.shaded_cell_regions(page(rs,fs),10)),[])

    def test_two_mixed_case_caption_panels_split_regions(self):
        rs,fs=shaded_rows((30,60,90));others,more=shaded_rows((150,180,210))
        caps=[run('Table 2 First experiment',0,5,220),run('Table 3 Second experiment',0,125,230)]
        fs+=more+[dict(kind='fill',box_px=[0,y,300,y+20]) for y in (0,120)]
        regions=list(c.shaded_cell_regions(page(caps+rs+others,fs),10))
        self.assertEqual(len(regions),2)
        self.assertFalse({e['id'] for e in regions[0][2]} & {e['id'] for e in regions[1][2]})

    def test_empty_band_does_not_bridge_distinct_parts(self):
        rs,fs=shaded_rows((0,30,60));other,more=shaded_rows((220,250,280))
        fs+=more+[dict(kind='fill',box_px=[0,100,300,210])]
        self.assertEqual(len(list(c.shaded_cell_regions(page(rs+other,fs),10))),2)

    def test_tail_label_follows_a_tall_shaded_row(self):
        rs,fs=shaded_rows((30,))
        for f in fs:f['box_px'][3]=120
        # Additional aligned baseline witnesses table columns in the tall row.
        rs += [run(t,x,60,40) for x,t in ((5,'Entry'),(105,'24 mo'),(205,'NR'))]
        tail=[run('Next study',5,125,50),run('continued label',5,140,75)]
        regions=list(c.shaded_cell_regions(page(rs+tail,fs),10))
        self.assertTrue({e['id'] for e in tail}<={e['id'] for e in regions[0][2]})

    def test_body_majority_cannot_set_cell_type_and_is_released_in_column_order(self):
        cap=run('TABLE 2',0,0,60);rs,fs=shaded_rows((20,40,60))
        prose=[run('The body sentence continues across the full printed column.',x,y,195)
               for x in (0,220) for y in range(110,260,15)]
        p=page([cap]+rs+prose,fs+[dict(kind='rule',box_px=[0,85,300,85])],
               [dict(id='t',angle=0,box_px=[0,20,420,280],members=[e['id'] for e in rs+prose])],
               [dict(caption='Table 2',blocks=['t'],box_px=[0,0,420,280])])
        for e in rs:e['run_size_px']=9
        # The closing border spans the table frame.
        p['elements'][-1]['box_px'][2]=420
        c.bound_table_before_body(p,10)
        self.assertEqual(set(p['tables'][0]['members']),{e['id'] for e in rs})
        bs=p['main_text']['blocks']
        self.assertEqual(len(bs),2)
        self.assertLess(bs[0]['order'],bs[1]['order'])
        self.assertEqual({m for b in p['blocks'] for m in b['members']},{e['id'] for e in prose})


if __name__=='__main__':unittest.main()
