"""Independent table-part ownership examples, including rotated pages."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('gate',Path(__file__).with_name('test_table_gate.py'))
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
c,run=gate.c,gate.run

class Parts(unittest.TestCase):
    def pages(self):
        bands=[dict(id=f'f{y}',kind='fill',box_px=[0,y,300,y+20]) for y in [20,40,120]]
        texts=[run(t,x,y,60) for y in [25,45,85,125,165] for x,t in [(0,'Left'),(120,'Middle'),(230,'Right')]]
        table=dict(id='t',angle=0,box_px=[0,20,300,180],members=[e['id'] for e in texts])
        cap=run('TABLE 7 (Continued)',0,0,200)
        first=dict(page=1,elements=[cap]+texts+bands+[dict(kind='rule',box_px=[0,180,300,180.2])],
                   tables=[table],floats=[dict(caption=cap['text'],blocks=['t'])],blocks=[])
        body=run('A following paragraph must remain ordinary prose.',0,220,290)
        second=dict(page=2,elements=copy.deepcopy(texts+bands)+[body],tables=[],floats=[],blocks=[])
        return [first,second],texts,body

    def test_missing_first_column_half_matches_row_geometry_in_every_frame(self):
        for angle in [0,90,180,270]:
            pages,texts,body=self.pages()
            for p in pages:
                for e in p['elements']:
                    e['box_px']=c.frame(-angle)(e['box_px'])
                    if e['kind']=='text':e['angle']=angle
                for t in p['tables']:
                    t['box_px']=c.frame(-angle)(t['box_px']);t['angle']=angle
            c.recover_table_column_parts(pages,10)
            t=pages[1]['tables'][0]
            self.assertEqual(set(t['members']),{e['id'] for e in texts})
            self.assertNotIn(body['id'],t['members'])
            self.assertEqual(pages[1]['copy_table_parts'][0]['row_count'],4)
            self.assertEqual(pages[1]['floats'][0]['caption'],'Table 7 (additional columns)')

    def test_different_row_geometry_is_not_a_part(self):
        pages,_,_=self.pages()
        for e in pages[1]['elements']:
            if e['kind']=='fill':e['box_px'][3]+=5
        c.recover_table_column_parts(pages,10)
        self.assertEqual(pages[1]['tables'],[])

    def test_new_caption_prevents_inferred_part(self):
        pages,_,_=self.pages()
        pages[1]['elements'].append(run('TABLE 8 Independent results',0,22,250))
        c.recover_table_column_parts(pages,10)
        self.assertEqual(pages[1]['tables'],[])

    def header_only_pages(self):
        pages,_,body=self.pages()
        for p in pages:
            p['elements']=[e for e in p['elements'] if e['kind']!='fill' or e['id']=='f20']
        return pages,body

    def test_header_only_half_keeps_numbers_and_wrapped_lines_in_every_frame(self):
        for angle in (0,90,180,270):
            pages,body=self.header_only_pages()
            cells=[e for e in pages[1]['elements'] if e['kind']=='text' and e is not body]
            cells[-1]['text']='13'
            wrapped=run('a wrapped cell',125,145,70)
            pages[1]['elements'].append(wrapped)
            for p in pages:
                for e in p['elements']:
                    e['box_px']=c.frame(-angle)(e['box_px'])
                    if e['kind']=='text':e['angle']=angle
                for t in p['tables']:
                    t['box_px']=c.frame(-angle)(t['box_px']);t['angle']=angle
            c.recover_table_column_parts(pages,10)
            t=pages[1]['tables'][0]
            self.assertEqual(set(t['members']),{e['id'] for e in cells+[wrapped]})
            self.assertNotIn(body['id'],t['members'])
            self.assertEqual(t['layout'],'unstructured')
            self.assertEqual(pages[1]['floats'][0]['caption'],'Table 7 (additional columns, page 2)')

    def test_matching_header_without_matching_data_rows_is_not_a_part(self):
        pages,_=self.header_only_pages()
        for e in pages[1]['elements']:
            if e['kind']=='text' and e['box_px'][1]==85:e['box_px'][1]+=12;e['box_px'][3]+=12
        c.recover_table_column_parts(pages,10)
        self.assertEqual(pages[1]['tables'],[])

    def test_caption_above_matching_header_is_not_a_facing_page_half(self):
        pages,_=self.header_only_pages()
        pages[1]['elements'].append(run('TABLE 8 Independent results',0,0,250))
        c.recover_table_column_parts(pages,10)
        self.assertEqual(pages[1]['tables'],[])

    def test_matching_header_above_prose_columns_is_not_a_part(self):
        pages,_=self.header_only_pages()
        pages[1]['elements']=[e for e in pages[1]['elements']
                             if e['kind']!='text' or e['box_px'][1]<=40 or e['box_px'][0]==0]
        c.recover_table_column_parts(pages,10)
        self.assertEqual(pages[1]['tables'],[])

    def test_printed_part_retains_neighbouring_but_distinct_baselines(self):
        rs=[run('An upper printed cell',0,20,100),run('A slightly lower cell',120,24.8,100)]
        source=c.table_source(rs,dict(elements=rs),preserve_run_lines=True)
        self.assertEqual([line['text'] for line in source['lines']],
                         ['An upper printed cell','A slightly lower cell'])

    def test_swallowed_float_is_partitioned_by_preceding_labels(self):
        for angle in [0,90,270]:
            caps=[run('TABLE '+str(i+1),0,100*i,80) for i in range(2)]
            rs=[run(t,x,y,35) for y in [30,50,130,150] for x,t in [(0,'Label'),(100,'Value')]]
            tables=[dict(id='t'+str(i),angle=0,box_px=[0,100*i+25,150,100*i+65],
                         members=[e['id'] for e in rs if 100*i<e['box_px'][1]<100*i+90]) for i in range(2)]
            blocks=[dict(id='b'+str(i),members=[e['id']],box_px=e['box_px']) for i,e in enumerate(caps)]
            p=dict(page=1,elements=caps+rs,blocks=blocks,tables=tables,
                   floats=[dict(caption='TABLE 2',blocks=['b1','t0','t1'],box_px=[0,25,150,165])],main_text={})
            for e in p['elements']:
                e['box_px']=c.frame(-angle)(e['box_px']);e['angle']=angle
            for e in p['blocks']+p['tables']+p['floats']:
                e['box_px']=c.frame(-angle)(e['box_px'])
                if e in p['tables']:e['angle']=angle
            result=c.table_float_regions(p,10)
            self.assertEqual(len(result['floats']),2)
            self.assertEqual([set(f['blocks']) & {'t0','t1'} for f in result['floats']],[{'t0'},{'t1'}])

class WrappedCells(unittest.TestCase):
    def test_body_classified_cell_stays_with_its_aligned_final_row(self):
        cap=run('TABLE 7',0,0,60)
        cells=[run(t,x,y,40) for y,labels in [(30,('Name','First','Second')),(60,('Alpha','One','Two')),(100,('Beta','Three','Four'))] for x,t in zip([0,120,240],labels)]
        wrapped=[run('Wrapped cell text',360,100,100),run('continues below',360,125,100),run('the short neighbours',360,150,100)]
        following=run('The following ordinary paragraph remains outside the table.',0,200,450)
        rs=[cap]+cells+wrapped+[following]
        for e in rs:e.update(run_size_px=10,size_px=10)
        blocks=[dict(id='caption',members=[cap['id']],box_px=cap['box_px']),
                dict(id='wrapped',members=[e['id'] for e in wrapped],box_px=c.hull(e['box_px'] for e in wrapped)),
                dict(id='body',members=[following['id']],box_px=following['box_px'])]
        meta=[dict(b,cls='main',order=i+1,lines=3 if b['id']=='wrapped' else 1,size_px=10,text='') for i,b in enumerate(blocks)]
        p=dict(page=1,elements=rs,tables=[dict(id='t',angle=0,box_px=[0,25,480,110],members=[e['id'] for e in cells])],
               blocks=blocks,floats=[dict(caption='TABLE 7',blocks=['caption','t'],box_px=[0,0,480,110])],
               region_box_px=[0,0,500,300],main_text=dict(blocks=meta,columns=[[0,500]]))
        # A final cell in another column establishes the final row and width.
        last=run('Last',470,100,20);last.update(run_size_px=10,size_px=10)
        p['elements'].append(last);p['tables'][0]['members'].append(last['id'])
        prose,floats,side=c.read_page(p,10,[])
        source=floats[0][5]['table_source']
        self.assertTrue({e['id'] for e in wrapped}<={x['id'] for l in source['lines'] for x in l['items']})
        self.assertEqual([b['lines'] for b in prose],[[following['text']]])

class ConflictingSeeds(unittest.TestCase):
    def test_offset_column_table_does_not_own_its_neighbours_rows_or_notes(self):
        for caption_inside in [False,True]:
            cap1=run('TABLE 1. Clinical results',0,0,140)
            cap2=run('TABLE 2. Observed patients',200,100,140)
            citation=run('Table 1. These results also appear in the ordinary discussion.',0,-120,150)
            left=[run(t,x,y,35) for y in [30,60,90,120,150,180] for x,t in [(0,'Label'),(100,'Value')]]
            right=[run(t,x,y,35) for y in [130,150,180] for x,t in [(200,'Item'),(300,'Count')]]
            for e in [cap1,cap2,citation]+left+right:e['run_size_px']=10
            broad=dict(id='broad',angle=0,box_px=[0,80 if caption_inside else 125,350,195],
                       members=[e['id'] for e in right+left[-4:]])
            narrow=dict(id='narrow',angle=0,box_px=[0,25,150,195],members=[e['id'] for e in left])
            p=dict(elements=[cap1,cap2,citation]+left+right,tables=[broad,narrow],blocks=[],
                   floats=[dict(caption=cap1['text'],blocks=['narrow'],box_px=[0,0,150,195]),
                           dict(caption=cap2['text'],blocks=['broad'],box_px=[0,80,350,195])],
                   main_text=dict(columns=[[0,150],[200,350]]))
            result=c.table_float_regions(p,10)
            self.assertEqual(len(result['tables']),2)
            self.assertEqual({frozenset(t['members']) for t in result['tables']},
                             {frozenset(e['id'] for e in left),frozenset(e['id'] for e in right)})
            self.assertTrue(all('discussion' not in f['caption'] for f in result['floats']))

    def test_page_wide_seed_is_split_into_independently_captioned_columns(self):
        caps=[run('TABLE '+str(i+1),x,0,100) for i,x in enumerate([0,200])]
        left=[run(t,x,y,40) for y in [30,60,90,120] for x,t in [(0,'Label'),(100,'Value')]]
        right=[run(t,x,y,40) for y in [30,60] for x,t in [(200,'Item'),(300,'Count')]]
        body=run('Ordinary prose below the shorter table must remain outside.',200,120,140)
        for e in caps+left+right:e['run_size_px']=10
        body['run_size_px']=14
        wide=dict(id='wide',angle=0,box_px=[0,-5,350,180],members=[e['id'] for e in caps+left+right+[body]])
        small=[dict(id='left',angle=0,box_px=[0,20,150,135],members=[e['id'] for e in left]),
               dict(id='right',angle=0,box_px=[200,20,350,75],members=[e['id'] for e in right])]
        p=dict(elements=caps+left+right+[body],tables=[wide]+small,blocks=[],
               floats=[dict(caption='TABLE 1',blocks=['wide','left','right'],box_px=wide['box_px'])],
               main_text=dict(columns=[[0,150],[200,350]]))
        result=c.table_float_regions(p,10)
        self.assertEqual(len(result['tables']),2)
        groups=[set(t['members']) for t in result['tables']]
        self.assertEqual(groups,[{e['id'] for e in left},{e['id'] for e in right}])
        self.assertNotIn(body['id'],set.union(*groups))

    def test_duplicate_grid_does_not_steal_the_following_narrow_list_or_prose(self):
        cap1=run('TABLE 1',0,0,60);cap2=run('TABLE 2',0,100,60)
        grid=[run(t,x,y,35) for y in [25,45,65] for x,t in [(0,'Label'),(100,'Value')]]
        listing=[run(t,10,y,100) for y,t in [(130,'A. First category'),(150,'B. Second category'),(170,'C. Final category')]]
        body=run('The next body paragraph starts with several ordinary words here.',0,210,150)
        beside=run('An independent body sentence beside the second caption.',180,100,150)
        for e in [cap1,cap2]+grid+listing+[body,beside]:e['run_size_px']=10
        tables=[dict(id='t'+str(i),angle=0,box_px=[0,20,340,80],members=[e['id'] for e in grid]) for i in range(2)]
        blocks=[dict(id='b1',members=[cap1['id']],box_px=cap1['box_px']),dict(id='b2',members=[cap2['id']],box_px=cap2['box_px'])]
        p=dict(elements=[cap1,cap2]+grid+listing+[body,beside],tables=tables,blocks=blocks,
               floats=[dict(caption='TABLE '+str(i+1),blocks=['b'+str(i+1),'t'+str(i)],box_px=[0,0,340,180]) for i in range(2)],
               main_text=dict(columns=[[0,160],[180,340]]))
        result=c.table_float_regions(p,10)
        self.assertEqual(len(result['tables']),2)
        groups=[set(t['members']) for t in result['tables']]
        self.assertFalse(groups[0]&groups[1])
        self.assertIn({e['id'] for e in listing},groups)
        self.assertTrue(all(body['id'] not in ms and beside['id'] not in ms for ms in groups))
        self.assertTrue(all('independent' not in f['caption'] for f in result['floats']))

if __name__=='__main__':unittest.main()
