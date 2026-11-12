"""Mixed title runs, end-only addresses, and overlapping OCR name segments."""
import importlib.util
import statistics
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


boxer = module('front5_boxer', ROOT/'standalone/element_boxer_sc.py')
paper = module('front5_copy', ROOT/'copy_paper.py')
conserve = module('front5_conserve', ROOT/'tools/conserve.py')


def page(number, specs):
    chars = []; runs = []; blocks = []; classes = []
    for i, (text, y, size, cls, bid, special) in enumerate(specs):
        x = 20; ids = []; sizes = []
        for j, ch in enumerate(text):
            em, raised = special.get(j, (size, False))
            if not ch.isspace():
                ids.append(len(chars)); sizes.append(em)
                chars.append(dict(text=ch, x0=x, x1=x+.45*em, y0=y-(5 if raised else 0),
                    y1=y+.7*em-(5 if raised else 0), size=em, font='Regular',
                    origin=(x,y+.7*em), adv_x1=x+.5*em))
            x += .5*em
        e = dict(id=str(i), text=text, kind='text', line=i, angle=0, size_px=size,
                 run_size_px=statistics.median(sizes), char_ids=ids, box_px=[20,y,x,y+.7*size])
        runs.append(e)
        b = next((b for b in blocks if b['id']==bid), None)
        if b:
            b['members'].append(e['id']); b['box_px']=paper.hull([b['box_px'],e['box_px']])
        else:
            blocks.append(dict(id=bid,members=[e['id']],box_px=e['box_px']))
            classes.append(dict(id=bid,cls=cls,box_px=e['box_px']))
    return dict(page=number,elements=runs,blocks=blocks,art=[],region_box_px=[0,0,1000,1400],
                main_text=dict(body_size_px=16,blocks=classes)), chars


def parse(fixtures):
    paths = [f'page-{i+1:02}.json' for i in range(len(fixtures))]
    with patch.object(boxer,'page_files',return_value=paths), \
         patch.object(boxer,'read_json',side_effect=lambda p:fixtures[paths.index(p)][0]), \
         patch.object(boxer,'pdfium_characters',side_effect=lambda p,n:fixtures[n-1][1]), \
         patch.object(boxer,'write_json'):
        return boxer.authors_and_affiliations('unused','unused')


class NativeFront(unittest.TestCase):
    def test_split_badge_needs_both_placements(self):
        authors=dict(title_rows=[dict(run='title',text='Properties of surfaces')],
                     title_exclusions=[dict(run='title',text='OPEN',reason='access badge')])
        self.assertTrue(paper.front_run_placed(dict(id='title'),authors,
                        conserve.CopyIndex('# Properties of surfaces\n\n- OPEN')))
        self.assertFalse(paper.front_run_placed(dict(id='title'),authors,
                         conserve.CopyIndex('# Properties of surfaces')))

    def test_byline_separator_change_requires_names_and_markers(self):
        authors=dict(checks=dict(status='verified'),author_run_ids=['names'],affiliation_sources=[dict(page=3)],
            authors=[dict(name='Ada Example',markers=['1']),dict(name='Ben Sample',markers=['2'])])
        run=dict(id='names',text='Ada Example1 and Ben Sample2')
        self.assertTrue(paper.front_run_placed(run,authors,conserve.CopyIndex('Ada Example 1; Ben Sample 2')))
        self.assertFalse(paper.front_run_placed(run,authors,conserve.CopyIndex('Ada Example 1; Ben Sample 1')))

    def title(self, text, special):
        return parse([page(1,[
            ('Properties of novel surfaces',100,30,'title','title',{}),
            (text,125,30,'title','title',special),
            ('Ada Example1, Ben Sample1',165,20,'authors','byline',{}),
            ('1Department of Science',200,12,'other','address',{})])])

    def test_tiny_production_suffix_cannot_hide_final_title_line(self):
        text='in a cohort studytag_12345 101..120'
        a=self.title(text,{i:(1,False) for i in range(len('in a cohort study'),len(text))})
        self.assertTrue(a['title']['text'].endswith('in a cohort study'))
        self.assertEqual([n['name'] for n in a['authors']],['Ada Example','Ben Sample'])
        self.assertEqual(a['checks']['status'],'verified')

    def test_ordinary_smaller_title_words_are_retained(self):
        a=self.title('in a cohort study',{i:(24,False) for i in range(4)})
        self.assertTrue(a['title']['text'].endswith('in a cohort study'))
        self.assertNotIn('title_exclusions',a)

    def test_badge_inside_same_run_is_not_title(self):
        a=self.title('OPEN Surface responses',{i:(20,False) for i in range(5)})
        self.assertNotIn('OPEN',a['title']['text'])
        self.assertEqual(a['title_exclusions'][0]['reason'],'access badge')

    def test_open_at_title_size_is_an_actual_title_word(self):
        a=self.title('OPEN questions in biology',{})
        self.assertIn('OPEN questions',a['title']['text'])

    def test_header_digit_is_not_an_address_and_end_panel_links(self):
        first=page(1,[('Example et al. 3D Science (2020) 2:10',20,12,'other','head',{}),
            ('Properties of novel surfaces',100,30,'title','title',{}),
            ('Ada Example1, Ben Sample3',145,20,'authors','byline',{}),
            ('1Department of Science',185,12,'other','address',{})])
        text='1Department of Science. 3Centre for Biology.'
        later=page(2,[('Author details',100,12,'main','panel',{}),
            (text,120,12,'main','panel',{i:(7,True) for i,ch in enumerate(text) if ch.isdigit()})])
        a=parse([first,later])
        self.assertEqual([x['text'] for x in a['affiliations']],
                         ['Department of Science.','Centre for Biology.'])
        self.assertEqual([x['page'] for x in a['affiliations']],[2,2])
        self.assertIsNone(a['affiliation_box_px'])
        self.assertEqual(a['article_info'][0]['block'],'head')
        self.assertFalse(a['checks']['markers_without_affiliation'])

    def test_unlabelled_or_unraised_late_numbers_cannot_supply_links(self):
        first=page(1,[('Properties of novel surfaces',100,30,'title','title',{}),
            ('Ada Example1, Ben Sample2',145,20,'authors','byline',{})])
        for heading in ('Results','Author details'):
            later=page(2,[(heading,100,12,'main','panel',{}),
                ('1Department of Science. 2Centre for Biology.',120,12,'main','panel',{})])
            self.assertEqual(parse([first,later])['affiliations'],[])


class ScanFront(unittest.TestCase):
    def test_overlapping_segments_stay_whole_even_if_pdf_order_is_reversed(self):
        groups=[]
        for n,(word,x,size) in enumerate([('ALICE',20,30),('Q.',65,20),('EXAMPLE,',95,30),
                                        ('&',250,30),('BEN',300,30),('SAMPLE',370,30)]):
            cs=[dict(text=c,size=size,x0=x+i*12,x1=x+(i+1)*12,origin=(x+i*12,210),
                     adv_x1=x+(i+1)*12,paint_order=(10-n,i)) for i,c in enumerate(word)]
            cs[-1]['space_after']=True;groups.extend(cs)
        chars=sorted(groups,key=lambda c:c['x0'])
        run=dict(text=paper.scan_character_text(chars),size_px=30,box_px=[20,180,500,210])
        source=[dict(size_px=60,box_px=[20,100,600,150]),run]
        fixed=paper.scan_front_order(chars,run,source,1000)
        self.assertEqual(paper.scan_character_text(fixed),'ALICE Q. EXAMPLE, & BEN SAMPLE')
        self.assertEqual({id(c) for c in fixed},{id(c) for c in chars})
        self.assertEqual(paper.scan_front_order(chars,run,[run],1000),chars)


if __name__=='__main__': unittest.main()
