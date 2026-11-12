"""Manuscript float and section regressions using invented printed geometry.

Run: /usr/bin/python3 -I tools/test_manuscript.py
"""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('copy_paper', ROOT / 'copy_paper.py')
paper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paper)


def run(name, value, y, x=40, width=220):
    return dict(id=name, kind='text', text=value, box_px=[x,y,x+width,y+10],
                angle=0, line=y, size_px=10, run_size_px=10, font='Regular')


def page(es, groups, floats=(), furniture=()):
    blocks = [dict(id=name, members=[e['id'] for e in members],
                   box_px=paper.hull(e['box_px'] for e in members)) for name,members in groups]
    meta = [dict(b, cls='main', order=i, lines=len(groups[i][1]), size_px=10)
            for i,b in enumerate(blocks) if b['id']=='body' or b['id']=='heading']
    return dict(page=2, elements=es, blocks=blocks, tables=[], floats=list(floats),
                region_box_px=[0,0,300,500], main_text=dict(blocks=meta, columns=[[40,260]],
                furniture=[dict(members=[e['id']]) for e in furniture]))


class Manuscripts(unittest.TestCase):
    def test_image_table_has_explicit_decision_without_empty_line_fallback(self):
        cap=run('caption','TABLE 7. Measurements.',200)
        size=run('size','120x80mm (300 x 300 DPI)',220)
        img=dict(id='image',kind='image',box_px=[40,20,260,180])
        f=dict(id='float',caption=cap['text'],blocks=['caption','image'],box_px=[40,20,260,230],
               _line_fallback_ids=['size'])
        p=page([cap,size,img],[('caption',[cap]),('image',[img]),('size',[size])],[f],[size])
        uncertain=[]
        with patch.object(paper,'table_float_regions',lambda p,body:p):
            _,floats,_=paper.read_page(p,10,uncertain)
        _,kind,caption,rows,notes,placement=floats[0]
        self.assertTrue(placement['image_only'])
        item=dict(kind=kind,caption=caption,rows=rows,notes=notes,page=2,**placement)
        decisions=paper.gate_tables([item],[p],uncertain)
        self.assertEqual(decisions[0]['decision'],'image_not_read')
        self.assertNotIn('table_gate',item)
        self.assertTrue(any('image; not read' in s for s in uncertain))

    def test_missing_grid_without_image_is_not_claimed_to_be_an_image(self):
        cap=run('caption','TABLE 7. Measurements.',200)
        f=dict(id='float',caption=cap['text'],blocks=['caption'],box_px=cap['box_px'])
        p=page([cap],[('caption',[cap])],[f])
        with patch.object(paper,'table_float_regions',lambda p,body:p):
            _,floats,_=paper.read_page(p,10,[])
        self.assertFalse(floats[0][-1]['image_only'])

    def test_image_with_printed_cells_keeps_its_text_fallback(self):
        cap=run('caption','TABLE 7. Measurements.',200)
        cell=run('cell','Observed value 42',240)
        img=dict(id='image',kind='image',box_px=[40,20,260,180])
        f=dict(id='float',caption=cap['text'],blocks=['caption','image'],box_px=[40,20,260,250],
               _line_fallback_ids=['cell'])
        p=page([cap,cell,img],[('caption',[cap]),('cell',[cell]),('image',[img])],[f])
        with patch.object(paper,'table_float_regions',lambda p,body:p):
            _,floats,_=paper.read_page(p,10,[])
        self.assertFalse(floats[0][-1]['image_only'])
        self.assertIn('Observed value 42',str(floats[0][-1]['table_source']))

    def test_captionless_image_float_is_declared(self):
        img=dict(id='image',kind='image',box_px=[40,20,260,180])
        f=dict(id='float',caption='',blocks=['image'],box_px=img['box_px'])
        p=page([img],[('image',[img])],[f])
        with patch.object(paper,'table_float_regions',lambda p,body:p):
            _,floats,_=paper.read_page(p,10,[])
        self.assertTrue(floats[0][-1]['image_only'])

    def test_recurring_caption_cannot_return_as_a_table_cell(self):
        cap=run('caption','TABLE 7. (Continued)',30)
        cell=run('cell','Observed value',70)
        f=dict(id='float',caption=cap['text'],blocks=['table'],
               box_px=[40,30,260,80],_caption_ids=['caption'])
        p=page([cap,cell],[],[f],[cap])
        p['tables']=[dict(id='table',members=['caption','cell'],box_px=f['box_px'],angle=0)]
        seen=[]
        def rows(es,*args):
            seen.extend(e['text'] for e in es)
            return [['Observed value']],[]
        with patch.object(paper,'table_float_regions',lambda p,body:p), patch.object(paper,'table_rows',rows):
            _,floats,_=paper.read_page(p,10,[])
        self.assertEqual(seen,['Observed value'])
        self.assertEqual(floats[0][2],'Table 7. (Continued)')

    def test_independent_heading_in_blank_row_gap_keeps_printed_order(self):
        first=run('first','First title line',50)
        last=run('last','Final title line.',110)
        middle=run('middle','Middle title line',80)
        p=page([first,last,middle],[('body',[first,last]),('heading',[middle])])
        with patch.object(paper,'table_float_regions',lambda p,body:p):
            blocks,_,_=paper.read_page(p,10,[])
        self.assertEqual([line for b in blocks for line in b['lines']],
                         ['First title line','Middle title line','Final title line.'])

    def test_equation_symbol_in_blank_gap_remains_a_separate_block(self):
        first=run('first','The displayed relation',50)
        last=run('last','The following explanation.',110)
        symbol=run('symbol','=',80)
        p=page([first,last,symbol],[('body',[first,last]),('heading',[symbol])])
        with patch.object(paper,'table_float_regions',lambda p,body:p):
            blocks,_,_=paper.read_page(p,10,[])
        self.assertEqual(len(blocks),2)

    def test_reviewer_label_and_salutation_are_section_boundaries(self):
        for line in ['Dear Editor,','Referee: 2','Reviewer 3']:
            self.assertTrue(paper.LETTER_HEAD.fullmatch(line))
        self.assertFalse(paper.LETTER_HEAD.fullmatch('The reviewer 3 rating was high.'))
        for line in ['Acknowledgements','Figure legends','Legend']:
            self.assertTrue(paper.REF_END.fullmatch(line))

    def test_cleaned_manuscript_reference_gaps_still_separate_entries(self):
        b=dict(lines=['Able, A. (2001) First study.', 'Journal 1: 2-3.',
                      'Baker, B. (2002) Second study.', 'Journal 2: 4-5.'],
               lefts=[40]*4, row_boxes=[[40,y,260,y+10] for y in [10,24,52,66]],
               meta=dict(size_px=10),preserve_row_gaps=True)
        parts=paper.split_references(b,paper.Joiner(b['lines']))
        self.assertEqual(len(parts),2)
        self.assertTrue(parts[1][0].startswith('Baker,'))

    def test_fused_margin_prefix_requires_verified_neighbouring_numbers(self):
        nums=[run(f'n{i}',str(i),20*i,10,5) for i in range(1,15) if i != 8]
        label=run('label','8 Description',160,10,200)
        label['_chars']=[dict(text='8',font='Regular',x0=10,y0=160,x1=15,y1=170)] + [
            dict(text=c,font='Regular',x0=40+5*i,y0=160,x1=45+5*i,y1=170) for i,c in enumerate('Description')]
        p=page(nums+[label],[('body',[label])],furniture=nums)
        for f in p['main_text']['furniture']:f['why']='consecutive manuscript line numbers in the margin'
        with patch.object(paper,'table_float_regions',lambda p,body:p):
            blocks,_,_=paper.read_page(p,10,[])
        self.assertEqual(blocks[0]['lines'],['Description'])
        self.assertEqual(p['copy_manuscript_furniture'][0]['text'],'8')
        label['_chars'][0].update(x0=40,x1=45)
        with patch.object(paper,'table_float_regions',lambda p,body:p):
            blocks,_,_=paper.read_page(p,10,[])
        self.assertEqual(blocks[0]['lines'],['8 Description'])
        self.assertNotIn('copy_manuscript_furniture',p)


if __name__ == '__main__':
    unittest.main()
