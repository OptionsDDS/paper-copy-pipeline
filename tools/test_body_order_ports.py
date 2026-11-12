"""Keyless ports from mapper stage3_text_body/markers (D-462/488/520/526/555/561).

The nine Slots pair names/outcomes are the public D-526 contract. These are
witness fixtures, not claimed replicas of the old image mapper's private box
ids: today's rule-2 boxes merge several of its paragraphs. No keys are read.
"""
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('base',Path(__file__).with_name('test_body_order.py'))
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
b=t.boxer


def prepared(bid, page=1, x=0, y=0, texts=('First line','Another line','Last.'), indent=0):
    p=t.page(page,t.block(bid,x,y,texts=texts,indent=indent))
    meta=p['main_text']['blocks'][0]
    return dict(meta,page=page,_rows=b.body_order_rows(p,meta),_column=[x,x+200],_heading=False)


class Ports(unittest.TestCase):
    def test_nine_slots_witness_contract_from_d526(self):
        cases=[('p7-6','p7-7','vertical-gap'),('p7-7','p7-8','vertical-gap'),
               ('p8-3','p8-4','vertical-gap'),('p8-4','p8-5','vertical-gap'),
               ('p8-7','p8-8','vertical-gap'),('p8-8','p8-9','vertical-gap'),
               ('p8-5','p8-7','indent'),('p7-8','p7-9',None),('p7-9','p8-3',None)]
        for left,right,witness in cases:
            with self.subTest(left=left,right=right):
                a=prepared(left,texts=('First','Second','unfinished' if witness is None else 'Done.'))
                c=prepared(right,page=2 if right=='p8-3' and left=='p7-9' else 1,
                           x=240 if left=='p7-8' else 0,y=80 if witness=='vertical-gap' else 45,
                           texts=('continues' if witness is None else 'New paragraph','Second','Last.'),
                           indent=10 if witness=='indent' else 0)
                x=c['_column'][0]
                starts=dict(first_line_starts=[x,x+10],continuation_line_starts=[x,x],first_line_samples=[{}])
                ws=b.body_order_layout_break_witnesses(a,c,starts,True,[15,15],[])
                self.assertEqual([w['kind'] for w in ws],[] if witness is None else [witness])
                grammar=b.body_order_grammar(a['_rows'][-1]['text'],c['_rows'][0]['text'])
                self.assertEqual(grammar['confirms_continuation'],witness is None)

    def test_start_intervals_preserve_overlap_and_do_not_choose_nearest(self):
        a=prepared('a');c=prepared('c',y=100,indent=10)
        starts=b.body_order_start_intervals(a,[a,c],10)
        self.assertEqual(starts['first_line_starts'],[0,10])
        self.assertEqual(starts['overlap'],[0,0])
        c['_rows'][0]['box_px'][0]=11
        self.assertEqual(b.body_order_layout_break_witnesses(a,c,starts,True,None,[]),[])

    def test_end_intervals_exclude_own_and_column_page_ends(self):
        a=prepared('a');c=prepared('c',y=50);d=prepared('d',x=240);e=prepared('e',page=2)
        ends=b.body_order_end_intervals(a,[a,c,d,e],10)
        self.assertEqual(ends['paragraph_last_samples'],[])
        self.assertEqual([s['block_id'] for s in ends['own_break_exclusions']],['a'])
        self.assertEqual([(s['block_id'],s['reason']) for s in ends['boundary_exclusions']],[('c','column-break')])
        self.assertEqual(len(ends['continuing_line_samples']),4)

    def test_only_intervening_heading_is_a_witness(self):
        a=prepared('a');c=prepared('c',y=100)
        starts=b.body_order_start_intervals(a,[a,c],10)
        ws=b.body_order_layout_break_witnesses(a,c,starts,False,None,[dict(id='h',kind='heading',box_px=[0,60,100,70])])
        self.assertEqual(ws[0]['kind'],'heading')

    def test_marker_grammar(self):
        for text in ('1. First','ii) Next','a. Choice','• Item'):
            self.assertIsNotNone(b.body_order_parse_marker(text))
        self.assertIsNone(b.body_order_parse_marker('1. 25 percent'))
        self.assertEqual(b.body_order_parse_marker('3. List')['ordinal'],3)
        self.assertEqual(b.body_order_heading_number('2.3.1 Methods'),(2,3,1))

    def test_sequence_depth_and_no_skipped_parent(self):
        self.assertFalse(b.body_order_outline_sequence_step(None,(2,1))[1])
        self.assertTrue(b.body_order_outline_sequence_step((2,),(2,1))[1])
        self.assertTrue(b.body_order_outline_sequence_step((2,1,3),(3,))[1])
        self.assertFalse(b.body_order_outline_sequence_step((2,),(4,))[1])
        self.assertFalse(b.body_order_outline_sequence_step((2,1,1),(2,1,1,1))[1])

    def test_section_resync_retains_misprint_and_flag(self):
        items=[dict(ref=(1,str(i)),lines=[dict(ref=(1,str(i),0),text=text)])
               for i,text in enumerate(['1 Intro','1.1 Methods','9.9 Wrong','1.3 Results'])]
        rows,events=b.body_order_section_sequence(items,set())
        self.assertEqual(rows[2]['observed_number'],(9,9))
        self.assertEqual(rows[2]['number'],(1,2))
        self.assertTrue(rows[2]['inferred']);self.assertEqual(rows[2]['flag'],'inferred from sequence')
        self.assertEqual(len(events),1)

    def test_numbered_heading_levels_and_out_of_sequence_flag(self):
        bs=[]
        for i,text in enumerate(['1 Introduction','1.1 Methods','1.1.1 Details','1.3 Misprint','2 Results']):
            bs.extend([t.block('h'+str(i),0,i*150,100,(text,),size=12),t.block('p'+str(i),0,i*150+40)])
        r=b.body_reading_order([t.page(1,*bs)])
        heads={x['id']:x for x in r['blocks'] if x['id'].startswith('h')}
        self.assertEqual(heads['h1']['level'],2);self.assertEqual(heads['h2']['level'],3)
        self.assertTrue(heads['h3']['flagged'])  # One skipped sibling resynchronizes, flagged.
        self.assertEqual(heads['h4']['level'],1)

    def test_list_precedence_does_not_advance_section_sequence(self):
        p=t.page(1,t.block('root',0,0,100,('2 Methods',),size=12),
                 t.block('body',0,40),t.block('list',0,100,texts=('3. First item','4. Second item','5. Third item')),
                 t.block('child',0,180,100,('2.1 Subjects',),size=12),t.block('end',0,220))
        r=b.body_reading_order([p]);nodes={x['id']:x for x in r['blocks']}
        self.assertFalse(nodes['list']['heading']);self.assertEqual(nodes['child']['level'],2)
        self.assertEqual(nodes['list']['heading_evidence']['reason'],'confirmed list system has precedence')

    def test_detached_heading_number_keeps_both_boxes_and_sequence_level(self):
        bs=[]
        for i,(number,title) in enumerate([('1','Introduction'),('1.1','Methods'),('9.9','Unexpected')]):
            bs.extend([t.block('n'+str(i),0,i*150,15,(number,),size=12),
                       t.block('h'+str(i),30,i*150,100,(title,),size=12),
                       t.block('p'+str(i),0,i*150+40)])
        r=b.body_reading_order([t.page(1,*bs)]);nodes={x['id']:x for x in r['blocks']}
        self.assertEqual(len(nodes),9)
        self.assertEqual(nodes['n1']['level'],2);self.assertEqual(nodes['h1']['level'],2)
        self.assertEqual(nodes['n1']['heading_before'],'h1')
        self.assertFalse(nodes['h2']['heading']);self.assertTrue(nodes['h2']['flagged'])

if __name__=='__main__':unittest.main()
