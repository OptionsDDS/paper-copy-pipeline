"""Parsers, adversarial conservation, page proposals and end-to-end patching."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('agree', Path(__file__).with_name('agree.py'))
a = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = a
spec.loader.exec_module(a)


def grid(rows):
    return a.parse_html('<table>' + ''.join('<tr>' + ''.join('<td>' + c + '</td>' for c in row) + '</tr>' for row in rows) + '</table>')


class Parsers(unittest.TestCase):
    def test_html_span_ownership_and_physical_count(self):
        g = a.parse_html('<table><thead><tr><th rowspan="2">Label</th><th colspan="2">Measures</th></tr>'
                         '<tr><th>A</th><th>B</th></tr></thead><tr><td>X</td><td>1</td><td>2</td></tr></table>')
        self.assertEqual(g.expanded(), [['Label', 'Measures', 'Measures'], ['Label', 'A', 'B'], ['X', '1', '2']])
        self.assertEqual(a.bag(g.text())['Measures'], 1)
        self.assertEqual(g.headers, 2)
        self.assertIn('| --- | --- | --- |', g.markdown())

    def test_inline_tags_do_not_split_words(self):
        g = a.parse_html('<table><tr><td>pre<i>fix</i><sup>2</sup></td><td>A<br>B &amp; C</td></tr></table>')
        self.assertEqual(g.expanded(), [['prefix2', 'A B & C']])

    def test_markdown_escapes_and_dash(self):
        g = a.parse_markdown('| Name | Value |\n| --- | --- |\n| a\\|b | −1 |')
        self.assertEqual(g.expanded()[1], ['a|b', '-1'])
        self.assertEqual(a.parse_markdown(g.markdown()).signature(), g.signature())

    def test_otsl_spans(self):
        g = a.parse_otsl('<otsl><ched>Label<ched>Measures<lcel><nl><fcel>X<fcel>1<fcel>2<nl></otsl>')
        self.assertEqual(g.expanded(), [['Label', 'Measures', 'Measures'], ['X', '1', '2']])
        g = a.parse_otsl('<fcel>A<lcel><fcel>B<nl><ucel><xcel><fcel>C<nl>')
        self.assertEqual(g.cells[0].rowspan, 2)

    def test_bad_html_and_otsl_abstain(self):
        for text in ['<table><tr><td>A</td><td>B</td>',
                     '<table><tr><td>A<td>B</tr></table>',
                     '<table><tr><td rowspan="3">A</td><td>B</td></tr></table>',
                     '<table><tr><td>A</td><td><img src="x"></td></tr></table>',
                     '<table><tr><td>A</td><td>B</td></tr><tr><td>C</td></tr></table>']:
            with self.assertRaises(ValueError, msg=text): a.parse_html(text)
        for text in ['<lcel><fcel>B<nl>', '<fcel>A<lcel><nl><ucel><fcel>B<nl>', '<fcel>A<ecel>B<nl>']:
            with self.assertRaises(ValueError, msg=text): a.parse_otsl(text)


class Acceptance(unittest.TestCase):
    def setUp(self):
        self.rows = [['Name', 'Value'], ['A', '1'], ['B', '2']]
        self.good = grid(self.rows)
        self.printed = ['Name Value', 'A 1', 'B 2']

    def test_exact_accepts_and_nfkc_is_typographic(self):
        self.assertTrue(a.accept_grid(self.good, self.good, self.printed)[0])
        self.assertEqual(a.normalise('ﬁeld\u00a0− ２'), 'field - 2')
        self.assertNotEqual(a.normalise('A'), a.normalise('a'))

    def test_value_missing_one_reader(self):
        self.assertFalse(a.accept_grid(self.good, grid(self.rows[:2]), self.printed)[0])

    def test_corrected_typo_in_both_readers(self):
        self.assertFalse(a.accept_grid(self.good, self.good, ['Nmae Value', 'A 1', 'B 2'])[0])

    def test_merged_row_and_extra_column(self):
        for bad in [[self.rows[0], ['A B', '1 2']], [['Name', 'Value', 'Extra'], ['A', '1', '3'], ['B', '2', '4']]]:
            self.assertFalse(a.accept_grid(self.good, grid(bad), self.printed)[0])
        with self.assertRaises(ValueError): grid([row + [''] for row in self.rows])

    def test_dropped_stacked_value_by_both(self):
        self.assertFalse(a.accept_grid(self.good, self.good, ['Name Value', 'A 1 3', 'B 2'])[0])

    def test_sign_decimal_and_multiplicity(self):
        for printed in [['Name Value', 'A -1', 'B 2'], ['Name Value', 'A 0.1', 'B 2'],
                        ['Name Value', 'A 1', 'B 2 2']]:
            self.assertFalse(a.accept_grid(self.good, self.good, printed)[0])
        self.assertNotEqual(a.bag('11'), a.bag('1 1'))

    def test_span_and_repeated_literal_are_different(self):
        span = a.parse_html('<table><tr><td colspan="2">H</td></tr><tr><td>A</td><td>1</td></tr></table>')
        repeated = grid([['H', 'H'], ['A', '1']])
        self.assertFalse(a.accept_grid(span, repeated, ['H', 'A 1'])[0])

    def test_cells_keep_printed_characters(self):
        g = grid([['Range', 'Area'], ['8-50', 'm2'], ['-0.5', '10 5']])
        printed = ['Range Area', '8–50 m²', '−0.5 10 5']
        self.assertTrue(a.accept_grid(g, g, printed)[0])
        self.assertEqual(a.printed_cells(g, printed), ['Range', 'Area', '8–50', 'm²', '−0.5', '10 5'])
        self.assertIn('| 8–50 | m² |', g.markdown(a.printed_cells(g, printed)))
        # Without an unused printed token of the same value nothing is invented.
        self.assertIsNone(a.printed_cells(g, ['Range Area', '8–50 m²', '−0.5 10']))

    def test_ambiguous_match_abstains(self):
        c = a.Candidate(self.good, 'Table 1. Test')
        self.assertIsNone(a.select_candidate([c, c], 'Table 1. Test', self.printed)[0])

    def test_correlated_caption_in_grid_abstains(self):
        for text in ['Table 1. Caption', 'Table 1Caption']:
            g = grid([[text, ''], ['A', '1']])
            self.assertFalse(a.accept_grid(g, g, ['Table 1. Caption', 'A 1'])[0])

    def test_source_notes_are_not_arbitrary_unmatched_values(self):
        candidate = a.Candidate(self.good, end=0)
        for tail in (['3'], ['C 3'], ['*A missing value 3']):
            core, notes = a.source_partition(self.good, self.printed + tail,
                [candidate, candidate], [('Other prose', {}, ''), ('Other prose', {}, '')])
            self.assertEqual(notes, [])
            self.assertFalse(a.accept_grid(self.good, self.good, core)[0])
        core, notes = a.source_partition(self.good, self.printed + ['Note: measured values.'],
            [candidate, candidate], [('Note: measured values.', {}, '')] * 2)
        self.assertEqual(core, self.printed)
        self.assertEqual(notes, ['Note: measured values.'])

    def test_row_headers_do_not_move_separator_to_bottom(self):
        g = a.parse_html('<table><tr><th>Name</th><th>Value</th></tr><tr><th>A</th><td>1</td></tr></table>')
        self.assertEqual(g.headers, 1)

    def test_formula_order_and_unknown_commands(self):
        self.assertTrue(a.ordered_characters('a2+b2c', r'\frac{a^2+b^2}{c}'))
        self.assertFalse(a.ordered_characters('a2+b2c', r'\frac{b^2+a^2}{c}'))
        self.assertFalse(a.ordered_characters('a2+b2c', r'\frac{a^2+b^2}{c}+1'))
        with self.assertRaises(ValueError): a.latex_characters(r'\unknown{x}')
        with self.assertRaises(ValueError): a.latex_characters(r'\frac{a+b}{2')

    def test_page_agreement_is_ordered(self):
        self.assertEqual(a.word_agreement('one two three', 'three two one'), 1/3)
        self.assertEqual(a.word_agreement('', ''), 0)
        self.assertEqual(a.formula_key(r'N=\left[x\right]^{2}'), a.formula_key(r'N=[x]^2'))

    def test_full_page_restores_furniture_without_discarding_text(self):
        info = {'blocks': [{'type': 'header', 'task': 'text', 'content': 'Journal'},
                           {'type': 'text', 'task': 'text', 'content': 'Body'},
                           {'type': 'page_number', 'task': 'text', 'content': '7'}]}
        self.assertEqual(a.full_page('Body', info), 'Journal\n\nBody\n\n7\n')
        self.assertEqual(a.word_agreement(a.full_page('Body', info), 'Journal Body 7'), 1)


class Integration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.copy = self.root / 'paper'; self.copy.mkdir()
        self.pdf = self.root / 'paper.pdf'; self.pdf.write_bytes(b'pdf fixture')
        self.readers = self.root / 'readers'
        self.md = '**Table 1. Measurements**\n\n[table structure not recovered: 3 printed lines follow as printed, left to right, top to bottom]\n\n- Name Value\n- A 1\n- B 2\n\nOriginal note stays.\n\nBody stays.\n<!-- end of page 1 -->\n'
        (self.copy / 'copy.md').write_text(self.md)
        self.reader_text = 'Table 1. Measurements\n\n' + '<table><tr><td>Name</td><td>Value</td></tr><tr><td>A</td><td>1</td></tr><tr><td>B</td><td>2</td></tr></table>'
        self.read(self.reader_text)

    def read(self, text):
        for model in a.MODELS:
            d = self.readers / model; d.mkdir(parents=True, exist_ok=True)
            (d / 'p001.md').write_text(text)
            (d / 'p001.json').write_text('{"finish_reason": "stop"}')

    def test_gate_repair_preserves_neighbors_and_is_idempotent(self):
        log = a.process(self.copy, self.readers, self.pdf)
        self.assertEqual(log['applied_edits'], 1)
        new = (self.copy / 'copy.md').read_text()
        self.assertIn('| A | 1 |', new)
        self.assertTrue(new.endswith('Original note stays.\n\nBody stays.\n<!-- end of page 1 -->\n'))
        self.assertEqual((self.copy / 'copy.agree-before.md').read_text(), self.md)
        self.assertEqual(a.process(self.copy, self.readers, self.pdf), log)

    def test_missing_reader_or_truncation_is_non_destructive(self):
        (self.readers / a.MODELS[0] / 'p001.json').write_text('{"finish_reason":"length"}')
        log = a.process(self.copy, self.readers, self.pdf)
        self.assertEqual(log['applied_edits'], 0)
        self.assertEqual((self.copy / 'copy.md').read_text(), self.md)

    def test_grid_without_printed_evidence_is_not_its_own_witness(self):
        (self.copy / 'copy.md').write_text('**Table 1. Measurements**\n\n| Name | Value |\n| A | 1 |\n<!-- end of page 1 -->')
        self.assertEqual(a.process(self.copy, self.readers, self.pdf)['applied_edits'], 0)

    def test_scan_proposal_never_applies_and_requires_flag(self):
        original = 'Document kind: scanned document with an OCR text layer\n<!-- page 1 -->\nBad text\n'
        (self.copy / 'copy.md').write_text(original)
        (self.copy / 'copy.readers-check.json').write_text(json.dumps({'pages': [{'page': 1, 'reason': 'interleaved'}]}))
        log = a.process(self.copy, self.readers, self.pdf)
        self.assertEqual(log['applied_edits'], 0)
        self.assertTrue(log['pages'][0]['accepted'])
        self.assertEqual((self.copy / 'copy.md').read_text(), original)
        self.assertEqual(len(json.loads((self.copy / 'copy.readers-page.json').read_text())['proposals']), 1)

    def test_unflagged_scan_is_not_offered(self):
        (self.copy / 'copy.md').write_text('Document kind: scanned document with an OCR text layer\n<!-- page 1 -->\nText\n')
        log = a.process(self.copy, self.readers, self.pdf)
        self.assertEqual(log['pages'], [])

    def test_flagged_formula_applies_with_real_source_order(self):
        original = 'Value: [formula: (a+b)/(2) inside an unread symbol; see PDF as printed]\n<!-- end of page 1 -->'
        (self.copy / 'copy.md').write_text(original)
        self.read(r'Value: $\frac{a+b}{2}$')
        with patch.object(a.subprocess, 'run', return_value=type('Result', (), {'stdout': 'Value: a+b 2'})()):
            log = a.process(self.copy, self.readers, self.pdf)
        self.assertEqual(log['applied_edits'], 1)
        self.assertIn(r'$\frac{a+b}{2}$', (self.copy / 'copy.md').read_text())

    def test_preserve_note_tail_below_gate(self):
        original = self.md.replace('3 printed', '4 printed').replace('- B 2\n', '- B 2\n- Note: measured values.\n')
        (self.copy / 'copy.md').write_text(original)
        self.read(self.reader_text + '\n\nNote: measured values.')
        log = a.process(self.copy, self.readers, self.pdf)
        self.assertEqual(log['applied_edits'], 1)
        self.assertEqual((self.copy / 'copy.md').read_text().count('Note: measured values.'), 1)


class NeededPages(unittest.TestCase):
    """Readers run only where an accepted agreement could change the copy."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.tmp.cleanup)
        self.copy = Path(self.tmp.name)

    def needed(self, text, check=None):
        (self.copy / 'copy.md').write_text(text)
        if check is not None:
            (self.copy / 'copy.readers-check.json').write_text(json.dumps(check))
        return a.needed_pages(self.copy)

    GATE = ('<!-- page 2 -->\n**Table 1. Gated**\n\n[table structure not recovered: 1 printed lines follow as printed, '
            'left to right, top to bottom]\n\n- A 1\n<!-- end of page 2 -->\n')
    GRID = '<!-- page 3 -->\n**Table 2. Grid**\n\n| A | 1 |\n| --- | --- |\n| B | 2 |\n<!-- end of page 3 -->\n'

    def test_gated_table_and_formula_pages(self):
        pages = self.needed(self.GATE + self.GRID + '<!-- page 4 -->\nx [formula: a+b inside an unread symbol] y\n<!-- end of page 4 -->\n')
        self.assertEqual(sorted(pages), [2, 4])
        self.assertIn('gated table', pages[2][0])

    def test_confident_grid_needs_no_reader(self):
        self.assertEqual(self.needed(self.GRID + '\n## Places the program is not sure of\n- none\n'), {})

    def test_grid_named_uncertain_or_float_checked(self):
        named = self.GRID + '\n## Places the program is not sure of\n- page 3: Table 2: its rows could not be read (table, layout uncertain)\n'
        # Without printed source lines (the sidecar) a grid cannot be checked: no reader.
        self.assertEqual(self.needed(named), {})
        (self.copy / 'copy.tables.json').write_text(json.dumps({'tables': [
            {'page': 3, 'caption': 'Table 2. Grid', 'printed_lines': ['A 1', 'B 2']}]}))
        self.assertEqual(sorted(self.needed(named)), [3])
        checked = self.GRID.replace('<!-- end of page 3 -->', '\n[Float check: Table 2, page 3: 1 objects cross the region edge; see copy.floats.json.]\n<!-- end of page 3 -->')
        self.assertEqual(sorted(self.needed(checked)), [3])
        # A body sentence citing the table in the uncertainty list is not a table item.
        cited = self.GRID + '\n## Places the program is not sure of\n- page 3: source token occurrence(s) not verified (run:4): "(Table 2) had"\n'
        self.assertEqual(self.needed(cited), {})

    def test_scan_only_flagged_pages(self):
        scan = 'Document kind: scanned document with an OCR text layer\n' + self.GATE
        self.assertEqual(self.needed(scan), {})
        self.assertEqual(sorted(self.needed(scan, {'pages': [{'page': 5, 'reason': 'garbled'}]})), [5])

    def test_cli_lists_pages_and_records_reasons(self):
        (self.copy / 'copy.md').write_text(self.GATE)
        from io import StringIO
        with patch('sys.stdout', new=StringIO()) as out:
            self.assertEqual(a.main(['--needed', str(self.copy)]), 0)
        self.assertEqual(out.getvalue().strip(), '2')
        record = json.loads((self.copy / 'copy.readers-needed.json').read_text())
        self.assertEqual(list(record['pages']), ['2'])


class Restatement(unittest.TestCase):
    """A replaced table's doubt items are restated; the trace keeps every unit."""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1])
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.copy = self.root / 'paper'; self.copy.mkdir()
        self.pdf = self.root / 'paper.pdf'; self.pdf.write_bytes(b'pdf fixture')
        self.readers = self.root / 'readers'
        self.gate = ('**Table 1. Measurements**\n\n[table structure not recovered: 3 printed lines follow as printed, '
                     'left to right, top to bottom]\n\n- Name Value\n- A 1\n- B 2\n')
        self.md = ('<!-- page 1 -->\nBody before.\n\n' + self.gate + '\nBody after.\n<!-- end of page 1 -->\n\n'
                   '## Places the program is not sure of\n- page 1: Table 1: its rows could not be read (table, layout uncertain)\n'
                   '- page 1: Table 1. Measurements: table structure not recovered (row_count); printed lines retained\n'
                   '- page 1: source token occurrence(s) not verified (run:4): "(Table 1) shows"\n')
        (self.copy / 'copy.md').write_text(self.md)
        for model in a.MODELS:
            d = self.readers / model; d.mkdir(parents=True)
            (d / 'p001.md').write_text('Table 1. Measurements\n\n<table><tr><td>Name</td><td>Value</td></tr>'
                                       '<tr><td>A</td><td>1</td></tr><tr><td>B</td><td>2</td></tr></table>')
            (d / 'p001.json').write_text('{"finish_reason": "stop"}')

    def test_items_restated_once_and_output_span_recorded(self):
        log = a.process(self.copy, self.readers, self.pdf)
        new = (self.copy / 'copy.md').read_text()
        event = log['tables'][0]
        self.assertTrue(event['accepted'])
        self.assertTrue(new[event['output_start']:event['output_end']].startswith('| Name | Value |'))
        self.assertTrue(new[event['output_start']:event['output_end']].endswith('checked against the PDF text\n'))
        notes = new.split('## Places the program is not sure of')[1]
        self.assertEqual(notes.count('Table 1'), 2)  # the restatement and the cited body sentence
        self.assertIn('Table 1. Measurements: rows and columns read with two local page readers', notes)
        self.assertNotIn('could not be read', notes)
        self.assertEqual(len(event['uncertainty_items']), 2)

    def test_trace_gives_replaced_units_the_replacement_span(self):
        spec = importlib.util.spec_from_file_location('_trace', Path(__file__).with_name('copy_trace.py'))
        t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
        body = self.md
        lines = ['Body before.', '[table structure not recovered', '- Name Value', '- A 1', '- B 2', 'Body after.']
        spans = {}
        for k, value in enumerate(lines):
            at = body.index(value); end = body.index('\n', at)
            spans[k] = [at, end]
        a.process(self.copy, self.readers, self.pdf)
        final = (self.copy / 'copy.md').read_text()
        mapped, _, _ = t.map_spans(body, spans, final)
        self.assertEqual([k for k, v in mapped.items() if v is None], [1, 2, 3, 4])
        unit_spans = [mapped[k] for k in range(len(lines))]
        members = t.reader_replacements(self.copy, final, body, spans, unit_spans)
        self.assertEqual(sorted(members), [1, 2, 3, 4])
        event = json.loads((self.copy / 'copy.agree.json').read_text())['tables'][0]
        self.assertEqual(unit_spans[1], [event['output_start'], event['output_end']])
        self.assertTrue(all(unit_spans[k] == [event['output_end']] * 2 for k in (2, 3, 4)))
        self.assertEqual(final[slice(*unit_spans[5])], 'Body after.')
        # A copy that is not the agreement's output keeps its spans unresolved.
        unit_spans = [mapped[k] for k in range(len(lines))]
        self.assertEqual(t.reader_replacements(self.copy, final + 'x', body, spans, unit_spans), {})
        self.assertIsNone(unit_spans[1])


if __name__ == '__main__':
    unittest.main()
