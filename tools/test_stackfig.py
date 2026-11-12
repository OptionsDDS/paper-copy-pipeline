#!/usr/bin/env python3
"""Lane r3-stackfig: bar-separated caption labels, page turns from a page's last text column,
a smaller-type reference list ended by the next page's body text, and a table region without
text runs."""
import importlib.util, os, sys, unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import copy_paper as copy

spec = importlib.util.spec_from_file_location('boxer_stackfig', Path(HERE).parents[0] / 'standalone' / 'element_boxer_sc.py')
boxer = importlib.util.module_from_spec(spec); spec.loader.exec_module(boxer)


def trun(i, text, top, size, x0=100, x1=900):
    return dict(id=f'run:{i}', kind='text', angle=0, text=text, box_px=[x0, top, x1, top + size], size_px=size, run_size_px=size)


class BarLabel(unittest.TestCase):
    def test_bar_label_is_a_caption_label_wherever_the_full_stop_form_is(self):
        # ruling 2026-11-11: no size or column condition; the bar form follows the full-stop form
        for bar, dot in (('Figure 1 | Eastern rows at dusk.', 'Figure 1. Eastern rows at dusk.'),
                         ('Fig. 2 | A flat.', 'Fig. 2. A flat.'), ('Table 3 | Station counts', 'Table 3. Station counts'),
                         ('Figure IV | Roman.', 'Figure IV. Roman.'), ('Fig. 5b | Panel.', 'Fig. 5b. Panel.')):
            self.assertEqual(boxer.is_caption_label(bar), boxer.is_caption_label(dot), bar)
            self.assertTrue(boxer.is_caption_label(bar), bar)
        self.assertTrue(boxer.is_caption_run(trun(1, 'Figure 3 | Two post types.', 998, 17)))

    def test_running_text_and_existing_forms(self):
        self.assertFalse(boxer.is_caption_label('Figure 1 shows the flat.'))
        self.assertFalse(boxer.is_caption_label('Table 2 lists the stations.'))
        self.assertTrue(boxer.is_caption_label('Figure 1. A flat.'))
        self.assertTrue(boxer.is_caption_label('Table 1: Counts'))


def para(text, page, col, box, flush=True):
    return dict(kind='para', text=text, page=page, box=box, col=col,
                flow_start=(page, 0, flush), flow_end=(page, 0, flush))


class PageTurnFromLastColumn(unittest.TestCase):
    COL = (100, 600)

    def items(self):
        x = para('Survey poles set in some beds were read for many years and the tile method', 1, self.COL, [100, 600, 600, 1300])
        y = para('Each bed was split into bands from the bank to open water.', 2, self.COL, [100, 100, 600, 400])
        return [x, dict(kind='page', page=1), y]

    def test_joins_when_the_column_is_the_page_last(self):
        out = copy.rejoin_paragraphs(self.items(), copy.Joiner([]), 20, 1, {1: [[100, 600, 600, 1300]]})
        self.assertEqual(len([i for i in out if i['kind'] == 'para']), 1)

    def test_text_column_to_the_right_stops_the_layout_join(self):
        blocks = {1: [[100, 600, 600, 1300], [650, 600, 1150, 700]]}
        out = copy.rejoin_paragraphs(self.items(), copy.Joiner([]), 20, 1, blocks)
        self.assertEqual([i['kind'] for i in out], ['para', 'page', 'para'])

    def test_lowercase_start_still_joins_across_it(self):
        items = self.items(); items[2]['text'] = 'gave calmer figures than the poles.'
        blocks = {1: [[100, 600, 600, 1300], [650, 600, 1150, 700]]}
        out = copy.rejoin_paragraphs(items, copy.Joiner([]), 20, 1, blocks)
        self.assertEqual(len([i for i in out if i['kind'] == 'para']), 1)

    def test_narrow_margin_note_or_lower_block_is_no_column(self):
        x = para('t', 1, self.COL, [100, 600, 600, 1300])
        ext = copy.column_extents([x])
        self.assertFalse(copy.later_column_on_page(x, {1: [[650, 600, 800, 700]]}, ext, 20))    # narrower than half
        self.assertFalse(copy.later_column_on_page(x, {1: [[650, 1350, 1150, 1400]]}, ext, 20))  # below X's last line
        self.assertTrue(copy.later_column_on_page(x, {1: [[650, 620, 1150, 700]]}, ext, 20))

    def test_blocks_inside_a_fill_are_left_out(self):
        page = dict(page=1, elements=[dict(kind='fill', box_px=[640, 580, 1160, 900])],
                    main_text=dict(blocks=[dict(cls='aside', box_px=[650, 600, 1150, 700]),
                                           dict(cls='main', box_px=[100, 600, 600, 1300]),
                                           dict(cls='furniture', box_px=[100, 50, 600, 70])]))
        self.assertEqual(copy.page_text_block_boxes([page]), {1: [[100, 600, 600, 1300]]})


class ReferenceListEnd(unittest.TestCase):
    def block(self, page, size, first):
        return dict(page=page, meta=dict(size_px=size), lines=[first])

    def test_body_size_block_on_the_next_page_ends_a_smaller_list(self):
        items = [dict(kind='ref', text='8. Flood F. Title. 2008;10:72-80.', page=1, _ref_size=16)]
        self.assertTrue(copy.refs_left_by(self.block(2, 20, 'Harbour Authority logs were kept.'), items, 20))

    def test_side_text_block_without_meta(self):
        # main() hands side text inside a reference section to add_refs as a bare block
        bare = {"lines": ["23. Gable K, Ferry L. Kiln floor notes."], "lefts": [0], "page": 2}
        item = copy.reference_item('23. Gable K, Ferry L. Kiln floor notes.', bare, None)
        self.assertEqual((item['kind'], item['page'], item['_ref_size']), ('ref', 2, None))
        # an unknown size never ends the list: neither a bare block nor an entry without a size
        items = [dict(kind='ref', text='8. Flood F. Title.', page=1, _ref_size=16)]
        self.assertFalse(copy.refs_left_by(bare, items, 20))
        self.assertFalse(copy.refs_left_by(self.block(2, 20, 'Harbour logs.'), items + [item], 20))
        no_page = {"lines": ["Harbour logs."], "meta": {"size_px": 20}}
        self.assertFalse(copy.refs_left_by(no_page, items, 20))

    def test_entries_running_on_stay_in_the_list(self):
        items = [dict(kind='ref', text='8. Flood F. Title.', page=1, _ref_size=16)]
        self.assertFalse(copy.refs_left_by(self.block(2, 16, 'reed. Estuar Lett. 2015.'), items, 20))   # same small size
        self.assertFalse(copy.refs_left_by(self.block(1, 20, 'Harbour logs.'), items, 20))              # same page
        self.assertFalse(copy.refs_left_by(self.block(2, 20, '9. Core B. Title.'), items, 20))          # numbered entry
        body_size = [dict(kind='ref', text='8. Flood F.', page=1, _ref_size=20)]
        self.assertFalse(copy.refs_left_by(self.block(2, 20, 'Harbour logs.'), body_size, 20))          # list at body size


def shape(name, box, kind='image'): return dict(id=name, kind=kind, box_px=list(box))


def block(name, es):
    return dict(id=name, members=[e['id'] for e in es],
                box_px=[min(e['box_px'][0] for e in es), min(e['box_px'][1] for e in es),
                        max(e['box_px'][2] for e in es), max(e['box_px'][3] for e in es)],
                text_lines=len({e.get('line') for e in es if e['kind'] == 'text'}),
                kinds=sorted({e['kind'] for e in es}), text=' '.join(e['text'] for e in es if e['kind'] == 'text'))


class HeadBand(unittest.TestCase):
    """The page's head band (top row with a folio, above every drawing, and a line within two body
    heights under it) never joins a page-top figure as title or lettering (step-3 mimic u1)."""
    def page(self, folio=True, caplabel='Figure 1 |'):
        def t(name, value, box, line, size):
            return dict(id=name, kind='text', text=value, box_px=list(box), line=line, angle=0, size_px=size, run_size_px=size)
        head = t('head', 'Reviews in Valley Crafts | Volume 4 | 2025', (151, 71, 463, 87), 1, 17)
        num = t('folio', '2' if folio else 'x', (1117, 72, 1124, 83), 1, 17)
        label = t('section', 'REVIEWS', (955, 103, 1123, 130), 2, 37)
        cap = t('cap', caplabel + ' Kiln sites along the upper valley. Each site was walked in spring.', (151, 666, 1117, 683), 3, 18)
        body = [t(f'b{i}', 'Meadow rafter copper hollow copper harbour rafter hollow ferry cobble ferry.', (150, 783 + 27 * i, 1124, 802 + 27 * i), 4 + i, 21) for i in range(6)]
        pic = shape('image:1', (150, 167, 1125, 646))
        es = [head, num, label, cap, pic] + body
        bs = [block('h', [head, num]), block('s', [label]), block('g', [pic]), block('c', [cap]), block('body', body)]
        fs = [dict(caption=cap['text'], blocks=['c', 'g'], box_px=[150, 167, 1125, 683])]
        boxer.join_figure_lettering(es, bs, [], fs, [])
        return fs[0]

    def test_no_head_band_without_a_bar_caption(self):
        # ruling 2026-11-12: a page whose caption is not bar-separated keeps the earlier lettering path
        # (the section label under the running head joins the figure as before)
        f = self.page(caplabel='Figure 1.')
        self.assertIn('section', f.get('lettering', []))

    def test_head_band_stays_out_of_the_figure(self):
        f = self.page()
        for rid in ('head', 'folio', 'section'): self.assertNotIn(rid, f.get('lettering', []))
        self.assertGreaterEqual(f['box_px'][1], 160)


class HeadBandPanelLetters(unittest.TestCase):
    """Panel letters at a page-top photograph's corner, within two body heights of the running-head row,
    belong to the figure (gate memo gate-stackfig-headband): they join it as lettering and the float
    region stays round the picture."""
    def test_letters_on_the_picture_join_the_figure(self):
        def t(name, value, box, line, size):
            return dict(id=name, kind='text', text=value, box_px=list(box), line=line, angle=0, size_px=size, run_size_px=size)
        head = t('head', 'ARDEN et al.', (150, 71, 248, 83), 1, 17)
        num = t('folio', '69', (1107, 72, 1124, 83), 1, 17)
        letters = [t('A', 'A', (157, 115, 172, 131), 2, 23), t('B', 'B', (488, 115, 502, 131), 2, 23)]
        pics = [shape('image:1', (150, 108, 464, 338)), shape('image:2', (481, 108, 794, 338))]
        cap = t('cap', 'FIGURE 7 In case there are plates on both banks the crews read the northern plate first.', (151, 360, 1117, 377), 3, 18)
        body = [t(f'b{i}', 'Meadow rafter copper hollow copper harbour rafter hollow ferry cobble ferry.', (150, 420 + 27 * i, 1124, 439 + 27 * i), 4 + i, 21) for i in range(6)]
        es = [head, num, cap] + letters + pics + body
        bs = [block('h', [head, num]), block('g', pics + letters), block('c', [cap]), block('body', body)]
        fs = [dict(caption=cap['text'], blocks=['c', 'g'], box_px=[150, 108, 1117, 377])]
        boxer.join_figure_lettering(es, bs, [], fs, [])
        self.assertEqual(sorted(fs[0].get('lettering', [])), ['A', 'B'])   # 4f74fce barred them as head band
        self.assertNotIn('head', fs[0].get('lettering', []))
        self.assertGreaterEqual(fs[0]['box_px'][1], 100)


class EmptyTableRegion(unittest.TestCase):
    def test_hull_caller_guards_empty_members(self):
        src = (Path(HERE).parents[0] / 'copy_paper.py').read_text()
        self.assertIn("if tab_ids and not table_members:", src)
        self.assertIn("'table region without text runs skipped'", src)


if __name__ == '__main__':
    unittest.main()
