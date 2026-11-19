"""masthead: banners and logos set as text are never the title (lane masthead, 2026-11-04).

R1 a display row with no name separator is never a byline; R2 recurrence on later pages is tested
on joined rows; R3 the title is chosen by adjacency (a proposed title off the alignment of a lower
title-plus-byline pair, or standing alone in the top band in a face used nowhere else, is a
masthead); R4 with no byline-shaped row nothing is promoted. Synthetic pages only."""
import importlib.util
import statistics
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); mod.__dict__['__file__'] = str(path); spec.loader.exec_module(mod)
    return mod


boxer = module('masthead_boxer', ROOT/'standalone/element_boxer_sc.py')
paper = module('masthead_copy', ROOT/'copy_paper.py')


def page(number, specs, body=16, height=1400):
    """specs: (text, y, size, cls, block, special[, x[, font]]); special maps character offsets to
    (size, raised). Runs sharing a y share a rule-1 line."""
    chars = []; runs = []; blocks = []; classes = []; lines = {}
    for i, spec in enumerate(specs):
        text, y, size, cls, bid, special = spec[:6]
        x = spec[6] if len(spec) > 6 else 20; font = spec[7] if len(spec) > 7 else 'Regular'
        x0 = x; ids = []; sizes = []
        for j, ch in enumerate(text):
            em, raised = special.get(j, (size, False))
            if not ch.isspace():
                ids.append(len(chars)); sizes.append(em)
                chars.append(dict(text=ch, x0=x, x1=x+.45*em, y0=y-(5 if raised else 0),
                                  y1=y+.7*em-(5 if raised else 0), size=em, font=font,
                                  origin=(x, y+.7*em), adv_x1=x+.5*em))
            x += .5*em
        line = lines.setdefault(round(y), len(lines))
        e = dict(id=f'run:{i}', text=text, kind='text', line=line, angle=0, size_px=size, font=font,
                 run_size_px=statistics.median(sizes), char_ids=ids, box_px=[x0, y, x, y+.7*size])
        runs.append(e)
        b = next((b for b in blocks if b['id'] == bid), None)
        if b:
            b['members'].append(e['id'])
            b['box_px'] = [min(b['box_px'][0], x0), min(b['box_px'][1], y), max(b['box_px'][2], x), max(b['box_px'][3], y+.7*size)]
        else:
            blocks.append(dict(id=bid, members=[e['id']], box_px=list(e['box_px'])))
            classes.append(dict(id=bid, cls=cls, box_px=list(e['box_px'])))
    return dict(page=number, elements=runs, blocks=blocks, art=[], region_box_px=[0, 0, 1000, height],
                main_text=dict(body_size_px=body, blocks=classes)), chars


def parse(fixtures):
    paths = [f'page-{i+1:02}.json' for i in range(len(fixtures))]
    with patch.object(boxer, 'page_files', return_value=paths), \
         patch.object(boxer, 'read_json', side_effect=lambda p: fixtures[paths.index(p)][0]), \
         patch.object(boxer, 'pdfium_characters', side_effect=lambda p, n: fixtures[n-1][1]), \
         patch.object(boxer, 'front_backgrounds', return_value=[]), \
         patch.object(boxer, 'write_json'):
        return boxer.authors_and_affiliations('unused', 'unused')


def raised_digits(text, size=10):
    return {i: (size, True) for i, ch in enumerate(text) if ch.isdigit()}


BYLINE = 'Ann B. Carter1, David E. Fong2 and Grace H. Ito1'
TITLE1, TITLE2 = 'Regenerative approaches to periodontal defects', 'in a practice-based cohort study'
BODY = 'The body text of the paper starts here and runs on at length across the column.'


def later(*specs):
    return page(2, list(specs) + [(BODY, 400, 16, 'main', 'm', {})])


class DisplayRowIsNoByline(unittest.TestCase):
    """R1: a display-size row with no name separator does not veto the banner test."""
    def fixture(self, subtitle):
        first, chars = page(1, [
            ('WORKSHOP SERIES', 40, 36, 'title', 't', {}, 20, 'Sans-Bold'),
            (subtitle, 90, 30, 'title', 's', {}, 20, 'Serif-Italic'),
            (TITLE1, 150, 30, 'aside', 'a', {}, 20, 'Serif-Bold'),
            (TITLE2, 185, 30, 'aside', 'a', {}, 20, 'Serif-Bold'),
            (BYLINE, 240, 18, 'aside', 'b', raised_digits(BYLINE)),
            (BODY, 330, 16, 'main', 'm', {})], body=16)
        first['art'] = [dict(kind='rule', box_px=[20, 80, 980, 81])]   # a rule under the banner
        return [(first, chars), later()]

    def test_display_subtitle_without_separator_is_not_a_byline(self):
        a = parse(self.fixture('Enhancing Periodontal Health Through Regenerative Approaches'))
        self.assertEqual(a['title']['text'], f'{TITLE1} {TITLE2}')
        self.assertEqual([n['name'] for n in a['authors']], ['Ann B. Carter', 'David E. Fong', 'Grace H. Ito'])
        self.assertIn('WORKSHOP SERIES', [r['text'] for r in a.get('article_info', [])])

    def test_display_row_with_name_separators_still_vetoes(self):
        # the same row set as names with commas: the top-band title keeps its own byline
        a = parse(self.fixture('Enhancing Periodontal, Health Through Regenerative'))
        self.assertEqual(a['title']['text'], 'WORKSHOP SERIES')


class RecurrenceOnJoinedRows(unittest.TestCase):
    """R2: a banner whose running version is split into runs on later pages recurs."""
    def fixture(self, gap):
        first, chars = page(1, [
            ('PRACTICAL APPLICATIONS', 40, 36, 'title', 't', {}, 20, 'Sans'),
            (TITLE1, 110, 30, 'main', 'a', {}, 20, 'Sans'),   # one face: no series-label reading
            (TITLE2, 145, 30, 'main', 'a', {}, 20, 'Sans'),
            (BYLINE, 200, 18, 'main', 'b', raised_digits(BYLINE)),
            (BODY, 300, 16, 'main', 'm', {})], body=16)
        # running head: two runs on one printed row, 'gap' px apart at 14 px
        run2_x = 600 + .5*14*len('PRACTICAL') + gap
        return [(first, chars), later(('PRACTICAL', 30, 14, 'furniture', 'f', {}, 600, 'Sans'),
                                      ('APPLICATIONS', 30, 14, 'furniture', 'f', {}, run2_x, 'Sans'))]

    def test_split_running_head_recurs_as_one_row(self):
        a = parse(self.fixture(gap=19))
        self.assertEqual(a['title']['text'], f'{TITLE1} {TITLE2}')
        self.assertEqual(len(a['authors']), 3)

    def test_runs_farther_apart_than_two_letter_heights_are_not_joined(self):
        a = parse(self.fixture(gap=60))
        self.assertEqual(a['title']['text'], 'PRACTICAL APPLICATIONS')


class AdjacencyChoosesTheTitle(unittest.TestCase):
    """R3 and R4: a logo off the alignment of a lower title-plus-byline pair is a masthead."""
    def fixture(self, logo_x=700, byline=BYLINE, logo_font='Bembo-Bold', page2_font='Palatino', logo_y=200, title=(TITLE1, TITLE2)):
        first, chars = page(1, [
            ('Sleep Research Reviews, Vol. 4, No. 1, p 27-43, 2000', logo_y - 5, 15, 'other', 'c', {}, 20, 'Palatino'),
            ('SLEEP', logo_y, 44, 'title', 't', {}, logo_x, logo_font),
            ('MEDICINE', logo_y + 32, 23, 'title', 't', {}, logo_x, logo_font),
            (title[0], logo_y + 140, 33, 'main', 'a', {}, 20, 'Univers-Bold'),
            (title[1], logo_y + 180, 33, 'main', 'a', {}, 20, 'Univers-Bold'),
            (byline, logo_y + 245, 25, 'main', 'b', raised_digits(byline), 20, 'Univers'),
            ('1Sleep Unit, Department of Clinical Neurophysiology, University of Gothenburg', logo_y + 300, 20, 'main', 'f', {0: (12, True)}, 20, 'Palatino'),
            (BODY, logo_y + 400, 20, 'main', 'm', {}, 20, 'Palatino')], body=20, height=1750)
        return [(first, chars), page(2, [(BODY, 400, 20, 'main', 'm', {}, 20, page2_font)], body=20, height=1750)]

    def test_offaxis_logo_above_title_and_byline_is_a_masthead(self):
        a = parse(self.fixture())
        self.assertEqual(a['title']['text'], f'{TITLE1} {TITLE2}')
        self.assertEqual([n['name'] for n in a['authors']], ['Ann B. Carter', 'David E. Fong', 'Grace H. Ito'])
        self.assertEqual([r['text'] for r in a['article_info']], ['SLEEP', 'MEDICINE'])

    def test_no_byline_shaped_row_promotes_nothing(self):
        # R4: the lower display block has prose under it, not names: the largest type stays
        a = parse(self.fixture(byline='the results of a survey were reported in this issue of the journal'))
        # Round 6 rule T6 supersedes the earlier 'SLEEP: MEDICINE' expectation: one word in large type is not the title
        # when a longer block in large type stands in the top half of the page.
        self.assertEqual(a['title']['text'], f'{TITLE1} {TITLE2}')

    def test_aligned_large_row_is_not_rejected_by_alignment(self):
        # same left edge as the lower pair, below the top band, its face used on page 2 too
        a = parse(self.fixture(logo_x=20, page2_font='Bembo-Bold'))
        # Round 6 rule T6 supersedes the earlier 'SLEEP: MEDICINE' expectation: one word in large type is not the title
        # when a longer block in large type stands in the top half of the page.
        self.assertEqual(a['title']['text'], f'{TITLE1} {TITLE2}')

    def test_lone_face_in_top_band_is_a_logo(self):
        # aligned with the pair, but in the top band and in a face used nowhere else on the paper
        a = parse(self.fixture(logo_x=20, logo_y=120))
        self.assertEqual(a['title']['text'], f'{TITLE1} {TITLE2}')

    def test_face_used_on_later_pages_is_no_logo_evidence(self):
        a = parse(self.fixture(logo_x=20, logo_y=120, page2_font='Bembo-Bold'))
        # Round 6 rule T6 supersedes the earlier 'SLEEP: MEDICINE' expectation: one word in large type is not the title
        # when a longer block in large type stands in the top half of the page.
        self.assertEqual(a['title']['text'], f'{TITLE1} {TITLE2}')

    def test_title_with_its_own_byline_stays(self):
        first, chars = page(1, [
            ('A Short Large Title', 100, 44, 'title', 't', {}, 600, 'Display'),
            ('Mary Ann Smith1 and Kim Lee2', 150, 22, 'authors', 'ab', raised_digits('Mary Ann Smith1 and Kim Lee2'), 600),
            (TITLE1, 300, 33, 'main', 'a', {}, 20, 'Univers-Bold'),
            (TITLE2, 340, 33, 'main', 'a', {}, 20, 'Univers-Bold'),
            (BYLINE, 405, 25, 'main', 'b', raised_digits(BYLINE), 20, 'Univers'),
            (BODY, 500, 20, 'main', 'm', {})], body=20, height=1750)
        a = parse([(first, chars), page(2, [(BODY, 400, 20, 'main', 'm', {})], body=20, height=1750)])
        self.assertEqual(a['title']['text'], 'A Short Large Title')

    # Re-ladder (2026-11-05)
    def test_lone_face_logo_overlapping_the_title_width_below_the_top_band_is_a_logo(self):
        # off the pair's axis (left edge and centre), standing out of its width by less than an
        # em, below the top band, in a face used nowhere else on the paper (MIMIC2 form)
        a = parse(self.fixture(logo_x=690, logo_y=300))
        self.assertEqual(a['title']['text'], f'{TITLE1} {TITLE2}')
        self.assertEqual([n['name'] for n in a['authors']], ['Ann B. Carter', 'David E. Fong', 'Grace H. Ito'])

    def test_overlapping_logo_in_a_face_used_on_later_pages_stays(self):
        a = parse(self.fixture(logo_x=690, logo_y=300, page2_font='Bembo-Bold'))
        # Round 6 rule T6 supersedes the earlier 'SLEEP: MEDICINE' expectation: one word in large type is not the title
        # when a longer block in large type stands in the top half of the page.
        self.assertEqual(a['title']['text'], f'{TITLE1} {TITLE2}')

    def test_title_case_title_row_is_not_the_logos_own_byline(self):
        # the pair's first title row reads as names (capitalised words and "and"); it is the
        # pair's title, which has its own smaller byline, not a byline of the logo above it
        rows = ('Regenerative Approaches and Periodontal Defects', 'In Practice Based Cohorts')
        a = parse(self.fixture(title=rows))
        self.assertEqual(a['title']['text'], ' '.join(rows))
        self.assertEqual([n['name'] for n in a['authors']], ['Ann B. Carter', 'David E. Fong', 'Grace H. Ito'])
        a = parse(self.fixture(title=rows, byline='the results of a survey were reported in this issue of the journal'))
        # Round 6 rule T6 supersedes the earlier 'SLEEP: MEDICINE' expectation: one word in large type is not the title
        # when a longer block in large type stands in the top half of the page.
        self.assertEqual(a['title']['text'], ' '.join(rows))


class WrappedTitleWordAfterReselection(unittest.TestCase):
    """Re-ladder (2026-11-05): a title-size row stacked directly under a reselected title is title text
    even when it is one article-type word (AS14 form); above the title such a word stays a label."""
    def fixture(self, tail_size=30):
        byline = 'Ann B. Carter1, David E. Fong2 and Grace H. Ito1'
        first, chars = page(1, [
            ('Journal of Periodontal Practice', 100, 36, 'title', 't', {}),
            ('Review', 250, 22, 'other', 'k', {}),
            ('Is grafting a viable alternative to open flap surgery? A critical', 300, 30, 'main', 'a', {}),
            ('review', 330, tail_size, 'main', 'a2', {}),
            (byline, 380, 24, 'main', 'b', raised_digits(byline)),
            ('1Department of Periodontology, University of Northfield', 420, 14, 'main', 'f', {0: (9, True)}),
            ('2Department of Prosthodontics, University of Southfield', 440, 14, 'main', 'f', {0: (9, True)}),
            (BODY, 520, 16, 'main', 'm', {})], body=16)
        return [(first, chars), later()]

    def test_one_word_continuation_row_ends_the_title(self):
        a = parse(self.fixture())
        self.assertEqual(a['title']['text'], 'Is grafting a viable alternative to open flap surgery? A critical review')
        self.assertEqual([n['name'] for n in a['authors']], ['Ann B. Carter', 'David E. Fong', 'Grace H. Ito'])
        self.assertNotIn('review', [n['name'] for n in a['authors']])

    def test_smaller_row_is_no_continuation(self):
        # set smaller than the title (outside the size tolerance) the row is not the title's last word
        a = parse(self.fixture(tail_size=24))
        self.assertEqual(a['title']['text'], 'Is grafting a viable alternative to open flap surgery? A critical')


class RaisedLabelAddressBand(unittest.TestCase):
    """Directly below the byline, a body-size block opening with a raised label the byline uses is
    an address band, whatever word follows the label (AP10 "1Sleep Unit, ...")."""
    def fixture(self, label='1'):
        byline = 'Ann B. Carter1 and David E. Fong2'
        address = f'{label}Sleep Unit, Department of Neurophysiology, University of Gothenburg, Sweden; 2Centre for Sleep Studies, University of Montreal, Canada'
        special = {0: (10, True), address.index('2Centre'): (10, True)}
        first, chars = page(1, [
            (TITLE1, 100, 33, 'title', 't', {}),
            (TITLE2, 140, 33, 'title', 't', {}),
            (byline, 200, 25, 'main', 'b', raised_digits(byline)),
            (address, 250, 20, 'main', 'f', special),
            (BODY, 330, 20, 'main', 'm', {})], body=20)
        return [(first, chars), page(2, [(BODY, 400, 20, 'main', 'm', {})], body=20)]

    def test_raised_byline_label_opens_an_address_band(self):
        a = parse(self.fixture())
        self.assertEqual([f['marker'] for f in a['affiliations']], ['1', '2'])
        self.assertTrue(a['affiliations'][0]['text'].startswith('Sleep Unit, Department of Neurophysiology'))
        self.assertEqual(a['checks']['status'], 'verified')

    def test_label_the_byline_does_not_use_is_no_address_band(self):
        a = parse(self.fixture(label='3'))
        self.assertEqual(a['affiliations'], [])



class AddressOpeningPunctuation(unittest.TestCase):
    """Copier: an address rebuilt from its repaired native rows keeps the punctuation it opens with."""
    def front(self, native_text, rule8_text):
        native = dict(kind='text', id='r', text=native_text, angle=0, box_px=[0, 0, 100, 20], char_ids=[], _chars=[])
        page = dict(elements=[native], blocks=[dict(id='b', members=['r'])], copy_prose_glyphs=[dict(run='r')])
        author = dict(affiliations=[dict(marker='2', block='b', text=rule8_text)])
        joiner = type('J', (), {'lines': staticmethod(lambda lines: ' '.join(lines))})
        return paper.front_matter([page], author, joiner)

    def test_opening_bracket_is_kept(self):
        self.assertEqual(self.front('2(1) Centre d’étude sur le sommeil, Montréal', '(1) Centre d’e´tude sur le sommeil, Montre´al'),
                         [('2', '(1) Centre d’étude sur le sommeil, Montréal', 1)])

    def test_address_without_opening_punctuation_is_unchanged(self):
        self.assertEqual(self.front('2 Faculté de Médecine, Montréal', 'Faculte´de Me´decine, Montre´al'),
                         [('2', 'Faculté de Médecine, Montréal', 1)])


if __name__ == '__main__':
    unittest.main()
