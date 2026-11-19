"""Lane r5-captionside (round 5): rules F13, F14/F15 and F16. All texts and geometry are invented; no literal from any paper.

F13 boxer rule 4 (caption_label_line_blocks, ported from lane r4-captionextent): a one-line block on a figure caption
    label's own line, to its right, in the caption's type, with nothing between and not at a body column's left edge,
    joins the caption block before pairing, so a side caption pairs with the picture beside it; a table caption's label
    line is left as before; a body column whose first line is level with a side caption stays apart.
F16 boxer rule 6 (ported): a block in a figure caption's type, level with the caption's top, beside it under the same
    drawing row, after a caption that ends open, is the caption's second column, never body text. Copier
    (caption_column_tail): a one-line second column out of the flow joins; a gap wider than four letter heights joins
    when both blocks open at the left edges of two neighbouring page columns (a ragged-right caption column).
F14 copier (caption_foot_continuations, apply_caption_continuations): a figure caption at the column foot whose last line
    is open continues in the next column (or the next page's first column) in the caption's own type, down to the
    first gap; a first line in another type or a label ends it.
F15 copier: the same caption set in the body type is listed as doubtful (copy.doubts.json, rule F15) and the copy is
    not changed.
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


paper = module('r5cs_copy_paper', 'copy_paper.py')
boxer = module('r5cs_element_boxer_sc', 'standalone/element_boxer_sc.py')
sys.meta_path[:] = [f for f in sys.meta_path if type(f).__name__ != 'SCImportGuard']   # the boxer's guard is for the boxer


def run(name, text, x, y, width=200, size=10, line=None, font='ABCDEF+Serif', angle=0, **kw):
    return dict(id=name, kind='text', text=text, box_px=[x, y, x + width, y + size], angle=angle,
                line=y if line is None else line, run_size_px=size, size_px=size, font=font,
                font_spans=[dict(font=font, start=0, end=len(text))], flags=[], **kw)


def block(name, members):
    return dict(id=name, members=[e['id'] for e in members], kinds=sorted({e['kind'] for e in members}),
                box_px=paper.hull(e['box_px'] for e in members),
                text_lines=len({e['line'] for e in members if e['kind'] == 'text'}),
                text=' '.join(e['text'] for e in members if e['kind'] == 'text'))


class SideCaptionLabelLine(unittest.TestCase):
    """F13"""
    def setUp(self):
        self.label = run('lab', 'FIGURE 4', 40, 100, width=60, size=12, line=2, font='ABCDEF+Sans-Bold')
        self.under = run('under', 'drawings', 40, 116, width=60, size=12, line=3, font='ABCDEF+Sans')
        self.title = run('title', 'Invented diagram of', 130, 100, width=110, size=12, line=2, font='ABCDEF+Sans')

    def join(self, extra=()):
        caption = block('block:1', [self.label, self.under])
        beside = block('block:2', [self.title])
        blocks = [caption, beside] + list(extra)
        elements = [self.label, self.under, self.title] + [e for b in extra for e in b['_runs']]
        boxer.caption_label_line_blocks(elements, blocks)
        return caption, blocks

    def test_title_on_the_label_line_joins_the_caption(self):
        caption, blocks = self.join()
        self.assertEqual(caption['members'], ['lab', 'under', 'title'])
        self.assertEqual([b['id'] for b in blocks], ['block:1'])

    def test_table_label_line_is_left_as_before(self):
        self.label['text'] = 'TABLE 4'
        caption, blocks = self.join()
        self.assertEqual(len(blocks), 2)

    def test_caption_with_its_picture_directly_above_is_left_as_before(self):
        pic = dict(id='image:1', kind='image', box_px=[40, 20, 400, 95])   # a picture right over the caption
        caption = block('block:1', [self.label, self.under])
        beside = block('block:2', [self.title])
        blocks = [caption, beside]
        boxer.caption_label_line_blocks([self.label, self.under, self.title, pic], blocks)
        self.assertEqual(len(blocks), 2)
        pic['box_px'] = [300, 20, 600, 300]   # a picture beside the caption (right of its label line block) does not stop it
        caption = block('block:1', [self.label, self.under])
        blocks = [caption, block('block:2', [self.title])]
        self.title['box_px'] = [130, 100, 240, 112]
        boxer.caption_label_line_blocks([self.label, self.under, self.title, dict(pic, box_px=[260, 20, 600, 300])], blocks)
        self.assertEqual(len(blocks), 1)

    def test_line_in_another_size_stays(self):
        self.title.update(size_px=15, run_size_px=15)
        caption, blocks = self.join()
        self.assertEqual(len(blocks), 2)

    def test_first_line_of_a_body_column_stays(self):
        col = [run(f'c{i}', 'an ordinary body line with several words', 130, 100 + 16 * i, width=300, size=12,
                   line=2 + i, font='ABCDEF+Sans') for i in range(1, 6)]
        body = block('block:3', col)
        body['_runs'] = col
        caption, blocks = self.join([body])
        self.assertNotIn('title', caption['members'])

    def test_lettering_on_a_drawing_beside_the_label_stays(self):
        box = dict(id='fill:1', kind='fill', box_px=[120, 80, 400, 300])
        caption = block('block:1', [self.label, self.under])
        beside = block('block:2', [self.title])
        blocks = [caption, beside]
        boxer.caption_label_line_blocks([self.label, self.under, self.title, box], blocks)
        self.assertEqual(len(blocks), 2)


def classify(pages):
    with tempfile.TemporaryDirectory(dir=ROOT) as folder:
        for p in pages:
            Path(folder, f"page-{p['page']:02d}.json").write_text(json.dumps(p))
        boxer.main_text(folder, draw=False)
        return [json.loads(Path(folder, f"page-{p['page']:02d}.json").read_text()) for p in pages]


WORDS = ['amber', 'birch', 'cedar', 'delta', 'ember', 'fjord', 'grove', 'heath', 'inlet', 'juniper']


def body(prefix, x, top, n, width=240, size=10, page=1):
    return [run(f'{prefix}{j}', f'{WORDS[(j + page) % 10]} paragraph {page} line {j} {prefix} has several ordinary words and goes on',
                x, top + 14 * j, width=width, size=size) for j in range(n)]


class TwoColumnCaptionRule6(unittest.TestCase):
    """F16, boxer"""
    def pages(self, last_line='and the column ends with the'):
        out = []
        for i in (1, 2, 3):
            if i != 2:
                groups = [('left', body('l', 40, 60, 60, page=i)), ('right', body('r', 320, 60, 60, page=i))]
                els = [e for _, g in groups for e in g]
                out.append(dict(page=i, elements=els, blocks=[block(n, g) for n, g in groups], tables=[], floats=[],
                                art=[], unpaired=[], region_box_px=[0, 0, 600, 1000], reading_angle=0))
                continue
            image = dict(id='image:1', kind='image', box_px=[40, 60, 560, 300])
            cap = [run('c0', 'Fig. 2. An invented caption for the drawings above', 40, 312, width=240, size=8, font='ABCDEF+Serif-Bold'),
                   run('c1', 'with ordinary words in its middle line', 40, 323, width=240, size=8, font='ABCDEF+Serif-Bold'),
                   run('c2', last_line, 40, 334, width=240, size=8, font='ABCDEF+Serif-Bold')]
            tail = [run('t0', 'keepers walked at dusk across the', 320, 312, width=240, size=8, font='ABCDEF+Serif-Bold'),
                    run('t1', 'field to the last line.', 320, 323, width=150, size=8, font='ABCDEF+Serif-Bold')]
            left = body('l', 40, 380, 40, page=2)
            right = body('r', 320, 380, 40, page=2)
            groups = [('drawing', [image]), ('caption', cap), ('tail', tail), ('left', left), ('right', right)]
            els = [e for _, g in groups for e in g]
            out.append(dict(page=2, elements=els, blocks=[block(n, g) for n, g in groups], tables=[],
                            floats=[dict(id='float:1', box_px=[40, 60, 560, 300], caption=cap[0]['text'],
                                         blocks=['caption', 'drawing'])],
                            art=[], unpaired=[], region_box_px=[0, 0, 600, 1000], reading_angle=0))
        return out

    def test_second_column_of_an_open_caption_is_out_of_the_flow(self):
        blocks = {b['id']: b for b in classify(self.pages())[1]['main_text']['blocks']}
        self.assertEqual(blocks['tail']['cls'], 'other')
        self.assertIsNone(blocks['tail'].get('order'))

    def test_beside_a_closed_caption_rule_6_decides(self):
        blocks = {b['id']: b for b in classify(self.pages('and the column ends here.'))[1]['main_text']['blocks']}
        self.assertNotEqual(blocks['tail'].get('why'), "a figure caption's second column, beside a caption that ends open")


class TwoColumnCaptionCopier(unittest.TestCase):
    """F16, copier"""
    def setUp(self):
        def rows(left, texts, prefix, width=200):
            return [dict(id=f'{prefix}{i}', kind='text', text=t, angle=0, line=i, font='Caption', size_px=10,
                         run_size_px=10, box_px=[left, 110 + i * 14, left + width, 120 + i * 14]) for i, t in enumerate(texts)]
        self.left = rows(10, ['Fig. 2. An invented caption for the picture above it', 'several ordinary words in the middle',
                              'and the column ends with the'], 'l')
        self.right = rows(230, ['keepers at dusk.'], 'r', width=70)
        self.page = dict(elements=[dict(kind='image', box_px=[10, 0, 430, 100])] + self.left + self.right)

    def test_a_one_line_second_column_out_of_the_flow_joins(self):
        self.assertEqual(paper.caption_column_tail(self.page, self.left, [self.right], [self.right]), self.right)

    def test_a_one_line_column_wider_than_the_caption_column_does_not(self):
        self.right[0]['box_px'][2] = 230 + 260
        self.assertFalse(paper.caption_column_tail(self.page, self.left, [self.right], [self.right]))

    def test_ragged_caption_column_joins_at_the_page_gutter(self):
        for e in self.left:
            e['box_px'][2] = 150   # the caption's lines end far short of their column
        for e in self.right:
            e['box_px'][0] = 230; e['box_px'][2] = 360
        self.page['main_text'] = dict(columns=[[10, 215], [230, 430]])
        self.assertEqual(paper.caption_column_tail(self.page, self.left, [self.right], [self.right]), self.right)
        self.page['main_text'] = dict(columns=[[10, 430]])   # no page gutter there: the gap stays too wide
        self.assertFalse(paper.caption_column_tail(self.page, self.left, [self.right], [self.right]))


def fpage(n, elements, blocks, floats, columns):
    mt_blocks = [dict(id=b['id'], cls='main', order=k + 1) for k, b in enumerate(blocks) if b['id'].startswith('body')]
    return dict(page=n, elements=elements, blocks=blocks, floats=floats, unpaired=[], tables=[],
                main_text=dict(columns=columns, blocks=mt_blocks, furniture=[]))


class CaptionAtColumnFoot(unittest.TestCase):
    """F14 and F15"""
    def build(self, cap_size=8, cap_font='ABCDEF+Sans', next_size=8, next_font='ABCDEF+Sans', last='with the values of the',
              next_text='other operators drawn as a line.'):
        left = body('l', 40, 60, 40)                       # body to y 606
        image = dict(id='image:1', kind='image', box_px=[40, 620, 280, 940])
        cap = [run('c0', 'Figure 3. Invented record of the readings', 40, 950, width=240, size=cap_size, font=cap_font),
               run('c1', last, 40, 962, width=240, size=cap_size, font=cap_font)]
        cont = [run('n0', next_text, 320, 60, width=240, size=next_size, font=next_font),
                run('n1', 'second line of the same part', 320, 72, width=200, size=next_size, font=next_font)]
        right = body('r', 320, 110, 61)                    # body to y 950 + ... the column foot
        els = left + [image] + cap + cont + right
        blocks = [block('body-left', left), block('drawing', [image]), block('caption', cap), block('cont', cont),
                  block('body-right', right)]
        floats = [dict(id='float:1', caption=cap[0]['text'], blocks=['caption', 'drawing'], box_px=[40, 620, 280, 972])]
        p2 = fpage(2, els, blocks, floats, [[40, 280], [320, 560]])
        p1 = fpage(1, body('a', 40, 60, 65) + body('b', 320, 60, 65),
                   [block('body-a', body('a', 40, 60, 65)), block('body-b', body('b', 320, 60, 65))], [], [[40, 280], [320, 560]])
        return [p1, p2]

    def find(self, pages, body_size=10):
        paper._doubt_list().reset()
        return paper.caption_foot_continuations(pages, body_size), paper._doubt_list().items()

    def test_continuation_in_the_caption_type_is_the_captions(self):
        conts, doubts = self.find(self.build())
        self.assertEqual(conts, [(1, 'c0', 1, ['n0', 'n1'])])
        self.assertEqual(doubts, [])

    def test_next_column_in_the_body_type_ends_the_caption(self):
        conts, doubts = self.find(self.build(next_size=10, next_font='ABCDEF+Serif'))
        self.assertEqual(conts, [])
        self.assertEqual(doubts, [])

    def test_closed_last_line_does_not_continue(self):
        conts, doubts = self.find(self.build(last='with the values of the operators.'))
        self.assertEqual(conts, [])

    def test_a_label_at_the_next_column_top_is_a_wall(self):
        conts, doubts = self.find(self.build(next_text='Figure 4. Another invented caption'))
        self.assertEqual(conts, [])

    def test_caption_in_the_body_type_is_listed_as_doubtful(self):
        conts, doubts = self.find(self.build(cap_size=10, cap_font='ABCDEF+Serif', next_size=10, next_font='ABCDEF+Serif'))
        self.assertEqual(conts, [])
        self.assertEqual([(d['rule'], d['page'], d['reason']) for d in doubts],
                         [('F15', 2, 'caption_open_at_column_foot_in_body_type')])
        self.assertEqual(len(doubts[0]['options']), 2)

    def test_caption_with_space_under_it_does_not_reach_the_foot(self):
        pages = self.build()
        for e in pages[1]['elements']:
            if e['id'] in ('c0', 'c1'):
                e['box_px'][1] -= 200; e['box_px'][3] -= 200
        conts, doubts = self.find(pages)
        self.assertEqual(conts, [])

    def test_apply_moves_the_part_into_the_caption(self):
        paper.trace_reset()
        r0 = paper.trace_row(2, ['n0'], 'other operators drawn as a line.')
        r1 = paper.trace_row(2, ['n1'], 'second line of the same part')
        b0 = paper.trace_row(2, ['r0'], 'a body line')
        blocks = [dict(lines=[r0, r1, b0], lefts=[0, 0, 0], row_boxes=[[0, 0, 1, 1]] * 3, first=r0, meta=dict(lines=3, box_px=[0, 0, 1, 1]))]
        floats = [(0, 'figure', 'Fig. 3. Invented record', [], [], dict(caption_ids=['c0']))]
        per_page = [([], floats, []), (blocks, [], [])]
        pages = [dict(page=1), dict(page=2)]
        paper.apply_caption_continuations(pages, per_page, [(0, 'c0', 1, ['n0', 'n1'])])
        caption = per_page[0][1][0][2]
        self.assertEqual(str(caption), 'Fig. 3. Invented record\nother operators drawn as a line.\nsecond line of the same part')
        self.assertEqual(per_page[0][1][0][5]['caption_cont_runs'], [(2, 'n0'), (2, 'n1')])
        self.assertEqual([str(x) for x in per_page[1][0][0]['lines']], ['a body line'])

    def test_apply_leaves_a_part_it_cannot_find(self):
        paper.trace_reset()
        b0 = paper.trace_row(2, ['r0'], 'a body line')
        blocks = [dict(lines=[b0], meta=dict(lines=1))]
        floats = [(0, 'figure', 'Fig. 3. Invented record', [], [], dict(caption_ids=['c0']))]
        per_page = [([], floats, []), (blocks, [], [])]
        paper.apply_caption_continuations([dict(page=1), dict(page=2)], per_page, [(0, 'c0', 1, ['n0'])])
        self.assertEqual(str(per_page[0][1][0][2]), 'Fig. 3. Invented record')
        self.assertEqual(len(per_page[1][0]), 1)


if __name__ == '__main__':
    unittest.main()
