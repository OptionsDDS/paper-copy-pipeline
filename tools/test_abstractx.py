"""Page-turn abstract ownership and the printed edges of captioned lists."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

b = module('abstractx_boxer', 'standalone/element_boxer_sc.py')
c = module('abstractx_copy', 'copy_paper.py')

def run(name, text, x, y, width=300, size=10, face='Regular', height=None):
    return dict(id=name, kind='text', text=text, box_px=[x,y,x+width,y+(height or size)],
                font=face, run_size_px=size, size_px=size, angle=0, line=y,
                _faces={face:len(text)}, char_ids=[])

def block(name, rows, cls='main'):
    return dict(id=name, cls=cls, box_px=c.hull(e['box_px'] for e in rows),
                members=[e['id'] for e in rows], rows=[[e] for e in rows],
                size=rows[0]['run_size_px'], lines=len(rows))

def flow(ordered, blocks, previous=None):
    return b.reading_order_abstract_flow(ordered, blocks, previous, lambda q:q['rows'],
        lambda q:'\n'.join(' '.join(e['text'] for e in row) for row in q['rows']))

class AbstractTurn(unittest.TestCase):
    def pending(self, ending='and the supporting structures,'):
        first=block('summary',[run('label','Abstract',100,600),run('end',ending,100,620)])
        return flow([first],[first])[1]

    def test_continuation_and_smaller_keywords_precede_two_body_columns(self):
        tail=block('tail',[run('continued','as well as adjacent tissues.',100,40),
                           run('keyword','KEYWORDS',100,65,size=8,face='Bold'),
                           run('values','biology, anatomy',100,80,size=8)])
        left=block('left',[run('body','The ordinary body begins here.',0,120,width=180)])
        right=block('right',[run('other','Another body paragraph.',220,120,width=180)])
        ordered,pending=flow([left,right,tail],[left,right,tail],self.pending())
        self.assertEqual([q['id'] for q in ordered],['tail','left','right'])
        self.assertTrue(tail['abstract_continuation'])
        self.assertIsNone(pending)

    def test_complete_summary_does_not_claim_body(self):
        self.assertIsNone(self.pending('The summary ends here.'))

    def test_body_section_named_summary_is_not_an_abstract(self):
        section=block('section',[run('head','Summary of the selected studies',0,600),
                                 run('end','The included studies report',0,620)])
        self.assertIsNone(flow([section],[section])[1])

    def test_summary_heading_after_body_cannot_open_abstract(self):
        section=block('section',[run('head','Summary',0,600),
                                 run('end','The included studies report',0,620)])
        _,pending=b.reading_order_abstract_flow([section],[section],None,
            lambda q:q['rows'],lambda q:'\n'.join(row[0]['text'] for row in q['rows']),
            allow_open=False)
        self.assertIsNone(pending)

    def test_wrong_face_or_size_or_intervening_text_stops_continuation(self):
        for change in ({'font':'Italic'},{'run_size_px':12}):
            e=run('tail','the next paragraph.',100,40);e.update(change)
            tail=block('tail',[e])
            flow([tail],[tail],self.pending())
            self.assertNotIn('abstract_continuation',tail)
        intervening=block('caption',[run('cap','Table 2 Sample',100,20)],'caption')
        tail=block('tail',[run('tail','the next paragraph.',100,40)])
        flow([tail],[intervening,tail],self.pending())
        self.assertNotIn('abstract_continuation',tail)

    def test_separate_keywords_stay_with_continuation(self):
        tail=block('tail',[run('tail','and related structures.',100,40)])
        keyword=block('keys',[run('keys','Keywords: biology, anatomy',100,65,size=8)])
        body=block('body',[run('body','Body starts here.',0,120)])
        ordered,_=flow([body,tail,keyword],[body,tail,keyword],self.pending())
        self.assertEqual([q['id'] for q in ordered],['tail','keys','body'])

    def test_copy_joins_abstract_only_to_its_witnessed_continuation(self):
        opening=dict(kind='para',text='Conclusion: The observations include',abstract=True,page=2)
        body=dict(kind='para',text='The body begins here.',page=3)
        tail=dict(kind='para',text='all adjacent tissues.',abstract=True,abstract_continuation=True,page=3)
        unmarked=dict(tail,abstract_continuation=False)
        self.assertEqual(len(c.rejoin_paragraphs(copy.deepcopy([opening,unmarked]),c.Joiner([]))),2)
        joined=c.rejoin_paragraphs(copy.deepcopy([opening,tail,body]),c.Joiner([]))
        self.assertEqual([q['text'] for q in joined],
                         ['Conclusion: The observations include all adjacent tissues.','The body begins here.'])

    def test_unlabelled_numeric_fragment_still_finishes_abstract(self):
        opening=dict(kind='para',text='Results: Follow-up lasted',abstract=True,page=1)
        tail=dict(kind='para',text='5.6 years on average.',page=1)
        joined=c.rejoin_paragraphs([opening,tail],c.Joiner([]))
        self.assertEqual(len(joined),1)
        self.assertEqual(joined[0]['text'],'Results: Follow-up lasted 5.6 years on average.')

class CaptionEdge(unittest.TestCase):
    def test_extra_leading_does_not_claim_smaller_same_face_table_header(self):
        label=run('label','Table 2',0,0,width=45,size=10,face='Bold',height=6)
        title=run('title','Search strategy',55,0,width=140,size=10,face='Bold',height=6)
        header=run('header','Focus question and study population',0,13,width=200,size=8,face='Bold')
        self.assertEqual(c.table_caption_members(dict(elements=[label,title,header]),label),['label','title'])

    def test_wide_final_numbered_row_belongs_to_gate_before_larger_body(self):
        cap=run('caption','Table 2. Sample categories',0,0,width=240,size=10)
        entries=[run('row'+str(i),str(i)+'. A listed category',10,30+i*18,width=200,size=8)
                 for i in range(1,5)]
        prose=run('prose','The following body paragraph is separate from the table.',0,140,width=240,size=10)
        blocks=[dict(id=e['id'],members=[e['id']],box_px=e['box_px']) for e in [cap,entries[-1],prose]]
        meta=[dict(q,cls='main',order=i+1,lines=1,size_px=e['run_size_px'])
              for i,(q,e) in enumerate(zip(blocks[1:],[entries[-1],prose]))]
        p=dict(page=2,elements=[cap]+entries+[prose],blocks=blocks,
               tables=[dict(id='table',angle=0,members=[e['id'] for e in entries[:-1]],
                            box_px=[0,40,240,entries[-2]['box_px'][3]])],
               floats=[dict(id='float',caption=cap['text'],blocks=['caption','table'],
                            box_px=[0,0,240,entries[-2]['box_px'][3]])],
               main_text=dict(blocks=meta,columns=[[0,240]]),region_box_px=[0,0,250,500])
        body,floats,_=c.read_page(copy.deepcopy(p),10,[])
        source=floats[0][5]['table_source']
        ids={e['id'] for row in source['lines'] for e in row['items']}
        self.assertEqual(ids,{e['id'] for e in entries})
        self.assertEqual([q['lines'] for q in body],[[prose['text']]])
        # A new body-sized numbered paragraph is not a table continuation.
        p['elements'][-2]['run_size_px']=10
        body,floats,_=c.read_page(p,10,[])
        ids={e['id'] for row in floats[0][5]['table_source']['lines'] for e in row['items']}
        self.assertNotIn(entries[-1]['id'],ids)

    def test_capital_label_ink_height_does_not_cut_wrapped_caption(self):
        label=run('label','TABLE 2',0,0,width=45,size=10,face='Label',height=6)
        title=run('title','Classification of materials and',55,0,width=140,size=9,height=6)
        tail=run('tail','their related properties',0,13,width=140,size=9,height=8)
        header=run('header','Group A',0,29,width=150,size=9,face='Bold')
        p=dict(elements=[label,title,tail,header])
        self.assertEqual(c.table_caption_members(p,label),['label','title','tail'])
        p['elements'].append(dict(kind='rule',box_px=[0,10,200,11]))
        self.assertEqual(c.table_caption_members(p,label),['label','title'])

if __name__ == '__main__':unittest.main()
