"""Keyless D-555/D-573 reference-system port checks; run with python3 -I."""
import importlib.util
import copy
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1] / 'copy_paper.py')
paper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paper)


def rows(values, page=1, column=0, x=100, edge=100, start=0):
    return [dict(ref=(page, start+i), text=f'{v}. Author AB. Title.' if isinstance(v, int) else v,
                 page=page, column=column, x=x, column_left_px=edge,
                 column_witness=dict(page=page, column=column)) for i, v in enumerate(values)]


class ReferenceSystems(unittest.TestCase):
    def test_adapter_flags_without_rewriting_or_renumbering(self):
        items = []
        for i, text in enumerate(['1. Author AB. First.', '2. Author CD. Second.',
                                  'Author EF. Missing label.', '4. Author GH. Last.']):
            items.append(dict(kind='ref', text=text, page=1, reference_sources=[dict(
                x=100, page=1, column=0, column_left_px=100, column_witness=[100, 400], bounds=[100, 100])]))
        before = [it['text'] for it in items]; warnings = []
        report = paper.check_reference_systems(items, warnings)
        self.assertEqual([it['text'] for it in items], before)
        self.assertTrue(any(f['reason'] == 'inferred from sequence' and f['expected'] == 3
                            for s in report['sections'] for f in s['flags']))
        self.assertTrue(any('printed text retained' in w for w in warnings))

    def test_adapter_starts_a_new_system_at_next_bibliography(self):
        def entry(number):
            return dict(kind='ref', text=f'{number}. Author AB. Title.', page=1, reference_sources=[dict(
                x=100, page=1, column=0, column_left_px=100, column_witness=[100, 400], bounds=[100, 100])])
        items = [entry(1), entry(2), dict(kind='heading', text='References', page=1), entry(1), entry(2)]
        warnings = []
        report = paper.check_reference_systems(items, warnings)
        self.assertEqual(len(report['sections']), 2)
        self.assertFalse(warnings)

    def test_numeric_title_and_unspaced_label_are_printed_not_missing(self):
        items = [dict(kind='ref', text=text, page=1, reference_sources=[dict(
            x=100, page=1, column=0, column_left_px=100, column_witness=[100, 400], bounds=[100, 100])])
            for text in ['1. Author AB. First.', '2. 2020 Annual report.', '3.Author CD. Last.']]
        warnings = []
        report = paper.check_reference_systems(items, warnings)
        self.assertFalse(warnings)
        self.assertEqual([e['printed_ordinal'] for e in report['sections'][0]['entries']], [1, 2, 3])
        self.assertEqual(items[-1]['text'], '3.Author CD. Last.')

    def test_label_column_moves_existing_labels_and_heading_only_with_witnesses(self):
        def element(name, text, box):
            return dict(id=name, kind='text', text=text, box_px=box)
        es = [element('heading', 'References', [0, 100, 50, 112]),
              element('one', '1.', [0, 120, 10, 132]), element('two', '2.', [0, 140, 10, 152]),
              element('a', 'Author AB. First title.', [30, 120, 350, 132]),
              element('b', 'Author CD. Second title.', [30, 140, 350, 152])]
        def block(name, box, order):
            return dict(id=name, cls='main', box_px=box, order=order, in_refs=True)
        bs = [block('heading-block', [0, 100, 50, 152], 0), block('body', [80, 20, 350, 90], 1),
              block('refs', [30, 120, 350, 152], 2)]
        p = dict(elements=es, main_text=dict(blocks=bs), blocks=[
            dict(id='heading-block', members=['heading', 'one', 'two']), dict(id='body', members=[]),
            dict(id='refs', members=['a', 'b'])])
        continuation = copy.deepcopy(p)
        continuation['elements'][1]['text'] = '21.'
        continuation['elements'][2]['text'] = '22.'
        before = copy.deepcopy(continuation)
        paper.prepare_reference_label_column(continuation, 16)
        self.assertEqual(continuation, before)
        ambiguous = copy.deepcopy(p)
        ambiguous['elements'].append(element('other', 'Another candidate.', [35, 120, 350, 132]))
        ambiguous['blocks'][2]['members'].append('other')
        before = copy.deepcopy(ambiguous)
        paper.prepare_reference_label_column(ambiguous, 16)
        self.assertEqual(ambiguous, before)
        interleaved = copy.deepcopy(p)
        interleaved['main_text']['blocks'].append(block('later-ref', [0, 200, 350, 212], .5))
        before = copy.deepcopy(interleaved)
        paper.prepare_reference_label_column(interleaved, 16)
        self.assertEqual(interleaved, before)
        paper.prepare_reference_label_column(p, 16)
        self.assertEqual(p['blocks'][0]['members'], ['heading'])
        self.assertEqual(set(p['blocks'][2]['members']), {'a', 'b', 'one', 'two'})
        self.assertEqual(bs[0]['order'], 1)
        self.assertEqual(bs[1]['order'], 0)
        self.assertFalse(bs[1]['in_refs'])
        # A second pass must not duplicate labels.
        paper.prepare_reference_label_column(p, 16)
        self.assertEqual(len(p['blocks'][2]['members']), 4)

    def test_exact_and_interval_evidence_are_additive(self):
        lines = rows([1, 2, 3])
        lines[1]['x'] = 101
        systems, _, _ = paper.reference_pair_list_systems(lines, [dict(id='starts', bounds=[100, 101])])
        self.assertTrue(any([m['ordinal'] for m in s['members']] == [1, 2, 3] for s in systems))
        self.assertFalse(paper.reference_pair_list_systems(lines)[0])

    def test_one_missing_marker_is_inferred_and_flagged(self):
        systems, _, _ = paper.reference_pair_list_systems(rows([1, 'Author CD. Missing label.', 3]))
        middle = systems[0]['members'][1]
        self.assertEqual(middle['ordinal'], 2)
        self.assertTrue(middle['inferred'])
        self.assertEqual(middle['flag'], 'inferred from sequence')

    def test_two_gaps_end_a_system(self):
        systems, _, _ = paper.reference_pair_list_systems(rows([1, 2, 'First gap', 'Second gap', 5, 6]))
        self.assertEqual([[m['ordinal'] for m in s['members']] for s in systems], [[1, 2], [5, 6]])

    def test_absent_line_is_not_invented(self):
        systems, gaps, _ = paper.reference_pair_list_systems(rows([1, 2, 4, 5]))
        self.assertEqual(gaps[0]['missing_ordinal'], 3)
        self.assertFalse(any(m['inferred'] for s in systems for m in s['members']))

    def test_bracketed_citations_are_outside_port_grammar(self):
        self.assertIsNone(paper.reference_marker('[1] Author AB. Title.'))
        self.assertIsNone(paper.reference_marker('(1) Author AB. Title.'))

    def test_bullets_are_never_inferred_or_joined_across_pages(self):
        self.assertFalse(paper.reference_pair_list_systems(rows(['• First', 'Missing', '• Third']))[0])
        lines = rows(['• First', '• Second']) + rows(['• Third', '• Fourth'], page=2)
        systems, _, events = paper.reference_cross_page_systems(lines)
        self.assertEqual(len(systems), 2)
        self.assertFalse(events[0]['joined'])

    def test_consecutive_columns_and_pages_join_by_relative_alignment(self):
        lines = rows([1, 2]) + rows([3, 4], column=1, x=350, edge=350, start=2) + rows([5, 6], page=2)
        systems, _, events = paper.reference_cross_page_systems(lines, column_relative=True)
        self.assertEqual(len(systems), 1)
        self.assertEqual([m['ordinal'] for m in systems[0]['members']], list(range(1, 7)))
        self.assertEqual([e['move'] for e in events], ['column', 'page'])
        self.assertTrue(all(e['joined'] for e in events))

    def test_unknown_column_declines_cross_column_join(self):
        lines = rows([1, 2]) + rows([3, 4], column=1, x=350, edge=None, start=2)
        systems, _, events = paper.reference_cross_page_systems(lines, column_relative=True)
        self.assertEqual(len(systems), 2)
        self.assertFalse(events[0]['alignment']['aligned'])

    def test_cross_page_unique_gap_is_flagged(self):
        lines = rows([1, 2]) + rows(['Author missing label', 4, 5], page=2, x=350, edge=350)
        systems, _, events = paper.reference_cross_page_systems(lines, column_relative=True)
        self.assertEqual(len(systems), 1)
        self.assertTrue(events[0]['inferred']['inferred'])
        self.assertEqual(events[0]['inferred']['ordinal'], 3)

    def test_intervening_marker_declines_join(self):
        lines = rows([1, 2]) + rows([9], x=200, start=2) + rows([3, 4], page=2, x=350, edge=350)
        _, _, events = paper.reference_cross_page_systems(lines, column_relative=True)
        self.assertFalse(events[0]['joined'])
        self.assertIn('intervening marker: next candidate is not this run', events[0]['declined_reasons'])


if __name__ == '__main__':
    unittest.main()
