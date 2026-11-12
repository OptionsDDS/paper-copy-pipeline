"""Keyless visible-layer/1.1 port and native PDF visibility regressions.

Source: paper-copy-language/converter/convert_page.py:dedupe_hidden_layers.
Its colour/size/similarity/order tests are exercised here; the source's only
other keyless caller test (test_r004.py) mocks removal to test map barriers,
which have no equivalent in the boxer's character reader.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hidden_fixture', ROOT/'tools/test_ocrscan.py')
f = importlib.util.module_from_spec(spec); spec.loader.exec_module(f)
b = f.boxer


def layer(text='abcdefghijk', colour=0, order=0, y=10):
    return [dict(text=t, font='Body', fill_color=colour, fill_alpha=1,
                 render_mode=0, hidden=False, size=10, x0=i*5, x1=i*5+4,
                 y0=y, y1=y+10, paint_order=(order,i), source_index=order*100+i)
            for i,t in enumerate(text)]


class HiddenLayers(unittest.TestCase):
    def test_source_rule_keeps_later_painted_colour_and_records_decision(self):
        early, late = layer(), layer(colour=1,order=1)
        kept, records = b.sc_dedupe_hidden_layers(early+late)
        self.assertEqual(kept,late)
        self.assertEqual(records[0]['dropped_glyphs'],11)
        self.assertEqual(records[0]['similarity'],1)
        self.assertFalse(any(c['hidden'] for c in early))

    def test_body_signature_cannot_override_the_visibility_witness(self):
        cs=layer()+layer(colour=1,order=1)
        self.assertEqual(b.sc_dedupe_hidden_layers(cs,'0'),(cs,[]))
        self.assertEqual(b.sc_dedupe_hidden_layers(cs,'1')[0],cs[11:])

    def test_source_minimum_size_share_similarity_and_overlap(self):
        cases=[layer('abcdefg')+layer('abcdefg',1,1),
               layer()+layer('zyxwvutsrq',1,1),
               layer()+layer(colour=1,order=1,y=40),
               layer()+layer(colour=1,order=1)+layer('x'*500,2,2,y=80)]
        for cs in cases:
            with self.subTest(length=len(cs)):
                self.assertEqual(b.sc_dedupe_hidden_layers(cs),(cs,[]))

    def test_overlapping_aggregate_boxes_do_not_prove_a_duplicate(self):
        cs=layer()+layer(colour=1,order=1,y=15)
        self.assertEqual(b.sc_dedupe_hidden_layers(cs),(cs,[]))

    def test_one_unique_glyph_or_translucent_twin_vetoes_group_removal(self):
        for field,value in [('text','z'),('fill_alpha',.5),('font','Italic'),('x0',1)]:
            early,late=layer(),layer(colour=1,order=1)
            late[0][field]=value
            cs=early+late
            self.assertEqual(b.sc_dedupe_hidden_layers(cs),(cs,[]))

    def test_paint_order_is_independent_of_reading_list_order(self):
        early,late=layer(),layer(colour=1,order=1)
        cs=[c for pair in zip(reversed(late),reversed(early)) for c in pair]
        kept,records=b.sc_dedupe_hidden_layers(cs)
        self.assertEqual(kept,list(reversed(late)))
        self.assertEqual(records[0]['kept_signature'],'1')

    def read(self,content):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path=Path(tmp)/'layers.pdf';f.pdf(path,content)
            chars,_,counts=b.sc_read_page(str(path),1)
            page=dict(page=1,region_box_px=[0,0,209,209],elements=[])
            b.sc_font_metadata(page,pdf_path=str(path))
            return chars,counts,page

    def test_invisible_twin_never_swallows_visible_object_or_letter(self):
        for mode in (3,7):
            for text in ('Repeated phrase','a'):
                hidden=f'BT /F 8 Tf {mode} Tr 10 50 Td ({text}) Tj ET '
                painted=f'BT /F 8 Tf 0 Tr 10 50 Td ({text}) Tj ET '
                for content in (hidden+painted,painted+hidden):
                    cs,_,page=self.read(content)
                    self.assertEqual(''.join(c['text'] for c in cs if not c['hidden']),text.replace(' ',''))
                    self.assertEqual(sum(c['hidden'] for c in cs),len(text.replace(' ','')))
                    self.assertEqual(page['counts']['characters_hidden_layers'],len(text.replace(' ','')))

    def test_page_colour_layers_beyond_legacy_window_reach_the_port(self):
        content=' '.join(f'{colour} g BT /F 4 Tf 10 {y} Td (abcdefghijk) Tj ET'
                         for colour in (.5,0) for y in (85,70,55,40,25,10))
        cs,_,page=self.read(content)
        self.assertEqual(len(cs),132)
        self.assertEqual(sum(not c['hidden'] for c in cs),66)
        self.assertEqual(page['hidden_layers'][0]['kept_signature'],'0.0')
        self.assertEqual(page['hidden_layers'][0]['source_ranges'],[[0,66]])

    def test_short_colour_overprints_keep_legacy_deduplication(self):
        for text in ('a','Short'):
            cs,_,_=self.read(f'0.5 g BT /F 8 Tf 10 50 Td ({text}) Tj ET '
                             f'0 g BT /F 8 Tf 10 50 Td ({text}) Tj ET')
            self.assertEqual(''.join(c['text'] for c in cs if not c['hidden']),text)

    def test_partly_clipped_object_cannot_swallow_complete_visible_line(self):
        cs,_,page=self.read('q 0 0 28 100 re W n BT /F 8 Tf 10 50 Td (Visible letters) Tj ET Q '
                            'BT /F 8 Tf 10 50 Td (Visible letters) Tj ET')
        self.assertEqual(''.join(c['text'] for c in cs if not c['hidden']), 'Visibleletters')
        self.assertTrue(page['hidden_layers'])

    def test_clipped_draft_record_and_no_record_for_unaffected_page(self):
        cs,_,page=self.read('q 0 0 1 1 re W n BT /F 8 Tf 10 50 Td (Draft) Tj ET Q '
                            'BT /F 8 Tf 10 50 Td (Final) Tj ET')
        self.assertEqual(''.join(c['text'] for c in cs if not c['hidden']),'Final')
        self.assertEqual(page['hidden_layers'][0]['text'],'Draft')
        self.assertEqual(page['hidden_layers'][0]['evidence'],'outside text clip')
        _,_,plain=self.read('BT /F 8 Tf 10 50 Td (Final) Tj ET')
        self.assertNotIn('hidden_layers',plain)
        self.assertNotIn('characters_hidden_layers',plain['counts'])

    def test_scan_keeps_ocr_runs(self):
        cs,counts,page=self.read(f.IMAGE+' 3 Tr '+f.TEXT)
        self.assertTrue(counts['scan_evidence']['ocr_layer'])
        self.assertTrue(counts['scan_evidence']['ocr_runs'])
        self.assertTrue(page['hidden_layers'])


if __name__=='__main__':unittest.main()
