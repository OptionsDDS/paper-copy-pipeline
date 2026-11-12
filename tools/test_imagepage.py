"""Text over a tinted text area, caption boxes, and the reference-list edges (AH06 rules)."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

b = module('imagepage_boxer', 'standalone/element_boxer_sc.py')
c = module('imagepage_copy', 'copy_paper.py')
PAGE = [0, 0, 1200, 1600]

def run(name, text, x, y, width=450, size=20, line=None):
    return dict(id=name, kind='text', text=text, box_px=[x, y, x + width, y + size],
                run_size_px=size, size_px=size, angle=0, line=line if line is not None else y, flags=[])

def fill(name, box):
    return dict(id=name, kind='fill', box_px=list(box), source='rect')

def prose(prefix, x, y0, n, width=450):
    return [run(f'{prefix}{i}', 'body text of a column line, long enough to be prose', x, y0 + 25 * i, width)
            for i in range(n)]


class TextAreaBackground(unittest.TestCase):
    def test_tint_under_two_columns_is_a_background(self):
        texts = prose('l', 150, 200, 40) + prose('r', 650, 200, 40)
        tint = fill('fill:1', [120, 150, 1150, 1500])
        why = b.text_area_background(tint, texts + [tint], PAGE)
        self.assertTrue(why)

    def test_caption_box_and_small_panel_are_not(self):
        texts = prose('l', 150, 200, 40) + prose('r', 650, 200, 40)
        caption_box = fill('fill:2', [140, 190, 620, 260])
        self.assertIsNone(b.text_area_background(caption_box, texts + [caption_box], PAGE))
        # most of the page's text, but a figure's short lettering, not prose
        labels = [run(f'a{i}', 'x', 200 + 30 * (i % 20), 200 + 30 * (i // 20), 10) for i in range(200)]
        picture = dict(id='image:1', kind='image', box_px=[150, 150, 1000, 1200])
        self.assertIsNone(b.text_area_background(picture, labels + [picture], PAGE))

    def test_page_sized_scan_keeps_its_own_rules(self):
        texts = prose('l', 150, 200, 40)
        scan = dict(id='image:1', kind='image', box_px=[0, 0, 1200, 1600])
        self.assertIsNone(b.text_area_background(scan, texts + [scan], PAGE))


class CaptionBoxes(unittest.TestCase):
    def test_body_text_under_a_caption_box_is_not_caption(self):
        cap = [run('c0', 'Figure 2.', 150, 300, 80, 17), run('c1', 'Cumulative proportion of bridges surviving.', 150, 320, 450, 17)]
        box = fill('fill:1', [148, 298, 620, 341])
        body = [run('b0', '8) Finally, the pontics were put in infra-occlusion.', 150, 350),
                run('b1', 'and the esthetic result was checked by the authors.', 150, 373)]
        blocks = b.larger_boxes(cap + [box] + body)
        owner = {m: blk['id'] for blk in blocks for m in blk['members']}
        self.assertEqual(owner['c0'], owner['c1'])
        self.assertNotEqual(owner['c1'], owner['b0'])
        self.assertEqual(owner['b0'], owner['b1'])


class ReferenceEdges(unittest.TestCase):
    def test_correspondence_label_ends_the_list(self):
        self.assertTrue(c.REF_CORRESPONDENCE.match('Send reprint requests to: Dr. A. Author, Department'))
        self.assertTrue(c.REF_CORRESPONDENCE.match('Correspondence: Dr. A. Author, 1 Main Road'))
        self.assertFalse(c.REF_CORRESPONDENCE.match('26. Author A. Correspondence of tooth loss. J Dent 1995;6:80-84.'))
        self.assertFalse(c.REF_CORRESPONDENCE.match('Correspondence to:'))   # a bare heading stays REF_END's


if __name__ == '__main__':
    unittest.main()
