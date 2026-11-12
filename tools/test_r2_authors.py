"""r2-authors: a degree or title token after a name belongs to that name (Dr Habil, Dipl-..., slashes);
a row opening with an affiliation marker and an institution ends the byline, in rule 8 and in the
copy's independent name-group count; surnames that look like degree tokens stay authors."""
import unittest

from test_front8 import boxer, paper, page, parse


def raised(text):
    """Every digit of the row set raised and small (affiliation markers)."""
    return {i: (10, True) for i, ch in enumerate(text) if ch.isdigit()}


def tail(y):
    return [('Background: the sites were measured at baseline and twelve months by one examiner.', y, 16, 'main', 'm', {})]


class DegreeAfterName(unittest.TestCase):
    def authors(self, rows):
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {})]
                            + [(r, 150 + 22 * i, 18, 'authors', 'b', {}) for i, r in enumerate(rows)] + tail(260))
        return parse([(first, chars)])

    def test_title_and_habilitation_after_a_name_are_its_degrees(self):
        a = self.authors(['Ada Example, Dr Habil; Ben Sample, Dr Med Dent; Cora Test, DDS'])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Cora Test'])
        self.assertEqual([n.get('degrees') for n in a['authors']], [['Dr Habil'], ['Dr Med Dent'], ['DDS']])
        self.assertEqual(a['checks']['byline_name_groups'], 3)

    def test_degrees_separated_by_slashes_and_diploma_degrees(self):
        a = self.authors(['Ada Example, Dr Med Dent/Dr Habil; Ben Sample, Dipl-Ing, PhD;',
                          'Cora Test, DDS, MSc/PhD; Dov Trial, Dipl.-Psych., Prof'])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Cora Test', 'Dov Trial'])
        self.assertTrue(all(n.get('degrees') for n in a['authors']))
        self.assertNotIn('Dr Habil', [n['name'] for n in a['authors']])

    def test_comma_only_list_keeps_a_title_led_degree_with_its_name(self):
        a = self.authors(['Ada Example, Dr Habil, Ben Sample, Dipl-Psych, Dr Med, and Cora Test, DDS'])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Cora Test'])

    def test_unlisted_post_nominals_after_a_complete_name_are_degrees(self):
        a = self.authors(['Ada Example, DDS, MS1; Ben Q. Sample, PT, MPT2; Cora Test, RN/BSN1'])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Q. Sample', 'Cora Test'])
        self.assertEqual([n.get('degrees') for n in a['authors']], [['DDS', 'MS'], ['PT', 'MPT'], ['RN', 'BSN']])

    def test_credential_after_a_name_split_by_the_reading_layer_stays_its_degree(self):
        a = self.authors(['Ada Exampl e, ScB; Ben Sample, PhD'])
        self.assertEqual([n.get('degrees') for n in a['authors']], [['ScB'], ['PhD']])
        self.assertEqual(len(a['authors']), 2)

    def test_byline_in_capitals_keeps_names_and_degrees_apart(self):
        a = self.authors(['ADA E. EXAMPLE, DDS, MS1, BEN L. SAMPLE, PT, MPT2, AND CORA TEST, RN, BSN1'])
        self.assertEqual([n['name'] for n in a['authors']], ['ADA E. EXAMPLE', 'BEN L. SAMPLE', 'CORA TEST'])
        self.assertEqual([n.get('degrees') for n in a['authors']], [['DDS', 'MS'], ['PT', 'MPT'], ['RN', 'BSN']])

    def test_unmarked_degree_like_surnames_after_a_name_stay_authors(self):
        a = self.authors(['Wen Ma, Arthur Dent, Rosa Med, Thanh Ba, Kofi Mensah'])
        self.assertEqual([n['name'] for n in a['authors']], ['Wen Ma', 'Arthur Dent', 'Rosa Med', 'Thanh Ba', 'Kofi Mensah'])

    def test_bracketed_qualifier_belongs_to_its_degree(self):
        a = self.authors(['Ada Example, BDS, MFDS (RCSEd); Ben Sample, DDS, MS (Perio); Ru Yi, BDS, FDS (RCS)'])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Ru Yi'])
        self.assertEqual([n.get('degrees') for n in a['authors']], [['BDS', 'MFDS (RCSEd)'], ['DDS', 'MS (Perio)'], ['BDS', 'FDS (RCS)']])

    def test_one_word_author_with_its_own_marker_in_a_capitals_byline(self):
        row = 'ADA EXAMPLE1, TAN2, MSC, AND BEN SAMPLE, DDS1'
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {}),
                                (row, 150, 18, 'authors', 'b', raised(row))] + tail(240))
        a = parse([(first, chars)])
        self.assertEqual([n['name'] for n in a['authors']], ['ADA EXAMPLE', 'TAN', 'BEN SAMPLE'])
        self.assertEqual([n['markers'] for n in a['authors']], [['1'], ['2'], ['1']])
        self.assertEqual(a['authors'][1].get('degrees'), ['MSC'])

    def test_unmarked_address_row_opening_with_a_place_ends_the_byline(self):
        a = self.authors(['Ada Example, Ben Sample and Cora Test', 'Westfield Regional Dental Hospital, Westfield, Norway'])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Cora Test'])

    def test_surnames_that_look_like_degree_tokens_stay_authors(self):
        row = 'Wen Ma1, Arthur Dent2, Rosa Med1, Thanh Ba2 and Kofi Mensah1'
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {}),
                                (row, 150, 18, 'authors', 'b', raised(row))] + tail(240))
        a = parse([(first, chars)])
        self.assertEqual([n['name'] for n in a['authors']], ['Wen Ma', 'Arthur Dent', 'Rosa Med', 'Thanh Ba', 'Kofi Mensah'])
        self.assertTrue(all(not n.get('degrees') for n in a['authors']))


class MarkerLedAffiliationRow(unittest.TestCase):
    def test_institution_row(self):
        self.assertTrue(boxer.institution_row('1Department of Testing, Northfield University; Northfield'))
        self.assertTrue(boxer.institution_row('* University of Trials, Southfield'))
        self.assertTrue(boxer.institution_row('1,2Department of Trials, Southfield'))
        self.assertTrue(boxer.institution_row('bInstitute for Invented Research, Westfield'))
        self.assertTrue(boxer.institution_row('a,b University of Westfield'))
        self.assertFalse(boxer.institution_row('Ada Examplea, Ben Sampleb'))
        self.assertFalse(boxer.institution_row('Ada Example1, Ben Sample2'))
        self.assertFalse(boxer.institution_row('1Ada Example, 2Ben Sample'))   # a byline with markers before names

    def fixture(self):
        by = 'Ada Example, DDS1, Ben Sample, PhD2, and Cora Test, DMD1,2'
        a1 = '1Department of Testing, Northfield School of Medicine, Northfield University; Northfield, MA'
        a2 = '2Department of Trials, Southfield College; Southfield'
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {}),
                                (by, 150, 18, 'authors', 'b', raised(by)),
                                (a1, 172, 18, 'authors', 'b', {0: (10, True)}),
                                (a2, 194, 18, 'authors', 'b', {0: (10, True)})] + tail(260))
        return first, chars

    def test_marker_led_institution_rows_are_affiliations_not_authors(self):
        first, chars = self.fixture()
        a = parse([(first, chars)])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Cora Test'])
        self.assertEqual(sorted(f['marker'] for f in a['affiliations']), ['1', '2'])

    def test_letter_marked_affiliation_rows_end_the_byline(self):
        by = 'Ada Examplea, Ben Sampleb, and Cora Testa,b'
        a1 = 'aUniversity of Northfield, School of Testing; Northfield, OR'
        a2 = 'bInstitute for Invented Research, Westfield; Westfield, WA'
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {}),
                                (by, 150, 18, 'authors', 'b', {i: (10, True) for i in (by.index('a,'), by.index('b,'), len(by)-3, len(by)-2, len(by)-1)}),
                                (a1, 172, 18, 'authors', 'b', {0: (10, True)}),
                                (a2, 194, 18, 'authors', 'b', {0: (10, True)})] + tail(260))
        a = parse([(first, chars)])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Cora Test'])
        self.assertEqual(paper.printed_front_matter([first], a)[1], 3)

    def test_marked_rows_opening_with_an_institution_name_end_a_marked_byline(self):
        by = 'Ada Example, DDS1, Ben Sample, PhD2, and Cora Test, MD1,2'
        a1 = '1Northfield Dental School, Northfield University; Northfield, ME'
        a2 = '2Saint Westfield Hospital, Division of Trials; Westfield, NH'
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {}),
                                (by, 150, 18, 'authors', 'b', raised(by)),
                                (a1, 172, 18, 'authors', 'b', {0: (10, True)}),
                                (a2, 194, 18, 'authors', 'b', {0: (10, True)})] + tail(260))
        a = parse([(first, chars)])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Cora Test'])
        self.assertEqual(paper.printed_front_matter([first], a)[1], 3)
        self.assertTrue(boxer.marked_row_after_marked_byline(by, a1))
        self.assertFalse(boxer.marked_row_after_marked_byline('1Ada Example, 2Ben Sample,', '3Cora Test'))

    def test_place_led_marked_rows_under_a_byline_with_markers_inside(self):
        by = 'Ada Example1, DMD, Ben Sample2, MSc, and Cora Test1, PhD'
        a1 = '1Northfield, Faculty of Testing, Northfield; Northfield, Norway'
        a2 = '2Westfield, Oral Health Services Unit; Westfield, Norway'
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {}),
                                (by, 150, 18, 'authors', 'b', raised(by)),
                                (a1, 172, 18, 'authors', 'b', {0: (10, True)}),
                                (a2, 194, 18, 'authors', 'b', {0: (10, True)})] + tail(260))
        a = parse([(first, chars)])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Cora Test'])
        self.assertEqual(paper.printed_front_matter([first], a)[1], 3)
        self.assertTrue(boxer.marked_row_after_marked_byline(by, a2))

    def test_citation_marker_in_body_prose_is_never_an_address(self):
        by = 'Ada Example, DDS1, Ben Sample, PhD2, and Cora Test, MD1,2'
        a1 = '1Department of Testing, Northfield University, Northfield, OR'
        lead = 'Jaw pain often follows joint inflammation)1,2. Jaw disorder is common in clinics.'
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {}),
                                (by, 150, 18, 'authors', 'b', raised(by)),
                                (a1, 172, 14, 'other', 'f', {0: (8, True)}),
                                (lead, 230, 17, 'other', 'p', raised(lead))] + tail(300))
        a = parse([(first, chars)])
        texts = {f['marker']: f['text'] for f in a['affiliations']}
        self.assertNotIn('Jaw disorder', ' '.join(texts.values()))

    def test_address_label_before_a_number_led_institution_is_kept(self):
        by = 'Ada Example, DDS1/Ben Sample, DDS2/Cora Test, DDS3'
        a1 = '1 4th Division, Northfield University School of Testing, Northfield'
        a2 = '2 2nd Department of Trials, Westfield College, Westfield'
        a3 = '3 3 Hospitals Network, Eastfield'
        specs = [(by, 150, 18, 'authors', 'b', raised(by))]
        for n, row in enumerate((a1, a2, a3)):
            specs.append((row.replace(' ', '', 1), 175 + 16 * n, 14, 'other', 'f', {0: (8, True)}))
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {})] + specs + tail(280))
        a = parse([(first, chars)])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Cora Test'])
        texts = {f['marker']: f['text'] for f in a['affiliations']}
        self.assertEqual(sorted(texts), ['1', '2', '3'])
        self.assertTrue(texts['1'].startswith('4th Division'))
        self.assertTrue(texts['2'].startswith('2nd Department'))

    def test_letter_and_symbol_labels_before_number_led_institutions(self):
        by = 'Ada Examplea, Ben Sampleb, and Cora Testc'
        rows = ['a1 st Faculty of Testing, Northfield University, Northfield',
                'b2nd Department of Trials, Westfield Hospital, Westfield',
                'c3 Hospitals Invented Care Group, Eastfield']
        specs = [(by, 150, 18, 'authors', 'b', {i: (10, True) for i in (by.index('a,'), by.index('b,'), len(by) - 1)})]
        for n, row in enumerate(rows):
            specs.append((row, 175 + 16 * n, 14, 'other', 'f', {0: (8, True)}))
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {})] + specs + tail(280))
        a = parse([(first, chars)])
        self.assertEqual(sorted(f['marker'] for f in a['affiliations']), ['a', 'b', 'c'])
        by = 'Ada Example* and Ben Sample\u2020'
        rows = ['*1st Faculty of Testing, Northfield University, Northfield', '\u20202nd Department of Trials, Westfield Hospital, Westfield']
        specs = [(by, 150, 18, 'authors', 'b', {by.index('*'): (10, True), len(by) - 1: (10, True)})]
        for n, row in enumerate(rows):
            specs.append((row, 175 + 16 * n, 14, 'other', 'f', {0: (8, True)}))
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {})] + specs + tail(280))
        a = parse([(first, chars)])
        self.assertEqual(sorted(f['marker'] for f in a['affiliations']), ['*', '\u2020'])

    def compound(self, by, row):
        sup = {i: (10, True) for i, ch in enumerate(by) if ch.isdigit() or (ch in 'ab' and i and by[i - 1] in 'el')}
        lab = len(row) - len(row.lstrip('0123456789ab,-'))
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {}),
                                (by, 150, 18, 'authors', 'b', sup),
                                (row, 175, 14, 'other', 'f', {i: (8, True) for i in range(lab)})] + tail(260))
        return parse([(first, chars)])

    def test_compound_label_set_names_every_marker(self):
        for by, row, want in (('Ada Example1, Ben Sample2', '1,2Department of Testing, Northfield University, Northfield', ['1', '2']),
                              ('Ada Example1, Ben Sample2, Cora Test3', '1-3 Institute of Invented Research, Westfield', ['1', '2', '3']),
                              ('Ada Examplea, Ben Sampleb', 'a,bUniversity of Northfield, Department of Trials, Northfield', ['a', 'b'])):
            a = self.compound(by, row)
            texts = {f['marker']: f['text'] for f in a['affiliations']}
            self.assertEqual(sorted(texts), want, row)
            self.assertTrue(all(len(t) > 20 for t in texts.values()), texts)

    def test_form_sheet_rows_are_not_cut_by_the_address_row_tests(self):
        rows = ['Corresponding Author: Ada Example, DDS', 'Northfield University School of Testing', 'Northfield, Ostria UNITED STATES']
        specs = [(r, 150 + 20 * n, 18, 'authors', 'b', {}) for n, r in enumerate(rows)]
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {})] + specs + tail(260))
        a = parse([(first, chars)])
        self.assertTrue(any('Northfield University' in l['text'] for l in a['byline_lines']))

    def test_address_label_before_an_opening_bracket_is_kept(self):
        by = 'Ada Example1 and Ben Sample2'
        a1 = '1Department of Testing, Northfield University, Northfield; 2(1) Centre for Trials and (2) Westfield Research Center, Westfield'
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {}),
                                (by, 150, 18, 'authors', 'b', raised(by)),
                                (a1, 175, 14, 'other', 'f', {0: (8, True), a1.index('2('): (8, True)})] + tail(260))
        a = parse([(first, chars)])
        self.assertEqual(sorted(f['marker'] for f in a['affiliations']), ['1', '2'])

    def test_institution_word_rows_and_group_names(self):
        self.assertTrue(boxer.institution_row('Westfield Regional Dental Hospital, Westfield, Norway'))
        self.assertFalse(boxer.institution_row('for the Northfield University Study Group'))
        self.assertFalse(boxer.institution_row('Cora Test and Dov Trial'))

    def inline(self, separate, neg=False):
        names = 'ADA EXAMPLE* & BEN SAMPLE†' + (', PhD' if neg else '')
        addr = '*Department of Testing, Faculty of Trials, Northfield University, Northfield and'
        second = '†The Westfield Council on Invented Research, Westfield, Norway'
        sup = {i: (10, True) for i, ch in enumerate(names) if ch in '*†'}
        if neg:
            specs = [(names, 150, 18, 'authors', 'b', sup), (addr[:-4], 172, 18, 'authors', 'b', {0: (10, True)}),
                     (second, 194, 18, 'authors', 'b', {0: (10, True)})]
        elif separate:
            specs = [(names, 150, 18, 'authors', 'b', sup, 20),
                     (addr, 150, 18, 'authors', 'b', {0: (10, True)}, 20 + 0.5 * 18 * (len(names) + 2)),
                     (second, 172, 18, 'authors', 'b', {0: (10, True)})]
        else:
            row = names + ' ' + addr
            sup[len(names) + 1] = (10, True)
            specs = [(row, 150, 18, 'authors', 'b', sup), (second, 172, 18, 'authors', 'b', {0: (10, True)})]
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {})] + specs + tail(260))
        return first, parse([(first, chars)])

    def test_affiliation_starting_on_the_byline_row_in_its_own_run(self):
        first, a = self.inline(separate=True)
        self.assertEqual([n['name'] for n in a['authors']], ['ADA EXAMPLE', 'BEN SAMPLE'])
        self.assertEqual(sorted(f['marker'] for f in a['affiliations']), ['*', '†'])

    def test_affiliation_starting_inside_the_names_run(self):
        first, a = self.inline(separate=False)
        self.assertEqual([n['name'] for n in a['authors']], ['ADA EXAMPLE', 'BEN SAMPLE'])
        self.assertEqual(sorted(f['marker'] for f in a['affiliations']), ['*', '†'])
        self.assertEqual(paper.printed_front_matter([first], a)[1], 2)

    def test_a_lower_case_note_after_and_is_not_a_continued_address(self):
        by = 'Ada Example1,* and Ben Sample2'
        a1 = '1Department of Testing, Northfield University, Northfield; 2Department of Trials, Westfield College, Westfield; and *corresponding author, ada@example.org'
        first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {}),
                                (by, 150, 18, 'authors', 'b', {i: (10, True) for i, ch in enumerate(by) if ch in '12,*'}),
                                (a1, 175, 14, 'other', 'f', {i: (8, True) for i, ch in enumerate(a1) if ch in '12*' and (i == 0 or a1[i-1] in ' ;')})] + tail(260))
        a = parse([(first, chars)])
        self.assertNotIn('*', [f['marker'] for f in a['affiliations']])

    def test_marker_after_the_last_name_before_a_degree_is_a_name_marker(self):
        first, a = self.inline(separate=False, neg=True)
        self.assertEqual([n['name'] for n in a['authors']], ['ADA EXAMPLE', 'BEN SAMPLE'])
        self.assertEqual(a['authors'][1].get('degrees'), ['PhD'])

    def test_copy_count_of_name_groups_stops_at_the_affiliation_row(self):
        first, chars = self.fixture()
        a = parse([(first, chars)])
        records, count = paper.printed_front_matter([first], a)
        self.assertEqual(count, 3)


if __name__ == '__main__':
    unittest.main()
