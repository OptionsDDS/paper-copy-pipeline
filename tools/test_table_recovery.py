"""Region/ownership counterexamples for small and rotated tables."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('gate',Path(__file__).with_name('test_table_gate.py'))
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
c,run=gate.c,gate.run


def page(es,number=1):
    for e in es:
        if e['kind']=='text': e.update(size_px=10,run_size_px=10)
    return dict(page=number,elements=es,tables=[],floats=[],blocks=[],
                region_box_px=[0,0,600,600],main_text=dict(blocks=[],columns=[[0,600]]))


class Recovery(unittest.TestCase):
    def partial_header_page(self, header_left=100):
        cap=run('TABLE 9',420,0,55)
        title=run('A comparison',420,12,85)
        headers=[run(t,x,25,60) for x,t in [(110,'Reference'),(210,'Effect'),(310,'Quality')]]
        group=run('Device group',10,65,85)
        cells=[run(t,x,y,60) for y in [85,125,165]
               for x,t in [(10,'Device'),(110,'Study'),(210,'Small'),(310,'High')]]
        bands=[dict(id=f'f{y}:{x}',kind='fill',box_px=[x,y,x+100,y+20])
               for y in [80,160] for x in [0,100,200,300]]
        bands.append(dict(id='header',kind='fill',box_px=[header_left,0,400,50]))
        p=page([cap,title]+headers+[group]+cells+bands)
        p['tables']=[dict(id='grid',angle=0,box_px=[0,80,400,180],members=[e['id'] for e in cells])]
        for i,e in enumerate(headers+[group]+cells):
            b=dict(id='b'+str(i),members=[e['id']],box_px=e['box_px'])
            p['blocks'].append(b)
            p['main_text']['blocks'].append(dict(b,order=i,cls='main',lines=1,
                                                size_px=10,in_refs=True,text=e['text']))
        return p,headers,group,cells

    def test_partial_header_keeps_reference_cell_out_of_body(self):
        p,headers,group,cells=self.partial_header_page()
        prose,floats,side=c.read_page(p,10,[])
        self.assertEqual(prose,[])
        self.assertEqual(side,[])
        self.assertEqual(len(floats),1)
        self.assertEqual(' '.join(floats[0][2].split()),'Table 9. A comparison')
        source=floats[0][5]['table_source']
        self.assertEqual({x['id'] for line in source['lines'] for x in line['items']},
                         {e['id'] for e in headers+[group]+cells})

    def test_partial_header_requires_repeated_internal_cell_edge(self):
        p,_,_,_=self.partial_header_page(header_left=90)
        self.assertEqual(list(c.table_drawing_region(p,p['tables'][0],10)),[0,80,400,180])

    def test_partial_header_requires_nearby_repeated_full_width_bands(self):
        p,_,_,_=self.partial_header_page()
        p['elements']=[e for e in p['elements'] if not e['id'].startswith('f160:')]
        self.assertEqual(list(c.table_drawing_region(p,p['tables'][0],10)),[0,80,400,180])

    def test_side_caption_recovers_both_columns_and_wrapped_caption(self):
        cap=run('TABLE 9',0,0,45);title=run('A caption',50,0,50)
        tail=run('with a second line',0,16,100)
        cells=[run(t,x,y,40) for y in [5,25,45,65] for x,t in [(150,'Label'),(250,'Value')]]
        bands=[dict(id=f'f{y}:{x}',kind='fill',box_px=[x,y,x+100,y+20]) for y in [0,40] for x in [140,240]]
        prose=run('This following paragraph has several ordinary words.',140,100,200)
        p=page([cap,title,tail]+cells+bands+[prose])
        result=c.table_float_regions(p,10)
        self.assertEqual(set(result['tables'][0]['members']),{e['id'] for e in cells})
        self.assertEqual(result['floats'][0]['_caption_ids'],[cap['id'],title['id'],tail['id']])
        self.assertNotIn(prose['id'],result['tables'][0]['members'])

    def test_independent_captions_do_not_share_baseline_or_tails(self):
        a=run('TABLE 7',0,0,40);b=run('TABLE 8',130,0,40)
        tails=[run('First title',0,15,90),run('Other title',130,15,90)]
        p=page([a,b]+tails)
        self.assertEqual(c.table_caption_members(p,a,[0,0,100,100]),[a['id'],tails[0]['id']])
        self.assertEqual(c.table_caption_members(p,b,[130,0,230,100]),[b['id'],tails[1]['id']])

    def rotated_pages(self,angle=90):
        cap=run('Table 9. Observations',0,0,220)
        rows=[run(t,x,y,40) for y in range(30,211,30) for x,t in [(0,'Entry'),(100,'Data'),(200,'Result')]]
        first=page([cap]+rows)
        second=page(copy.deepcopy(rows),2)
        for p in (first,second):
            for e in p['elements']:
                e['box_px']=c.frame(-angle)(e['box_px']);e['angle']=angle
        return [first,second]

    def test_side_by_side_captioned_tables_keep_disjoint_full_widths(self):
        es=[];expected=[]
        for i,left in enumerate([0,240]):
            es += [run('TABLE '+str(i+1),left,0,55),run('A title',left+60,0,100)]
            cells=[run(t,left+x,y,60) for y in [30,50,70]
                   for x,t in [(5,'Label'),(110,'Description')]]
            es += cells;expected.append({e['id'] for e in cells})
            es += [dict(id=f'f{i}:{y}:{x}',kind='fill',box_px=[left+x,y,left+x+100,y+20])
                   for y in [25,65] for x in [0,100]]
        p=page(es);p['main_text']['columns']=[[0,200],[240,440]]
        prose,floats,side=c.read_page(p,10,[])
        self.assertEqual(len(floats),2)
        actual=[{x['id'] for line in f[5]['table_source']['lines'] for x in line['items']} for f in floats]
        self.assertEqual(actual,expected)
        self.assertFalse(actual[0]&actual[1])

    def test_rotated_caption_and_following_rows_keep_every_source(self):
        for angle in (90,270):
            pages=self.rotated_pages(angle);c.recover_rotated_table_lines(pages,10)
            self.assertEqual([len(p['tables']) for p in pages],[1,1])
            for p in pages:
                expected={e['id'] for e in p['elements'] if not e['text'].startswith('Table')}
                self.assertEqual(set(p['tables'][0]['members']),expected)
            self.assertEqual(pages[1]['floats'][0]['caption'],'Table 9 (continued)')

    def test_unaligned_following_page_is_not_a_continuation(self):
        pages=self.rotated_pages()
        for e in pages[1]['elements']:
            b=list(c.frame(90)(e['box_px']));b[0]+=40;b[2]+=40;e['box_px']=c.frame(-90)(b)
        c.recover_rotated_table_lines(pages,10)
        self.assertEqual(pages[1]['tables'],[])

    def test_ruled_grid_overrides_body_without_borrowing_page_background(self):
        cells=[run(t,x,y,30) for y,values in [(40,('Name','One','Two')),(80,('Alpha','12','24')),(120,('Beta','36','48'))]
               for x,t in zip([10,110,210],values)]
        body=run('A paragraph above the grid must stay outside.',0,0,300)
        rules=[dict(id='h'+str(y),kind='rule',box_px=[0,y,260,y]) for y in [65,105]]
        rules += [dict(id='v'+str(x),kind='rule',box_px=[x,30,x,145]) for x in [90,190]]
        p=page([body]+cells+rules+[dict(id='background',kind='fill',box_px=[0,0,600,600])])
        p['tables']=[dict(id='grid',angle=0,box_px=[0,30,260,145],members=[e['id'] for e in cells])]
        b=dict(id='body',members=[e['id'] for e in [body]+cells],box_px=[0,0,300,130])
        p['blocks']=[b];p['main_text']['blocks']=[dict(b,cls='main',order=1,lines=4,size_px=10)]
        prose,floats,side=c.read_page(p,10,[])
        source=floats[0][5]['table_source']
        self.assertEqual({x['id'] for l in source['lines'] for x in l['items']},{e['id'] for e in cells})
        self.assertEqual(prose[0]['lines'],[body['text']])
        p['elements']=[e for e in p['elements'] if e['kind']!='rule']
        self.assertFalse(c.ruled_numeric_table(p,p['tables'][0],10))

    def test_empty_part_reports_its_printed_frame(self):
        e=run('A real cell',20,20,50);p=page([e])
        for image_only in (False,True):
            it=dict(kind='table',page=1,id='empty',caption='Table 9. Example',rows=[],notes=[],
                    box=[0,0,100,100],table_source=c.table_source([],p),image_only=image_only)
            uncertain=[];rec=c.gate_tables([it],[p],uncertain)[0]
            self.assertIn('empty_output',rec['fired'])
            self.assertEqual(rec['region_coverage']['missing_frame_line_count'],1)
            self.assertIn('ERROR: empty table output',uncertain[0])
            self.assertNotIn('printed lines retained',uncertain[0])


if __name__=='__main__':unittest.main()
