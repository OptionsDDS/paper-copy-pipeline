"""Detached section openers keep their column and their source text."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1]/'copy_paper.py')
paper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paper)


def row(text, y, face='Heading.B', size=9):
    return [[dict(id=str(y), text=text, angle=0, box_px=[210,y,390,y+7],
                  run_size_px=size, _faces={face:len(text)})]]


class DetachedOpeners(unittest.TestCase):
    def setUp(self):
        self.page = dict(page=2, region_box_px=[0,0,420,800], _body_face='Regular',
                         main_text=dict(columns=[[10,190],[210,390]]), floats=[])
        self.anchor = dict(order=4,meta=dict(box_px=[210,150,390,250],size_px=10),panel=False,
                           page=2,lines=['The next subsection'],sizes=[10],faces=['Regular'],
                           row_boxes=[[210,150,390,157]],emphasis=[False])

    def recover(self, rows):
        return paper.detached_heading_block(rows,self.page,dict(id='head',cls='other'),[self.anchor],10)

    def test_heading_and_opening_sentence_precede_their_column(self):
        result = self.recover(row('Treatment characteristics',100,'Heading.I') +
                              row('Parameters were measured.',120,'Regular',10))
        self.assertIs(result[0],self.anchor)
        b=result[1]
        paper.heading_context([([b,self.anchor],[],[])],10)
        parts=paper.paragraph_blocks(b,10)
        self.assertTrue(paper.is_heading(parts[0]['lines'][0],parts[0]['meta'],10,1))
        self.assertEqual(parts[1]['lines'],['Parameters were measured.'])

    def test_another_column_cannot_anchor_a_heading(self):
        self.anchor['meta']['box_px']=[10,160,190,250]
        self.assertIsNone(self.recover(row('Experimental design',100)))

    def test_float_and_unstyled_notes_stay_out(self):
        self.assertIsNone(self.recover(row('Additional information',100,'Regular',10)))
        self.page['floats']=[dict(box_px=[200,90,400,130])]
        self.assertIsNone(self.recover(row('Experimental design',100)))

    def test_caption_label_cannot_become_a_heading(self):
        self.assertIsNone(self.recover(row('Table 2 Selected studies',100)))

    def test_unnumbered_photo_caption_stays_with_picture(self):
        self.page['elements']=[dict(kind='image',box_px=[210,20,390,90])]
        self.assertIsNone(self.recover(row('The organisms in their host cells',100)))

    def test_affiliations_without_boxed_markers_keep_correspondence(self):
        address='Department of Biology, University of Example, Example City'
        joiner=paper.Joiner([address])
        self.assertEqual(paper.without_front_text([address,'Correspondence: a@example.org'],
                         ['1'+address],joiner,prefixes=[address]),'Correspondence: a@example.org')

    def test_closing_email_initials_are_consumed_with_the_address(self):
        address='Department of Biology, University of Example; a@example.org (A.B.)'
        self.assertEqual(paper.without_front_text([address,'Correspondence: b@example.org'],
                         [address],paper.Joiner([address])),'Correspondence: b@example.org')

    def test_short_address_cannot_strip_the_end_of_a_longer_address(self):
        short='Associate Professor, School of Dentistry, University of Example.'
        long='Director and '+short
        first='Clinical Instructor, School of Dentistry, University of Example.'
        text='1'+first+' 2'+long+' 3'+short
        self.assertEqual(paper.without_front_text([text],['1'+first,'2'+long,'3'+short],
                         paper.Joiner([text]),prefixes=[first,long,short]),'')


if __name__ == '__main__': unittest.main()
