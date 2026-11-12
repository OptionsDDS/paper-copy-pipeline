"""Header-band and diagnostic regressions using invented page geometry."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj
paper = module('copy_paper', 'copy_paper.py')
boxer = module('element_boxer_sc', 'standalone/element_boxer_sc.py')

def run(name, text, x, y, width=220, size=10, angle=0, height=10):
    return dict(id=name,kind='text',text=text,box_px=[x,y,x+width,y+height],
                angle=angle,line=y,run_size_px=size,size_px=size,font='Regular',flags=[])

def page(number, groups, tables=()):
    es=[e for _,members in groups for e in members]
    blocks=[dict(id=name,members=[e['id'] for e in members],kinds=['text'],
                 box_px=paper.hull(e['box_px'] for e in members),text_lines=len(members),
                 text=' '.join(e['text'] for e in members)) for name,members in groups]
    return dict(page=number,elements=es,blocks=blocks,tables=list(tables),floats=[],art=[],unpaired=[],
                region_box_px=[0,0,320,1000],reading_angle=0)

class PageTops(unittest.TestCase):
    def classify(self, pages):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            for p in pages:
                Path(folder,f"page-{p['page']:02d}.json").write_text(json.dumps(p))
            boxer.main_text(folder,draw=False)
            first=[json.loads(Path(folder,f"page-{p['page']:02d}.json").read_text()) for p in pages]
            boxer.main_text(folder,draw=False)
            second=[json.loads(Path(folder,f"page-{p['page']:02d}.json").read_text()) for p in pages]
            self.assertEqual(first,second,'paper pass must be idempotent')
            return first

    def test_table_continuations_do_not_cut_other_column_feet(self):
        pages=[]
        for i,word in enumerate(['Red','Green','Blue','Gold'],1):
            body=[run(f'body{j}',f'{word} ordinary paragraph line {j}.',40,860+15*j) for j in range(6)]
            if i<4: body=body[:-1]+[run('cont','(Continues)',180,935,width=80,size=8)]
            pages.append(page(i,[('body',body)]))
        result=self.classify(pages)[-1]['main_text']
        self.assertNotIn('body5',{m for f in result['furniture'] for m in f['members']})
        self.assertIsNone(result['footer_top'])

    def test_nearby_folio_is_not_a_column_tail(self):
        pages=[]
        for i,word in enumerate(['Red','Green','Blue'],1):
            body=[run(f'body{j}',f'{word} ordinary paragraph line {j}.',40,840+15*j) for j in range(6)]
            footer=run('footer','Repeated publication footer',40,932,width=220,size=10)
            groups=[('body',body),('footer',[footer])]
            if i==3:
                groups=[('body',body+[run('folio','217',40,932,width=20,size=10)])]
            pages.append(page(i,groups))
        result=self.classify(pages)[-1]['main_text']
        furniture={m for f in result['furniture'] for m in f['members']}
        self.assertIn('folio',furniture)
        self.assertNotIn('body5',furniture)

    def test_detached_reference_url_keeps_its_baseline(self):
        pages=[]
        for i,word in enumerate(['Red','Green'],1):
            body=[run(f'body{j}',f'{word} paragraph with several words.',40,145+15*j) for j in range(6)]
            groups=[('body',body)]
            if i==2:
                groups += [('citation',[run('citation','2008;15:22-29.',40,100,width=90,size=10)]),
                           ('url',[run('url','https://doi.org/10.0000/',150,100,width=110,size=10)])]
            pages.append(page(i,groups))
        result=self.classify(pages)[-1]['main_text']
        self.assertNotIn('url',{m for f in result['furniture'] for m in f['members']})

    def test_alternating_heads_cross_folio_digit_boundary(self):
        pages=[]
        words='Red Green Blue Gold Amber White Black Brown Pink Purple Grey Cyan Teal Coral Lime Ochre Navy'.split()
        for i,word in enumerate(words,1):
            body=[run(f'body{j}',f'{word} paragraph has ordinary words {j}.',40,150+15*j) for j in range(6)]
            groups=[('body',body)]
            if i>1:
                number=run('folio',str(i),40 if i%2==0 else 270,30,width=15,size=8)
                head=run('header','Sample et al.',180 if i%2==0 else 40,30,width=80,size=8)
                groups.append(('head',[number,head]))
            pages.append(page(i,groups))
        for p in self.classify(pages)[1:]:
            furniture={m for f in p['main_text']['furniture'] for m in f['members']}
            self.assertTrue({'folio','header'}<=furniture)
            self.assertFalse(any(m.startswith('body') for m in furniture))

    def test_interior_measurements_do_not_gain_folio_matching(self):
        pages=[]
        for i,(word,value) in enumerate([('Red','12'),('Green','9')],1):
            body=[run(f'body{j}',f'{word} paragraph has several ordinary words.',40,200+15*j) for j in range(6)]
            data=[run('label','Length, mm',40,400,width=100),run('value',value,220,400,width=20)]
            pages.append(page(i,[('title',[run('title',word+' study',40,40,size=20)]),('body',body),('data',data)]))
        for p in self.classify(pages):
            furniture={m for f in p['main_text']['furniture'] for m in f['members']}
            self.assertFalse({'label','value'}&furniture)

    def test_decimal_measurements_at_page_top_keep_their_digit_width(self):
        pages=[]
        for i,(word,value) in enumerate([('Red','8.5'),('Green','10.5')],1):
            body=[run(f'body{j}',f'{word} paragraph has several ordinary words.',40,200+15*j) for j in range(6)]
            data=run('measurement',f'Fixture dimensions 3.8 mm x {value} mm, 3.5',40,100)
            pages.append(page(i,[('title',[run('title',word+' study',40,40,size=20)]),('body',body),('data',[data])]))
        for p in self.classify(pages):
            furniture={m for f in p['main_text']['furniture'] for m in f['members']}
            self.assertNotIn('measurement',furniture)

    def test_global_band_stops_at_local_heading_and_body(self):
        pages=[]
        for i,word in enumerate(['Red','Green','Blue'],1):
            top=200 if i<3 else 80
            body=[run(f'body{j}',f'{word} paragraph has several ordinary words.',40,top+15*j) for j in range(5)]
            head=run('header','Running journal title',160,100 if i<3 else 20,width=100,size=8)
            groups=[('head',[head]),('body',body)]
            if i==3:
                groups += [('heading',[run('heading','A section heading',40,65,width=120,size=12)]),
                           ('sidebar',[run('sidebar','Downloaded publication notice',300,5,width=8,size=8,angle=90,height=980)])]
            pages.append(page(i,groups))
        result=self.classify(pages)[-1]['main_text']
        classes={b['id']:b['cls'] for b in result['blocks']}
        self.assertTrue(all(b['cls']=='main' for b in result['blocks'] if b['id'].startswith('body')))
        self.assertEqual(classes['heading'],'main')
        self.assertEqual(classes['sidebar'],'furniture')
        self.assertLessEqual(result['header_bottom'],65)
        self.assertIsNone(result['page_top_check']['flag'])

    def test_restored_column_opening_keeps_later_layout_below_it(self):
        pages=[]
        for i,word in enumerate(['Red','Green','Blue'],1):
            top=200 if i<3 else 80
            groups=[('head',[run('header','Running journal title',160,100 if i<3 else 20,width=100,size=8)])]
            for col,x in enumerate([40,170]):
                groups.append((f'upper{col}',[run(f'u{col}-{j}',f'{word} upper paragraph sentence.',x,top+15*j,width=100) for j in range(5)]))
            if i==3:
                groups.append(('heading',[run('heading','A new section across columns',40,185,width=110,size=14)]))
                for col,x in enumerate([40,120,200]):
                    groups.append((f'lower{col}',[run(f'l{col}-{j}',f'Later section text {col} {j}.',x,220+15*j,width=60) for j in range(5)]))
            pages.append(page(i,groups))
        result=self.classify(pages)[-1]['main_text']
        orders={b['id']:b['order'] for b in result['blocks'] if b['cls']=='main'}
        self.assertTrue(all(order<orders['heading'] for key,order in orders.items() if key.startswith('upper')))
        self.assertTrue(all(order>orders['heading'] for key,order in orders.items() if key.startswith('lower')))

    def test_numbered_heading_edge_includes_separate_number_and_wrapped_line(self):
        pages=[]
        for i,word in enumerate(['Red','Green','Blue'],1):
            body=[run(f'body{j}',f'{word} paragraph has several ordinary words.',40,200+15*j) for j in range(6)]
            groups=[('head',[run('header','Running journal title',160,100 if i<3 else 20,width=100,size=8)]),('body',body)]
            if i==3:
                groups.append(('heading',[run('number','4.2',40,85,width=18,size=14),
                    run('divider','|',70,85,width=2,size=14),
                    run('label','Measured outcomes and',90,85,width=160,size=14),
                    run('wrap','their interpretation',40,104,width=150,size=14)]))
            pages.append(page(i,groups))
        result=self.classify(pages)[-1]['main_text']
        furniture={m for f in result['furniture'] for m in f['members']}
        self.assertFalse(furniture.intersection({'number','divider','label','wrap'}))
        heading=next(b for b in result['blocks'] if b['id']=='heading')
        self.assertEqual(heading['cls'],'main')
        self.assertEqual(heading['lines'],2)
        self.assertLessEqual(result['header_bottom'],85)

    def test_repeated_table_heading_is_not_running_furniture(self):
        pages=[]
        for i,word in enumerate(['Red','Green','Blue'],1):
            title=run('tablehead','Treatment outcomes',40,100,width=140)
            cells=[run(f'cell{j}',f'{word} measured result with several words',40,125+15*j) for j in range(5)]
            table=dict(id='table:1',angle=0,members=[e['id'] for e in cells],box_px=[40,125,260,200])
            pages.append(page(i,[('tableblock',[title,*cells])],[table]))
        for p in self.classify(pages):
            self.assertNotIn('tablehead',{m for f in p['main_text']['furniture'] for m in f['members']})
            self.assertIsNone(p['main_text']['header_bottom'])

    def test_rotated_cells_and_caption_are_not_sidebar_notices(self):
        cells=[run(f'cell{i}',f'Printed cell {i}',10,20+100*i,width=8,angle=90,height=15) for i in range(10)]
        for e in cells:e['line']=1
        caption=run('caption','TABLE 4 Measured results',100,10,width=10,angle=90,height=980)
        body=[run(f'body{i}',f'Ordinary paragraph line {i} with enough words.',40,200+15*i) for i in range(5)]
        p=self.classify([page(1,[('cells',cells),('caption',[caption]),('body',body)])])[0]
        furniture={m for f in p['main_text']['furniture'] for m in f['members']}
        self.assertFalse(furniture.intersection(e['id'] for e in cells+[caption]))

    def test_running_head_stays_furniture_when_folio_gains_a_digit(self):
        pages=[]
        for i,word in enumerate(['Red','Green','Blue','Gold'],1):
            number=run('folio',str(i if i<4 else 10),40,90,width=15,size=12)
            head=run('header','General Journal of Science',130,90,width=130,size=12)
            body=[run(f'body{j}',f'{word} text has several ordinary words.',40,150+15*j) for j in range(6)]
            pages.append(page(i,[('number',[number]),('head',[head]),('body',body)]))
        result=self.classify(pages)[-1]['main_text']
        self.assertEqual({b['id']:b['cls'] for b in result['blocks']}['head'],'furniture')

    def test_near_title_size_masthead_does_not_limit_the_band(self):
        pages=[]
        for i,word in enumerate(['Red','Green','Blue'],1):
            body=[run(f'body{j}',f'{word} paragraph has several ordinary words.',40,300+15*j) for j in range(5)]
            groups=[('body',body)]
            if i==1:
                groups += [('logo',[run('logo','General Science',40,40,width=200,size=36.7)]),
                           ('title',[run('title','A study of useful things',40,150,width=220,size=37.5)])]
            else:groups.append(('header',[run('header','Journal header',160,50,width=100,size=8)]))
            pages.append(page(i,groups))
        result=self.classify(pages)[0]['main_text']
        self.assertEqual({b['id']:b['cls'] for b in result['blocks']}['logo'],'furniture')

    def test_detector_groups_split_lines_but_ignores_footer_and_sidebar(self):
        es=[run('a','First three words',40,80),run('b','next two',40,95),
            run('main','Ordinary paragraph',40,125),run('side','A long rotated notice with many words',300,5,width=8,angle=90,height=980)]
        p=page(2,[('lost',es[:2]),('main',es[2:3]),('side',es[3:])])
        p['main_text']=dict(body_size_px=10,blocks=[dict(id='lost',cls='furniture',box_px=[40,80,260,105]),
            dict(id='main',cls='main',box_px=[40,125,260,135])],furniture=[
                dict(text=e['text'],members=[e['id']],box_px=e['box_px'],why='inside the recurring header band') for e in es[:2]+es[3:]])
        check=boxer.page_top_check(p)
        self.assertEqual(check['flag'],'page top may be dropped')
        self.assertEqual(check['gap_px'],20)
        self.assertEqual(check['evidence'][0]['members'],['a','b'])
        p['main_text']['page_top_check']=check
        uncertain=[]
        with patch.object(paper,'table_float_regions',lambda p,body:p):paper.read_page(p,10,uncertain)
        self.assertTrue(any('page 2: page top may be dropped' in u for u in uncertain))
        for f in p['main_text']['furniture'][:2]:f['why']='inside the recurring footer band'
        self.assertIsNone(boxer.page_top_check(p)['flag'])

    def test_empty_page_has_null_gap(self):
        p=page(1,[])
        self.assertEqual(boxer.page_top_check(p)['gap_px'],None)
        result=self.classify([p])[0]['main_text']['page_top_check']
        self.assertIsNone(result['flag'])
        self.assertIsNone(result['gap_px'])

if __name__=='__main__':unittest.main()
