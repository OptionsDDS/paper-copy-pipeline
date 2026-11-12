"""Exporter polish: source evidence, discretionary breaks and top-float order."""
import importlib.util
from pathlib import Path
import unittest
import tempfile

spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1] / 'copy_paper.py')
copy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copy)


class Polish(unittest.TestCase):
    def test_native_white_fill_needs_white_background(self):
        # A minimal born-digital PDF: black text, white-on-white text, and
        # visible white text on a black panel. No external PDF library.
        stream = (b'BT /F1 12 Tf 30 170 Td (Visible) Tj ET\n'
                  b'1 g BT /F1 12 Tf 30 130 Td (Hidden) Tj ET\n'
                  b'0 g 25 80 110 25 re f\n'
                  b'1 g BT /F1 12 Tf 30 90 Td (Reversed) Tj ET\n')
        objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
                   b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
                   b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] '
                   b'/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
                   b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
                   b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'endstream']
        data = bytearray(b'%PDF-1.4\n'); offsets = [0]
        for i, obj in enumerate(objects, 1):
            offsets.append(len(data)); data.extend(f'{i} 0 obj\n'.encode()+obj+b'\nendobj\n')
        start = len(data)
        data.extend(b'xref\n0 6\n0000000000 65535 f \n')
        for offset in offsets[1:]: data.extend(f'{offset:010} 00000 n \n'.encode())
        data.extend(f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF\n'.encode())
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
            path = Path(temp)/'paint.pdf'; path.write_bytes(data)
            page = dict(page=1, region_box_px=[0, 0, 417, 417], _table_pdf=str(path), elements=[])
            chars = copy.table_characters(page)
            groups = {}
            for i, c in enumerate(chars): groups.setdefault(c['paint_order'][0], []).append(i)
            for k, ids in groups.items():
                cs = [chars[i] for i in ids]
                page['elements'].append(dict(id=str(k), kind='text', text=''.join(c['text'] for c in cs),
                                             char_ids=ids, _chars=cs))
            copy.omit_unpainted_text([page])
            self.assertEqual([r['text'] for r in page['elements']], ['Visible', '', 'Reversed'])

    def test_spaced_caption_digits_but_not_next_line_or_panel(self):
        self.assertEqual(copy.label_fix('F I G U R E 1 0 A, A finding'), 'Figure 10. A, A finding')
        self.assertEqual(copy.label_fix('TABLE 1 0 controls'), 'Table 1. 0 controls')
        self.assertEqual(copy.label_fix('F I G U R E 1\n2 groups'), 'Figure 1. \n2 groups')

    def test_discretionary_hyphen_inside_and_at_end_of_line(self):
        j = copy.Joiner(['The nonsurgical result; high-level review.'])
        self.assertEqual(j.lines(['ASSO\xad CIATED']), 'ASSOCIATED')
        self.assertEqual(j.lines(['Epstein-\xadBarr']), 'Epstein-Barr')
        self.assertEqual(j.lines(['non\xad', 'surgical']), 'nonsurgical')
        self.assertEqual(j.lines(['high-\xad', 'level']), 'high-level')
        self.assertEqual(j.lines(['frag\xad', 'ment']), 'fragment')

    def test_closed_word_beats_prefix_but_printed_compound_survives(self):
        for left, right in [('non', 'smokers'), ('non', 'surgical'), ('anti', 'microbial'), ('pre', 'term')]:
            with self.subTest(left=left, right=right):
                j = copy.Joiner([left+right])
                self.assertEqual(j.lines([left+'-', right]), left+right)
                both = copy.Joiner([left+right, left+'-'+right])
                self.assertEqual(both.lines([left+'-', right]), left+'-'+right)

    def test_unhyphenated_break_needs_lexical_evidence(self):
        j = copy.Joiner(['A microorganism grows. It lives in a micro ecosystem.'])
        self.assertEqual(j.lines(['microorg', 'anism']), 'microorganism')
        self.assertEqual(j.lines(['micro', 'ecosystem']), 'micro ecosystem')
        self.assertEqual(j.lines(['The e', 'Life. 2020;9:123.']), 'The eLife. 2020;9:123.')

    def test_omitting_source_positions_preserves_table_indices(self):
        cs = [dict(text=t) for t in 'ABCD']
        page = {'_table_chars': cs[:]}
        run = dict(id='r', text='AB CD', char_ids=[0, 1, 2, 3], _chars=cs)
        copy.omit_run_characters(page, run, [2, 3], 'invisible')
        self.assertEqual(run['text'], 'AB')
        self.assertEqual(run['char_ids'], [0, 1])
        self.assertEqual(len(page['_table_chars']), 4)
        self.assertEqual([c['text'] for c in page['_table_chars']], ['A', 'B', '', ''])

    def test_top_float_precedes_new_paragraph_but_follows_continuation(self):
        p = dict(page=2, elements=[], tables=[], region_box_px=[0, 0, 300, 500])
        f = dict(kind='figure', page=2, top=10, box=[0, 10, 100, 100], caption='Figure 1. A view', rows=[], notes=[])
        first = dict(kind='para', page=2, box=[0, 120, 100, 200], text='A new paragraph.')
        self.assertEqual(copy.arrange_floats([first, f], [p], []), [f, first])
        resumed = dict(kind='para', page=1, pages={1, 2}, box=[0, 400, 100, 500],
                       flow_parts=[(1, [0, 400, 100, 500]), (2, [0, 120, 100, 180])],
                       text='A paragraph completed across the page break.')
        first['box'] = [0, 220, 100, 300]
        self.assertEqual(copy.arrange_floats([resumed, first, f], [p], []), [resumed, f, first])

    def test_mid_column_float_retains_citation_anchor(self):
        p = dict(page=1, elements=[], tables=[], region_box_px=[0, 0, 300, 500])
        first = dict(kind='para', page=1, box=[0, 10, 100, 100], text='Earlier prose.')
        last = dict(kind='para', page=1, box=[0, 300, 100, 400], text='Figure 1 shows the result.')
        f = dict(kind='figure', page=1, top=150, box=[0, 150, 100, 250], caption='Figure 1. View', rows=[], notes=[])
        self.assertEqual(copy.arrange_floats([first, last, f], [p], []), [first, last, f])

    def test_top_float_waits_for_list_started_on_previous_page(self):
        p = dict(page=2, elements=[], tables=[], region_box_px=[0, 0, 300, 500])
        intro = dict(kind='para', page=1, text='The following data:')
        one = dict(kind='para', page=2, box=[0, 120, 100, 150], text='- First datum', list=True)
        two = dict(kind='para', page=2, box=[0, 160, 100, 190], text='- Second datum', list=True)
        after = dict(kind='para', page=2, box=[0, 210, 100, 250], text='Figure 1 shows the result.')
        f = dict(kind='figure', page=2, top=10, box=[0, 10, 100, 100], caption='Figure 1. View', rows=[], notes=[])
        self.assertEqual(copy.arrange_floats([intro, one, two, after, f], [p], []), [intro, one, two, f, after])


if __name__ == '__main__': unittest.main()
