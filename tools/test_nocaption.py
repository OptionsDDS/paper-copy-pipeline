#!/usr/bin/env python3
"""Lane r5-nocaption: rules F28 (furniture first), F29 (inside means part of), F30 (pair the orphans), F31 (block it
and flag it), F32 (a table with no label) for uncaptioned pictures and unlabeled tables."""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import copy_paper as copy

W, H = 1240, 1650


def run(i, box, text='words in a line'):
    return dict(id=f'run:{i}', kind='text', box_px=list(box), text=text)


def page(elements, blocks=(), main=(), furniture=()):
    """main: (block id, box, size) of main-flow blocks; blocks: (block id, member ids)"""
    return dict(page=1, region_box_px=[0, 0, W, H], params=dict(dpi=150), elements=list(elements),
                blocks=[dict(id=b, members=list(m)) for b, m in blocks],
                main_text=dict(body_size_px=18, furniture=[dict(members=list(furniture))],
                               blocks=[dict(id=b, cls='main', order=k + 1, size_px=s, box_px=list(x))
                                       for k, (b, x, s) in enumerate(main)]))


BODY = [('block:9', [80, 400, 1160, 1500], 18)]


class Furniture(unittest.TestCase):
    def test_small_picture_above_the_body_with_nothing_above_it_is_a_logo(self):
        p = page([run(1, [300, 420, 1100, 440])], main=BODY)
        self.assertTrue(copy.nocaption_furniture(p, [80, 120, 200, 260], [], 18, []))

    def test_text_between_picture_and_page_edge_keeps_it(self):
        p = page([run(1, [60, 60, 400, 80]), run(2, [300, 420, 1100, 440])], main=BODY)
        self.assertIsNone(copy.nocaption_furniture(p, [80, 120, 200, 260], [], 18, []))

    def test_furniture_text_above_does_not_count(self):
        p = page([run(1, [60, 60, 400, 80]), run(2, [300, 420, 1100, 440])], main=BODY, furniture=['run:1'])
        self.assertTrue(copy.nocaption_furniture(p, [80, 120, 200, 260], [], 18, []))

    def test_large_picture_at_the_top_is_not_small(self):
        p = page([], main=BODY)
        self.assertIsNone(copy.nocaption_furniture(p, [80, 100, 1160, 390], [], 18, []))

    def test_picture_inside_the_body_is_not_at_an_edge(self):
        p = page([run(1, [80, 380, 1100, 398])], main=BODY)
        self.assertIsNone(copy.nocaption_furniture(p, [500, 700, 600, 800], [], 18, []))

    def test_repeated_at_an_edge_is_furniture_whatever_its_size(self):
        p = page([], main=BODY)
        self.assertTrue(copy.nocaption_furniture(p, [80, 1510, 1160, 1640], [[81, 1512, 1161, 1639]], 18, []))
        self.assertIsNone(copy.nocaption_furniture(p, [80, 1510, 1160, 1640], [[81, 1400, 1161, 1520]], 18, []))

    def test_repeated_large_picture_inside_the_body_is_not_furniture(self):
        p = page([run(1, [80, 600, 1100, 618]), run(2, [80, 1000, 1100, 1018])], main=BODY)
        self.assertIsNone(copy.nocaption_furniture(p, [80, 700, 1160, 900], [[81, 702, 1161, 899]], 18, []))

    def test_a_piece_beside_a_captioned_float_is_never_furniture(self):
        p = page([run(1, [300, 420, 1100, 440])], main=BODY)
        self.assertIsNone(copy.nocaption_furniture(p, [80, 120, 200, 260], [], 18, [[210, 100, 600, 380]]))

    def test_cover_page_without_body_type_uses_its_main_flow(self):
        p = page([run(1, [500, 160, 1060, 186])], main=[('block:1', [500, 160, 1060, 280], 29)])
        self.assertTrue(copy.nocaption_furniture(p, [83, 167, 468, 233], [], 18, []))


class TextFrame(unittest.TestCase):
    def test_shaded_box_full_of_text_is_a_frame(self):
        es = [run(i, [120, 760 + 30 * i, 1100, 780 + 30 * i]) for i in range(8)]
        self.assertTrue(copy.nocaption_text_frame(page(es), [110, 750, 1120, 1000]))

    def test_ruled_grid_of_many_cells_is_a_frame(self):
        es = [run(10 * r + k, [120 + 200 * k, 160 + 40 * r, 150 + 200 * k, 172 + 40 * r], '1.2') for r in range(10) for k in range(4)]
        self.assertTrue(copy.nocaption_text_frame(page(es), [110, 150, 1120, 1000]))

    def test_chart_with_few_labels_is_a_picture(self):
        es = [run(k, [120, 160 + 60 * k, 150, 172 + 60 * k], str(k)) for k in range(8)]
        self.assertFalse(copy.nocaption_text_frame(page(es), [110, 150, 1120, 1000]))

    def test_photo_with_lettering_is_a_picture(self):
        es = [run(1, [130, 610, 150, 630], 'A'), dict(id='image:1', kind='image', box_px=[120, 600, 800, 1080])]
        self.assertFalse(copy.nocaption_text_frame(page(es), [120, 600, 800, 1080]))


class Owner(unittest.TestCase):
    def setUp(self):
        self.record = dict(id='Figure 1', kind='figure')
        self.part = dict(box=[80, 1140, 800, 1200], has_caption=True, has_content=True, caption_run_ids=['run:5'])

    def test_picture_above_its_caption_with_nothing_between_belongs_to_it(self):
        p = page([run(5, [80, 1140, 800, 1160], 'Figure 1. A chart.')], blocks=[('block:9', ['run:7'])],
                 main=[('block:9', [820, 150, 1160, 1500], 18)])
        p['elements'].append(run(7, [820, 150, 1160, 170]))
        self.assertIs(copy.nocaption_owner(p, [80, 150, 800, 1120], [self.part], lambda q: self.record), self.record)

    def test_body_text_between_blocks_ownership(self):
        p = page([run(5, [80, 1140, 800, 1160]), run(7, [80, 1125, 800, 1135])], blocks=[('block:9', ['run:7'])],
                 main=[('block:9', [80, 1125, 800, 1135], 18)])
        self.assertIsNone(copy.nocaption_owner(p, [80, 150, 800, 1120], [self.part], lambda q: self.record))

    def test_caption_without_content_does_not_own_by_space(self):
        part = dict(self.part, has_content=False)
        p = page([run(5, [80, 1140, 800, 1160])])
        self.assertIsNone(copy.nocaption_owner(p, [80, 150, 800, 1120], [part], lambda q: self.record))

    def test_table_never_owns_a_picture(self):
        p = page([run(5, [80, 1140, 800, 1160])])
        self.assertIsNone(copy.nocaption_owner(p, [80, 150, 800, 1120], [self.part], lambda q: dict(id='Table 1', kind='table')))


class Doubts(unittest.TestCase):
    def test_shared_doubt_list_is_loaded_and_written(self):
        import tempfile, json
        d = copy.nocaption_doubts()
        d.reset()
        d.add('F31', 2, [1, 2, 3, 4], 'uncaptioned_picture', line=7)
        with tempfile.TemporaryDirectory() as t:
            d.write(t)
            with open(os.path.join(t, 'copy.doubts.json'), encoding='utf-8') as f:
                data = json.load(f)
        d.reset()
        self.assertEqual(data, [dict(rule='F31', page=2, box=[1, 2, 3, 4], reason='uncaptioned_picture', line=7)])


class Ground(unittest.TestCase):
    def test_object_covering_the_page_under_its_text_is_ground(self):
        p = page([run(1, [200, 200, 1000, 230]), run(2, [200, 300, 1000, 330])])
        self.assertTrue(copy.nocaption_ground(p, [0, 0, W, H]))

    def test_half_page_object_under_all_the_text_is_ground(self):
        p = page([run(1, [200, 200, 1000, 230]), run(2, [200, 300, 1000, 330])])
        self.assertTrue(copy.nocaption_ground(p, [100, 100, 1140, 1200]))

    def test_large_photo_with_body_text_outside_it_is_no_ground(self):
        p = page([run(1, [200, 120, 1000, 140]), run(2, [200, 1500, 1000, 1520]), run(3, [300, 400, 320, 420], 'A')])
        self.assertFalse(copy.nocaption_ground(p, [80, 200, 1160, 1400]))

    def test_object_without_text_over_it_is_no_ground(self):
        self.assertFalse(copy.nocaption_ground(page([]), [0, 0, W, H]))


class SamePicture(unittest.TestCase):
    def test_drawn_keys_take_the_images_inside_the_box(self):
        keys = {1: [([100, 100, 200, 200], 'a'), ([500, 500, 600, 600], 'b')], 2: [([101, 99, 201, 201], 'a')]}
        self.assertEqual(copy.nocaption_drawn_keys(1, [98, 98, 202, 202], keys), frozenset({'a'}))
        self.assertEqual(copy.nocaption_drawn_keys(2, [98, 98, 202, 202], keys), frozenset({'a'}))
        self.assertEqual(copy.nocaption_drawn_keys(1, [450, 450, 650, 650], keys), frozenset({'b'}))

    def test_no_pdf_gives_no_keys(self):
        self.assertEqual(copy.nocaption_image_keys(None), {})


if __name__ == '__main__':
    unittest.main()
