"""Flow regressions using invented text and page geometry."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
copy = module('flow_copy', 'copy_paper.py')
boxer = module('flow_boxer', 'standalone/element_boxer_sc.py')


def block(name, text, box, size=10):
    return dict(id=name, text=text, box_px=box, size=size, cls='main', lines=2, members=[])


def run(name, text, box, size=10):
    return dict(id=name, kind='text', text=text, box_px=box, run_size_px=size,
                size_px=size, angle=0, line=box[1])


class Flow(unittest.TestCase):
    def test_labelled_note_follows_its_table_when_anchor_moves(self):
        table=dict(kind='table',page=2,caption='Table 4. Measurements',box=[0,20,200,100],notes=[])
        note=dict(kind='para',page=2,text='Note: The values are averages.',box=[0,108,200,118])
        para=dict(kind='para',page=2,text='The preceding sentence ends here.',box=[250,150,450,200])
        result=copy.flow_furniture([para,note,table],[dict(page=2,elements=[],blocks=[])],10)
        self.assertEqual(result,[para,table])
        self.assertEqual(table['notes'],[note['text']])

    def paragraph_parts(self, lines, lefts=None):
        if lefts is None:lefts=[0]*len(lines)
        boxes=[[lefts[i],100+20*i,200,110+20*i] for i in range(len(lines))]
        b=dict(lines=lines,lefts=lefts,sizes=[10]*len(lines),row_boxes=boxes,
               meta=dict(id='prose',box_px=copy.hull(boxes),size_px=10,lines=len(lines)),
               page=2,first=lines[0])
        return copy.paragraph_blocks(b,10)

    def test_marker_looking_wrapped_sentence_is_not_a_list(self):
        for marker in ['3)', 'p.', '(a)', '•', '-']:
            with self.subTest(marker=marker):
                lines=['The expression continues with',marker+' another term.']
                parts=self.paragraph_parts(lines)
                self.assertEqual([p['lines'] for p in parts],[lines])
                self.assertFalse(parts[0]['list'])
        self.assertEqual(len(self.paragraph_parts(['An open parenthesis;','p. Another term) ends it.'])),1)

    def test_list_markers_need_a_block_or_sentence_boundary(self):
        for marker in ['1.', '1)', 'a.', '•', '-']:
            with self.subTest(marker=marker):
                for before in ['A finished sentence.','Choose from:','Choose from:3']:
                    parts=self.paragraph_parts([before,marker+' A choice.'])
                    self.assertEqual(len(parts),2)
                    self.assertTrue(parts[1]['list'])
                self.assertTrue(self.paragraph_parts([marker+' A choice.'])[0]['list'])
        parts=self.paragraph_parts(['References','1. A reference.'])
        self.assertEqual(len(parts),2)
        self.assertTrue(parts[1]['list'])

    def test_rejected_marker_keeps_the_following_paragraph_gap(self):
        lines=['Some explanatory text','continues through a label',
               'd) within the sentence','and another wrapped line','ending with a file type (DATA)',
               'Table 2 Another legend.']
        boxes=[[0,y,200,y+10] for y in [100,120,140,160,180,240]]
        b=dict(lines=lines,lefts=[0]*6,sizes=[10]*6,row_boxes=boxes,page=2,first=lines[0],
               meta=dict(id='prose',box_px=copy.hull(boxes),size_px=10,lines=6))
        parts=copy.paragraph_blocks(b,10)
        self.assertEqual([p['lines'] for p in parts],[lines[:5],lines[5:]])
        self.assertTrue(parts[1]['list_exit'])

    def test_aligned_unpunctuated_items_are_independent_blocks(self):
        parts=self.paragraph_parts(['e. An unpunctuated nested item','• Another outer item.'],[20,0])
        self.assertEqual(len(parts),2)
        self.assertTrue(all(p['list'] for p in parts))
        self.assertEqual(copy.list_block_starts(['1. A short task title','i) First step.','ii) Second step.'],
                                               [0,3,3]),{1,2})
        self.assertEqual(copy.list_block_starts(['A list heading','• First choice','• Second choice'],
                                               [0,0,0],boundaries={1}),{1,2})
        self.assertEqual(copy.list_block_starts(['(a) First choice','(b) Second choice'],[0,0]),{0,1})
        self.assertTrue(copy.list_item_start('(a) First choice'))
        self.assertEqual(copy.list_block_starts(['• First choice','• Second choice'],[0,0]),{0,1})
        self.assertEqual(copy.list_block_starts(['continued item;','2. Next choice;',
                                               '3. Another','wrapped choice'],[20,0,0,20]),{1,2})
        self.assertEqual(copy.list_block_starts(['An inline choice of type','1. has value',
                                               '2. in the expression.'],[0,0,0]),set())
        self.assertEqual(copy.list_block_starts(['1. The next term is','2. in this formula.'],[0,30]),set())
        parts=self.paragraph_parts(['• First choice','• Second choice'])
        self.assertEqual(len(parts),2)
        self.assertTrue(all(p['list'] for p in parts))

    def test_margin_divider_and_folio_require_furniture_evidence(self):
        divider=run('bar','|',[180,950,182,960])
        folio=run('folio','1',[190,950,200,960])
        notice=run('foot','Journal footer',[0,950,170,960])
        es={e['id']:e for e in [divider,folio,notice]}
        page=dict(region_box_px=[0,0,200,1000],main_text={})
        self.assertTrue(copy.fragment_furniture(divider,page,es,{'foot'}))
        self.assertTrue(copy.fragment_furniture(folio,page,es,{'foot'}))
        self.assertFalse(copy.fragment_furniture(folio,page,es,set()))
        interior=run('value','1',[190,500,200,510])
        self.assertFalse(copy.fragment_furniture(interior,page,{'value':interior},set()))
        page['main_text']['header_bottom']=80
        header=run('header','12',[190,40,200,50])
        self.assertTrue(copy.fragment_furniture(header,page,{'header':header},set()))

    def test_copy_keeps_marker_looking_sentence_before_the_page_end(self):
        lines=['The receptor (surface expression;','p. Variant) changes risk.']
        boxes=[[0,100,200,110],[0,120,200,130]]
        block=dict(lines=lines,lefts=[0,0],sizes=[10,10],row_boxes=boxes,page=1,first=lines[0],
                   meta=dict(id='prose',cls='main',order=0,size_px=10,lines=2,box_px=copy.hull(boxes)))
        page=dict(page=1,elements=[],blocks=[],tables=[],floats=[],region_box_px=[0,0,220,800],
                  main_text=dict(blocks=[],columns=[[0,200]]),
                  font_metadata={'unpaired_surrogate':'\ud835'})
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            (Path(directory)/'page-01.json').write_text(json.dumps(page))
            page['copy_conservation']={'excluded':[]}
            with patch.object(copy,'load',return_value=([page],{'body_size_px':10},{})), \
                 patch.object(copy,'read_page',return_value=([block],[],[])), \
                 patch.object(copy,'table_pdf_path',return_value=None):
                result=Path(copy.main(directory)).read_text()
            saved=json.loads((Path(directory)/'page-01.json').read_text())
            self.assertEqual(saved['font_metadata'],page['font_metadata'])
            self.assertIn('copy_conservation',saved)
        self.assertIn('The receptor (surface expression; p. Variant) changes risk.',result)
        self.assertNotIn('- p. Variant',result)
        self.assertLess(result.index('Variant'),result.index('<!-- end of page 1 -->'))

    def test_abstract_owns_whole_final_labelled_paragraph(self):
        bs = [block('a', 'Background: The study begins.\nSecond line.', [0,20,200,40]),
              block('b', 'Results: The study ends.\nSecond line.', [0,50,200,70]),
              block('c', 'Clinical implications: A long paragraph.\nIts last word.', [0,80,200,100]),
              block('d', 'The body starts.', [0,140,200,160])]
        boxer.structured_abstract_blocks(bs,10,lambda b:b['text'])
        self.assertEqual([b['id'] for b in bs if b.get('abstract')], ['a','b','c'])
        self.assertFalse(boxer.INSTITUTION.match('Clinical implications:'))
        self.assertTrue(boxer.INSTITUTION.match('Clinic for Dentistry'))

    def test_unrelated_label_in_another_column_is_not_an_abstract(self):
        bs=[block('a','Background: Some text.',[0,20,200,40]),
            block('b','Results: Other text.',[240,50,440,70])]
        boxer.structured_abstract_blocks(bs,10,lambda b:b['text'])
        self.assertFalse(any(b.get('abstract') for b in bs))

    def test_short_list_uses_the_colon_leadin_column(self):
        bs=[block('lead','Characteristics include:',[0,10,200,30]),
            block('list','• First.\n• Second.',[0,50,80,80]),
            block('after','Next paragraph.',[0,100,200,130])]
        cols=[[0,80],[0,200]]
        boxer.introduced_list_columns(bs,cols,10,lambda b:b['text'])
        seq,_=boxer.reading_order_bands(bs,cols,10)
        self.assertEqual([b['id'] for b in seq],['lead','list','after'])
        bs[0]['text']='A complete sentence.';bs[1].pop('list_column')
        boxer.introduced_list_columns(bs,cols,10,lambda b:b['text'])
        self.assertNotIn('list_column',bs[1])

    def test_list_recovers_a_chain_of_detached_words(self):
        es=[run('first','1. The',[0,20,35,30]),run('wrap','continued item.',[10,35,120,45]),
            run('second','2. Another item.',[0,50,130,60]),
            run('tail','last word',[100,20,150,30]),run('middle','middle',[45,20,90,30])]
        rs={e['id']:e for e in es};members={'list':['first','wrap','second'],'tail':['tail'],'middle':['middle']}
        result=copy.assemble_list_rows(members,rs,{k:{} for k in members},[[0,200]],10)
        self.assertEqual(set(result),{'list'})
        self.assertEqual(' '.join(e['text'] for e in copy.text_rows([rs[m] for m in result['list']])[0]),
                         '1. The middle last word')

    def test_column_footnote_inside_body_block_is_owned_separately(self):
        es=[run('body','An unfinished sentence',[0,780,200,790]),
            run('note','i Instrument supplier.',[0,800,200,807],7),
            run('tail','The address.',[5,810,100,817],7)]
        b=block('mixed','',[0,780,200,817]);b['members']=[e['id'] for e in es]
        notes=boxer.column_footnotes([b],es,10,1000)
        self.assertEqual(notes[0]['members'],['note','tail'])
        es[1]['run_size_px']=10
        self.assertEqual(boxer.column_footnotes([b],es,10,1000),[])

    def test_note_waits_until_sentence_continues_on_next_page(self):
        items=[dict(kind='para',text='The lowest point was',page=3),
               dict(kind='side',text='i Instrument supplier.',page=3),
               dict(kind='page',page=3),dict(kind='para',text='below the boundary.',page=4)]
        joined=copy.rejoin_paragraphs(items,copy.Joiner([]))
        self.assertEqual(joined[0]['text'],'The lowest point was below the boundary.')
        self.assertEqual(joined[1]['kind'],'side')

    def test_drop_cap_does_not_swallow_or_swap_neighbor_lines(self):
        e=run('cap','Anew subject',[0,10,160,45])
        e['_chars']=[dict(text='A',size=40,x0=0,y0=10,x1=30,y1=45,origin=(0,45),adv_x1=30)]
        for i,t in enumerate('newsubject'):
            e['_chars'].append(dict(text=t,size=10,x0=34+i*8,y0=10,x1=40+i*8,y1=20,origin=(34+i*8,20)))
        second=run('second','second line',[34,25,160,35]);third=run('third','third line',[34,40,160,50])
        rows=copy.prose_text_rows([e,second,third],{})
        self.assertEqual([[r['text'] for r in row] for row in rows], [['A new subject'],['second line'],['third line']])
        self.assertEqual(e['text'],'Anew subject')

    def test_document_kind_requires_layout_and_cover_evidence(self):
        slide=dict(page=1,region_box_px=[0,0,400,300],elements=[dict(kind='fill',box_px=[0,0,400,300]),
                   run('title','Example lecture',[20,20,220,40],20)])
        self.assertTrue(copy.document_kind([slide]*6)[0].startswith('lecture slides'))
        portrait=dict(slide,region_box_px=[0,0,300,400])
        self.assertIsNone(copy.document_kind([portrait]*6))
        self.assertEqual(copy.document_kind([portrait],True)[0],'scanned document')
        manuscript=dict(portrait,elements=[run('cover','Manuscript ID: 123',[0,0,200,10]),
                        run('review','Reviewer 1',[0,20,100,30])],main_text=dict(furniture=[dict(why='consecutive manuscript line numbers in the margin')]))
        self.assertEqual(copy.document_kind([manuscript]*3)[0],'manuscript submission with reviewer correspondence')


if __name__=='__main__': unittest.main()
