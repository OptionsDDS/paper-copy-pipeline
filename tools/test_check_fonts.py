"""Safety checks for occurrence OCR, including a lying font's honest letters.

Run: /usr/bin/python3 -I tools/test_check_fonts.py
"""
import copy
import importlib.util
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('font_checks',Path(__file__).with_name('check_fonts.py'))
fonts = importlib.util.module_from_spec(spec); spec.loader.exec_module(fonts)


def reading(text='',confidence=0):
    return dict(text=text,confidence=confidence,status='read' if text else 'empty')


def bitmap(width,height,points):
    return width,height,b''.join(b'\0\0\0' if (x,y) in points else b'\xff\xff\xff'
                                 for y in range(height) for x in range(width))


def proposed(offset=0,after='µ'):
    return dict(offset=offset,char_id=offset,before='m',after=after,font='subset+face',
                model=fonts.SYMBOL_MODEL,symbol_ocr=reading(after,92),letter_ocr=reading('m',61),
                symbol_confidence=92,letter_confidence=61,margin=31,raster_symbols=[after],crop_xywh=[0,0,20,30])


class SafetyTests(unittest.TestCase):
    def test_word_guard_covers_edges_and_unicode(self):
        for text in ('BioMends','Significancen','nPaired','molar','mmol','métre','nPo0.05'):
            for i,ch in enumerate(text):
                if ch.isalpha() and ch in fonts.SUSPECTS: self.assertFalse(fonts.symbol_eligible(text,i),(text,i))
        for text,i in [('536 mM',4),('3.5 mm',4),('420%',0),('71.',1),('(1)',1),('nP <0.05',0)]:
            self.assertTrue(fonts.symbol_eligible(text,i),(text,i))

    def test_confidence_boundaries_and_empty_readings(self):
        self.assertEqual(fonts.symbol_decision('m',reading('µ',75),reading('m',60),['µ'])[0],'µ')
        self.assertIsNone(fonts.symbol_decision('m',reading('µ',74.99),reading(),['µ'])[0])
        self.assertIsNone(fonts.symbol_decision('m',reading('µ',90),reading('m',75.01),['µ'])[0])
        self.assertIsNone(fonts.symbol_decision('m',reading(),reading(),['µ'])[0])
        self.assertEqual(fonts.symbol_decision('m',reading('µ',75),reading(),['µ'])[0],'µ')
        for confidence in (float('nan'),float('inf'),-1,101):
            self.assertIsNone(fonts.symbol_decision('m',reading('µ',confidence),reading(),['µ'])[0])
        self.assertIsNone(fonts.symbol_decision('m',reading('µ',99),dict(status='error'),['µ'])[0])

    def test_comparison_lower_bar_veto(self):
        points=set()
        for y in range(2,17):
            x=3+abs(y-9)*2
            points.update((x+dx,y) for dx in (0,1))
        image=bitmap(24,25,points)
        self.assertIn('<',fonts.raster_symbols(image,25,22))
        points.update((x,y) for x in range(3,20) for y in (20,21))
        shapes=fonts.raster_symbols(bitmap(24,25,points),25,22)
        self.assertIn('≤',shapes)
        self.assertNotIn('<',shapes)
        self.assertIsNone(fonts.symbol_decision('4',reading('<',99),reading(),shapes)[0])

    def test_micro_requires_descender_and_open_top(self):
        points={(x,y) for x in (3,4,14,15) for y in range(3,18)}
        points.update((x,y) for x in range(3,16) for y in (16,17))
        points.update((x,y) for x in (3,4) for y in range(18,24))
        self.assertIn('µ',fonts.raster_symbols(bitmap(20,27,points),28,19))
        self.assertNotIn('µ',fonts.raster_symbols(bitmap(20,27,points),28,26))
        points.update((x,y) for x in range(3,16) for y in (3,4))
        self.assertNotIn('µ',fonts.raster_symbols(bitmap(20,27,points),28,19))

    def test_crop_margin_and_no_neighbour_ink(self):
        image=bitmap(20,20,{(x,y) for x in range(5,15) for y in range(5,15)})
        box,glyph=fonts.isolate_glyph(image,[5,5,10,15],[[10,5,15,15]],300)
        self.assertEqual(box,(3,3,9,14))
        w,h,p=glyph
        self.assertTrue(all(p[(y*w+x)*3:(y*w+x+1)*3]==b'\xff'*3 for y in range(h) for x in (7,8)))
        self.assertTrue(all(p[(y*w+x)*3:(y*w+x+1)*3]==b'\xff'*3 for y in (0,1,h-2,h-1) for x in range(w)))
        with self.assertRaisesRegex(ValueError,'overlapping'):
            fonts.isolate_glyph(image,[5,5,10,15],[[9,5,15,15]],300)

    def test_registered_requires_inner_letter_not_just_a_ring(self):
        ring={(x,y) for x in range(25) for y in range(25) if 9.5 <= math.hypot(x-12,y-12) <= 10.5}
        self.assertNotIn('®',fonts.raster_symbols(bitmap(25,25,ring),25,23))
        inner={(9,y) for y in range(6,19)}|{(x,6) for x in range(9,16)}|{(15,y) for y in range(6,12)}|{(x,12) for x in range(9,16)}|{(10+i,12+i) for i in range(7)}
        self.assertIn('®',fonts.raster_symbols(bitmap(25,25,ring|inner),25,23))

    def test_connected_letter_strokes_are_not_plus_minus(self):
        # A small s can have two broad horizontal strokes, but its strokes
        # remain connected; a plus/minus must have a separate lower bar.
        points={(x,y) for x in range(4,16) for y in (4,5,12,13,20,21)}
        points|={(x,y) for x in (4,5) for y in range(5,13)}|{(x,y) for x in (14,15) for y in range(13,22)}
        self.assertNotIn('±',fonts.raster_symbols(bitmap(20,25,points),30,23))

    def page(self):
        chars=[dict(text=ch,font='subset+face') for ch in 'mm']
        elements=[dict(id=f'run:{i}',kind='text',text='m',char_ids=[i],font_subs=[dict(proposed(),char_id=i)] if i==0 else []) for i in range(2)]
        return dict(page=1,elements=elements,_table_chars=chars)

    def test_occurrence_only_and_table_characters(self):
        page=self.page();before=copy.deepcopy(page);warnings=[]
        fonts.apply_copy([page],warnings)
        self.assertEqual([e['text'] for e in page['elements']],['µ','m'])
        self.assertEqual([c['text'] for c in page['_table_chars']],['µ','m'])
        self.assertEqual(before['elements'][0]['text'],'m')
        self.assertEqual(warnings,['1 individual glyphs read as symbols by OCR; check them; lowest symbol-over-letter confidence margin 31.0 points'])

    def test_copy_rejects_stale_or_forged_evidence(self):
        mutations=[dict(char_id=1),dict(font='different'),dict(margin=90),dict(raster_symbols=[]),
                   dict(model='unknown'),dict(symbol_confidence=93),dict(after='<')]
        for changes in mutations:
            page=self.page();page['elements'][0]['font_subs'][0].update(changes);warnings=[]
            fonts.apply_copy([page],warnings)
            self.assertEqual(page['elements'][0]['text'],'m',changes)
            self.assertEqual(warnings,[])

    def test_lowest_margin_across_pages_and_without_pdf(self):
        pages=[self.page(),self.page()];pages[1]['page']=2
        sub=pages[1]['elements'][0]['font_subs'][0]
        sub.update(letter_ocr=reading('m',72),letter_confidence=72,margin=20)
        for p in pages:
            p.pop('_table_chars')
            p['elements'][0]['font_spans']=[dict(start=0,end=1,font='subset+face')]
        warnings=[];fonts.apply_copy(pages,warnings)
        self.assertEqual(len(warnings),1)
        self.assertIn('2 individual glyphs',warnings[0]);self.assertIn('20.0 points',warnings[0])

    def test_legacy_mapping_still_requires_three_independent_runs(self):
        runs=[dict(page=1,id=f'run:{i}',candidates=[dict(font='f',before='o',offset=0)],
                   readings=[dict(offset=0,reading='<')]) for i in range(3)]
        self.assertIsNone(fonts.decide(runs,dict(f=[0,1]))['f']['o']['after'])
        self.assertEqual(fonts.decide(runs,dict(f=[0,1,2]))['f']['o']['after'],'<')

    def test_exact_psm_and_whitelist(self):
        result=type('Result',(),dict(stdout='level\ttext\tconf\n5\tµ\t91\n'))()
        with patch.object(fonts.subprocess,'run',return_value=result) as run:
            got=fonts.single_read(Path('crop.ppm'),fonts.SYMBOL_WHITELIST,'tesseract','data','libs')
        self.assertEqual(got['text'],'µ')
        command=run.call_args.args[0]
        self.assertEqual(command[command.index('--psm')+1],'10')
        self.assertIn('tessedit_char_whitelist=µ≤≥°*±×®−<>=',command)


if __name__=='__main__': unittest.main()
