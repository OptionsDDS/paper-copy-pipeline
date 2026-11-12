"""A stacked expression owns its operands before prose baselines are joined."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('formulas',Path(__file__).resolve().parents[1]/'copy_paper.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)


def run(name,text,x,y,size=10):
    chars=[dict(text=ch,x0=x+i*5,x1=x+i*5+4,y0=y-size*.7,y1=y,
                origin=(x+i*5,y),size=size,adv_x1=x+(i+1)*5) for i,ch in enumerate(text)]
    return dict(id=name,kind='text',text=text,angle=0,_chars=chars,
        char_ids=list(range(len(chars))),box_px=f.hull([c[k] for k in ('x0','y0','x1','y1')] for c in chars),run_size_px=size)


def fixture(root=None):
    top=run('top','a+b',20,29)
    bottom=run('bottom','2',25,39)
    tail=run('tail','=0.7 (Smith &',44,35)
    following=run('next','Jones, 2020).',10,55)
    runs=[top,bottom,tail,following]
    if root is not None:
        enclosure=run('root',root,9,42)
        c=enclosure['_chars'][0];c.update(x1=20,y0=14,y1=42)
        roof=dict(c,text='f',x0=20,x1=35,y0=14,y1=14.5)
        enclosure['_chars'].append(roof);enclosure['text']+='f';enclosure['box_px']=[9,14,35,42]
        runs.insert(0,enclosure)
    page=dict(page=1,tables=[],floats=[],elements=[dict(id='bar',kind='rule',box_px=[19,30,35,30.5])])
    return runs,page


class Formulas(unittest.TestCase):
    def test_plain_fraction_does_not_spill_into_following_citation(self):
        runs,p=fixture();original=copy.deepcopy(runs)
        rows=f.prose_text_rows(runs,p)
        text=' / '.join(f.prose_row(r,p)[0] for r in rows)
        self.assertIn('(a+b)/(2) =0.7 (Smith &',text)
        self.assertTrue(text.endswith('Jones, 2020).'))
        self.assertEqual(runs,original)
        self.assertEqual(set(p['copy_formulas'][0]['runs']),{'top','bottom'})

    def test_unknown_enclosure_stays_in_flagged_formula(self):
        runs,p=fixture('q');result=f.display_formula_runs(runs,p)
        self.assertEqual(result[0]['text'],'[formula: (a+b)/(2) inside an unread symbol; see PDF as printed]')
        self.assertEqual([e['id'] for e in result],['root','tail','next'])
        self.assertEqual(p['copy_formulas'][0]['status'],'flagged')

    def test_readable_radical_is_linear(self):
        runs,p=fixture('√')
        self.assertEqual(f.display_formula_runs(runs,p)[0]['text'],'√((a+b)/(2))')

    def test_unknown_operand_is_flagged(self):
        runs,p=fixture();runs[0]['text']='a+�';runs[0]['_chars'][-1]['text']='�'
        self.assertIn('[formula:',f.display_formula_runs(runs,p)[0]['text'])

    def test_indices_use_base_baseline_not_previous_subscript(self):
        e=run('math','σ12+σ22',0,30)
        for i in (1,2,5,6):
            c=e['_chars'][i];c['size']=7;c['origin']=(c['origin'][0],32 if i in (1,5) else 26)
        self.assertEqual(f.formula_baseline_text([e]),'σ_1^2+σ_2^2')

    def test_table_float_prose_and_missing_geometry_abstain(self):
        for reason in ('table','float','prose','missing','underline'):
            runs,p=fixture()
            if reason in ('table','float'): p[reason+'s']=[dict(box_px=[0,0,60,50])]
            elif reason=='prose': runs[0]=run('top','word',20,29)
            elif reason=='missing':runs[0].pop('_chars')
            else:p['elements'][0]['box_px']=[19,41,35,41.5]
            self.assertEqual(f.display_formula_runs(runs,p),runs,reason)
            self.assertFalse(p.get('copy_formulas'))


if __name__=='__main__':unittest.main()
