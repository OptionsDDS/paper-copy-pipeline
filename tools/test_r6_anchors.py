"""r6-anchors: the title and author anchors of the front page (round 6 rules T3, T4/T5, T6, T7, A1, A4, A6, C5).

A wrapped title's last row in the title's exact type is title, never authors; a short label set apart above the title,
or one word in large type with a longer large block on the page, is not the title; a subtitle that reads like names
over a row of figures stays with the title; the author line is looked for above the title when nothing stands under
or beside it; a number in brackets after a name is a marker; the author list ends at a label such as "Abstract"; the
printed-byline reader never crashes on byline runs it cannot read. All names and texts are made up."""
import unittest

from test_front8 import boxer, page, paper, parse


def raised(text):
    return {i: (10, True) for i, ch in enumerate(text) if ch.isdigit()}


def tail(y):
    return [('Background: the sites were measured at baseline and twelve months by one examiner.', y, 16, 'main', 'm', {})]


def later():
    return page(2, [('Body text of the second page continues here at length and in the body size.', 200, 16, 'main', 'm1', {})])


class TitleType(unittest.TestCase):
    """T4/T5: every stacked row in the title's exact font and size is title, even when it reads as names."""
    def fixture(self, last_font='Bold', last_size=30, by_font='Regular'):
        by = 'Ada Example1, Ben Sample2, Cora Test1'
        first, chars = page(1, [
            ('Journal of Invented Studies', 40, 40, 'title', 'j', {}, 20, 'Italic'),
            ('Surface Changes of Invented Discs after Three', 120, 30, 'other', 't', {}, 20, 'Bold'),
            ('Cleaning Methods: A Laboratory Comparison of', 156, 30, 'other', 't', {}, 20, 'Bold'),
            ('Brushing Protocols', 192, last_size, 'other', 't', {}, 20, last_font),
            (by, 250, 18, 'authors', 'b', raised(by), 20, by_font),
            ('1Department of Testing, Northfield University, Northfield', 275, 14, 'other', 'a', {0: (8, True)}),
            ('2School of Trials, Westfield College, Westfield', 293, 14, 'other', 'a', {0: (8, True)})] + tail(360))
        return parse([(first, chars), later()])

    def test_last_row_in_title_type_is_title(self):
        a = self.fixture()
        self.assertTrue(a['title']['text'].endswith('Comparison of Brushing Protocols'), a['title']['text'])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Cora Test'])

    def test_names_in_the_title_face_but_smaller_stay_authors(self):
        a = self.fixture(by_font='Bold')
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Cora Test'])

    def test_a_row_in_another_face_is_not_taken_by_this_rule(self):
        a = self.fixture(last_font='Regular')
        self.assertFalse(a['title']['text'].endswith('Brushing Protocols'))


class LabelApart(unittest.TestCase):
    """T3: a short opening row of the proposed title sharing no width with the title's rows is a label."""
    def fixture(self, label_x=700, label='Special Issue'):
        by = 'Ada Example, Ben Sample'
        first, chars = page(1, [
            (label, 60, 30, 'title', 't', {}, label_x, 'Bold'),
            ('Gingival Health in Invented Young Adults', 110, 30, 'title', 't', {}, 20, 'Bold'),
            (by, 170, 18, 'authors', 'b', {}, 20)] + tail(240))
        return parse([(first, chars), later()])

    def test_label_set_apart_is_not_the_title(self):
        a = self.fixture()
        self.assertEqual(a['title']['text'], 'Gingival Health in Invented Young Adults')
        self.assertIn('Special Issue', [r['text'] for r in a.get('article_info', [])])

    def test_short_first_row_sharing_width_stays_title(self):
        a = self.fixture(label_x=20, label='Implant Surfaces')
        self.assertEqual(a['title']['text'], 'Implant Surfaces Gingival Health in Invented Young Adults')


class OneWordLabel(unittest.TestCase):
    """T6: one word in large type is not the title when a longer block in large type is in the top half."""
    def test_one_word_label_gives_way(self):
        by = 'Ada Example, DDS; Ben Sample, PhD'
        first, chars = page(1, [
            ('Invented Disease in Older Adults', 300, 40, 'other', 't', {}, 20, 'Medium'),
            (by, 360, 16, 'other', 'b', {}, 20, 'Black'),
            ('ABSTRACT', 560, 60, 'title', 'x', {}, 500, 'Medium'),
            ('Background. This review summarizes the invented literature on one disease.', 640, 16, 'title', 'x', {}, 500)] + tail(900))
        a = parse([(first, chars), later()])
        self.assertEqual(a['title']['text'], 'Invented Disease in Older Adults')
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample'])
        # memo 1 (M2): the label set aside by T6 is no article-information record; the copy quotes its block
        self.assertEqual(a.get('t6_label_run_ids'), ['run:2'])
        self.assertFalse(a.get('article_info'))

    def test_label_over_a_title_whose_byline_reaches_under_the_label(self):
        # the byline of the real title stands under the label's width, but the title stands between them
        first, chars = page(1, [('PRIMER', 120, 100, 'title', 'x', {}, 700, 'Light'),
                                ('Invented diseases', 300, 50, 'authors', 'a', {}, 300, 'Medium'),
                                ('Ada B. Example1, Ben C. Sample1 and Cora D. Test2', 380, 20, 'authors', 'a',
                                 raised('Ada B. Example1, Ben C. Sample1 and Cora D. Test2'), 300, 'Italic')] + tail(500))
        a = parse([(first, chars), later()])
        self.assertEqual(a['title']['text'], 'Invented diseases')
        self.assertEqual([n['name'] for n in a['authors']], ['Ada B. Example', 'Ben C. Sample', 'Cora D. Test'])

    def test_one_word_title_alone_stays(self):
        first, chars = page(1, [('Periimplantitis', 100, 40, 'title', 't', {}, 20, 'Bold'),
                                ('Ada Example, Ben Sample', 160, 18, 'authors', 'b', {}, 20)] + tail(240))
        a = parse([(first, chars), later()])
        self.assertEqual(a['title']['text'], 'Periimplantitis')


class SubtitleOverFigures(unittest.TestCase):
    """T7: a display row under the title that reads as names is a subtitle when its block holds a row of figures
    and smaller names stand under it."""
    def fixture(self, years=True):
        specs = [('Invented Disease in Adults', 100, 36, 'title', 't', {}, 20, 'Bold'),
                 ('Northern Regional Health Survey', 150, 32, 'title', 't', {}, 20, 'Light')]
        y = 190
        if years:
            specs.append(('2010-2016', 190, 32, 'title', 't', {}, 20, 'Light')); y = 230
        specs += [('Ada Example, PhD; Ben Sample, DDS; Cora Test, MS', y + 40, 20, 'main', 'b', {}, 20, 'Light')]
        first, chars = page(1, specs + tail(y + 160), body=20)
        return parse([(first, chars), later()])

    def test_subtitle_over_years_stays_with_title(self):
        a = self.fixture()
        self.assertEqual(a['title']['text'], 'Invented Disease in Adults: Northern Regional Health Survey 2010-2016')
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Cora Test'])

    def test_without_the_figures_row_the_rule_does_not_fire(self):
        a = self.fixture(years=False)
        self.assertEqual(a['title']['text'], 'Invented Disease in Adults')


class AuthorsAbove(unittest.TestCase):
    """A1: under the title first, then beside it, then above it."""
    def fixture(self, recur=False):
        first, chars = page(1, [
            ('ORIGINAL ARTICLE', 60, 20, 'other', 'o', {}),
            ('A. Example · B. Sample · C. Test', 220, 22, 'title', 't', {}, 20, 'Times-Bold'),
            ('Invented Matrix Proteins in Deep Defects', 260, 36, 'title', 't', {}, 20, 'Gothic'),
            ('Received: 13 October 1999 / Accepted: 10 February 2000', 460, 18, 'authors', 'd', {})] + tail(600))
        specs = [('Body text of the second page continues here at length and in the body size.', 200, 16, 'main', 'm1', {})]
        if recur: specs.append(('A. Example · B. Sample · C. Test', 40, 22, 'furniture', 'f', {}))
        return parse([(first, chars), page(2, specs)])

    def test_names_above_the_title(self):
        a = self.fixture()
        self.assertEqual([n['name'] for n in a['authors']], ['A. Example', 'B. Sample', 'C. Test'])
        self.assertIn('authors read from the row above the title', a['flags'])

    def test_a_recurring_row_above_is_not_the_author_line(self):
        a = self.fixture(recur=True)
        self.assertEqual(a['authors'], [])


class CitationIsNoAuthorLine(unittest.TestCase):
    """A9 then A1: the article's own citation under the title is no author line; the name beside the title is."""
    def fixture(self, cite=True):
        rows = [('Invented plaque: biological', 300, 56, 'title', 't', {}, 20, 'Display'),
                ('P. D. Example', 300, 18, 'other', 's', {}, 800, 'Bold'),
                ('Northfield Dental Institute, and Health Agency', 326, 16, 'other', 's', {}, 800, 'Regular'),
                ('Agency, Centre for Invented Research, Northfield', 345, 16, 'other', 's', {}, 800, 'Regular'),
                ('of a biofilm and life-style', 363, 56, 'title', 't', {}, 20, 'Display')]
        if cite:
            rows += [('Example PD. Invented plaque: biological significance of a biofilm and community life-', 460, 16, 'authors', 'c', {}, 20, 'Italic'),
                     ('style. J Inv Periodontol 2005; 32 (Suppl. 6): 7-15.', 480, 16, 'authors', 'c', {}, 20, 'Italic')]
        first, chars = page(1, rows + tail(600))
        return parse([(first, chars), later()])

    def test_citation_gives_way_to_the_name_beside_the_title(self):
        a = self.fixture()
        self.assertEqual([n['name'] for n in a['authors']], ['P. D. Example'])
        self.assertIn('authors read from a sidebar beside the title', a['flags'])
        # memo 1 (M1): the institution rows under the names stay printed, as the unmarked affiliation
        self.assertEqual([c['text'] for c in a.get('unmarked_affiliation_candidates', [])],
                         ['Northfield Dental Institute, and Health Agency Agency, Centre for Invented Research, Northfield'])


class BesideRowsCutIntoRuns(unittest.TestCase):
    """Memo 2 (M1): the institution row under names beside the title is read as one printed row even when its first
    letters are a run of their own; it and the row under it stay printed as the unmarked affiliation."""
    def test_row_cut_into_runs(self):
        rows = [('Invented plaque: biological', 300, 56, 'title', 't', {}, 20, 'Display'),
                ('P. D. Example', 300, 18, 'title', 'side', {}, 800, 'Bold'),
                ('Wes', 326, 16, 'title', 'side', {}, 800, 'Regular'),
                ('tmoor Oral Health Institute,', 326, 16, 'title', 'side', {}, 824, 'Regular'),
                ('Lindale, Ruritania', 345, 16, 'title', 'side', {}, 800, 'Regular'),
                ('of a biofilm and life-style', 363, 56, 'title', 't', {}, 20, 'Display')]
        first, chars = page(1, rows + tail(600))
        a = parse([(first, chars), later()])
        self.assertEqual([n['name'] for n in a['authors']], ['P. D. Example'])
        self.assertEqual([c['text'] for c in a.get('unmarked_affiliation_candidates', [])],
                         ['Westmoor Oral Health Institute, Lindale, Ruritania'])


class BracketMarkers(unittest.TestCase):
    """A4: a number in brackets after a name is a marker."""
    def test_round_brackets(self):
        by = 'Ada Example (1), Ben Sample (2), Cora Test (2)'
        first, chars = page(1, [('Invented Implants in Dry Mouth', 100, 30, 'title', 't', {}),
                                (by, 150, 18, 'title', 't', {})] + tail(260))
        a = parse([(first, chars), later()])
        self.assertEqual([(n['name'], n['markers']) for n in a['authors']],
                         [('Ada Example', ['1']), ('Ben Sample', ['2']), ('Cora Test', ['2'])])
        self.assertEqual(boxer.byline_name_groups([by]), ['Ada Example', 'Ben Sample', 'Cora Test'])

    def test_square_brackets(self):
        by = 'Ada Example [1], Ben Sample [2]'
        first, chars = page(1, [('Invented Root Coverage Technique', 100, 30, 'title', 't', {}),
                                (by, 150, 18, 'authors', 'b', {})] + tail(260))
        a = parse([(first, chars), later()])
        self.assertEqual([(n['name'], n['markers']) for n in a['authors']], [('Ada Example', ['1']), ('Ben Sample', ['2'])])

    def test_bracketed_letters_are_no_marker(self):
        by = 'Ada Example (DDS), Ben Sample (PhD)'
        first, chars = page(1, [('Invented Root Coverage Technique', 100, 30, 'title', 't', {}),
                                (by, 150, 18, 'authors', 'b', {})] + tail(260))
        a = parse([(first, chars), later()])
        self.assertTrue(all(not n['markers'] for n in a['authors']))


class ListEndsAtLabel(unittest.TestCase):
    """A6: the author list ends at a label such as "Abstract", also in the names' size."""
    def test_abstract_row_in_the_names_size_ends_the_list(self):
        by = 'Ada Example1, Ben Sample1 and Cora Test2'
        first, chars = page(1, [('Invented Disease in Pregnancy', 100, 40, 'title', 't', {}),
                                (by, 160, 18, 'authors', 'b', raised(by), 20, 'Italic'),
                                ('Abstract | Invented disease is common and may change the course of things.', 185, 18, 'authors', 'b', {}, 20, 'Light'),
                                ('The aim of this short review is to bring the main findings together.', 208, 18, 'authors', 'b', {}, 20, 'Light')]
                       + tail(300))
        a = parse([(first, chars), later()])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample', 'Cora Test'])
        # memo 1: the label row the list ends at is recorded as released, so the copy keeps it printed
        self.assertIn('run:2', a.get('released_run_ids', []))


class NeverCrash(unittest.TestCase):
    """C5: byline runs that are not readable rows of their block (a later column's prose) give no crash."""
    def test_byline_run_outside_the_readable_rows_of_its_block(self):
        by = 'Ada Example1 and Ben Sample2'
        first, chars = page(1, [('Invented Title of a Long Review Article', 100, 30, 'title', 't', {}),
                                (by, 150, 16, 'authors', 'b', raised(by)),
                                ('Cora Test3', 400, 16, 'other', 'c', raised('Cora Test3'))] + tail(500))
        first['elements'][2]['angle'] = 90   # this byline run is no upright text row of its block
        au = {'title': {'text': 'Invented Title of a Long Review Article', 'box_px': [20, 100, 600, 121]},
              'authors': [], 'author_run_ids': ['run:1', 'run:2'], 'byline_lines': [{'run_ids': ['run:1', 'run:2']}]}
        records, count = paper.printed_front_matter([first], au)
        self.assertEqual(count, 2)


if __name__ == '__main__':
    unittest.main()
