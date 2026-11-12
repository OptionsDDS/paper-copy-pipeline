"""Synthetic regressions for lane r2-figlet (a heading under a framed figure taken as its lettering; caption
bodies left unplaced, 2026-11-06):
F1 an exhibit drawn round its own caption ends at that drawing: a body-face run wholly beyond the outermost
   shape enclosing the caption label is never the figure's lettering (join_figure_lettering);
F4 a heading band (a fill or a rule pair holding one centred line of non-lettering-size text, no drawing) that
   follows a figure's caption with no drawing between is the page's: neither it nor its text joins the figure;
F3 a capital that letters continue on its baseline (a small-caps heading's large initial) is no panel letter in
   the copy's one-letter band round a figure (copy_paper read_page);
F2 the caption's band (the smallest drawn shape round the label holding no other drawing and no text above
   the label) holds the caption: every line inside it at caption size continues it, whatever its face
   (split_figure_caption_blocks).
Every geometry here is invented; no line of any paper is quoted."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


boxer = module('figlet_boxer', 'standalone/element_boxer_sc.py')
paper = module('figlet_copy', 'copy_paper.py')


def text(name, value, box, line, size=10, font='Body-Regular'):
    return dict(id=name, kind='text', text=value, box_px=list(box), line=line, angle=0, size_px=size,
                run_size_px=size, font=font, font_spans=[dict(font=font, start=0, end=len(value))])


def block(name, elements):
    es = list(elements)
    return dict(id=name, members=[e['id'] for e in es],
                box_px=[min(e['box_px'][0] for e in es), min(e['box_px'][1] for e in es),
                        max(e['box_px'][2] for e in es), max(e['box_px'][3] for e in es)],
                text_lines=len({e['line'] for e in es if e['kind'] == 'text'}),
                kinds=sorted({e['kind'] for e in es}), text=' '.join(e['text'] for e in es if e['kind'] == 'text'))


def shape(name, box, kind='fill'): return dict(id=name, kind=kind, box_px=list(box))


class ExhibitBorder(unittest.TestCase):
    """F1: a frame enclosing chart and caption band; what lies under the frame's bottom edge."""
    def page(self, below, frame_kind='outline', band=True, cap_box=(6, 142, 150, 150), frame=True):
        tick = text('tick', '10', (14, 20, 22, 27), 1, 7, 'Sans')
        legend = text('legend', 'Treated group', (60, 40, 140, 50), 2)
        cap = text('cap', 'Figure 9. An invented chart.', cap_box, 5, 8)
        prose = [text(f'prose{i}', 'An invented body line long enough to set the page body size and face here.',
                      (230, 20 + 12 * i, 420, 30 + 12 * i), 10 + i) for i in range(4)]
        es = [tick, legend, cap, shape('axes', (24, 15, 190, 120), 'outline'), shape('plot', (30, 30, 180, 110)),
              ] + ([shape('frame', (0, 0, 200, 170), frame_kind)] if frame else []) + prose + list(below)
        if band: es.append(shape('band', (1, 136, 199, 168)))
        bs = [block('graphic', [e for e in es if e['id'] in ('tick', 'legend', 'axes', 'plot', 'frame', 'band')]),
              block('cap', [cap])] + [block(e['id'], [e]) for e in prose + list(below)]
        fs = [dict(caption=cap['text'], blocks=['cap', 'graphic'], box_px=[0, 0, 200, 170])]
        boxer.join_figure_lettering(es, bs, [], fs, [])
        return fs[0]

    def test_body_face_heading_under_the_frame_is_not_lettering(self):
        f = self.page([text('head', 'Discussion', (70, 173, 130, 181), 6, 8)])
        self.assertIn('tick', f['lettering'])
        self.assertNotIn('head', f['lettering'])
        self.assertLessEqual(f['box_px'][3], 170)

    def test_small_caps_initial_larger_than_the_page_median_is_not_lettering(self):
        # a small-caps heading drawn as a large initial and smaller capitals, the initial above the page's
        # median size of long runs (justified body drawn word by word leaves few long runs)
        f = self.page([text('init', 'S', (70, 172, 78, 183), 6, 13), text('rest', 'ECOND', (78, 175, 120, 183), 6, 8)])
        self.assertNotIn('init', f['lettering'])
        self.assertNotIn('rest', f['lettering'])

    def test_heading_under_a_caption_band_without_outline_is_not_lettering(self):
        f = self.page([text('head', 'Discussion', (70, 171, 130, 179), 6, 8)], frame_kind='fill')
        self.assertNotIn('head', f['lettering'])

    def test_a_band_alone_bounds_only_its_far_side(self):
        # no frame: the caption band at the chart's foot; a heading under the band is the page's, while a
        # body-face legend line above the band (on the chart) stays lettering
        f = self.page([text('head', 'Discussion', (70, 170, 130, 178), 6, 8)], frame=False)
        self.assertNotIn('head', f['lettering'])
        self.assertIn('legend', f['lettering'])

    def test_heading_under_a_frame_whose_caption_band_is_at_its_top(self):
        f = self.page([text('head', 'Discussion', (70, 173, 130, 181), 6, 8)], band=False, cap_box=(6, 2, 150, 10))
        self.assertNotIn('head', f['lettering'])

    def test_axis_title_just_inside_the_frame_bottom_stays_lettering(self):
        # caption band at the frame's top: the axis title sits inside the frame, above its bottom edge
        title = text('title', 'Months', (80, 158, 120, 166), 6, 8)
        f = self.page([title], band=False, cap_box=(6, 2, 150, 10))
        self.assertIn('title', f['lettering'])

    def test_a_label_in_another_face_under_the_frame_is_unaffected(self):
        f_new = self.page([text('scale', '1 cm', (90, 172, 110, 179), 6, 7, 'Sans')])
        self.assertIn('scale', f_new['lettering'])


class HeadingBand(unittest.TestCase):
    """F4: a shaded heading band with edge rules under the frame, the heading in a face of its own."""
    def page(self, band_text, extra=(), rules_only=False, x=(0, 150), capsize=8):
        tick = text('tick', '10', (14, 20, 22, 27), 1, 7, 'Sans')
        cap = text('cap', 'Figure 9. An invented chart.', (6, 142, 150, 150), 5, capsize)
        prose = [text(f'prose{i}', 'An invented body line long enough to set the page body size and face here.',
                      (230, 20 + 12 * i, 420, 30 + 12 * i), 10 + i) for i in range(4)]
        frame = [shape('plot', (30, 30, 180, 110)), shape('capband', (1, 136, 199, 160)),
                 shape('fr1', (0, 0, 200, 1), 'rule'), shape('fr2', (0, 162, 200, 163), 'rule'), shape('fr3', (0, 166, 200, 167), 'rule')]
        band = [shape('ht', (x[0], 186, x[1], 187), 'rule'), shape('hb', (x[0], 206, x[1], 207), 'rule')]
        if not rules_only: band.append(shape('hfill', (x[0], 186, x[1], 207)))
        es = [tick, cap] + frame + band + prose + list(band_text) + list(extra)
        bs = [block('graphic', [tick] + frame), block('cap', [cap])] + [block(e['id'], [e]) for e in prose + band + list(band_text) + list(extra)]
        fs = [dict(caption=cap['text'], blocks=['cap', 'graphic'], box_px=[0, 0, 200, 167])]
        boxer.join_figure_lettering(es, bs, [], fs, [])
        return fs[0]

    def head(self, size=9): return text('head', 'DISCUSSION', (50, 192, 100, 201), 6, size, 'Heading-SC')

    def test_heading_in_a_shaded_ruled_band_is_not_lettering(self):
        f = self.page([self.head()])
        self.assertIn('tick', f['lettering'])
        self.assertNotIn('head', f['lettering'])
        self.assertLessEqual(f['box_px'][3], 167)

    def test_a_rule_pair_band_is_a_heading_band_too(self):
        f = self.page([self.head()], rules_only=True)
        self.assertNotIn('head', f['lettering'])

    def test_a_band_holding_a_drawing_or_lettering_size_text_stays_with_the_figure(self):
        swatch = shape('swatch', (60, 192, 66, 198))
        key = text('key', 'Treated arm', (68, 192, 110, 199), 6, 7, 'Sans')
        f = self.page([key], extra=[swatch])
        self.assertIn('key', f['lettering'])
        f = self.page([text('key', 'Treated arm', (55, 192, 95, 199), 6, 7, 'Sans')])
        self.assertIn('key', f['lettering'])

    def test_a_note_smaller_than_the_caption_stays_with_the_figure(self):
        # body size from long runs can be as small as the caption; a note below caption size is lettering
        f = self.page([text('note', 'Source: invented data', (40, 192, 110, 199), 6, 8.2, 'Sans')], capsize=9)
        self.assertIn('note', f['lettering'])


class CaptionBand(unittest.TestCase):
    """F2: a bold caption title over a regular caption body, both inside the caption's shaded band."""
    def page(self, band=True, text_above_in_band=False):
        axis = text('axis', 'Axis label', (10, 10, 60, 18), 1, 7, 'Sans')
        cap = text('cap', 'Figure 9. An invented title.', (6, 142, 150, 150), 2, 8, 'Body-Bold')
        body1 = text('body1', 'Panel lines describe the invented measure', (6, 152, 194, 160), 3, 8)
        body2 = text('body2', 'over invented months.', (6, 162, 100, 170), 4, 8)
        es = [axis, cap, body1, body2, shape('plot', (20, 5, 190, 130))]
        if band: es.append(shape('band', (1, 138, 199, 174)))
        if text_above_in_band:
            es.append(text('above', 'x', (100, 139, 104, 141), 2, 3, 'Sans'))
        bs = [block('mixed', es)]
        boxer.split_figure_caption_blocks(es, bs)
        return bs

    def test_regular_body_lines_inside_the_band_continue_a_bold_title(self):
        bs = self.page()
        self.assertEqual(bs[-1]['members'], ['cap', 'body1', 'body2'])

    def test_without_a_band_the_face_rule_still_decides(self):
        bs = self.page(band=False)
        self.assertEqual(bs[-1]['members'], ['cap'])


class WordInitial(unittest.TestCase):
    """F3: the copy's one-letter band under a figure frame."""
    def read(self, rest):
        cap = text('cap', 'FIGURE 9. A caption.', (5, 105, 195, 115), 2)
        init = text('init', 'S', (80, 121, 88, 130), 3, 11)
        body = text('body', 'The body remains outside the figure and runs on in its column.', (0, 150, 200, 160), 5)
        drawing = shape('frame', (0, 10, 200, 120))
        es = [cap, init, body, drawing] + ([text('rest', 'ECTION', (89, 123, 130, 130), 3, 8)] if rest else [])
        heads = [e for e in es if e['id'] in ('init', 'rest')]
        bs = [block('graphic', [drawing]), block('caption', [cap]), block('head', heads), block('body', [body])]
        p = dict(page=1, elements=es, blocks=bs, tables=[], region_box_px=[0, 0, 220, 300],
                 main_text=dict(columns=[[0, 200]], blocks=[
                     dict(id=bid, cls='main', order=i + 1, lines=1, size_px=e['size_px'], box_px=e['box_px'])
                     for i, (bid, e) in enumerate([('head', init), ('body', body)])]),
                 floats=[dict(id='figure', caption=cap['text'], blocks=['caption', 'graphic'], box_px=[0, 10, 200, 120])])
        prose, floats, side = paper.read_page(p, 10, [])
        return p, prose

    def test_initial_continued_by_letters_is_not_a_panel_letter(self):
        p, prose = self.read(True)
        self.assertNotIn('init', p.get('copy_figure_lettering', []))

    def test_a_lone_capital_in_the_band_stays_a_panel_letter(self):
        p, prose = self.read(False)
        self.assertIn('init', p.get('copy_figure_lettering', []))


if __name__ == '__main__':
    unittest.main()
