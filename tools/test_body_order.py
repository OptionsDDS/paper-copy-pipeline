"""Rule 9's independent order, ownership and continuation contract."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('boxer', ROOT/'standalone/element_boxer_sc.py')
boxer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boxer)


def block(bid, x, y, width=200, texts=('A paragraph starts', 'with a second line', 'and finishes here.'), cls='main', size=10, indent=0):
    es = [dict(id=f'{bid}:{i}', kind='text', text=t, line=i, angle=0,
               box_px=[x+(indent if i==0 else 0), y+i*15, x+width, y+i*15+10],
               run_size_px=size, size_px=size) for i,t in enumerate(texts)]
    box = [x,y,x+width,y+(len(texts)-1)*15+10]
    return dict(id=bid, cls=cls, size_px=size, box_px=box, lines=len(es)), dict(id=bid, members=[e['id'] for e in es], box_px=box), es


def page(n, *bs, floats=()):
    return dict(page=n, elements=[e for b in bs for e in b[2]], blocks=[b[1] for b in bs], floats=list(floats),
                main_text=dict(body_size_px=10, columns=[[999,1999]], blocks=[b[0] for b in bs]))


def ids(result):
    return [(b['page'],b['id']) for b in result['blocks']]


class BodyOrder(unittest.TestCase):
    def test_columns_are_local_not_y_sorted_or_borrowed(self):
        p=page(1, block('r1',240,0), block('l2',0,200), block('l1',0,50), block('r2',240,300))
        original=copy.deepcopy(p); r=boxer.body_reading_order([p])
        self.assertEqual(ids(r),[(1,'l1'),(1,'l2'),(1,'r1'),(1,'r2')])
        self.assertEqual([c['box'] for c in r['pages'][0]['columns']],[[0,200],[240,440]])
        self.assertEqual(r['edges'][1]['kind'],'next_column')
        self.assertEqual(p,original)

    def test_only_main_and_every_main_exactly_once(self):
        p=page(1,block('main',0,0),*(block(c,240,i*80,cls=c) for i,c in enumerate(
            ['title','authors','furniture','caption','aside','other','rotated'])))
        r=boxer.body_reading_order([p]); self.assertEqual(ids(r),[(1,'main')])
        self.assertEqual(r['counts']['main_boxes'],r['counts']['placed'])
        self.assertEqual(r['unplaced'],[])

    def test_short_heading_follows_own_column(self):
        p=page(1,block('r',240,0),block('h',0,90,80,('Methods',),size=12),block('l',0,120))
        r=boxer.body_reading_order([p]); self.assertEqual(ids(r),[(1,'h'),(1,'l'),(1,'r')])
        self.assertEqual(r['blocks'][0]['heading_before'],'l')
        self.assertEqual(r['blocks'][0]['column'],[0,200])

    def test_spanning_float_changes_bands_and_is_not_a_body_box(self):
        f=dict(id='f',box_px=[0,100,440,180])
        p=page(1,block('above_l',0,0),block('below_r',240,210),block('above_r',240,0),block('below_l',0,210),floats=[f])
        r=boxer.body_reading_order([p])
        self.assertEqual(ids(r),[(1,'above_l'),(1,'above_r'),(1,'below_l'),(1,'below_r')])
        # The port records the crossing but only a same-column intervening
        # float witnesses a paragraph break (stage3_text_body, D-520).
        self.assertIn('across_float', r['edges'][1]['transitions'])
        self.assertEqual(r['edges'][1]['geometry']['break_witnesses'], [])

    def test_float_conflict_never_guesses(self):
        f=dict(id='f',box_px=[0,60,200,130])
        p=page(1,block('a',0,0,texts=('The first line','another full line','unfinished')),
               block('b',0,150,texts=('continues here','next line','last line.')),floats=[f])
        e=boxer.body_reading_order([p])['edges'][0]
        self.assertEqual(e['kind'],'across_float'); self.assertTrue(e['flagged'])
        self.assertEqual(e['continuation'],'undecided'); self.assertEqual(e['evidence'],'both')

    def test_column_or_page_terminal_is_not_a_paragraph_break(self):
        p=page(1,block('a',0,0),block('b',240,0,texts=('New sentence.','More words.','Done.')))
        q=page(3,block('c',20,0))
        r=boxer.body_reading_order([q,p])
        for e in r['edges']:
            self.assertEqual(e['continuation'],'continue')
            self.assertEqual(e['geometry']['break_witnesses'],[])
            self.assertEqual(e['statement'],'stream continues, no break witnessed')
        self.assertEqual(r['edges'][-1]['kind'],'next_page')

    def test_first_indent_requires_paper_evidence(self):
        a=block('a',0,0); b=block('b',240,0)
        r=boxer.body_reading_order([page(1,a,b)])
        self.assertFalse(r['indent_model']['uses_indents'])
        self.assertEqual(r['edges'][0]['continuation'],'continue')
        b=block('b',240,0,indent=10)
        r=boxer.body_reading_order([page(1,a,b)])
        self.assertTrue(r['indent_model']['uses_indents'])
        self.assertEqual(r['edges'][0]['continuation'],'break')
        self.assertEqual(r['edges'][0]['geometry']['break_witnesses'][0]['kind'],'indent')

    def test_fullness_does_not_create_an_unwitnessed_break(self):
        a=block('a',0,0); a[2][-1]['box_px'][2]=40
        r=boxer.body_reading_order([page(1,a,block('b',240,0))])
        e=r['edges'][0]; self.assertFalse(e['geometry']['last_line_full'])
        self.assertEqual(e['continuation'],'continue')

    def test_gap_and_grammar_conflict(self):
        r=boxer.body_reading_order([page(1,block('a',0,0,texts=('A','B','mid-')),
                                           block('b',0,100,texts=('word continues','More','Last.')))])
        e=r['edges'][0]; self.assertTrue(e['grammar']['hyphen_completing_start'])
        self.assertEqual(e['continuation'],'undecided')
        self.assertEqual(e['geometry']['break_witnesses'][0]['kind'],'vertical-gap')

    def test_unknown_members_are_flagged_unplaced(self):
        p=page(1,block('a',0,0)); p['elements']=[]
        r=boxer.body_reading_order([p]); self.assertEqual(r['counts']['unplaced'],1)
        self.assertTrue(r['unplaced'][0]['flagged'])

    def test_terminal_and_numeral_grammar_is_inconclusive(self):
        for last,first in [('Ends.','lowercase'),('unfinished','12 percent'),('unfinished','Name')]:
            self.assertFalse(boxer.body_order_grammar(last,first)['confirms_continuation'])
        self.assertTrue(boxer.body_order_grammar('unfinished','lowercase')['confirms_continuation'])
        # D-488 compares boundary characters exactly; it does not strip quotes
        # or citations or require lowercase after an actual soft hyphen.
        self.assertTrue(boxer.body_order_grammar('inter\xad','Action')['confirms_continuation'])
        self.assertTrue(boxer.body_order_grammar('inter\x02','12')['confirms_continuation'])
        self.assertFalse(boxer.body_order_grammar('unfinished','“lowercase')['confirms_continuation'])

    def test_real_last_words_come_from_runs_not_abbreviated_metadata(self):
        p=page(1,block('a',0,0)); p['main_text']['blocks'][0]['text']='abbreviated text'
        r=boxer.body_reading_order([p]); self.assertTrue(r['blocks'][0]['last_words'].endswith('and finishes here.'))

    def test_replay_writes_only_ledger_and_is_deterministic(self):
        p=page(1,block('a',0,0),block('b',240,0))
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            file=Path(d)/'page-01.json'; file.write_text(json.dumps(p)); original=file.read_bytes()
            a=boxer.write_body_order(d); b=boxer.write_body_order(d)
            self.assertEqual(a,b); self.assertEqual(file.read_bytes(),original)
            self.assertEqual(set(f.name for f in Path(d).iterdir()),{'page-01.json','body-order.json'})

    def test_sparse_page_has_review_not_a_borrowed_column(self):
        r=boxer.body_reading_order([page(1,block('a',0,0,texts=('One line.',)),block('b',240,0,texts=('Second.',)))])
        self.assertTrue(all(b['flagged'] for b in r['blocks']))
        self.assertTrue(r['edges'][0]['order_flagged'])

    def test_empty_paper_reports_no_order_without_breaking_rule8(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as d:
            r=boxer.write_body_order(d)
            self.assertEqual(r['counts']['placed'],0)
            self.assertEqual(r['flags'],['no page records: body order cannot be assessed'])

    def test_larger_body_beside_smaller_references_uses_same_lane(self):
        p=page(1,block('lower',0,200,size=12),block('upper',.2,0,size=12),
               block('refs',240,0,texts=tuple('A reference line.' for _ in range(20)),size=10))
        self.assertEqual(ids(boxer.body_reading_order([p])),[(1,'upper'),(1,'lower'),(1,'refs')])

    def test_smaller_main_box_is_retained_with_ownership_review(self):
        p=page(1,block('a',0,0),block('note',0,100,texts=('A short footnote.',),size=7))
        r=boxer.body_reading_order([p])
        self.assertEqual(len(r['blocks']),2)
        self.assertIn('main box smaller than page body; ownership requires review',r['blocks'][1]['flags'])

    def test_indented_list_shares_column_right_edge(self):
        p=page(1,block('left',0,0),block('nested',270,0,170),
               block('body',240,100),block('last',250,200,190))
        r=boxer.body_reading_order([p])
        self.assertEqual(ids(r),[(1,'left'),(1,'nested'),(1,'body'),(1,'last')])
        self.assertEqual([c['box'] for c in r['pages'][0]['columns']],[[0,200],[240,440]])

    def test_bracketed_inset_quote_stays_between_surrounding_prose(self):
        p=page(1,block('before',0,0),block('quote',30,100,140),block('after',0,200),block('right',240,0))
        r=boxer.body_reading_order([p])
        self.assertEqual(ids(r),[(1,'before'),(1,'quote'),(1,'after'),(1,'right')])
        self.assertEqual(r['pages'][0]['columns'][0]['inset_witnesses'],['quote'])

    def test_page_wide_open_and_close_do_not_absorb_parallel_columns(self):
        p=page(1,block('intro',0,0,440),block('left',10,100,190),block('right',240,100,190),block('close',0,200,440))
        r=boxer.body_reading_order([p])
        self.assertEqual(ids(r),[(1,'intro'),(1,'left'),(1,'right'),(1,'close')])
        self.assertIn([10,200],[c['box'] for c in r['pages'][0]['columns']])
        self.assertIn([240,430],[c['box'] for c in r['pages'][0]['columns']])

    def test_recorded_panel_boundary_survives_geometric_reordering(self):
        bs=[block('left',0,100),block('panel',250,0,180),
            block('continued',240,100),block('new_paragraph',240,200)]
        for b,n in zip(bs,[1,3,2,4]): b[0]['order']=n
        p=page(1,*bs)
        p['main_text']['panels']=[dict(id='panel-region',blocks=['panel'],box_px=bs[1][0]['box_px'],
                                     order=3,move=dict(from_order=2,to_order=3,why='recorded paragraph boundary'))]
        original=copy.deepcopy(p);r=boxer.body_reading_order([p])
        self.assertEqual(ids(r),[(1,'left'),(1,'continued'),(1,'panel'),(1,'new_paragraph')])
        self.assertEqual(r['pages'][0]['panel_placements'][0]['after'],'continued')
        self.assertEqual(p,original)

    def test_conflicting_recorded_panel_boundary_is_flagged(self):
        ordinary=[dict(id=k,order=n,_flags=[]) for k,n in [('a',1),('b',4),('c',2)]]
        panel=dict(id='panel',order=3,_flags=[])
        original=[ordinary[0],panel,ordinary[1],ordinary[2]]
        result,records=boxer.body_order_preserve_panel_moves(original,[dict(id='p',blocks=['panel'],order=3,move=dict(to_order=3))])
        self.assertEqual(result,original)
        self.assertIn('conflicts',records[0]['status'])
        self.assertTrue(panel['_flags'])

    def test_shaped_paragraph_witnesses_narrow_column_without_saved_float(self):
        flow=block('flow',240,100,texts=tuple('A full line of body prose.' for _ in range(6)))
        for e in flow[2][:3]: e['box_px'][0]=300
        p=page(1,block('top',300,0,140),flow,block('left',0,210))
        r=boxer.body_reading_order([p])
        self.assertEqual(ids(r),[(1,'left'),(1,'top'),(1,'flow')])
        self.assertEqual(len(r['pages'][0]['columns']),2)
        self.assertEqual(r['pages'][0]['columns'][1]['shaped_column_witnesses'][0]['rows'],[0,1,2])

    def test_one_short_row_cannot_witness_a_shaped_column(self):
        flow=block('flow',240,100,texts=tuple('A full line of body prose.' for _ in range(6)))
        flow[2][0]['box_px'][0]=300
        r=boxer.body_reading_order([page(1,block('top',300,0,140),flow,block('left',0,210))])
        self.assertEqual(len(r['pages'][0]['columns']),3)


if __name__=='__main__': unittest.main()
