"""Conservation checks use typography, order, ownership and real paragraph spans."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('conserve',Path(__file__).with_name('conserve.py'))
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class Conservation(unittest.TestCase):
    def test_typography_and_hyphenated_line_breaks(self):
        copy=c.CopyIndex('An efficient full-mouth examination.\n\nhttps://doi.org/10.1234/test')
        self.assertTrue(copy.contains('An efﬁcient full‐mouth'))
        self.assertTrue(copy.contains('https://doi.org/10.1234/ test'))
        self.assertFalse(copy.contains('An inefficient full mouth'))
        self.assertTrue(c.CopyIndex('https://doi.org/10.1586/17434440.2.3.267').contains('440.2.3.267'))
        self.assertFalse(c.CopyIndex('2006 44').contains('2006 4'))
        self.assertTrue(c.CopyIndex('| Author et al., 201844 |').contains('2018 44'))

    def test_lines_require_order_within_one_local_region(self):
        copy=c.CopyIndex('Alpha value red.\n\nBeta value green.\n\nGamma value blue.')
        self.assertFalse(copy.contains('Alpha Beta Gamma'))
        self.assertTrue(c.CopyIndex('| Alpha | intervening | Beta |\n| Gamma |').contains('Alpha Beta Gamma'))
        self.assertTrue(c.CopyIndex('| Alpha '+('intervening '*50)+'| Beta |').contains('Alpha Beta'))
        self.assertFalse(c.CopyIndex('Gamma Beta Alpha').contains('Alpha Beta Gamma'))
        self.assertFalse(c.CopyIndex('2006 4\n2007 6').contains('2006 5'))

    def test_repeated_sentence_tail_inside_longer_paragraph(self):
        tail='The second branch supplies the posterior soft tissues.'
        hits=c.duplicate_paragraphs('An opening. '+tail+'\n\n'+tail+'\n\n'+c.UNCERTAINTY+'\n'+tail)
        self.assertEqual(len(hits),1)
        self.assertEqual(hits[0]['text'],tail)
        self.assertEqual(hits[0]['occurrences'],2)
        caption='**Figure 1.** An example caption.'
        self.assertEqual(c.duplicate_paragraphs(caption+'\n\n'+caption)[0]['occurrences'],2)

    def test_repeated_number_on_another_page_cannot_hide_a_missing_line(self):
        copy=c.CopyIndex('2005 3\n\n<!-- end of page 2 -->\n\nA paragraph.\n\n2007 6\n\n<!-- end of page 3 -->')
        self.assertFalse(copy.contains('2007',page=2))
        self.assertTrue(copy.contains('2007',page=3))

    def test_floating_table_uses_its_source_page_and_actual_payload(self):
        with tempfile.TemporaryDirectory() as d:
            caption='Table 1. Measured values for the experiment.'
            Path(d,'copy.tables.json').write_text(json.dumps(dict(tables=[dict(page=5,caption=caption,region_coverage=dict(frame=[10,10,90,90]))])))
            body='**'+caption+'**\n\n| Year | Value |\n| 2007 | 44 |\n\n<!-- end of page 2 -->'
            tables=c.placed_tables(body,d)
            self.assertEqual(tables[0][0],5)
            self.assertTrue(tables[0][2].contains('2007 44'))
            self.assertFalse(tables[0][2].contains('2007 4'))
            self.assertEqual(c.placed_tables(body+'\n\n**'+caption+'**',d),[])

    def test_final_table_ownership_overrides_old_figure_membership(self):
        p=dict(elements=[dict(id='cell',kind='text',text='2006 4',box_px=[0,0,30,10])],
               floats=[dict(lettering=['cell'])],copy_conservation=dict(excluded=[]))
        self.assertEqual(c.exclusions(p),[])
        del p['copy_conservation']
        self.assertEqual(c.exclusions(p)[0]['id'],'cell')

    def test_partial_invisible_caption_does_not_exclude_visible_words(self):
        excluded=[dict(text='Invisible',box=[50,10,90,20],reason='white rendered glyph area')]
        self.assertIsNone(c.covered(dict(text='Visible',box=[10,10,45,20]),excluded,1,1))
        self.assertEqual(c.covered(dict(text='Invisible',box=[50,10,90,20]),excluded,1,1),'white rendered glyph area')

    def test_shifted_and_rotated_pdf_frames(self):
        g=dict(media=[9,9,603,792],width=594,height=783,rotation=0)
        self.assertEqual(c.native_box([39,755,63,765],g,2,2),[96,1492,144,1512])
        g=dict(media=[10,20,110,220],width=200,height=100,rotation=90)
        self.assertEqual(c.native_box([30,40,50,60],g,1,1),[50,30,70,50])

    def test_invisible_suffix_does_not_hide_the_visible_part_of_a_word(self):
        excluded=[dict(text='Hidden continuation',box=[40,10,120,20],reason='white fill and white rendered glyph area')]
        word=dict(text='VisibleHidden',box=[10,10,70,20])
        kept,removed=c.visible_word(word,excluded,1,1)
        self.assertEqual(kept['text'],'Visible')
        self.assertEqual(removed['text'],'Hidden')
        self.assertIsNone(c.covered(kept,excluded,1,1))
        self.assertFalse(c.CopyIndex('Different').contains(kept['text']))
        # Nearby white text cannot excuse a suffix that does not match it.
        word['text']='VisibleOther'
        self.assertEqual(c.visible_word(word,excluded,1,1),(word,None))

    def test_numeric_tail_needs_the_printed_url_context(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'copy.md').write_text('https://doi.org/10.1000/1234567890')
            lines=[(1,100,100,[dict(text='https\u200b://doi.org/10.1000/12345',box=[10,10,90,20])]),
                   (1,100,100,[dict(text='67890',box=[10,21,40,31])])]
            with patch.object(c,'pdf_lines',return_value=iter(lines)):
                self.assertEqual(c.audit(d,'unused')['missing_count'],0)
            lines[1][3][0]['box']=[60,21,90,31]
            with patch.object(c,'pdf_lines',return_value=iter(lines)):
                self.assertEqual(c.audit(d,'unused')['missing_count'],1)

    def test_poppler_control_characters_do_not_abort_the_audit(self):
        data=b'<doc><page width="100" height="100"><line><word xMin="1" yMin="2" xMax="3" yMax="4">Printed\x08</word></line></page></doc>'
        with patch.object(c.subprocess,'run',return_value=type('Result',(),dict(stdout=data))()):
            self.assertEqual(list(c.pdf_lines('unused'))[0][3][0]['text'],'Printed')

    def test_numeric_url_tail_after_fragmented_reference_baseline(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d,'copy.md').write_text('2012;9:30 https://doi.org/10.1000/1234567890')
            lines=[(1,200,200,[dict(text='2012;9:30',box=[10,10,40,20])]),
                   (1,200,200,[dict(text='https://doi.org/10.1000/123',box=[45,10,140,20])]),
                   (1,200,200,[dict(text='45',box=[135,10,155,20])]),
                   (1,200,200,[dict(text='67890',box=[10,21,40,31])])]
            with patch.object(c,'pdf_lines',return_value=iter(lines)):
                # The isolated middle fragment is conservative; the wrapped
                # final line has exact complete-URL evidence in the copy.
                self.assertNotIn('67890',[f['text'] for f in c.audit(d,'unused')['missing']])
            lines[-1][3][0]['text']='67891'
            with patch.object(c,'pdf_lines',return_value=iter(lines)):
                self.assertIn('67891',[f['text'] for f in c.audit(d,'unused')['missing']])

if __name__=='__main__':unittest.main()
