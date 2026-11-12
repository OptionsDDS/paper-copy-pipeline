"""Order scoring must not turn missing/ambiguous truth into a correct edge."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
spec=importlib.util.spec_from_file_location('score',Path(__file__).with_name('score_body_order.py'))
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

def rows(*xs):return [dict(text=x) for x in xs]

class Alignment(unittest.TestCase):
    def score_fixture(self,blocks,markdown,current=None):
        class Boxer:
            @staticmethod
            def body_order_rows(page,block):return block['rows']
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as td:
            p=Path(td)
            bs=[dict(id=str(i),cls='main',box_px=[0,i*20,100,i*20+10],rows=rows(*texts)) for i,texts in enumerate(blocks)]
            (p/'page-01.json').write_text(json.dumps(dict(page=1,main_text=dict(blocks=bs))))
            (p/'order.json').write_text(json.dumps(dict(blocks=[dict(page=1,id=x['id']) for x in bs],edges=[],unplaced=[])))
            (p/'copy.md').write_text(markdown)
            (p/'current.md').write_text(markdown if current is None else current)
            return s.score(dict(paper='fixture',cohort='truth',pages=str(p),order=str(p/'order.json'),truth=str(p/'copy.md'),current=str(p/'current.md')),Boxer)

    def test_unicode_and_hyphen_normalization(self):
        r=s.align(rows('A difﬁcult inter-','action, 50% of observations.'),s.normalise('A difficult interaction, 50% of observations.'))
        self.assertEqual(r['status'],'aligned');self.assertEqual(r['method'],'whole')
    def test_repeated_heading_stays_ambiguous(self):
        self.assertEqual(s.align(rows('Discussion'),s.normalise('Discussion text Discussion'))['status'],'unresolved')
    def test_interleaved_atomic_box_cannot_pass(self):
        a='The first printed line is long enough.';b='The second printed line is also long.'
        r=s.align(rows(a,b),s.normalise(b+' Other material. '+a))
        self.assertEqual(r['status'],'interleaved')
    def test_uncertainty_is_not_a_body_occurrence(self):
        self.assertEqual(s.visible('Body.\n## Places the program is not sure of\nMissing.'),'Body.\n')
    def test_missing_lines_are_not_individually_word_bag_matched(self):
        r=s.align(rows('a sentence with specific ordering'),s.normalise('ordering specific with sentence a'))
        self.assertEqual(r['status'],'unresolved')
    def test_unique_short_fragment_does_not_anchor_to_unrelated_paragraph(self):
        self.assertEqual(s.align(rows('and were'),s.normalise('Other findings and were excluded.'))['status'],'unresolved')
    def test_explicit_short_heading_is_still_an_anchor(self):
        text='## Methods\nSome body.'
        self.assertEqual(s.align(rows('Methods'),s.normalise(s.visible(text)),s.heading_offsets(text))['status'],'aligned')
    def test_source_table_header_cannot_borrow_reference_heading(self):
        r=self.score_fixture([['References'],['References','A sufficiently long reference list entry.']],
                             '## References\nA sufficiently long reference list entry.')
        self.assertEqual(r['alignments']['1:0']['status'],'unresolved')
    def test_two_source_boxes_cannot_claim_one_span(self):
        text='A sufficiently long and unique source paragraph.'
        r=self.score_fixture([[text],[text]],text)
        self.assertEqual(r['aligned'],0)
        self.assertFalse(r['rule9']['fully_right'])
    def test_empty_paper_is_not_a_correct_order(self):
        r=self.score_fixture([],'')
        self.assertFalse(r['rule9']['fully_right']);self.assertFalse(r['current_copy']['fully_right'])
        self.assertFalse(r['rule9']['aligned_order_right']);self.assertFalse(r['current_copy']['aligned_order_right'])
    def test_box_spanning_another_box_has_no_atomic_truth_order(self):
        a='The first printed line is sufficiently long.'
        b='The last printed line also has enough text.'
        note='A long separate note inserted inside that paragraph.'
        r=self.score_fixture([[a,b],[note]],a+' '+note+' '+b)
        self.assertEqual(r['aligned'],0)
        self.assertEqual(r['alignments']['1:0']['competing_boxes'],['1:1'])
        self.assertFalse(r['current_copy']['fully_right'])
    def test_touching_spans_are_valid_adjacency(self):
        a='The first paragraph is sufficiently long.'
        b='The second paragraph also has enough text.'
        r=self.score_fixture([[a],[b]],a+' '+b)
        self.assertTrue(r['rule9']['fully_right'])
        self.assertEqual(r['rule9']['edges']['right'],1)
    def test_plain_isolated_heading_does_not_become_a_missing_box(self):
        r=self.score_fixture([['A sufficiently long preceding paragraph.'],['Methods'],
                              ['A sufficiently long following paragraph.']],
                             'A sufficiently long preceding paragraph.\n\nMethods\n\nA sufficiently long following paragraph.')
        self.assertTrue(r['current_copy']['fully_right'])
        self.assertEqual(r['alignments']['1:1']['method'],'standalone text block')
    def test_table_row_cannot_supply_an_isolated_heading_anchor(self):
        text='Other body.\n\n| Methods |\n\nMore body.'
        self.assertNotIn('methods',s.heading_offsets(text))
    def test_unresolved_current_box_does_not_manufacture_a_wrong_order(self):
        a='A sufficiently long first paragraph.'
        b='A sufficiently long middle paragraph.'
        c='A sufficiently long final paragraph.'
        r=self.score_fixture([[a],[b],[c]],a+'\n\n'+b+'\n\n'+c,a+'\n\n'+c)
        self.assertEqual(r['current_copy']['edges'].get('wrong',0),0)
        self.assertEqual(r['current_copy']['edges']['unscored'],2)
        self.assertFalse(r['current_copy']['fully_right'])

if __name__=='__main__':unittest.main()
