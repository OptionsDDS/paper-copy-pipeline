"""Printed heading, caption and glossary ownership; synthetic boundary controls."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result
c = module('copy_boxes', 'copy_paper.py')
b = module('boxer_boxes', 'standalone/element_boxer_sc.py')


def run(name, text, x, y, width, bold=False, size=10):
    return dict(id=name, kind='text', text=text, box_px=[x,y,x+width,y+size*.9],
                font='Text-Bold' if bold else 'Text-Roman', size_px=size,
                run_size_px=size, angle=0, line=y, char_ids=[])


def page(es, number=1):
    blocks=[dict(id='block:'+e['id'],members=[e['id']],box_px=e['box_px'],text=e['text']) for e in es]
    mt=[dict(id=x['id'],cls='main',order=i+1,lines=1,size_px=10,
             box_px=x['box_px'],text=x['text']) for i,x in enumerate(blocks)]
    return dict(page=number,region_box_px=[0,0,500,800],elements=es,blocks=blocks,
                floats=[],tables=[],main_text=dict(blocks=mt,furniture=[],columns=[[0,400]]))


class Ownership(unittest.TestCase):
    def opening(self):
        return [dict(id='head',cls='other',lines=1,size=6.9,text='INTRODUCTION',box_px=[0,40,55,47]),
                dict(id='body',cls='main',lines=12,size=10,text='Opening prose.',box_px=[0,70,150,250]),
                dict(id='right',cls='main',lines=12,size=10,text='Continuing prose.',box_px=[180,40,330,250])]

    def test_small_cap_heading_precedes_its_column(self):
        blocks=self.opening(); cols=[[0,150],[180,330]]
        b.reading_order_opening_headings(blocks,cols,10)
        ordered,_=b.reading_order_bands([x for x in blocks if x['cls']=='main'],cols,10)
        self.assertEqual([x['id'] for x in ordered],['head','body','right'])

    def test_heading_recovery_rejects_furniture_floats_and_intervening_text(self):
        for change,occupied in [('furniture',[]),('float',[[0,48,150,65]]),('gap',[]),('above',[])]:
            blocks=self.opening()
            if change=='furniture': blocks[0]['cls']='furniture'
            if change=='gap': blocks[1]['box_px'][1]=100
            if change=='above': blocks.append(dict(id='note',cls='other',box_px=[0,50,80,60]))
            b.reading_order_opening_headings(blocks,[[0,150],[180,330]],10,occupied)
            self.assertNotEqual(blocks[0]['cls'],'main',change)

    def caption(self):
        es=[run('label','FIGURE 7',0,100,50,True),run('title','A sample diagram',60,100,90),
            run('tail','with its wrapped caption',60,114,130)]
        p=page(es)
        p['blocks']=[p['blocks'][0],dict(id='title-block',members=['title','tail'],box_px=[60,100,190,123])]
        p['unpaired']=[dict(block='block:label',caption='FIGURE 7')]
        return p

    def test_detached_label_owns_caption_and_wrapped_row_once(self):
        p=self.caption(); c.detached_caption_labels(p,10)
        self.assertEqual(p['floats'][0]['_caption_ids'],['label','title','tail'])
        self.assertEqual(p['floats'][0]['caption'],'Figure 7. A sample diagram\nwith its wrapped caption')

    def test_caption_stops_at_blank_band_and_cannot_cross_body_gutter(self):
        p=self.caption();p['elements'][2]['box_px']=[60,140,190,149]
        c.detached_caption_labels(p,10)
        self.assertEqual(p['floats'][0]['_caption_ids'],['label','title'])
        p=self.caption();p['main_text']['columns']=[[0,50],[60,200]]
        c.detached_caption_labels(p,10)
        self.assertEqual(p['floats'],[])

    def test_complete_journal_record_is_front_information_only_after_summary(self):
        for first,expected in [('CLINICAL SIGNIFICANCE',True),('The experiment continued.',False)]:
            es=[run('h',first,0,0,200),run('p','The summary ends here.',0,20,200),
                run('j','(J Example Res 12: 34–56, 2020)',100,40,150)]
            p=page(es);p['blocks']=[dict(id='summary',members=['h','p','j'])]
            c.prepare_front_matter([p],{})
            self.assertEqual('j' in p.get('_front_info_run_ids',[]),expected)

    def glossary(self):
        es=[run('h','Glossary',0,10,70,True,size=12)]
        for i,t in enumerate(['Alpha','Beta','Gamma']):
            y=40+40*i
            es.extend([run('t'+str(i),t,20,y,35,True),
                       run('d'+str(i),'A definition with several words',100,y,240),
                       run('e'+str(i),'and its remaining text.' if i<2 else 'and its remaining',100,y+13,220)])
        return page(es)

    def test_glossary_rows_keep_wrapped_terms_and_cross_page_tail(self):
        p=self.glossary()
        q=page([run('carry','words on the next page.',100,10,220),
                run('t','Longer',20,40,40,True),run('tw','term',20,53,30,True),
                run('d','A definition on this new page',100,40,240),run('e','that finishes here.',100,53,190),
                run('stop','References',0,80,70,True,size=12)],2)
        c.prepare_definition_boxes([p,q],10)
        rows=p['_definition_layout']; self.assertEqual([x['kind'] for x in rows],['heading']+['definition']*3)
        self.assertEqual(rows[-1]['terms'],['t2'])
        self.assertEqual(q['_definition_layout'][0]['members'],['carry'])
        self.assertEqual(q['_definition_layout'][1]['terms'],['t','tw'])
        self.assertNotIn('stop',{m for x in q['_definition_layout'] for m in x['members']})
        # No run can be assigned twice or lost from the accepted region.
        ids=[m for x in rows for m in x['members']]
        self.assertEqual(len(ids),len(set(ids)))
        self.assertEqual(set(ids),{e['id'] for e in p['elements']})

    def test_glossary_requires_alignment_long_definitions_and_immediate_continuation(self):
        for bad in ('alignment','width','heading'):
            p=self.glossary()
            if bad=='alignment':p['elements'][2]['box_px'][1]+=9
            if bad=='width':
                for e in p['elements']:
                    if e['id'].startswith(('d','e')):e['box_px'][2]=140
            if bad=='heading':p['elements'][0]['text']='A normal heading'
            c.prepare_definition_boxes([p],10)
            self.assertNotIn('_definition_layout',p,bad)
        p=self.glossary();q=copy.deepcopy(p);q['page']=3;q['elements']=q['elements'][1:]
        c.prepare_definition_boxes([p,q],10)
        self.assertNotIn('_definition_layout',q)


if __name__=='__main__':unittest.main()
