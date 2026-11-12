"""Advance geometry, blank backing tiles and repository thesis front matter."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('spanlines_boxer', ROOT/'standalone/element_boxer_sc.py')
b = importlib.util.module_from_spec(spec); spec.loader.exec_module(b)


def page(*rows):
    return dict(elements=[dict(id=str(i), kind='text', text=t, angle=0,
        box_px=[100-(len(t)*2), 50+i*25, 100+(len(t)*2), 65+i*25],
        run_size_px=12) for i,t in enumerate(rows)])


class Spanlines(unittest.TestCase):
    def test_missing_font_uses_each_advance_not_face_hull(self):
        font = SimpleNamespace(bboxes={}, prog=None, basefont='UnembeddedFace',
            desc={'FontBBox':[-600,-200,2000,800]}, width=lambda code: 250 if code==1 else 600)
        self.assertEqual(b.SCFont.bbox(font,1),(0,800,250,-200))
        self.assertEqual(b.SCFont.bbox(font,2),(0,800,600,-200))

    def test_unknown_advance_keeps_conservative_face_hull(self):
        font = SimpleNamespace(bboxes={},prog=None,basefont='UnembeddedFace',
            desc={'FontBBox':[-600,-200,2000,800]},width=lambda code:0)
        self.assertEqual(b.SCFont.bbox(font,1),(-600,800,2000,-200))

    def image(self, samples=None, **extra):
        attrs=dict(Width=10,Height=10,BitsPerComponent=8,ColorSpace=b.PSLiteral('DeviceRGB'),**extra)
        return dict(stream=b.PDFStream(attrs,bytes([255])*300 if samples is None else samples))

    def test_blank_edge_tiles_do_not_contain_columns(self):
        self.assertTrue(b.blank_background_image(self.image(),[0,0,600,600],[0,0,1000,1400]))
        self.assertFalse(b.blank_background_image(self.image(bytes([254])+bytes([255])*299),[0,0,600,600],[0,0,1000,1400]))
        self.assertFalse(b.blank_background_image(self.image(),[100,100,700,700],[0,0,1000,1400]))
        self.assertFalse(b.blank_background_image(self.image(Decode=[1,0]*3),[0,0,600,600],[0,0,1000,1400]))

    def test_variable_soft_mask_is_not_blank(self):
        mask=b.PDFStream(dict(Width=10,Height=10,BitsPerComponent=8,ColorSpace=b.PSLiteral('DeviceGray')),bytes(range(100)))
        self.assertFalse(b.blank_background_image(self.image(SMask=mask),[0,0,600,600],[0,0,1000,1400]))

    def test_thesis_cover_requires_deposit_and_matching_submitted_title(self):
        title='MECHANICAL PROPERTIES OF NOVEL BIOLOGICAL SCAFFOLD MATERIALS'
        wrapper=page(title,'Downloaded from https://archive.example.edu/theses/12',
            'Free and open access; accepted for inclusion by an authorized administrator')
        copyright=page('© Ada Example 2020','All Rights Reserved')
        thesis=page(title,'A thesis submitted in partial fulfillment for the degree of Master of Science','By','Ada Example')
        self.assertTrue(b.repository_cover(wrapper,[copyright,thesis]))
        self.assertFalse(b.repository_cover(wrapper,[page('Introduction to the study'),thesis]))
        self.assertFalse(b.repository_cover(page('University repository'),[thesis]))
        self.assertEqual([e['text'] for e in b.thesis_title_runs(thesis)],[title])
        self.assertFalse(b.thesis_title_runs(page(title,'Introduction')))


# Import the exporter after the reader: both use only the standard library here.
spec = importlib.util.spec_from_file_location('spanlines_copy', ROOT/'copy_paper.py')
copy = importlib.util.module_from_spec(spec); spec.loader.exec_module(copy)

class CaptionColumns(unittest.TestCase):
    def test_short_values_and_sustained_text_are_prose(self):
        self.assertTrue(copy.prose_side_group([dict(text='490nm.', angle=0)]))
        rows=[dict(text='An ordinary sentence with several words.',angle=0) for _ in range(4)]
        self.assertTrue(copy.prose_side_group(rows))
        rows[0]['angle']=90
        self.assertFalse(copy.prose_side_group(rows))

    def test_graphic_labels_keep_the_geometry_reader(self):
        rows=[dict(text=t,angle=0) for t in ['Age','Diabetes','Heredity','Health','Risk factors',
            'Fig. 1. A caption beneath the diagram','and the remaining caption words.']]
        self.assertFalse(copy.prose_side_group(rows))

    def rows(self,left,first,last):
        return [dict(id=str(left)+str(i),kind='text',text=t,angle=0,line=i,
            font='Caption',size_px=10,run_size_px=10,box_px=[left,110+i*14,left+200,120+i*14])
            for i,t in enumerate([first,'several ordinary words forming the middle of a long explanation',last])]
    def test_continuation_follows_whole_left_column(self):
        left=self.rows(10,'Fig. 2. A long explanation of these scientific illustrations','the remaining cells form')
        right=self.rows(230,'continuous layers across the specimen and its surrounding structures','the last visible layer of the specimen.')
        page=dict(elements=[dict(kind='image',box_px=[10,0,430,100])])
        self.assertEqual(copy.caption_column_tail(page,left,[right]),right)
        right[0]['text']='Fig. 3. A separate caption for a different specimen'
        self.assertFalse(copy.caption_column_tail(page,left,[right]))
        right[0]['text']='continuation of the previous explanation'
        left[-1]['text']='A complete sentence.'
        self.assertFalse(copy.caption_column_tail(page,left,[right]))
    def test_body_font_and_unspanned_picture_do_not_supply_caption(self):
        left=self.rows(10,'Fig. 2. The first caption explanation','the remaining cells form')
        right=self.rows(230,'continuous layers across the specimen and its surrounding structures','the last visible layer of the specimen.')
        page=dict(elements=[dict(kind='image',box_px=[10,0,210,100])])
        self.assertFalse(copy.caption_column_tail(page,left,[right]))
        page['elements'][0]['box_px'][2]=430
        for e in right:e['font']='Body'
        self.assertFalse(copy.caption_column_tail(page,left,[right]))

if __name__=='__main__': unittest.main()
