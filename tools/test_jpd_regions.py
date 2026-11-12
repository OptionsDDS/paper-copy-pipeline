"""Region ownership and drop-initial regressions, independent of any paper text."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
boxer=module('jpd_boxer',ROOT/'standalone/element_boxer_sc.py')
copy=module('jpd_copy',ROOT/'copy_paper.py')

def run(i,text,x,y,w=180,size=10):
    return dict(id=f'run:{i}',kind='text',line=i,angle=0,text=text,
                box_px=[x,y,x+w,y+size],size_px=size,run_size_px=size)

class Regions(unittest.TestCase):
    def test_roman_caption_is_distinct_from_sentence(self):
        self.assertTrue(boxer.is_caption_label('Table XIV. Measurements'))
        self.assertFalse(boxer.is_caption_label('Table IV shows the measurements'))
        self.assertEqual(copy.label_fix('TABLE IX. Measurements'),'Table IX. Measurements')

    def test_header_above_saved_border_still_belongs_to_table(self):
        es=[run(1,'Table IV. Measurements',10,10),run(2,'Measure',10,25,40,7),
            run(3,'Value',150,25,30,7),run(4,'First',10,45,40),run(5,'12',150,45,20),
            run(6,'Second',10,60,40),run(7,'34',150,60,20)]
        es += [dict(id=f'rule:{i}',kind='rule',box_px=[10,y,210,y+1]) for i,y in enumerate((35,75))]
        ts=boxer.bounded_caption_tables(es,[],[])
        self.assertEqual(len(ts),1)
        self.assertTrue({'run:2','run:3'}<=set(ts[0]['members']))

    def test_arabic_fallback_preserves_an_existing_grid(self):
        es=[run(1,'Table 12. Measurements',10,10),run(2,'First',10,35,40),run(3,'12',150,35,20),
            run(4,'Second',10,50,40),run(5,'34',150,50,20)]
        es += [dict(id=f'rule:{i}',kind='rule',box_px=[10,y,210,y+1]) for i,y in enumerate((25,65))]
        self.assertEqual(boxer.bounded_caption_tables(es,[],[]),[])
        ts=boxer.bounded_caption_tables(es,[],[],fallback=True)
        self.assertEqual(len(ts),1)
        self.assertEqual(boxer.bounded_caption_tables(es,[],ts,fallback=True),[])

    def test_border_owned_letters_exclude_adjacent_prose_and_next_caption(self):
        es=[run(1,'Table II. Measurements',220,10),run(2,'Item',220,35,40),run(3,'12',350,35,20),
            run(4,'Next',220,50,40),run(5,'34',350,50,20),
            run(6,'Table III. More measurements',220,90),run(7,'Other',220,115,40),run(8,'56',350,115,20),
            run(9,'Last',220,130,40),run(10,'78',350,130,20)]
        for i,y in enumerate((25,65,105,145)):
            es.append(dict(id=f'rule:{i}',kind='rule',box_px=[220,y,420,y+1]))
        for i,y in enumerate((35,50,115,130),20):es.append(run(i,'Justified body text beside the table.',10,y,190))
        blocks=[];tables=[]
        recovered=boxer.bounded_caption_tables(es,blocks,tables)
        self.assertEqual(len(recovered),2)
        self.assertEqual([{m for m in t['members'] if m.startswith('run:')} for t in recovered],
                         [{'run:2','run:3','run:4','run:5'},{'run:7','run:8','run:9','run:10'}])
        self.assertTrue(all(t['layout']=='unstructured' for t in recovered))

    def test_mixed_front_block_reserves_summary_only(self):
        es=[run(1,'A scientific title',10,10,size=18),run(2,'Ada Example',10,35),
            run(3,'University of Example, City',10,50),run(4,'Statement of problem. Some uncertainty.',10,75),
            run(5,'Purpose. Test the hypothesis.',10,90),run(6,'Results. Measurements increased.',10,105),
            run(7,'Conclusions. The evidence supports it.',10,120)]
        block=dict(id='block:1',members=[e['id'] for e in es],box_px=[10,10,190,130])
        page=dict(runs=es,blocks=[block],d=dict(blocks=[block.copy()]))
        boxer.split_runin_abstract(page,10)
        self.assertEqual(len(page['blocks']),2)
        abstract=next(b for b in page['blocks'] if b['runin_abstract'])
        self.assertEqual(abstract['members'],['run:4','run:5','run:6','run:7'])

    def test_existing_abstract_panel_keeps_heading_and_keywords_in_order(self):
        es=[run(1,'Abstract',10,10),run(2,'Background: Some uncertainty.',10,25),
            run(3,'Methods: A measurement.',10,40),run(4,'Results: Evidence.',10,55),
            run(5,'Conclusions: A result.',10,70),run(6,'KEYWORDS',10,85,size=8),
            run(7,'measurement, evidence',10,100,size=8)]
        block=dict(id='block:1',members=[e['id'] for e in es],box_px=[10,10,190,110])
        page=dict(runs=es,blocks=[block],d=dict(blocks=[block.copy()]))
        boxer.split_runin_abstract(page,10)
        self.assertEqual(page['blocks'],[block])
        self.assertEqual(len(page['d']['blocks']),1)

class Initials(unittest.TestCase):
    def test_tall_initial_unmixes_two_character_baselines(self):
        def char(text,x,y,size=10):return dict(text=text,x0=x,y0=y-size*.7,x1=x+5,y1=y,
                                             origin=(x,y),adv_x1=x+5,size=size,font='Example')
        cap=char('S',0,30,30)
        first=[char(c,6+i*5,30) for i,c in enumerate('ample')]
        second=[char(c,i*5,42) for i,c in enumerate('next')]
        e=run(1,'nSaemxtple',0,9,35);e['_chars']=[second[0],cap]+first+second[1:]
        rows=copy.prose_text_rows([e],{})
        self.assertEqual([copy.prose_row(row,{})[0] for row in rows],['Sample','next'])
        self.assertEqual(sum(len(r['_chars']) for row in rows for r in row),10)

    def test_ocr_initial_moves_from_later_line_without_reordering(self):
        es=[dict(run(1,'ample starts here',35,10),size_px=10,baseline=18),
            dict(run(2,'and continues here',35,22),size_px=10,baseline=30),
            dict(run(3,'S The following sentence.',5,6,210),size_px=10,baseline=42)]
        es[2]['box_px'][3]=50
        out=copy.scan_drop_caps(es)
        self.assertEqual(out[0]['text'],'Sample starts here')
        self.assertEqual(out[1]['text'],'and continues here')
        self.assertEqual(out[2]['text'],'The following sentence.')
        self.assertEqual(len(copy.scan_rows(out)),3)


class ImageCaptions(unittest.TestCase):
    def test_styled_bare_number_and_image_geometry_own_caption(self):
        a=run(1,'7 A measured feature appears here.',20,80,180)
        a['font_spans']=[dict(start=0,end=1,font='Bold'),dict(start=2,end=34,font='Body')]
        b=run(2,'Its caption continues on this line.',20,95,180)
        im=dict(id='image:1',kind='image',box_px=[20,10,200,75])
        p=dict(elements=[a,b,im],blocks=[dict(id='block:1',members=[a['id'],b['id']])],floats=[])
        copy.numbered_image_captions(p,10)
        self.assertEqual(len(p['floats']),1)
        self.assertTrue(p['floats'][0]['caption'].startswith('Fig. 7. A measured'))
        self.assertEqual(p['floats'][0]['_caption_ids'],['run:1','run:2'])
        self.assertEqual(a['text'],'7 A measured feature appears here.')
        copy.numbered_image_captions(p,10)
        self.assertEqual(len(p['floats']),1)

    def test_list_number_below_image_is_not_a_caption(self):
        a=run(1,'7. A numbered item appears here.',20,80,180)
        a['font_spans']=[dict(start=0,end=1,font='Bold'),dict(start=2,end=34,font='Body')]
        b=run(2,'The item continues on this line.',20,95,180)
        p=dict(elements=[a,b,dict(id='image:1',kind='image',box_px=[20,10,200,75])],
               blocks=[dict(id='block:1',members=[a['id'],b['id']])],floats=[])
        copy.numbered_image_captions(p,10)
        self.assertEqual(p['floats'],[])

if __name__=='__main__':unittest.main()
