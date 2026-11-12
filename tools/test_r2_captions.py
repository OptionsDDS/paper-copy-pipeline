"""Lane r2-captions: a caption block out of rule 6's flow is a caption, never a side note; dash labels follow the page."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r2_captions_copy', ROOT/'copy_paper.py')
copy = importlib.util.module_from_spec(spec); spec.loader.exec_module(copy)


def run(i, text, left, top, size=9, font='Caption', width=400):
    return dict(id=f'run:{i}', kind='text', text=text, angle=0, line=i, font=font, size_px=size,
                run_size_px=size, box_px=[left, top, left+width, top+size])


def page(rows, cls='other', drawing=True, order=None):
    """rows: one block of runs; a drawn fill above it unless drawing is False."""
    elements = list(rows)
    if drawing: elements.append(dict(id='fill:1', kind='fill', box_px=[100, 20, 400, 80]))
    return dict(page=3, elements=elements, art=[], tables=[], floats=[], region_box_px=[0, 0, 1000, 1400],
                blocks=[dict(id='block:1', members=[e['id'] for e in rows], box_px=copy.hull(e['box_px'] for e in rows))],
                main_text=dict(blocks=[dict(id='block:1', cls=cls, order=order)], furniture=[]))


class UnflowedCaptionBlocks(unittest.TestCase):
    def caption_rows(self, label='Fig. 4. Invented caption title for the drawing above', top=100):
        return [run(1, 'Upper lettering', 200, top-30, size=8, font='Sans', width=80),
                run(2, label, 50, top),
                run(3, 'and its second line continues the same sentence', 50, top+11),
                run(4, 'to its full stop.', 50, top+22, width=120)]

    def test_label_row_and_rows_below_become_a_figure_caption(self):
        p = page(self.caption_rows())
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(len(p['floats']), 1)
        f = p['floats'][0]
        self.assertEqual(f['_caption_ids'], ['run:2', 'run:3', 'run:4'])
        self.assertTrue(f['caption'].startswith('Fig. 4. Invented caption title'))
        self.assertIn('run:1', p['blocks'][0]['members'])   # the lettering stays in its own block
        # the drawn band above the caption is the float's region, taken whole
        self.assertEqual(f['_graphic_box'][:2], [100, 20])
        self.assertNotIn('_caption_only', f)

    def test_without_a_band_above_the_caption_is_caption_only(self):
        p = page(self.caption_rows(), drawing=False)
        p['elements'].append(dict(id='fill:2', kind='fill', box_px=[50, 140, 400, 200]))   # a drawing below only
        copy.unflowed_caption_blocks(p, 11)
        self.assertTrue(p['floats'][0]['_caption_only'])

    def test_dash_label_opens_a_caption_too(self):
        p = page(self.caption_rows('Figure 2—Invented caption joined by a dash'))
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(len(p['floats']), 1)

    def test_a_row_in_another_size_ends_the_caption(self):
        rows = self.caption_rows(); rows[3] = run(4, 'a smaller credit line', 50, 122, size=7)
        p = page(rows)
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(p['floats'][0]['_caption_ids'], ['run:2', 'run:3'])

    def test_side_note_without_a_label_stays(self):
        rows = [run(1, 'A marginal note set in a smaller face', 900, 100, size=8),
                run(2, 'with no figure label at all.', 900, 110, size=8)]
        p = page(rows)
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(p['floats'], [])

    def test_body_block_in_the_flow_is_never_read(self):
        p = page(self.caption_rows(), cls='main', order=4)
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(p['floats'], [])

    def test_no_drawing_near_the_caption_no_caption(self):
        p = page(self.caption_rows(), drawing=False)
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(p['floats'], [])

    def test_a_figure_citation_is_not_a_label(self):
        p = page(self.caption_rows('Fig. 4 shows the invented drawing above'))
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(p['floats'], [])

    def test_a_claimed_block_is_left_alone(self):
        p = page(self.caption_rows())
        p['floats'].append(dict(id='f', caption='Fig. 4.', blocks=['block:1'], box_px=[0, 0, 1, 1]))
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(len(p['floats']), 1)


class WidenedCaptionStarts(unittest.TestCase):
    def test_lone_label_takes_the_title_row_in_another_face(self):
        rows = [run(2, 'Table 1.', 50, 100, font='Bold'), run(3, 'Invented title line', 50, 111, font='Title'),
                run(4, 'and its second line', 50, 122, font='Title', width=120)]
        p = page(rows)
        p['tables'].append(dict(id='table:1', members=['t1'], box_px=[50, 140, 450, 200]))
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(p['floats'][0]['_caption_ids'], ['run:2', 'run:3', 'run:4'])
        self.assertEqual(p['floats'][0]['blocks'][1], 'table:1')

    def test_table_caption_without_a_table_under_it_is_left(self):
        p = page([run(2, 'Table 1. Invented title of the table', 50, 100)])
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(p['floats'], [])

    def test_space_and_panel_letter_needs_a_label_face_of_its_own(self):
        same = [run(2, 'Fig. 1', 50, 100, width=30), run(5, 'A invented panel text', 82, 100, width=300)]
        p = page(same)
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(p['floats'], [])
        bold = [run(2, 'Fig. 1', 50, 100, width=30, font='Bold'), run(5, 'A invented panel text', 82, 100, width=300)]
        p = page(bold)
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(len(p['floats']), 1)

    def test_a_caption_beside_a_picture_touches_it(self):
        rows = [run(2, 'Figure 4 | Invented caption beside the picture', 420, 30, width=100)]
        p = page(rows)   # the fill spans x 100-400, y 20-80
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(len(p['floats']), 1)

    def test_continuation_rows_in_another_block_and_text_size_join(self):
        rows = [run(2, 'Figure 5 |', 50, 100, size=11, width=50, font='Bold'),
                run(3, 'Invented caption text whose row ends mid', 105, 101, size=9, width=300)]
        p = page(rows)
        more = [run(6, 'sentence and goes on in a second block', 50, 112, size=9), run(7, 'to its end.', 50, 123, size=9, width=60)]
        p['elements'] += more
        p['blocks'].append(dict(id='block:2', members=['run:6', 'run:7'], box_px=copy.hull(e['box_px'] for e in more)))
        p['main_text']['blocks'].append(dict(id='block:2', cls='other', order=None))
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(p['floats'][0]['_caption_ids'], ['run:2', 'run:3', 'run:6', 'run:7'])

    def test_orphan_picture_with_insets_is_the_float_region(self):
        p = page([run(2, 'Figure 4 | Invented caption beside the picture', 470, 64, width=200)], drawing=False)
        p['elements'] += [dict(id='image:1', kind='image', box_px=[100, 20, 400, 80]), dict(id='image:2', kind='image', box_px=[380, 60, 460, 85])]
        p['unpaired'] = [dict(kind='graphic without a caption on this page', block='block:9', box_px=[100, 20, 400, 80]),
                         dict(kind='graphic without a caption on this page', block='block:10', box_px=[380, 60, 460, 85])]
        copy.unflowed_caption_blocks(p, 11)
        f = p['floats'][0]
        self.assertNotIn('_caption_only', f)
        self.assertEqual(f['box_px'][:3], [100, 20, 670])
        self.assertIn('block:9', f['blocks']); self.assertIn('block:10', f['blocks'])

    def test_a_labelled_float_keeps_its_region_and_takes_the_caption(self):
        p = page([run(2, 'Figure 4 | Invented caption under the picture', 100, 90)])
        p['floats'].append(dict(id='f', caption='Figure 4', blocks=['image:1'], box_px=[90, 10, 470, 85]))
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(len(p['floats']), 1)
        self.assertEqual(p['floats'][0]['box_px'], [90, 10, 470, 85])
        self.assertEqual(p['floats'][0]['_caption_ids'], ['run:2'])

    def test_lettering_above_the_label_on_the_drawing_is_lettering(self):
        rows = [run(1, 'Lettering', 150, 85, size=8, font='Sans', width=80),
                run(2, 'Fig. 4. Invented caption title', 50, 100)]
        p = page(rows)
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(p['floats'][0]['lettering'], ['run:1'])


class GeometryMemoForms(unittest.TestCase):
    def test_bold_span_over_label_and_panel_letter(self):
        r = run(2, 'Fig. 1 A invented panel text', 50, 100, width=300)
        r['font'] = ['Bold', 'Regular']; r['font_spans'] = [dict(start=0, end=8, font='Bold'), dict(start=8, end=28, font='Regular')]
        self.assertTrue(copy.unflowed_caption_start([r]))
        r['font_spans'][0]['end'] = 12   # a bold span running into a word is not a label face
        self.assertIsNone(copy.unflowed_caption_start([r]))

    def test_rows_differing_only_by_subset_tag_continue_the_caption(self):
        rows = [run(2, 'Figure 4 | Invented caption whose first row is short', 50, 100, font=['ABCDEF+Sans-Light', 'ABCDEF+Sans-Bold']),
                run(3, 'and whose second row is set in the same face under another tag', 50, 111, font='GHIJKL+Sans-Light', width=500),
                run(4, 'to its end.', 50, 122, font='GHIJKL+Sans-Light', width=60)]
        p = page(rows)
        p['blocks'] = [dict(id='block:1', members=['run:2'], box_px=rows[0]['box_px']),
                       dict(id='block:2', members=['run:3', 'run:4'], box_px=copy.hull(e['box_px'] for e in rows[1:]))]
        p['main_text']['blocks'].append(dict(id='block:2', cls='other', order=None))
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(p['floats'][0]['_caption_ids'], ['run:2', 'run:3', 'run:4'])

    def test_lone_table_label_with_a_larger_title_over_a_raster(self):
        rows = [run(2, 'Table 1.', 50, 100, size=10, font='Label'), run(3, 'Invented larger title', 50, 119, size=12, font='Title')]
        p = page(rows, drawing=False)
        p['elements'].append(dict(id='image:1', kind='image', box_px=[50, 138, 400, 300]))
        p['unpaired'] = [dict(kind='graphic without a caption on this page', block='block:7', box_px=[50, 138, 400, 300])]
        copy.unflowed_caption_blocks(p, 11)
        f = p['floats'][0]
        self.assertEqual(f['_caption_ids'], ['run:2', 'run:3']); self.assertIn('block:7', f['blocks'])
        self.assertEqual(f['box_px'][3], 300)


class WholeDrawingRegion(unittest.TestCase):
    def test_a_chart_wider_than_its_caption_is_taken_whole(self):
        rows = [run(2, 'Figure 4 | Invented caption narrower than its chart', 100, 300, width=200),
                run(3, 'and its second row.', 100, 311, width=150)]
        p = page(rows, drawing=False)
        p['elements'] += [dict(id='fill:%d' % k, kind='fill', box_px=[100 + 40 * k, 200, 130 + 40 * k, 280]) for k in range(10)]
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(p['floats'][0]['_graphic_box'][2], 490)


class PicturesInOneBand(unittest.TestCase):
    def test_each_caption_keeps_its_own_picture(self):
        left = [run(2, 'Figure 1 | Invented caption of the left picture', 100, 300, width=280)]
        right = [run(3, 'Figure 2 | Invented caption of the right picture', 400, 300, width=280)]
        p = page(left, drawing=False)
        p['elements'] += right + [dict(id='image:1', kind='image', box_px=[100, 150, 390, 290]),
                                  dict(id='image:2', kind='image', box_px=[400, 150, 690, 290])]
        p['blocks'].append(dict(id='block:2', members=['run:3'], box_px=right[0]['box_px']))
        p['main_text']['blocks'].append(dict(id='block:2', cls='other', order=None))
        copy.unflowed_caption_blocks(p, 11)
        boxes = sorted(f['_graphic_box'] for f in p['floats'])
        self.assertEqual(boxes, [[100, 150, 390, 290], [400, 150, 690, 290]])

    def test_one_caption_over_two_panels_takes_both(self):
        p = page([run(2, 'Figure 3 | (a) Invented left panel. (b) Invented right panel.', 100, 300, width=590)], drawing=False)
        p['elements'] += [dict(id='image:1', kind='image', box_px=[100, 150, 390, 290]),
                          dict(id='image:2', kind='image', box_px=[400, 150, 690, 290])]
        copy.unflowed_caption_blocks(p, 11)
        self.assertEqual(p['floats'][0]['_graphic_box'], [100, 150, 690, 290])


class TableCaptionColumn(unittest.TestCase):
    def test_a_body_row_across_the_gutter_is_not_caption(self):
        lab = dict(id='run:1', kind='text', text='Table 5. Invented caption row one', angle=0, box_px=[130, 85, 588, 103], run_size_px=18.7)
        body = dict(id='run:2', kind='text', text='Invented body row of the next column', angle=0, box_px=[651, 85, 1128, 104], run_size_px=19.7)
        row2 = dict(id='run:3', kind='text', text='invented caption row two.', angle=0, box_px=[131, 107, 583, 126], run_size_px=18.7)
        p = dict(elements=[lab, body, row2], blocks=[dict(id='block:1', members=['run:1', 'run:3']), dict(id='block:2', members=['run:2'])],
                 main_text=dict(columns=[[130, 609], [650, 1128]], blocks=[dict(id='block:1', cls='caption', order=None),
                                                                           dict(id='block:2', cls='main', order=18)]))
        self.assertEqual(copy.table_caption_members(p, lab), ['run:1', 'run:3'])


class UnflowedCaptionTail(unittest.TestCase):
    def test_only_whole_unflowed_unowned_blocks_are_offered(self):
        runs = {f'r{i}': dict(id=f'r{i}') for i in range(6)}
        blocks = {'a': ['r0', 'r1'], 'b': ['r2', 'r3'], 'c': ['r4'], 'd': ['r5']}
        mtb = {'a': dict(cls='other', order=None), 'b': dict(cls='main', order=3),
               'c': dict(cls='furniture', order=None), 'd': dict(cls='other', order=None)}
        members = lambda bid: blocks.get(bid, [])
        groups = copy.caption_tail_unflowed_groups(runs, blocks, mtb, members, ['x'], set(), set())
        self.assertEqual(groups, [[runs['r0'], runs['r1']], [runs['r5']]])
        self.assertEqual(copy.caption_tail_unflowed_groups(runs, blocks, mtb, members, ['x'], {'r1'}, {'d'}), [])
        self.assertEqual(copy.caption_tail_unflowed_groups(runs, blocks, mtb, members, [], set(), set()), [])


class ShorterUnflowedColumn(unittest.TestCase):
    def setUp(self):
        def rows(left, texts, prefix):
            return [dict(id=f'{prefix}{i}', kind='text', text=t, angle=0, line=i, font='Caption', size_px=10,
                         run_size_px=10, box_px=[left, 110+i*14, left+200, 120+i*14]) for i, t in enumerate(texts)]
        self.left = rows(10, ['Fig. 2. An invented caption for the picture above it', 'several ordinary words in the middle',
                              'more ordinary words', 'and the column ends with the'], 'l')
        self.right = rows(230, ['keepers walked at dusk', 'to the last line.'], 'r')
        self.page = dict(elements=[dict(kind='image', box_px=[10, 0, 430, 100])] + self.left + self.right)

    def test_a_shorter_unflowed_second_column_joins(self):
        self.assertEqual(copy.caption_column_tail(self.page, self.left, [self.right], [self.right]), self.right)

    def test_the_same_column_offered_as_a_body_block_does_not(self):
        self.assertFalse(copy.caption_column_tail(self.page, self.left, [self.right]))

    def test_other_tests_still_hold_for_unflowed_columns(self):
        self.right[0]['text'] = 'Keepers walked at dusk'
        self.assertFalse(copy.caption_column_tail(self.page, self.left, [self.right], [self.right]))


class PrintedDashLabels(unittest.TestCase):
    def items(self, caption, printed, kind='figure'):
        pages = [dict(page=2, elements=[dict(id='run:9', kind='text', text=printed)])]
        items = [dict(kind=kind, page=2, caption=caption, caption_ids=['run:9'])]
        copy.printed_dash_labels(items, pages)
        return items[0]['caption']

    def test_closed_up_dash_loses_the_added_period(self):
        self.assertEqual(self.items('Figure 2. —Invented title', 'Figure 2—Invented title'), 'Figure 2—Invented title')
        self.assertEqual(self.items('Table 3. —Invented title', 'Table 3—Invented', 'table'), 'Table 3—Invented title')

    def test_spaced_and_period_forms_follow_the_page(self):
        self.assertEqual(self.items('Figure 2. —Invented title', 'Figure 2 —Invented title'), 'Figure 2 —Invented title')
        self.assertEqual(self.items('Figure 2. —Invented title', 'Figure 2.—Invented title'), 'Figure 2.—Invented title')
        self.assertEqual(self.items('Fig. 5. –Invented', 'FIG. 5. –Invented'), 'Fig. 5. –Invented')

    def test_without_a_printed_run_or_a_dash_nothing_changes(self):
        self.assertEqual(self.items('Figure 2. —Invented title', 'Some other line'), 'Figure 2. —Invented title')
        self.assertEqual(self.items('Figure 2. Invented title', 'Figure 2. Invented title'), 'Figure 2. Invented title')


if __name__ == '__main__': unittest.main()
