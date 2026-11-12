"""Paragraph/heading boundary regressions: /usr/bin/python3 -I tools/test_headings.py."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1] / 'copy_paper.py')
paper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paper)


def block(lines, emphasis=None, faces=None, tops=None, lefts=None):
    n = len(lines)
    tops = tops or [100 + 17 * i for i in range(n)]
    lefts = lefts or [0] * n
    boxes = [[x, y, 200, y + 9] for x, y in zip(lefts, tops)]
    return dict(lines=lines, first=lines[0], lefts=lefts, sizes=[10] * n,
                row_boxes=boxes, emphasis=emphasis or [False] * n,
                faces=faces or ['Text-Regular'] * n, prefixes=[0] * n,
                meta=dict(id='block', size_px=10, box_px=paper.hull(boxes)),
                page=2, page_height=800)


def headings(b):
    return [' '.join(p['lines']) for p in paper.paragraph_blocks(b, 10)
            if paper.is_heading(' '.join(p['lines']), p['meta'], 10, len(p['lines']))]


class HeadingBoundaries(unittest.TestCase):
    def test_italic_span_in_generously_spaced_sentence_stays_whole(self):
        b = block(['The organisms include', 'Alpha beta, Gamma delta',
                   'and Epsilon zeta', 'which increase the measured response.'],
                  [False, True, True, False],
                  ['Text-Regular', 'Text-Italic', 'Text-Italic', 'Text-Regular'])
        self.assertEqual(headings(b), [])
        self.assertEqual(len(paper.paragraph_blocks(b, 10)), 1)

    def test_sentence_veto_overrides_boxer_heading_class_and_size(self):
        b = block(['Alpha beta'], [True], ['Text-Italic'])
        b.update(heading_before='The organisms include', heading_after='which cause the response.')
        b['meta'].update(why='heading before main text in its column', size_px=14)
        self.assertEqual(headings(b), [])

    def test_complete_sentence_alone_is_not_a_paragraph_boundary(self):
        b = block(['A complete sentence.', 'An emphasized sentence fragment',
                   'Continues in the same paragraph.'], [False, True, False],
                  ['Text-Regular', 'Text-Bold', 'Text-Regular'])
        self.assertEqual(headings(b), [])

    def test_separate_italic_heading_has_white_bands(self):
        b = block(['Experimental design'], [True], ['Text-Italic'])
        b.update(heading_blank_above=18, heading_blank_below=18,
                 heading_before='The introduction ends.', heading_after='Samples were measured.')
        self.assertEqual(headings(b), ['Experimental design'])
        b['heading_blank_below'] = 1
        self.assertEqual(headings(b), [])

    def test_leading_heading_with_larger_gap(self):
        b = block(['Study design', 'Samples were selected', 'and measured.'],
                  [True, False, False], ['Text-Bold', 'Text-Regular', 'Text-Regular'],
                  tops=[100, 125, 142])
        self.assertEqual(headings(b), ['Study design'])

    def test_display_heading_before_small_doi_line(self):
        b = block(['A display heading', 'DOI: 10.0000/example',
                   'The explanatory paragraph starts here.'])
        b['sizes'] = [14, 8, 10]
        self.assertEqual(headings(b), ['A display heading'])

    def test_numbered_display_heading_keeps_indented_continuation_after_colon(self):
        b = block(['6. Delivery methods:', 'Growth factors'], lefts=[0, 12])
        b['sizes'] = [14, 14]
        self.assertEqual(headings(b), ['6. Delivery methods: Growth factors'])

    def test_heading_wrap_stops_before_body_new_number_or_changed_type(self):
        b = block(['6. Delivery methods:', 'Growth factors', 'Samples were collected.'],
                  tops=[100,117,145],lefts=[0,12,8])
        b['sizes']=[14,14,10]
        self.assertEqual(headings(b),['6. Delivery methods: Growth factors'])
        for key,value in [('faces',['Text-Regular','Text-Bold']),
                          ('sizes',[14,12]),('row_boxes',[[0,100,200,109],[12,140,200,149]])]:
            b=block(['6. Delivery methods:', 'Growth factors'],lefts=[0,12])
            b['sizes']=[14,14];b[key]=value
            self.assertEqual(headings(b),['6. Delivery methods:','Growth factors'])
        b=block(['6. Delivery methods:', '7. Next section'],lefts=[0,12]);b['sizes']=[14,14]
        self.assertEqual(headings(b),['6. Delivery methods:','7. Next section'])

    def test_smaller_indented_body_keeps_heading_when_superscripts_shrink_gap(self):
        b = block(['Measurement protocol', 'Samples were collected.', 'A following line.'],
                  tops=[100, 110, 127], lefts=[0, 8, 0])
        b['sizes'] = [12, 10, 10]
        self.assertEqual(headings(b), ['Measurement protocol'])

    def test_stacked_display_headings_before_indented_body(self):
        b = block(['RESULTS', 'Measurements', 'Samples were collected.'],
                  tops=[100, 125, 135], lefts=[0, 0, 8])
        b['sizes'] = [14, 12, 10]
        self.assertEqual(headings(b), ['RESULTS', 'Measurements'])

    def test_previous_heading_is_not_unfinished_prose(self):
        a = block(['Materials and methods'])
        a['sizes'] = [14]; a['meta']['size_px'] = 14
        b = block(['Experimental animals', 'mutants were studied.'], tops=[140, 150], lefts=[0, 8])
        b['sizes'] = [12, 10]
        paper.heading_context([([a, b], [], [])], 10)
        self.assertEqual(headings(b), ['Experimental animals'])

    def test_italic_leading_sentence_without_separate_band_is_not_a_heading(self):
        b = block(['AN EMPHASIZED FRAGMENT', 'continues as ordinary text.', 'A later sentence.'],
                  [True, False, False], ['Text-Italic', 'Text-Regular', 'Text-Regular'])
        b['heading_blank_above'] = 30
        self.assertEqual(headings(b), [])

    def test_bold_run_in_label_keeps_existing_split(self):
        b = block(['a. Clinical assessment Samples were measured.'], [False], ['Text-Regular'])
        b['prefixes'] = [len('a. Clinical assessment')]
        self.assertEqual(headings(b), ['a. Clinical assessment'])

    def test_capital_run_in_checks_its_prefix_not_the_whole_paragraph(self):
        b = block(['PARTICIPANTS', 'Samples were selected.', 'A later paragraph.'],
                  lefts=[0, 0, 8])
        parts = paper.paragraph_blocks(b, 10)
        self.assertTrue(parts[0]['meta']['leading_heading_candidate'])
        b.update(heading_before='The selected samples include')
        b['lines'][1] = 'the following observations.'
        self.assertFalse(paper.paragraph_blocks(b, 10)[0]['meta']['leading_heading_candidate'])

    def test_context_crosses_source_blocks(self):
        a = block(['The organisms include'])
        b = block(['Alpha beta'], [True], ['Text-Italic'], tops=[140])
        c = block(['which increase the response.'], tops=[180])
        paper.heading_context([([a, b, c], [], [])], 10)
        self.assertEqual(headings(b), [])

    def test_terminal_punctuation_and_closing_brackets_are_boundaries(self):
        for end in ('.', ':', '?', '!', ')', ']', '}', '.12'):
            with self.subTest(end=end):
                self.assertFalse(paper.heading_continuation('Earlier text' + end, 'lowercase text'))
        self.assertTrue(paper.heading_continuation('Earlier text,', 'lowercase text'))


if __name__ == '__main__':
    unittest.main()
