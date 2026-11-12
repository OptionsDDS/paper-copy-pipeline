"""Native glyph evidence distinguishes powers of ten from citation digits."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('copy_exponents',ROOT/'copy_paper.py')
copy=importlib.util.module_from_spec(spec)
spec.loader.exec_module(copy)


def glyphs(text,raised=()):
    return [dict(text=ch,size=7 if i in raised else 10,
                 origin=(i*5,96 if i in raised else 100),x0=i*5,x1=i*5+5,adv_x1=i*5+5)
            for i,ch in enumerate(text)]


class Powers(unittest.TestCase):
    def test_single_and_multiple_digits(self):
        for text,indices,want in [('109 cells',(2,),'10^9 cells'),
                ('1011 cells',(2,3),'10^11 cells'),('2 ×10−3',(5,6),'2 ×10^−3'),
                ('x 109',(4,),'x 10^9'),('x109',(3,),'x10^9')]:
            self.assertEqual(copy.raised_power_text(text,glyphs(text,indices)),want)

    def test_ordinary_numbers_and_citations_are_unchanged(self):
        for text,indices in [('109 cells',()),('words109',(5,6,7)),('2109',(3,)),
                             ('10,9',(3,)),('10 9',())]:
            self.assertEqual(copy.raised_power_text(text,glyphs(text,indices)),text)

    def test_mismatched_or_missing_evidence_is_not_a_power(self):
        self.assertEqual(copy.raised_power_text('109',glyphs('108',(2,))),'109')
        self.assertEqual(copy.raised_power_text('109',[]),'109')
        cs=glyphs('109',(2,));cs[-1]['origin']=(10,104)
        self.assertEqual(copy.raised_power_text('109',cs),'109')

    def test_symbol_font_minus_encoded_as_digit_is_not_a_positive_power(self):
        cs=glyphs('1024',(2,3))
        cs[2].update(y0=92,y1=92.4)
        cs[3].update(y0=91,y1=96)
        self.assertEqual(copy.raised_power_text('1024',cs),'1024')

    def test_detached_superscript_uses_same_joiner(self):
        cs=glyphs('109',(2,))
        row=[dict(text='10',angle=0,box_px=[0,90,10,100],_chars=cs[:2]),
             dict(text='9',angle=0,box_px=[10,89,15,96],_chars=cs[2:],_superscript=True)]
        self.assertEqual(copy.prose_row(row,{})[0],'10^9')


if __name__=='__main__':unittest.main()
