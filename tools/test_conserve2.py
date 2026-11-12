"""Occurrence conservation, wrapped identifiers and cross-column term lists."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
c=module('copy_conserve2','copy_paper.py')
a=module('audit_conserve2','tools/conserve.py')
h=module('helpers_conserve2','tools/test_box_ownership.py')

class Occurrences(unittest.TestCase):
    def runs(self,*texts):
        return [dict(page=1,id=str(i),text=t,box=[0,i*10,100,i*10+9]) for i,t in enumerate(texts)]

    def test_output_occurrence_cannot_satisfy_two_source_tokens(self):
        result=a.token_ledger('Measured value 1234.',self.runs('Measured value 1234.','1234'))
        self.assertEqual(result['missing_tokens'],1)
        self.assertEqual(result['tokens'][-1]['status'],'missing')
        self.assertEqual(a.token_ledger('Measured value 12345.',self.runs('1234'))['missing_tokens'],1)

    def test_wrapped_word_and_url_use_disjoint_output_spans(self):
        result=a.token_ledger('The examination. https://example.org/1234-5678',
                             self.runs('The exam-','ination.','https://example.org/1234-','5678'))
        self.assertEqual(result['missing_tokens'],0)
        spans=[t['output'] for t in result['tokens']]
        self.assertTrue(all(min(b,d)<=max(a,c) for i,(a,b) in enumerate(spans) for c,d in spans[i+1:]))

    def test_extra_output_run_is_reported_and_sign_is_not_silently_ignored(self):
        result=a.token_ledger('Measured response increased. Measured response increased.',self.runs('Measured response increased.'))
        self.assertEqual(len(result['extra_run_occurrences']),1)
        self.assertEqual(a.token_ledger('one two',self.runs('one = two'))['missing_tokens'],1)

    def test_marker_does_not_steal_another_tokens_suffix(self):
        result=a.token_ledger('Name1; Name2. 1',self.runs('Name1 and Name2','1'))
        self.assertEqual([t['text'] for t in result['tokens'] if t['status']=='missing'],['and'])
        self.assertEqual(a.token_ledger('2.9',self.runs('2'))['missing_tokens'],1)

    def test_single_glyph_runs_use_their_printed_baseline_order(self):
        text='Printedcopyright'
        runs=[dict(page=1,id=str(i),text=ch,box=[i*6,10,i*6+5,20]) for i,ch in enumerate(text)]
        self.assertEqual(a.token_ledger(text,list(reversed(runs)))['missing_tokens'],0)

    def test_saved_status_cannot_hide_edited_output_and_metadata_is_not_evidence(self):
        saved=dict(token_ledger=a.token_ledger('1234',self.runs('1234')))
        result=a.audit_run_tokens('', 'page 1234: run:1234', {}, {}, saved)
        self.assertEqual(result['missing_tokens'],1)
        result=a.audit_run_tokens('', 'page 1: token not placed: "1234"', {}, {}, saved)
        self.assertEqual(result['reported_tokens'],1)

class Placement(unittest.TestCase):
    def test_wrapped_numeric_identifier_is_not_furniture(self):
        es=[h.run('name','A Name',10,80,40),h.run('url','https://example.org/1234-',60,80,110),
            h.run('tail','5678',10,94,30)]
        p=h.page(es)
        p['blocks']=[dict(id='original',members=['name','url','tail'],box_px=[10,80,170,103]),
                     dict(id='text',members=['name','url'],box_px=[10,80,170,89]),
                     dict(id='folio',members=['tail'],box_px=[10,94,40,103])]
        p['main_text']['blocks']=[dict(id='text',cls='main',order=1),dict(id='folio',cls='furniture')]
        p['main_text']['furniture']=[dict(members=['tail'],why='page number outside the page text frame')]
        p['copy_conservation']=dict(excluded=[dict(id='tail',text='5678',box=es[-1]['box_px'],reason='page number outside the page text frame')])
        self.assertEqual(a.exclusions(p),[])
        c.restore_wrapped_url_tails([p])
        self.assertNotIn('tail',c.table_furniture(p))
        self.assertIn('tail',p['blocks'][1]['members'])
        # A detached folio without a URL witness stays furniture.
        q=copy.deepcopy(p);q['elements'][1]['text']='Ordinary printed text'
        q['copy_conservation']['excluded'][0]['id']='tail'
        self.assertEqual(len(a.exclusions(q)),1)

    def test_abbreviations_cross_columns_then_page_before_references(self):
        es=[h.run('head','Abbreviations',10,500,100,size=12)]
        for col,left,top in [('a',10,530),('b',240,20)]:
            for i in range(3):
                es += [h.run(col+'t'+str(i),'Term'+str(i)+':',left,top+i*30,40),
                       h.run(col+'d'+str(i),'Meaning with words',left+90,top+i*30,100)]
        es.append(h.run('pending','LAST:',240,730,40))
        p=h.page(es)
        q=h.page([h.run('carry','Continued meaning',100,20,140),
                  h.run('stop','References',10,200,100,size=12)],2)
        for i in range(3):
            q['elements'] += [h.run('t'+str(i),'New'+str(i)+':',10,60+i*30,40),
                              h.run('d'+str(i),'Other meaning',100,60+i*30,130)]
        q=h.page(q['elements'],2)
        c.prepare_abbreviation_boxes([p,q],10)
        self.assertEqual([r.get('term_text') for r in p['_definition_layout'][1:]],
                         ['Term0','Term1','Term2','Term0','Term1','Term2','LAST'])
        self.assertEqual(q['_definition_layout'][0]['kind'],'definition_continuation')
        self.assertNotIn('stop',{m for r in q['_definition_layout'] for m in r['members']})
        self.assertEqual(len({m for r in p['_definition_layout'] for m in r['members']}),len(es))

    def test_sentence_cannot_skip_an_intervening_pages_body(self):
        items=[dict(kind='para',page=1,text='The preceding result showed that this'),
               dict(kind='para',page=2,barrier=True,flow_start=(2,0,True),flow_end=(2,0,True),text='The body of the intervening page has words. '*6),
               dict(kind='para',page=3,text='of another result.')]
        result=c.rejoin_paragraphs(items,c.Joiner([]))
        self.assertEqual(len(result),3)

    def test_long_float_side_text_does_not_block_witnessed_body_join(self):
        items=[dict(kind='para',page=1,text='The preceding result showed that this'),
               dict(kind='side',page=2,text='A long table caption or note has words. '*6),
               dict(kind='para',page=3,text='is a valid continuation.')]
        result=c.rejoin_paragraphs(items,c.Joiner([]))
        self.assertIn('this is a valid continuation.',result[0]['text'])

if __name__=='__main__':unittest.main()
