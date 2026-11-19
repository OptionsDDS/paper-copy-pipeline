"""r6-affiliations: the affiliations hang on the author marks (round 6 rules A10-A13, A16, A19, A20).

A symbol address may name its institution anywhere in its row (A10, A11); a byline symbol with no address pairs with
the text after the same symbol in a block of addresses (A11); symbols set together after a name are one mark each
(A11, A12); the affiliations run in the usual mark order (A12); an affiliation ends at a section label, a blank line
or a correspondence opening (A16); a marked line opening with author-note words is no affiliation (A19); a sign-font
letter marker whose shape was rejected is never printed as the letter (A20). All names and texts are made up."""
import unittest

from test_front8 import boxer, page, paper, parse


def tail(y):
    return [('Background: the sites were measured at baseline and twelve months by one examiner.', y, 16, 'main', 'm', {})]


def front(byline, notes, note_y=1250, gap=16, size=12, cls='other', block='f'):
    rows = [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {}),
            (byline, 150, 18, 'authors', 'b', {})] + tail(260)
    y = note_y
    for n in notes:   # 'GAP' leaves a blank row
        if n == 'GAP':
            y += 2 * gap; continue
        rows.append((n, y, size, cls, block, {})); y += gap
    first, chars = page(1, rows)
    return parse([(first, chars)])


class SymbolAddress(unittest.TestCase):
    """A10/A11 with A19: institution anywhere, never a note, a support statement or an e-mail row."""
    def test_institution_named_after_a_qualifier_or_place(self):
        for body in ['Neurology Department, Northfield University Hospital, Eastwick, Norland.',
                     'Primary Healthcare Center Lakeside, Eastwick, Norland.',
                     'Previously, Department of Public Health, Northfield College of Dentistry.',
                     'Northfield College of Dentistry; private practice, Eastwick.']:
            self.assertTrue(boxer.symbol_address(body), body)

    def test_notes_support_and_contact_rows_are_not_addresses(self):
        for body in ['Corresponding author: Department of Periodontics, Westvale University, Eastwick.',
                     'Address all correspondence to Dr A. Example, Westvale University.',
                     'These authors contributed equally to this work at Westvale University.',
                     'Ada B. Example and Ben C. Sample contributed equally; Westvale University.',
                     'Present address: School of Dentistry, Westvale University, Eastwick.',
                     'Deceased; formerly Department of Periodontics, Westvale University.',
                     'Supported by a grant from the National Institute of Dental Research.',
                     'Westvale Health Agency, Centre for Preparedness, Eastwick. E-mail address: a.example@westvale.nl']:
            self.assertFalse(boxer.symbol_address(body), body)

    def test_no_institution_word_is_not_admitted_alone(self):
        self.assertFalse(boxer.symbol_address('Invented Therapeutics, Eastwick, Norland.'))


class SymbolFootnotes(unittest.TestCase):
    def test_qualified_symbol_addresses_are_affiliations_in_mark_order(self):
        a = front('Ada Example,§ Ben Sample,† and Cora Test*',
                  ['* School of Dentistry, Westvale University, Eastwick, Norland.',
                   '† Neurology Department, Northfield University Hospital, Eastwick.',
                   '§ Primary Healthcare Center Lakeside, Eastwick, Norland.'])
        self.assertEqual([x['marker'] for x in a['affiliations']], ['*', '†', '§'])   # A12: usual order, not code order
        self.assertEqual(a['checks']['status'], 'verified')

    def test_support_note_naming_an_institute_stays_out(self):
        a = front('Ada Example,* Ben Sample,† and Cora Test‡',
                  ['* School of Dentistry, Westvale University, Eastwick, Norland.',
                   '† Neurology Department, Northfield University Hospital, Eastwick.',
                   '‡ Supported by a grant from the National Institute of Dental Research.'])
        self.assertEqual(sorted(x['marker'] for x in a['affiliations']), ['*', '†'])

    def test_compound_symbols_after_a_name_are_one_mark_each(self):
        a = front('Ada Example*† and Ben Sample‡',
                  ['* Department of Medicine, Westvale Medical School, Eastwick.',
                   '† Center for Invented Studies, Northfield Hospital, Eastwick.',
                   '‡ School of Dentistry, Westvale University, Eastwick.'])
        self.assertEqual(a['authors'][0]['markers'], ['*', '†'])
        self.assertEqual([x['marker'] for x in a['affiliations']], ['*', '†', '‡'])


class MarkPairsInAddressBlock(unittest.TestCase):
    """A11: a byline symbol pairs with its text inside a block of addresses even with no institution word."""
    def test_unnamed_address_between_two_addresses(self):
        a = front('Ada Example,* Ben Sample** and Cora Test***',
                  ['*Department of Medicine, Westvale University Hospitals, **Royal Northfield and',
                   'Eastwick Health Trust and ***Department of Orthodontics, Westvale School of Dentistry, UK'])
        found = {x['marker']: x['text'] for x in a['affiliations']}
        self.assertEqual(sorted(found), ['*', '**', '***'])
        self.assertTrue(found['**'].startswith('Royal Northfield'))

    def test_a_note_in_the_block_does_not_pair(self):
        a = front('Ada Example,* Ben Sample† and Cora Test*',
                  ['*Department of Medicine, Westvale University Hospitals, Eastwick.',
                   '†Corresponding author: Ben Sample, Eastwick Health Trust.'])
        self.assertNotIn('†', [x['marker'] for x in a['affiliations']])
        self.assertEqual(a.get('author_note_marks'), ['†'])   # A19: the mark has its author note


class AffiliationEnds(unittest.TestCase):
    """A16: at a section label, at a blank line, at a correspondence opening; the cut rows are recorded."""
    def test_label_row_ends_the_last_affiliation(self):
        a = front('Ada Example1 and Ben Sample2',
                  ['1Department of Testing, Northfield University, Northfield', '2School of Trials, Westfield College, Westfield',
                   'SUMMARY This trial compared two invented membranes in forty deep defects over a year.'],
                  note_y=190, gap=20, size=14)
        last = next(x for x in a['affiliations'] if x['marker'] == '2')
        self.assertNotIn('SUMMARY', last['text'])
        self.assertTrue(a.get('released_run_ids'))

    def test_correspondence_opening_ends_the_affiliation(self):
        a = front('Ada Example1 and Ben Sample2',
                  ['1Department of Testing, Northfield University, Northfield', '2Westfield Physiotherapy Associates, Westfield',
                   'Address all correspondence and requests for reprints to: Ada Example.'], note_y=1250, gap=16)
        last = next(x for x in a['affiliations'] if x['marker'] == '2')
        self.assertNotIn('Address all', last['text'])

    def test_blank_line_ends_the_affiliation(self):
        a = front('Ada Example1 and Ben Sample2',
                  ['1Department of Testing, Northfield University, Northfield', '2School of Trials, Westfield College, Westfield',
                   'GAP', 'The invented membranes were compared in forty deep defects.'], note_y=1250, gap=16)
        last = next(x for x in a['affiliations'] if x['marker'] == '2')
        self.assertNotIn('invented membranes', last['text'])

    def test_rows_at_an_even_pitch_never_part(self):
        # memo 1 M1: an affiliation over three rows set at the block's own pitch stays whole
        a = front('Ada Example1 and Ben Sample2',
                  ['1Department of Testing, Northfield University, Northfield.', '2Department of Oral and Maxillofacial Sur-',
                   'gery, Westfield Regional Hospital and Clinical Insti-', 'tute of Studies, Westfield.'], note_y=1250, gap=25)
        last = next(x for x in a['affiliations'] if x['marker'] == '2')
        self.assertTrue(last['text'].endswith('Westfield.'), last['text'])

    def test_wrapped_affiliation_stays_whole(self):
        a = front('Ada Example1 and Ben Sample2',
                  ['1Department of Testing, Northfield University,', 'Northfield, Norland', '2School of Trials, Westfield College, Westfield'],
                  note_y=1250, gap=16)
        first = next(x for x in a['affiliations'] if x['marker'] == '1')
        self.assertIn('Norland', first['text'])
        self.assertFalse(a.get('released_run_ids'))


class UnknownFormMarker(unittest.TestCase):
    """A20: a letter marker coded in a sign font with a rejected shape is printed as the copy's checked sign."""
    def test_rejected_sign_font_letter_is_not_printed_as_the_letter(self):
        byline = {'id': 'run:1', 'kind': 'text', 'text': 'Ada Example,i', 'box_px': [0, 0, 10, 10],
                  'font_spans': [dict(start=0, end=12, font='Name'), dict(start=12, end=13, font='Sign')],
                  'font_subs': [dict(offset=12, before='i', status='rejected', font='Sign', source_code=105)]}
        foot = {'id': 'run:2', 'kind': 'text', 'text': 'i Invented Division, Eastwick', 'box_px': [0, 90, 10, 100],
                'font_spans': [dict(start=0, end=1, font='Sign')],
                'font_subs': [dict(offset=0, before='i', status='rejected', font='Sign', source_code=105)]}
        pages = [dict(page=1, elements=[byline, foot])]
        au = dict(page=1, authors=[dict(name='Ada Example', markers=['i'], notes=[])], author_run_ids=['run:1'],
                  affiliations=[dict(marker='i', text='Invented Division, Eastwick')], checks=dict(markers_used=['i']))
        pending = paper.unknown_form_markers(pages, au)
        self.assertEqual(sorted(pending), ['i'])
        byline['text'] = 'Ada Example,‖'; foot['text'] = '‖ Invented Division, Eastwick'   # the copy's font check
        uncertain = []
        paper.resolve_unknown_markers(pages, au, pending, uncertain)
        self.assertEqual(au['authors'][0]['markers'], ['‖'])
        self.assertEqual(au['affiliations'][0]['marker'], '‖')
        self.assertEqual(uncertain, [])


class Memo1Shapes(unittest.TestCase):
    """memo 1: a reprint request opening with "Address" ends the affiliation before that word (M3); a dash is never a
    mark (M4); an unread sign after a name is a mark that keeps its count, and rows opening with it pair (M6)."""
    def test_address_reprint_requests_ends_the_affiliation(self):
        a = front('Ada Example1 and Ben Sample2',
                  ['1Department of Testing, Northfield University, Northfield', '2School of Trials, Westfield College, Westfield.',
                   'Address reprint requests to Dr Ada Example, Northfield University.'], note_y=1250, gap=16)
        last = next(x for x in a['affiliations'] if x['marker'] == '2')
        self.assertFalse(last['text'].endswith('Address'), last['text'])
        self.assertNotIn('reprint', last['text'])

    def test_dash_is_no_mark(self):
        by = 'Ada Example1,A–D, Ben Sample2 and Cora Test1'
        rows = [('A Trial of Invented Membranes in Deep Defects', 100, 30, 'title', 't', {}),
                (by, 150, 18, 'authors', 'b', {i: (10, True) for i, ch in enumerate(by) if ch.isdigit() or ch in 'A–D' and i in (12, 13, 14, 15, 16)}),
                ('1Department of Testing, Northfield University, Northfield', 180, 14, 'other', 'a', {0: (8, True)}),
                ('2School of Trials, Westfield College, Westfield', 198, 14, 'other', 'a', {0: (8, True)}),
                ('A – Study Design; B – Data Collection; C – Analysis; D – Interpretation', 240, 14, 'other', 'g', {})] + tail(300)
        first, chars = page(1, rows)
        a = parse([(first, chars)])
        self.assertTrue(all(x['marker'] in ('1', '2') for x in a['affiliations']), a['affiliations'])

    def test_unread_sign_marks_keep_their_count(self):
        a = front('Ada Example*, Ben Sample\ufffd, Cora Test\ufffd\ufffd and Dov Trial†',
                  ['* Department of Testing, Northfield University, Northfield.',
                   '\ufffd School of Trials, Westfield College, Westfield.',
                   '\ufffd\ufffd Institute of Studies, Eastwick Hospital, Eastwick.',
                   '† Division of Tests, Lakeside Clinic, Lakeside.'])
        marks = {x['name']: x['markers'] + x['notes'] for x in a['authors']}
        self.assertEqual(marks['Ben Sample'], ['\ufffd'])
        self.assertEqual(marks['Cora Test'], ['\ufffd\ufffd'])
        found = {x['marker']: x['text'] for x in a['affiliations']}
        self.assertTrue(found.get('\ufffd', '').startswith('School of Trials'), found)
        self.assertTrue(found.get('\ufffd\ufffd', '').startswith('Institute of Studies'), found)


    def test_spaced_unread_signs_are_one_mark(self):
        # memo 2 M6: "Name \ufffd \ufffd" in the byline is one mark of two signs
        a = front('Ada Example*, Ben Sample \ufffd \ufffd and Cora Test \ufffd',
                  ['* Department of Testing, Northfield University, Northfield.',
                   '\ufffd School of Trials, Westfield College, Westfield.',
                   '\ufffd\ufffd Institute of Studies, Eastwick Hospital, Eastwick.'])
        marks = {x['name']: x['markers'] + x['notes'] for x in a['authors']}
        self.assertEqual(marks['Ben Sample'], ['\ufffd\ufffd'])
        self.assertEqual(marks['Cora Test'], ['\ufffd'])
        self.assertEqual(sorted(x['marker'] for x in a['affiliations']), ['*', '\ufffd', '\ufffd\ufffd'])


if __name__ == '__main__':
    unittest.main()
