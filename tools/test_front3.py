"""Front-panel ownership, mixed reference columns and uncertain unit glyphs."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


paper = module('front3_copy', ROOT / 'copy_paper.py')
fonts = module('front3_fonts', ROOT / 'tools/check_fonts.py')


class Byline(unittest.TestCase):
    def read(self, delayed=False, body_first=False):
        boxer = module('front3_boxer', ROOT / 'standalone/element_boxer_sc.py')
        chars = []; runs = []; blocks = []; classes = []
        specs = [('title', 'Properties of novel surfaces', 20, 100, 30, 'aside' if delayed else 'title'),
                 ('names', 'Ada Example1, Ben', 700 if not delayed else 30, 100 if not delayed else 280, 18, 'other'),
                 ('names', 'Q. Sample1', 700 if not delayed else 30, 123 if not delayed else 303, 18, 'other'),
                 ('address' if delayed else 'names', '1Department of Science, Example University', 700 if not delayed else 20, 153 if not delayed else 500, 12, 'other')]
        if delayed:
            specs[1] = ('names', 'Ada Example, DDS1', 30, 280, 18, 'main')
            specs[2] = ('names', 'Ben Q. Sample, DDS1', 30, 303, 18, 'main')
        for i,(bid,text,left,top,size,cls) in enumerate(specs):
            x = left; ids=[]
            for ch in text:
                if not ch.isspace():
                    ids.append(len(chars)); chars.append(dict(text=ch,x0=x,y0=top,x1=x+.45*size,y1=top+.7*size,
                        size=size,font='Regular',origin=(x,top+.7*size),adv_x1=x+.5*size))
                x += .5*size
            e=dict(id=f'run:{i}',kind='text',text=text,box_px=[left,top,x,top+.7*size],
                   size_px=size,run_size_px=size,line=i+1,angle=0,char_ids=ids)
            runs.append(e)
            block=next((b for b in blocks if b['id']==bid),None)
            if block: block['members'].append(e['id']);block['box_px']=paper.hull([block['box_px'],e['box_px']])
            else:
                blocks.append(dict(id=bid,members=[e['id']],box_px=e['box_px']))
                classes.append(dict(id=bid,cls=cls,size_px=size,order=None,lines=1,box_px=e['box_px']))
        p=dict(page=2 if delayed else 1,elements=runs,blocks=blocks,
               main_text=dict(blocks=classes,body_size_px=16),region_box_px=[0,0,1200,1600],art=[])
        paths=['page-01.json','page-02.json'] if delayed else ['page-01.json']
        blank=dict(page=1,elements=[],blocks=[],main_text=dict(blocks=[]),region_box_px=p['region_box_px'])
        if body_first:
            blank['elements']=[dict(runs[0],text='Body prose begins here',run_size_px=16)]
        with patch.object(boxer,'page_files',return_value=paths), \
             patch.object(boxer,'read_json',side_effect=lambda path: blank if delayed and str(path).endswith('page-01.json') else p), \
             patch.object(boxer,'pdfium_characters',return_value=chars), patch.object(boxer,'write_json'):
            return boxer.authors_and_affiliations('unused','unused')

    def test_sidebar_given_name_continues_before_middle_initial(self):
        self.assertEqual([a['name'] for a in self.read()['authors']], ['Ada Example','Ben Q. Sample'])

    def test_first_text_page_can_have_a_detached_marked_byline(self):
        result=self.read(delayed=True)
        self.assertEqual(result['page'],2)
        self.assertEqual([a['name'] for a in result['authors']], ['Ada Example','Ben Q. Sample'])
        self.assertEqual(result['checks']['status'],'verified')

    def test_search_does_not_skip_a_page_with_body_words(self):
        result=self.read(delayed=True,body_first=True)
        self.assertNotIn('page',result)
        self.assertFalse(result['checks']['title_found'])


class UnitOutlines(unittest.TestCase):
    def test_only_number_unit_prefixes(self):
        for token in ('50 ll', '2.5 lm', '10 ug', '3 mm', '4 umol', '25 ml'):
            self.assertEqual(len(fonts.unit_prefix_offsets(token)), 1, token)
        for token in ('small', 'lemma', '2 mmolars', 'a50 ll', '50 urea', 'lm'):
            self.assertFalse(fonts.unit_prefix_offsets(token), token)

    def test_weak_mu_is_flagged_only_in_units(self):
        scores = {'l': .37, 'μ': .65, 'µ': .66, 'P': .49}
        self.assertEqual(fonts.outline_decision('l', scores), ('unchanged', 'l'))
        self.assertEqual(fonts.outline_decision('l', scores, unit=True), ('uncertain', 'l'))
        self.assertEqual(fonts.outline_decision('m', {'m': .85, 'μ': .55}, unit=True), ('confirmed', 'm'))
        self.assertEqual(fonts.outline_decision('u', {'u': .5, 'μ': .65, 'v': .6}, unit=True), ('unchanged', 'u'))

    def test_evidence_context_and_identity_are_revalidated(self):
        scores = {'l': .37, 'μ': .65, 'µ': .66, 'P': .49}
        sub = dict(model=fonts.OUTLINE_MODEL, font='f', source_code=108,
                   before='l', after='l', status='uncertain', offset=3, char_id=2)
        chars = [dict(text=ch, font='f', source_code=108 if ch=='l' else ord(ch)) for ch in '50ll']
        e = dict(id='run:1', text='50 ll', char_ids=list(range(4)))
        p = dict(page=2, fonts={'f': {'outline_verification': {'108': dict(sub, scores=scores)}}})
        self.assertTrue(fonts.valid_outline_occurrence(p, e, sub, chars))
        self.assertIn('possible Greek mu', fonts.outline_notice(p, e, sub))
        e['text'] = 'no ll'; chars[0]['text']='n'; chars[1]['text']='o'
        self.assertFalse(fonts.valid_outline_occurrence(p, e, sub, chars))


class ReferenceColumns(unittest.TestCase):
    def fixture(self, refsize=8):
        specs = [('tail', 'accuracy continues here.', [220, 10, 310, 40], 10, 4, False),
                 ('head', 'References', [220, 60, 310, 72], 12, 1, False),
                 ('left', 'Body paragraph continuing from the previous page.', [0, 100, 90, 180], 10, 6, True),
                 ('conclusion', 'Conclusions', [110, 120, 200, 132], 12, 1, False),
                 ('ending', 'The conclusion ends with improved', [110, 150, 200, 200], 10, 4, False),
                 ('refs', '1. Example A.', [220, 90, 310, 180], refsize, 6, True)]
        p = dict(elements=[], blocks=[], main_text=dict(columns=[[0,90],[110,200],[220,310]], blocks=[]))
        for i,(name,text,box,size,lines,ref) in enumerate(specs):
            p['elements'].append(dict(id=name,kind='text',text=text,box_px=box))
            p['blocks'].append(dict(id=name,members=[name]))
            p['main_text']['blocks'].append(dict(id=name,cls='main',order=i,box_px=box,size_px=size,lines=lines,in_refs=ref))
        p['elements'].append(dict(id='ref2',kind='text',text='2. Another B.',box_px=[220,140,310,150]))
        p['blocks'][-1]['members'].append('ref2')
        return p

    def test_body_columns_finish_before_reference_column(self):
        p = self.fixture(); paper.prepare_reference_columns([p], 10)
        blocks = sorted(p['main_text']['blocks'], key=lambda b:b['order'])
        self.assertEqual([b['id'] for b in blocks], ['left','conclusion','ending','tail','head','refs'])
        self.assertFalse(blocks[0]['in_refs']); self.assertTrue(blocks[-1]['in_refs'])

    def test_same_size_reference_style_does_not_license_reorder(self):
        p = self.fixture(refsize=10); before = copy.deepcopy(p)
        paper.prepare_reference_columns([p], 10)
        self.assertEqual(p, before)

    def test_numbered_entries_in_larger_type_are_not_body_prose(self):
        p = self.fixture()
        next(e for e in p['elements'] if e['id']=='left')['text']='1. An entry in larger type.'
        before=copy.deepcopy(p); paper.prepare_reference_columns([p],10)
        self.assertEqual(p,before)

    def test_recovered_body_keeps_witnessed_compound_prefix(self):
        lines=['The load-', 'resistance was measured.', 'An independent load-bearing frame.']
        runs=[dict(id=str(i),kind='text',text=t,angle=0,box_px=[0,i*20,100,i*20+10]) for i,t in enumerate(lines)]
        p=dict(elements=runs,blocks=[dict(id='body',members=['0','1'])],
               copy_reference_columns=dict(body_blocks=['body']))
        joiner=paper.Joiner(lines);paper.witness_reference_body_compounds([p],joiner)
        self.assertEqual(joiner.lines(lines[:2]),'The load-resistance was measured.')
        # An actual closed spelling remains stronger than the prefix witness.
        joiner=paper.Joiner(lines+['loadresistance']);paper.witness_reference_body_compounds([p],joiner)
        self.assertEqual(joiner.lines(lines[:2]),'The loadresistance was measured.')


class ScanFront(unittest.TestCase):
    def test_address_after_cover_keeps_lines_and_every_source_run(self):
        def run(text, x, y, w=140, h=12):
            return dict(text=text,box_px=[x,y,x+w,y+h],size_px=12)
        address = ['A. EXAMPLE', 'Pathology Division', 'Centre for Applied Research', 'Example Town', 'Country']
        runs = [run(t,20,100+i*15) for i,t in enumerate(address)]
        runs += [run('Abstract: these words describe the printed research.',20,200,260),
                 run('The summary continues with further ordinary words.',20,215,260)]
        runs += [run('These words form the adjacent body column.',350,y,260) for y in (100,120,140,160)]
        runs.append(run('T With a tall initial and another continuation.',350,96,260,70))
        p = dict(page=2,region_box_px=[0,0,650,800],elements=[],scan_evidence=dict(ocr_layer=True,ocr_runs=runs))
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            text = Path(paper.copy_ocr_scan(tmp,[p],{})).read_text()
            self.assertIn('\n'.join(address), text)
            audit = json.loads((Path(tmp)/'copy.scan.json').read_text())['pages'][0]
            self.assertEqual(len(audit['destinations']),len(runs))


if __name__ == '__main__': unittest.main()
