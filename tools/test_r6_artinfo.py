"""Lane r6-artinfo (round 6): the article-information rules I4/I10 (records cut at their labels before the licence
cleanup) and I5 (a held lowercase entry that tops a column continues the paragraph at the foot of the column to
its left). Made-up rows only, no paper text."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('r6artinfo_copy', ROOT / 'copy_paper.py')
copy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copy)

join = lambda rows: ' '.join(rows)


class CutRecords(unittest.TestCase):
    ROWS = ['Citation: Example A, Sample B (2020) A made-up title. Some Journal 1(2): e3. doi:10.0000/x.1',
            'Editor: Carla Model, Example Institute, Country',
            'Received May 1, 2020; Accepted June 2, 2020; Published July 3, 2020',
            'Copyright: � 2020 Example et al. This is an open-access article distributed under the terms of the',
            'licence named here, which permits use, provided the original author and source are credited.',
            'Funding: This work was supported by grant 1 from a made-up trust, which took no part in the',
            'design of the study.',
            'Competing Interests: None of the made-up authors reports a',
            'competing interest of any kind.',
            '* E-mail: someone@example.org']

    def test_licence_record_alone_is_removed(self):
        rows, licence = copy.cut_records([list(self.ROWS)], join, [])
        self.assertEqual([r[0][:8] for r in rows], ['Citation', 'Editor: ', 'Received', 'Copyrigh', 'Funding:', 'Competin', '* E-mail'])
        self.assertEqual(len(licence), 1)
        self.assertTrue(licence[0][0].startswith('Copyright'))
        self.assertEqual(len(licence[0]), 2)          # the licence sentence's wrapped row goes with it
        kept = [copy.clean_article_info(join(r)) for r in rows if not any(r is x for x in licence)]
        self.assertTrue(all(kept))                     # nothing after the licence is cut away
        self.assertIn('design of the study.', kept[3])
        self.assertIn('competing interest of any kind.', kept[4])   # a wrapped row opening with a label word in lower case

    def test_record_the_cleanup_leaves_whole_is_unchanged(self):
        rows = [self.ROWS[0], self.ROWS[1], self.ROWS[2]]
        out, licence = copy.cut_records([rows], join, [])
        self.assertEqual(out, [rows]); self.assertEqual(licence, [])

    def test_wrapped_licence_sentence_alone_stays_one_record(self):
        rows = [self.ROWS[3], self.ROWS[4]]
        out, licence = copy.cut_records([rows], join, [])
        self.assertEqual(out, [rows]); self.assertEqual(licence, [])

    def test_explicitly_owned_rows_are_never_cut(self):
        rows = list(self.ROWS)
        out, licence = copy.cut_records([rows], join, [rows])
        self.assertEqual(out, [rows]); self.assertEqual(licence, [])

    def test_no_label_row_after_the_licence_opening_is_unchanged(self):
        rows = ['Received May 1, 2020. This is an open-access article distributed under the terms of the',
                'licence named here, which permits use.']
        out, licence = copy.cut_records([rows], join, [])
        self.assertEqual(out, [rows]); self.assertEqual(licence, [])


class HeldEntryColumnOrder(unittest.TestCase):
    """Two open paragraphs on the front page: one at the foot of column 1, one at the foot of column 2. The held
    lowercase rows top column 3; they continue the paragraph of column 2 (the column directly to their left)."""
    body = 10

    def items(self):
        return [dict(kind='para', page=1, text='The first paragraph of the made-up body ends without a stop at the',
                     box=[50, 400, 200, 700], flow_last_box=[50, 680, 200, 700]),
                dict(kind='para', page=1, text='The second paragraph also stops at the column foot, with the',
                     box=[220, 300, 370, 720], flow_last_box=[220, 700, 370, 720])]

    def test_column_top_entry_goes_to_the_column_on_its_left(self):
        held = dict(text='following words of the sentence that ends here.', box=[390, 420, 540, 432])
        self.assertEqual(copy.place_front_resume(self.items(), held, 1, self.body), 1)

    def test_entry_directly_under_a_paragraph_keeps_the_old_rule(self):
        items = self.items()
        held = dict(text='following words of the sentence that ends here.', box=[52, 705, 198, 715])
        self.assertEqual(copy.place_front_resume(items, held, 1, self.body), 0)

    def test_entry_left_of_every_paragraph_is_not_placed(self):
        items = self.items()
        held = dict(text='following words of the sentence that ends here.', box=[10, 420, 45, 432])
        self.assertIsNone(copy.place_front_resume(items, held, 1, self.body))


if __name__ == '__main__':
    unittest.main()


class PageOneDoiForms(unittest.TestCase):
    """I6/I9: a page-one DOI that the page reading dropped as furniture in a band is kept in its printed form."""

    def page(self, text, dropped=True, y=20):
        e = dict(id='run:1', kind='text', angle=0, text=text, box_px=[50, y, 300, y + 10], size_px=10)
        body = dict(id='run:2', kind='text', angle=0, text='A made-up body row of the page.', box_px=[50, 400, 500, 410], size_px=10)
        return dict(page=1, region_box_px=[0, 0, 600, 800], elements=[e, body],
                    main_text=dict(furniture=[dict(why='made-up', members=['run:1'])] if dropped else []))

    def texts(self, page):
        return [str(group[0]) for group in copy.article_doi_lines(page) + copy.article_doi_lines(page, other_forms=True)]

    def test_other_forms_come_apart_from_the_old_ones(self):
        self.assertEqual(copy.article_doi_lines(self.page('DOI 10.0000/made.up.11')), [])
        self.assertEqual(copy.article_doi_lines(self.page('10.0000/made.up.12'), other_forms=True), [])

    def test_label_without_colon_and_resolver_address(self):
        self.assertEqual(self.texts(self.page('DOI 10.0000/made.up.1')), ['DOI 10.0000/made.up.1'])
        self.assertEqual(self.texts(self.page('https://doi.org/10.0000/made.up.2')), ['https://doi.org/10.0000/made.up.2'])

    def test_a_run_the_page_reading_kept_is_never_taken_again(self):
        self.assertEqual(self.texts(self.page('https://doi.org/10.0000/made.up.3', dropped=False)), [])

    def test_outside_the_bands_it_is_not_taken(self):
        self.assertEqual(self.texts(self.page('DOI 10.0000/made.up.4', y=400)), [])

    def test_old_forms_unchanged(self):
        self.assertEqual(self.texts(self.page('DOI: 10.0000/made.up.5', dropped=False, y=400)), ['DOI: 10.0000/made.up.5'])
        self.assertEqual(self.texts(self.page('10.0000/made.up.6', dropped=False)), ['10.0000/made.up.6'])


class LicenceCleanup(unittest.TestCase):
    def test_copyright_label_with_colon_opens_the_notice(self):
        self.assertEqual(copy.clean_article_info('Copyright: © 2020 by the made-up authors. Licensee X.'), '')
        self.assertEqual(copy.clean_article_info('Copyright: � 2020 Example et al.'), '')
        self.assertEqual(copy.clean_article_info('Received 1 May 2020. Copyright: © 2020 X.'), 'Received 1 May 2020.')

    def test_a_later_licence_row_cuts_the_record(self):
        rows = ['Some Journal 2020, Vol. 1(2) 3-4', '© A Made-up Society 2020', 'Reuse notes: example.org/permissions',
                'DOI: 10.0000/made.up.7']
        out, licence = copy.cut_records([rows], join, [])
        self.assertEqual([r[0] for r in out], rows)
        self.assertEqual([r[0] for r in licence], [rows[1]])


class BrokenIdentifiers(unittest.TestCase):
    def test_doi_broken_at_a_row_end_is_joined(self):
        rows = ['Example A. A made-up title. Some J 2020; 1: 2-3. doi: 10.0000/j.1234-567X.', '2020.00012.x.']
        self.assertEqual(copy.join_broken_identifiers(join(rows), rows),
                         'Example A. A made-up title. Some J 2020; 1: 2-3. doi: 10.0000/j.1234-567X.2020.00012.x.')

    def test_address_broken_at_a_row_end_is_joined(self):
        rows = ['Correspondence: made-up.person@example.', 'org']
        self.assertEqual(copy.join_broken_identifiers(join(rows), rows), 'Correspondence: made-up.person@example.org')

    def test_complete_doi_then_a_new_row_is_unchanged(self):
        rows = ['DOI: 10.0000/made.up.8.', 'Received 1 May 2020']
        self.assertEqual(copy.join_broken_identifiers(join(rows), rows), join(rows))
        rows = ['DOI: 10.0000/made.up.8', '2020;1:2']
        self.assertEqual(copy.join_broken_identifiers(join(rows), rows), join(rows))


class UnlabelledLowercaseEntry(unittest.TestCase):
    def test_sentence_piece_is_no_record(self):
        self.assertTrue(copy.unlabelled_lowercase_entry('changes of the made-up kind were seen in some specimens after loading.'))
        self.assertTrue(copy.unlabelled_lowercase_entry('and 3 Made-up Institute, Sampletown, Country'))

    def test_labelled_or_formed_entries_stay_records(self):
        for t in ['e-mail: someone@example.org', 'journal homepage: www.example.org/made-up', 'doi: 10.0000/made.up.9',
                  'a Professor of Made-up Studies, University of Exampleton.', 'Received 1 May 2020; accepted 2 June 2020',
                  'https://doi.org/10.0000/made.up.10', 'published online: 3 July 2020 in a made-up issue']:
            self.assertFalse(copy.unlabelled_lowercase_entry(t), t)


class PublishedLabel(unittest.TestCase):
    def test_published_is_a_date_label_only_before_a_date(self):
        self.assertTrue(copy.INFO_LABEL.match('Published: 3 July 2020'))
        self.assertTrue(copy.INFO_LABEL.match('Published online 3 July 2020'))
        self.assertTrue(copy.INFO_LABEL.match('Published July 3, 2020'))
        self.assertFalse(copy.INFO_LABEL.match('Published by a Made-up Press Ltd'))


class LicenceContinuation(unittest.TestCase):
    """I3/I10: a label-less row set directly under a copyright row, in its size, is that notice's second row."""

    def setUp(self):
        copy.trace_reset()

    def run_(self, i, text, y, x=500, size=14):
        return dict(id=f'run:{i}', kind='text', text=text, box_px=[x, y, x + 240, y + size], size_px=size, run_size_px=size)

    def records(self, gap):
        es = [self.run_(1, '© 2020 A Made-up Press Ltd.', 1000), self.run_(2, 'Distributed by a made-up house', 1014 + gap),
              self.run_(3, 'Received 1 May 2020', 1100)]
        page = dict(page=1, elements=es)
        recs = [[copy.trace_row(1, [e], e['text'])] for e in es]
        return page, recs

    def test_row_directly_under_the_notice_goes_with_it(self):
        page, recs = self.records(gap=4)
        self.assertEqual([str(r[0]) for r in copy.licence_continuations(recs, page)], ['Distributed by a made-up house'])

    def test_a_row_after_a_gap_or_with_a_label_stays(self):
        page, recs = self.records(gap=20)
        self.assertEqual(copy.licence_continuations(recs, page), [])


class MemoOneShapes(unittest.TestCase):
    def test_m2_contact_record_stays_a_record(self):
        self.assertFalse(copy.unlabelled_lowercase_entry('correspondence and reprint requests to: A. Made, 1 Example Road, Town. E-mail: a.made@example.org'))
        self.assertFalse(copy.unlabelled_lowercase_entry('address for reprints: made-up person, example street 2, town'))
        self.assertTrue(copy.unlabelled_lowercase_entry('and 2 Made-up Institute, Town; *corresponding author, someone@example.org'))

    def test_m1_term_list(self):
        self.assertTrue(copy.keyword_term_list('loading; thickness; made-up material'))
        self.assertTrue(copy.keyword_term_list('loading, thickness, made-up material, test'))
        self.assertFalse(copy.keyword_term_list('changes of the made-up kind were seen, and then more.'))


class MemoTwoShape(unittest.TestCase):
    """M3: a citation after the copyright sign stays a record; only the sign and a rights sentence go."""

    def test_citation_after_the_sign_is_kept(self):
        t = 'Peer reviewed DOI: 10.0000/made.up.13 © Journal of Made-up Studies 2020; 12: 34-56'
        self.assertEqual(copy.clean_article_info(t), 'Peer reviewed DOI: 10.0000/made.up.13 Journal of Made-up Studies 2020; 12: 34-56')
        self.assertEqual(copy.clean_article_info('© Made-up J 2021;3(2):10-19. All rights reserved.'), 'Made-up J 2021;3(2):10-19.')

    def test_rights_notice_alone_still_goes(self):
        self.assertEqual(copy.clean_article_info('© 2021 A Made-up Press Ltd. All rights reserved.'), '')
        self.assertEqual(copy.clean_article_info('Received 1 May 2020. Copyright: © 2020 X.'), 'Received 1 May 2020.')

    def test_unread_mark_alone_is_no_sign(self):
        self.assertIsNone(copy.sign_citation('Example � Made-up J 2021;3:10-19'))
