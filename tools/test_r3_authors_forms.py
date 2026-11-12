"""r3-authors-forms: titles set before a name belong to it; on a manuscript cover sheet the author list
is the "Order of Authors:" (else "First Author:") field, one name per row, and its institution field is
the affiliation; a labelled field row under a byline ("Designation: ...", "Corresponding author: ...")
is never a row of names; ordinary bylines (title-like surnames, no field rows) are read as before."""
import unittest

from test_front8 import boxer, page, parse


def raised(text):
    return {i: (10, True) for i, ch in enumerate(text) if ch.isdigit()}


def tail(y):
    return [('Background: the sites were measured at baseline and twelve months by one examiner.', y, 16, 'main', 'm', {})]


def byline(rows, after=()):
    first, chars = page(1, [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {})]
                        + [(r, 150 + 22 * i, 18, 'authors', 'b', raised(r)) for i, r in enumerate(rows)]
                        + [(r, 150 + 22 * (len(rows) + i), 18, 'other', 'a', raised(r)) for i, r in enumerate(after)]
                        + tail(150 + 22 * (len(rows) + len(after)) + 60))
    return parse([(first, chars)])


class PrenominalTitles(unittest.TestCase):
    def test_titles_before_a_name_belong_to_it(self):
        a = byline(['Prof. Dr. med. dent. Ada Example1, Dr. Dr. Ben Sample2, Dipl.-Ing. Cora Test1'],
                   ['1Department of Invented Studies, Example University, Exampletown',
                    '2Institute of Sample Research, Sample City'])
        self.assertEqual([n['name'] for n in a['authors']],
                         ['Prof. Dr. med. dent. Ada Example', 'Dr. Dr. Ben Sample', 'Dipl.-Ing. Cora Test'])
        self.assertTrue(all(n['name_ok'] for n in a['authors']))
        self.assertEqual(a['checks']['byline_name_groups'], 3)

    def test_titles_without_periods_and_mixed_with_degrees(self):
        a = byline(['PD Dr med Ada Example, MSc1, Dr. rer. nat. Ben Sample, PhD2'],
                   ['1Department of Invented Studies, Example University, Exampletown',
                    '2Institute of Sample Research, Sample City'])
        self.assertEqual([n['name'] for n in a['authors']], ['PD Dr med Ada Example', 'Dr. rer. nat. Ben Sample'])
        self.assertEqual([n.get('degrees') for n in a['authors']], [['MSc'], ['PhD']])
        self.assertTrue(all(n['name_ok'] for n in a['authors']))

    def test_titles_by_their_printed_form_in_other_national_styles(self):
        for printed, name in [('Univ.-Prof. DDr. Ada Example', 'Ada Example'), ('OA Dr. Ben Sample', 'Ben Sample'),
                              ('Ass.-Prof. Dr. med. dent. Cora Test', 'Cora Test'), ('Doc. MUDr. Dov Trial', 'Dov Trial'),
                              ('prof. dr hab. n. med. Eve Probe', 'Eve Probe'), ('lek. dent. Fay Sample', 'Fay Sample'),
                              ('dr n. med. Gus Example', 'Gus Example')]:
            self.assertEqual(boxer.prenominal_rest(printed), name)
        a = byline(['Univ.-Prof. DDr. Ada Example1, OA Dr. Ben Sample2,', 'Ass.-Prof. Dr. med. dent. Cora Test1'],
                   ['1Department of Invented Studies, Example University, Exampletown',
                    '2Institute of Sample Research, Sample City'])
        self.assertEqual([n['name'] for n in a['authors']],
                         ['Univ.-Prof. DDr. Ada Example', 'OA Dr. Ben Sample', 'Ass.-Prof. Dr. med. dent. Cora Test'])
        self.assertTrue(all(n['name_ok'] for n in a['authors']))
        a = byline(['prof. dr hab. n. med. Ada Example1, lek. dent. Ben Sample2, dr n. med. Cora Test1'],
                   ['1Department of Invented Studies, Example University, Exampletown',
                    '2Institute of Sample Research, Sample City'])
        self.assertEqual([n['name'] for n in a['authors']],
                         ['prof. dr hab. n. med. Ada Example', 'lek. dent. Ben Sample', 'dr n. med. Cora Test'])
        self.assertTrue(all(n['name_ok'] for n in a['authors']))
        self.assertEqual(a['checks']['byline_name_groups'], 3)

    def test_titles_end_where_initials_and_a_surname_start(self):
        for printed, name in [('Prof. Dr. A. Example', 'A. Example'), ('Dr. med. dent. B. C. Sample', 'B. C. Sample'),
                              ('PD Dr. H.-P. Test', 'H.-P. Test'), ('dr n. med. D. Trial', 'D. Trial'),
                              ('Dr. med. M. Sc. E. Probe', 'E. Probe')]:
            self.assertEqual(boxer.prenominal_rest(printed), name)
        self.assertIsNone(boxer.prenominal_rest('Prof. Dr. med.'))   # titles only: no name is invented
        self.assertIsNone(boxer.prenominal_rest('A. Example'))
        a = byline(['Prof. Dr. A. Example1, Dr. med. dent. B. C. Sample2, PD Dr. H.-P. Test1'],
                   ['1Department of Invented Studies, Example University, Exampletown',
                    '2Institute of Sample Research, Sample City'])
        self.assertEqual([n['name'] for n in a['authors']],
                         ['Prof. Dr. A. Example', 'Dr. med. dent. B. C. Sample', 'PD Dr. H.-P. Test'])
        self.assertTrue(all(n['name_ok'] for n in a['authors']))

    def test_the_surname_after_initials_is_what_the_name_test_reads_as_one(self):
        for printed, name in [('prof. dr. A.B. van der Example', 'A.B. van der Example'), ('dr. C.D. de Sample', 'C.D. de Sample'),
                              ('drs. E.F. ter Test', 'E.F. ter Test'), ('Prof. Dr. G.H. van der Trial', 'G.H. van der Trial'),
                              ('Dr. med. K. EXAMPLE', 'K. EXAMPLE'), ('PD Dr. L. SAMPLE-TEST', 'L. SAMPLE-TEST'),
                              ("Dr. med. P. O'Example", "P. O'Example"), ('Dr. med. dent. R. Sample Jr.', 'R. Sample Jr.'),
                              ('Dr. A. Example-Sample', 'A. Example-Sample'), ('Dott. A. della Example', 'A. della Example')]:
            self.assertEqual(boxer.prenominal_rest(printed), name)
        # a title run followed by a lower-case word that is no particle, or a particle without a name word, is no name
        for printed in ('Prof. Dr. K. example', 'dr. G.A. van example', 'Prof. Dr. abstract', 'Prof. Dr. med.'):
            self.assertIsNone(boxer.prenominal_rest(printed))
        a = byline(['prof. dr. A.B. van der Example1, dr. C.D. de Sample2, drs. E.F. ter Test1'],
                   ['1Department of Invented Studies, Example University, Exampletown',
                    '2Institute of Sample Research, Sample City'])
        self.assertEqual([n['name'] for n in a['authors']],
                         ['prof. dr. A.B. van der Example', 'dr. C.D. de Sample', 'drs. E.F. ter Test'])
        self.assertTrue(all(n['name_ok'] for n in a['authors']))

    def test_a_degree_after_the_name_stays_its_degree(self):
        a = byline(['Ada Example, MUDr.1, Ben Sample, Dr. med. dent.2'],
                   ['1Department of Invented Studies, Example University, Exampletown',
                    '2Institute of Sample Research, Sample City'])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample'])

    def test_title_like_surnames_are_not_titles(self):
        self.assertIsNone(boxer.prenominal_rest('Profeta Giulia'))
        self.assertIsNone(boxer.prenominal_rest('Doktor Ilse Brandl'))
        self.assertIsNone(boxer.prenominal_rest('Drago Medina'))
        self.assertIsNone(boxer.prenominal_rest('and Ben Sample'))
        self.assertIsNone(boxer.prenominal_rest('J. Sample'))
        a = byline(['Profeta Giulia1, Dragan Prokic2, Elena Medina1'],
                   ['1Department of Invented Studies, Example University, Exampletown',
                    '2Institute of Sample Research, Sample City'])
        self.assertEqual([n['name'] for n in a['authors']], ['Profeta Giulia', 'Dragan Prokic', 'Elena Medina'])


class FieldRows(unittest.TestCase):
    def test_designation_rows_are_not_authors(self):
        a = byline(['Ada Example, MDS1',
                    'Designation: Senior Lecturer, Department of Invented Studies, Example College, Exampletown',
                    'Ben Sample, MDS2',
                    'Designation: Professor and Head, Department of Invented Studies, Example College, Exampletown',
                    'Corresponding author: Ada Example, ada@example.org'])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample'])
        self.assertEqual([n.get('degrees') for n in a['authors']], [['MDS'], ['MDS']])
        # Each author's field rows, the last author's included, are role/affiliation lines as printed.
        self.assertEqual([c['text'].split(':')[0] for c in a.get('unmarked_affiliation_candidates', [])],
                         ['Designation', 'Designation', 'Corresponding author'])

    def test_corresponding_field_under_a_byline_is_not_a_name(self):
        a = byline(['Ada Example1, Ben Sample2, Cora Test1,', 'Dov Trial2 and Eve Probe1',
                    'Corresponding author: Ada Example, Faculty of Invented Studies, Exampletown'],
                   ['1Faculty of Invented Studies, Example University, Exampletown',
                    '2Department of Sample Research, Sample Hospital, Sample City'])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Cora Test', 'Dov Trial', 'Eve Probe'])
        self.assertEqual(a['checks']['status'], 'verified')
        # The field row is printed as article information, not dropped.
        self.assertIn('field row under the byline', [x.get('role') for x in a.get('article_info', [])])

    def test_run_in_abstract_label_is_not_a_field(self):
        a = byline(['Ada Example1, Ben Sample2', 'Background: Most patients in the cohort were seen twice by one examiner.'],
                   ['1Department of Invented Studies, Example University, Exampletown',
                    '2Institute of Sample Research, Sample City'])
        self.assertNotIn('field row under the byline', [x.get('role') for x in a.get('article_info', [])])

    def test_form_name_row(self):
        self.assertTrue(boxer.form_name_row('Ben Sample, MDS2'))
        self.assertTrue(boxer.form_name_row('Prof. Dr. med. Ada Example, PhD'))
        self.assertFalse(boxer.form_name_row('micro-recorder; adherence; Apnea Hypopnea Index;'))
        self.assertFalse(boxer.form_name_row('Example College of Dental Sciences, Exampletown'))
        self.assertFalse(boxer.form_name_row('1Faculty of Invented Studies, Example University'))


class CoverSheet(unittest.TestCase):
    def sheet(self, order=True, same_run=False):
        L, V = 20, 300
        specs = [('Invented Journal of Examples', 40, 30, 'title', 't0', {}, 300),
                 ('Manuscript Number:', 150, 16, 'other', 'l1', {}, L), ('EX-20-00001', 150, 16, 'other', 'v1', {}, V),
                 ('Full Title:', 180, 16, 'other', 'l2', {}, L), ('A Trial of Invented Membranes in Deep Defects', 180, 16, 'other', 'v2', {}, V),
                 ('Keywords:', 210, 16, 'other', 'l3', {}, L), ('membranes; Deep Defects; Bone Fill;', 210, 16, 'other', 'v3', {}, V),
                 ('Invented Regeneration Index; smoking', 230, 16, 'other', 'v3', {}, V),
                 ('Corresponding Author:', 260, 16, 'other', 'l4', {}, L), ('Ada Example, DDS', 260, 16, 'other', 'v4', {}, V),
                 ('Example University School of Dentistry', 280, 16, 'other', 'v4', {}, V),
                 ("Corresponding Author's Institution:", 310, 16, 'other', 'l5', {}, L),
                 ('Example University School of Dentistry', 310, 16, 'other', 'v5', {}, V),
                 ('First Author:', 340, 16, 'other', 'l6', {}, L), ('Ada Example, DDS', 340, 16, 'other', 'v6', {}, V)]
        y = 370
        if order:
            if same_run: specs.append(('Order of Authors: Ada Example, DDS', y, 16, 'other', 'l7', {}, L))
            else: specs += [('Order of Authors:', y, 16, 'other', 'l7', {}, L), ('Ada Example, DDS', y, 16, 'other', 'v7', {}, V)]
            for k, n in enumerate(['Ben Sample, MS', 'Cora Test, PhD']):
                specs.append((n, y + 20 * (k + 1), 16, 'other', 'v7', {}, V if not same_run else 20 + 18 * 8))
            y += 60
        specs += [('Order of Authors Secondary Information:', y + 30, 16, 'other', 'l8', {}, L),
                  ('Manuscript Region of Origin:', y + 60, 16, 'other', 'l9', {}, L), ('EXAMPLELAND', y + 60, 16, 'other', 'v9', {}, V)]
        first, chars = page(1, specs)
        return parse([(first, chars)])

    def test_order_of_authors_field_is_the_author_list(self):
        a = self.sheet()
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Cora Test'])
        self.assertEqual([n.get('degrees') for n in a['authors']], [['DDS'], ['MS'], ['PhD']])
        self.assertEqual([c['text'] for c in a.get('unmarked_affiliation_candidates', [])], ['Example University School of Dentistry'])

    def test_first_author_field_when_no_order_field(self):
        a = self.sheet(order=False)
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example'])

    def test_value_in_the_label_run(self):
        a = self.sheet(same_run=True)
        self.assertEqual([n['name'] for n in a['authors']][:1], ['Ada Example'])
        self.assertNotIn('Order of Authors', ' '.join(n['name'] for n in a['authors']))


if __name__ == '__main__':
    unittest.main()
