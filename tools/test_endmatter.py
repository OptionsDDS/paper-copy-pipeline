"""Synthetic regressions for end sections and independently printed columns."""
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

paper = module('endmatter_copy', 'copy_paper.py')
boxer = module('endmatter_boxer', 'standalone/element_boxer_sc.py')

def block(name, box, text='Prose paragraph'):
    return dict(id=name, box_px=box, text=text)

def run(name, text, box):
    return dict(id=name, text=text, box_px=box, kind='text', line=box[1],
                angle=0, size_px=10, run_size_px=10)


class Endmatter(unittest.TestCase):
    def test_appendix_follows_both_columns_and_keeps_next_appendix_separate(self):
        bs = [block('left',[0,0,90,80]), block('right',[110,0,200,60]),
              block('a',[0,100,60,110],'APPENDIX A'),
              block('wide',[0,130,200,170]),
              block('b',[0,190,60,200],'APPENDIX B'),
              block('end',[0,220,200,260])]
        ordered,_ = boxer.reading_order_bands(bs,[[0,90],[110,200],[0,200]],10)
        self.assertEqual([b['id'] for b in ordered], [b['id'] for b in bs])

    def test_appendix_inside_continuing_column_does_not_cut_other_column(self):
        bs = [block('left',[0,0,90,80]),block('head',[0,100,60,110],'Appendix A'),
              block('right',[110,0,200,180])]
        self.assertEqual(boxer.reference_section_cuts(bs,[[0,90],[110,200]],10),[])

    def test_appendix_float_veto_and_prose_mention(self):
        bs=[block('head',[0,100,60,110],'Appendix A')]
        self.assertEqual(boxer.reference_section_cuts(bs,[[0,90],[110,200]],10,[[110,50,200,150]]),[])
        self.assertFalse(boxer.appendix_heading('Appendix A contains additional measurements.'))

    def column_runs(self):
        es=[]
        for side,x in [('l',0),('r',130)]:
            for i in range(3):
                es.append(run(side+str(i),'This sentence supplies several ordinary words in the prose column.',[x,i*15,x+100,i*15+10]))
        es.append(run('kw','Key words: alpha, beta, gamma',[0,60,230,70]))
        return {e['id']:e for e in es}

    def test_spanning_keyword_suffix_does_not_interleave_prose_columns(self):
        runs=self.column_runs()
        self.assertEqual(paper.prose_column_groups(list(runs),runs,10),
                         [['l0','l1','l2'],['r0','r1','r2'],['kw']])

    def test_crossing_prose_or_short_cells_do_not_form_columns(self):
        runs=self.column_runs()
        runs['cross']=run('cross','A full-width sentence crossing the gutter.',[0,46,230,56])
        self.assertEqual(paper.prose_column_groups(list(runs),runs,10),[list(runs)])
        del runs['cross']
        for e in runs.values():e['text']='Short cell'
        self.assertEqual(paper.prose_column_groups(list(runs),runs,10),[list(runs)])

    def reference_page(self):
        es=[];bs=[];mts=[]
        for i in range(3):
            x=110*i;ms=[]
            for j in range(2):
                e=run(f'{i}-{j}',f'{2*i+j+1}. Writer A. A study. Journal 2020.',[x,100+20*j,x+90,110+20*j])
                es.append(e);ms.append(e['id'])
            bs.append(dict(id=str(i),members=ms))
            mts.append(dict(id=str(i),cls='aside' if i==1 else 'main',order=None if i==1 else i+10,
                            in_refs=i!=1,size_px=10,box_px=[x,100,x+90,140]))
        return dict(elements=es,blocks=bs,main_text=dict(blocks=mts))

    def test_reference_island_enters_geometric_sequence(self):
        p=self.reference_page();paper.prepare_reference_islands([p],12)
        bs=p['main_text']['blocks']
        self.assertEqual([b['order'] for b in bs],[10,11,12])
        self.assertTrue(all(b['in_refs'] for b in bs))

    def test_reference_island_requires_cross_column_number_continuity(self):
        p=self.reference_page();p['elements'][2]['text']='13. Writer A. A study.'
        paper.prepare_reference_islands([p],12)
        self.assertIsNone(p['main_text']['blocks'][1]['order'])

    def test_trailing_address_box_is_not_a_reference_continuation(self):
        lines=['Writer A, Department of Research, University of Example.',
               'Correspondence: Writer A, Street 12.']
        self.assertTrue(paper.end_address_note(lines))
        self.assertFalse(paper.end_address_note(['12. Correspondence: University Hospital study.']))
        self.assertFalse(paper.end_address_note(['Writer A. University Hospital study.']))

    def keyword_block(self, lines, page, top):
        boxes=[[40,top+15*i,240,top+15*i+10] for i in range(len(lines))]
        return dict(lines=lines,page=page,meta=dict(box_px=paper.hull(boxes)),row_boxes=boxes,
                    sizes=[10]*len(lines),faces=['Regular']*len(lines),lefts=[40]*len(lines),
                    emphasis=['']*len(lines),prefixes=['']*len(lines))

    def test_keyword_continuation_joins_across_page_before_body_columns(self):
        a=self.keyword_block(['KEYWORDS','alpha, beta, gamma, delta, epsilon'],1,700)
        b=self.keyword_block(['zeta, eta, theta'],2,100)
        c=self.keyword_block(['Body starts here.'],2,300)
        pages=[([a],[],[]),([c,b],[],[])]
        paper.continue_keyword_lists(pages,12)
        self.assertEqual(a['lines'][-1],b['lines'][0]);self.assertEqual(pages[1][0],[c])
        self.assertEqual(a['_continued_keyword_page'],2)

    def test_keyword_continuation_requires_matching_typography(self):
        a=self.keyword_block(['KEYWORDS','alpha, beta, gamma, delta, epsilon'],1,700)
        b=self.keyword_block(['zeta, eta, theta'],2,100);b['faces']=['Italic']
        pages=[([a],[],[]),([b],[],[])]
        paper.continue_keyword_lists(pages,12)
        self.assertEqual(pages[1][0],[b])

    def test_styled_section_after_keywords_is_not_a_keyword_continuation(self):
        a=self.keyword_block(['KEYWORDS','alpha, beta, gamma, delta, epsilon',
                              'Summary panel','A separate paragraph, with a continued'],1,700)
        a['faces'][2]='Bold';a['sizes'][2]=12
        b=self.keyword_block(['sentence, its explanation, and its examples.'],2,100)
        pages=[([a],[],[]),([b],[],[])]
        paper.continue_keyword_lists(pages,12)
        self.assertEqual(pages[1][0],[b])
        self.assertEqual(a['lines'][-1],'A separate paragraph, with a continued')

    def test_italic_terms_keep_the_keyword_family(self):
        a=self.keyword_block(['KEYWORDS','alpha, beta, gamma, delta, epsilon',
                              'a scientific name'],1,700)
        a['faces']=['Text-Regular','Text-Regular','Text-Italic']
        b=self.keyword_block(['zeta, eta, theta'],2,100);b['faces']=['Text-Italic']
        pages=[([a],[],[]),([b],[],[])]
        paper.continue_keyword_lists(pages,12)
        self.assertFalse(pages[1][0])

    def test_table_foot_note_owned_once_with_its_continuation(self):
        t=dict(kind='table',page=2,box=[0,20,200,100],notes=['Abbreviation, expanded form.'])
        n=dict(kind='para',page=2,box=[0,102,200,120],text='Abbreviation, expanded form. * Further note.')
        result=paper.flow_furniture([n,t],[dict(page=2,elements=[],blocks=[])],10)
        self.assertEqual(result,[t]);self.assertEqual(t['notes'],[n['text']])
        n['box']=[220,102,420,120]
        self.assertEqual(len(paper.flow_furniture([n,t],[dict(page=2,elements=[],blocks=[])],10)),2)


if __name__=='__main__':unittest.main()
