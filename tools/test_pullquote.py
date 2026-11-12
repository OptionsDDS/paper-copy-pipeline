"""Lane r3-pullquote: display-face pieces keep their own line (framed, or at their own pitch), framed pull
quotes, and a side abstract printed only under a front-page Abstract/Summary heading. (The seal-lettering
and rotated-majority tests left with the badge work for the future seal lane, 2026-11-11.)
Synthetic geometry only; no paper's text."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result
b = module('boxer_pullquote', 'standalone/element_boxer_sc.py')
c = module('copy_pullquote', 'copy_paper.py')

SIZE = 20.0
def word(text, u, vb, font, adv=10.0):
    out = []
    for ch in text:
        out.append(dict(text=ch, u0=u, u1=u + adv - 1, v0=vb - SIZE * .7, v1=vb, vb=vb, size=SIZE, font=font))
        u += adv
    return out, u

def line(pieces, vb):
    """pieces: (text, font, gap before) -> one clustered line"""
    chars, u = [], 40.0
    for text, font, gap in pieces:
        u += gap
        for i, w in enumerate(text.split()):
            cs, u = word(w, u, vb[font] if isinstance(vb, dict) else vb, font)
            chars += cs; u += 5.0   # word space 0.25 em
        u -= 5.0
    return dict(vb=min(c['vb'] for c in chars), size=SIZE, chars=chars)

def to_read(x0, y0, x1, y1): return (x0, y0, x1, y1)
QUOTE, BODY = 'Display-Heavy', 'Text-Roman'


class DisplayPieces(unittest.TestCase):
    def quote_lines(self, quote_pitch, body_pitch, n=6, gap=13.0):
        return [line([('quote words', QUOTE, 0), ('body text runs on here', BODY, gap)],
                     {QUOTE: 100 + quote_pitch * i, BODY: 100 + body_pitch * i}) for i in range(n)]

    def split(self, lines, objs=()):
        out = b.split_display_face_lines([dict(ln, chars=list(ln['chars'])) for ln in lines], list(objs), to_read)
        return [{ch['font'] for ch in ln['chars']} for ln in out]

    def test_framed_by_rule_pair_is_its_own_line(self):
        lines = self.quote_lines(25, 25)
        # rules above and below the quote, as wide as it, stopping short of the body text
        rules = [dict(kind='rule', box_px=[38, 60, 152, 61]), dict(kind='rule', box_px=[38, 260, 152, 261])]
        faces = self.split(lines, rules)
        self.assertEqual(len(faces), 12)
        self.assertTrue(all(len(f) == 1 for f in faces))

    def test_framed_by_own_fill_is_its_own_line(self):
        faces = self.split(self.quote_lines(25, 25), [dict(kind='fill', box_px=[36, 70, 152, 250])])
        self.assertTrue(all(len(f) == 1 for f in faces))

    def test_own_pitch_without_frame_is_its_own_line(self):
        # quote at 29 px beside body at 25 px: the offset drifts by 4 px a line
        lines = self.quote_lines(29 * .5 + 25 * .5, 25, n=4)   # 2 px drift a line, 6 px over the stack
        faces = self.split(lines)
        # the first quote line stands on the body line's own baseline: it stays (an inline word there)
        self.assertEqual(sorted(len(f) for f in faces), [1, 1, 1, 1, 1, 1, 2])

    def test_same_pitch_without_frame_stays(self):
        faces = self.split(self.quote_lines(25, 25))
        self.assertTrue(all(len(f) == 2 for f in faces))

    def test_rule_pair_reaching_over_the_body_is_no_frame(self):
        rules = [dict(kind='rule', box_px=[38, 60, 400, 61]), dict(kind='rule', box_px=[38, 260, 400, 261])]
        faces = self.split(self.quote_lines(25, 25), rules)
        self.assertTrue(all(len(f) == 2 for f in faces))

    def test_run_in_label_at_word_space_stays(self):
        # a bold run-in label followed by its paragraph at a word space, even inside a framed box
        lines = [line([('Methods.', QUOTE, 0), ('the text of the paragraph', BODY, 5.0)], 100 + 25 * i) for i in range(3)]
        rules = [dict(kind='rule', box_px=[38, 60, 400, 61]), dict(kind='rule', box_px=[38, 200, 400, 201])]
        faces = self.split(lines, rules)
        self.assertTrue(all(len(f) == 2 for f in faces))

    def test_framed_piece_between_two_body_texts(self):
        # body text, a framed quote at the column's gutter side, then the next column's body (far, own run)
        lines = [line([('body text here', BODY, 0), ('quote words', QUOTE, 13.0), ('next column text', BODY, 40.0)], 100 + 25 * i)
                 for i in range(3)]
        start = 40 + 14 * 10 - 5 + 13   # the quote's first letter
        faces = self.split(lines, [dict(kind='fill', box_px=[start - 4, 70, start + 112, 190])])
        self.assertEqual(sorted(len(f) for f in faces), [1, 1, 1, 1, 1, 1])

    def test_run_in_names_beside_a_column_at_another_pitch_stay(self):
        # author notes: a bold-italic name, a wide justified space, its italic sentence on the same baseline;
        # the next column's body text (far, own run) at another pitch drifts against the note lines
        lines = [line([('Ida Moor PhD', QUOTE, 0), ('is a professor at', 'Text-Italic', 13.0), ('next column text', BODY, 40.0)],
                      {QUOTE: 100 + 20 * i, 'Text-Italic': 100 + 20 * i, BODY: 100 + 23 * i}) for i in range(4)]
        faces = self.split(lines)
        self.assertTrue(all(len(f) == 3 for f in faces))

    def test_italic_journal_names_in_references_stay(self):
        # J Periodontol-style references: roman authors and title, an italic journal name at a wide
        # justified space, roman volume and pages on the same baseline; the next column runs at another pitch
        lines = []
        for i in range(5):
            lead = 'author title words' + ' xx' * (i % 3)
            ln = line([(lead, BODY, 0), ('J Shore Dent', 'Text-Italic', 13.0), ('2002;73:1231', BODY, 13.0),
                       ('the next column text runs on here with many more words than the note', 'Text-Sans', 40.0)], 100 + 22 * i)
            for ch in ln['chars']:   # the next column, set in the same roman face, at its own pitch
                if ch['font'] == 'Text-Sans': ch['font'] = BODY; ch['vb'] = 100 + 25 * i
            lines.append(ln)
        faces = self.split(lines)
        self.assertEqual(len(faces), 5)

    def test_single_letter_stays(self):
        lines = [line([('A', QUOTE, 0), ('body text runs on here', BODY, 13.0)], 100)]
        faces = self.split(lines, [dict(kind='fill', box_px=[36, 70, 52, 110])])
        self.assertEqual(faces, [{QUOTE, BODY}])


def trun(rid, x0, y, x1, font, line, size=20.0):
    return dict(id=rid, kind='text', text='words here', box_px=[x0, y, x1, y + size], font=font,
                font_spans=[dict(font=font, start=0, end=10)], line=line, angle=0, size_px=size, run_size_px=size)


class PullQuoteGroups(unittest.TestCase):
    def page(self, quote_font, quote_x=50, body_gap=30, columns=1):
        quote = [trun('q%d' % i, quote_x, 300 + 29 * i, quote_x + 150, quote_font, 100 + i) for i in range(5)]
        if columns == 1:   # the quote at the left of one column; the column's lines above and below run full width
            body = [trun('b%d' % i, quote_x + 150 + body_gap, 290 + 25 * i, 630, BODY, i) for i in range(8)]
            body += [trun('a', quote_x, 240, 630, BODY, 50), trun('z', quote_x, 470, 630, BODY, 51)]
        else:              # straddling the gutter between columns [0, 380] and [400, 760]; both narrow beside it
            body = [trun('b%d' % i, quote_x + 150 + body_gap, 290 + 25 * i, 760, BODY, i) for i in range(8)]
            body += [trun('l%d' % i, 0, 290 + 25 * i, quote_x - body_gap, BODY, i) for i in range(8)]
            body += [trun('a', 0, 240, 380, BODY, 50), trun('z', 400, 470, 760, BODY, 51)]
        return quote + body

    def groups(self, runs, drawn):
        return [sorted(g) for g in b.pull_quote_groups(runs, drawn, BODY)]

    def test_framed_display_lines_beside_body_are_a_pull_quote(self):
        runs = self.page(QUOTE)
        rules = [dict(kind='rule', box_px=[46, 280, 204, 281]), dict(kind='rule', box_px=[46, 450, 204, 451])]
        self.assertEqual(self.groups(runs, rules), [['q0', 'q1', 'q2', 'q3', 'q4']])
        self.assertEqual(self.groups(runs, [dict(kind='fill', box_px=[44, 290, 206, 450])]), [['q0', 'q1', 'q2', 'q3', 'q4']])

    def test_straddling_quote_beside_is_measured_from_the_frame(self):
        # quote lines centred between two columns, the runaround text 46 px (2.3 em) from the widest line but
        # within 2 em of the rule pair's ends
        runs = self.page(QUOTE, quote_x=300, body_gap=46, columns=2)
        rules = [dict(kind='rule', box_px=[290, 280, 460, 281]), dict(kind='rule', box_px=[290, 450, 460, 451])]
        self.assertEqual(self.groups(runs, rules), [['q0', 'q1', 'q2', 'q3', 'q4']])

    def test_column_heading_crossing_the_frame_does_not_block(self):
        # the right column's heading starts inside the frame's width and runs past its edge
        runs = self.page(QUOTE, quote_x=300, body_gap=46, columns=2)
        runs.append(trun('h', 420, 430, 640, 'Text-Sans-Bold', 300))
        rules = [dict(kind='rule', box_px=[290, 280, 460, 281]), dict(kind='rule', box_px=[290, 455, 460, 456])]
        self.assertEqual(self.groups(runs, rules), [['q0', 'q1', 'q2', 'q3', 'q4']])

    def test_smaller_boxed_notice_is_no_pull_quote(self):
        runs = self.page(QUOTE)
        for e in runs:
            if e['id'].startswith('q'): e['size_px'] = e['run_size_px'] = 14.0
        self.assertEqual(self.groups(runs, [dict(kind='fill', box_px=[44, 290, 206, 450])]), [])

    def test_panel_filling_its_column_is_no_pull_quote(self):
        # a Clinical Relevance panel between rules fills the left column [50, 296]; the right column's text
        # stands 37 px away across the gutter and never reaches over the panel
        panel = [trun('p%d' % i, 50, 300 + 25 * i, 296, QUOTE, 100 + i) for i in range(5)]
        left = [trun('a', 50, 250, 296, BODY, 50), trun('z', 50, 450, 296, BODY, 51)]
        right = [trun('r%d' % i, 333, 240 + 25 * i, 580, BODY, i) for i in range(12)]
        rules = [dict(kind='rule', box_px=[50, 285, 296, 286]), dict(kind='rule', box_px=[50, 425, 296, 426])]
        self.assertEqual(self.groups(panel + left + right, rules), [])

    def test_panel_of_several_sentences_with_runaround_is_no_pull_quote(self):
        # an abstract panel (or a wrapped key-points box) with the column running round it: same geometry as a
        # pull quote, but its text holds several sentences
        runs = self.page(QUOTE)
        for i, e in enumerate(r for r in runs if r['id'].startswith('q')):
            e['text'] = 'the survey ran. Counts rose' if i == 2 else 'words of the panel'
        self.assertEqual(self.groups(runs, [dict(kind='fill', box_px=[44, 290, 206, 450])]), [])

    def test_body_face_box_is_no_pull_quote(self):
        self.assertEqual(self.groups(self.page(BODY), [dict(kind='fill', box_px=[44, 290, 206, 450])]), [])

    def test_unframed_or_alone_is_no_pull_quote(self):
        runs = self.page(QUOTE)
        self.assertEqual(self.groups(runs, []), [])
        alone = [e for e in runs if e['id'].startswith('q')]
        self.assertEqual(self.groups(alone, [dict(kind='fill', box_px=[44, 290, 206, 450])]), [])


class SideAbstractHeading(unittest.TestCase):
    def test_later_summary_section_does_not_take_the_abstract(self):
        items = [dict(kind='para', text='x', page=1), dict(kind='heading', text='SUMMARY', page=4)]
        self.assertIsNone(c.side_abstract_heading(items, 1))

    def test_front_page_abstract_heading_takes_it(self):
        items = [dict(kind='heading', text='Abstract', page=1), dict(kind='heading', text='Summary', page=4)]
        self.assertEqual(c.side_abstract_heading(items, 1), 0)

    def test_front_page_after_a_cover_sheet(self):
        items = [dict(kind='heading', text='SUMMARY', page=3)]
        self.assertEqual(c.side_abstract_heading(items, 3), 0)


if __name__ == '__main__':
    unittest.main()
