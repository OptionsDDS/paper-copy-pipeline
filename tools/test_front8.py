"""front8: top-band banners over the title, degrees and middle-dot separators, bylines cut at a
same-row affiliation, other-column rows passed over, labelled end panels, next-page marked
addresses, From-the footnotes; copier: panel rows leave blocks by run id, leftover conjunctions."""
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


boxer = module('front8_boxer', ROOT/'standalone/element_boxer_sc.py')
paper = module('front8_copy', ROOT/'copy_paper.py')


def page(number, specs, body=16, height=1400):
    """specs: (text, y, size, cls, block, special) or with x and font appended.

    special maps character offsets to (size, raised). Runs sharing a y share a
    rule-1 line; a later page carries the same run ids as the first.
    """
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
            b['members'].append(e['id']); b['box_px'] = paper.hull([b['box_px'], e['box_px']])
        else:
            blocks.append(dict(id=bid, members=[e['id']], box_px=e['box_px']))
            classes.append(dict(id=bid, cls=cls, box_px=e['box_px']))
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


class TopBandBanners(unittest.TestCase):
    """R1: a masthead and section banners in the top band are never the title (AM03)."""
    def fixture(self, rule=True):
        first, chars = page(1, [
            ('CHEST', 40, 60, 'title', 'b1', {}, 20, 'Garamond'),
            ('Postgraduate Education Corner', 50, 34, 'other', 'b2', {}, 400, 'Myriad'),
            ('CONTEMPORARY REVIEWS IN SLEEP MEDICINE', 100, 13, 'other', 'b3', {}, 560, 'Myriad'),
            ('Dental Appliance Treatment for', 170, 30, 'authors', 'b4', {}, 20, 'Helvetica-Bold'),
            ('Obstructive Sleep Apnea', 205, 30, 'authors', 'b4', {}, 20, 'Helvetica-Bold'),
            ('Andrew S. L. Chan, MBBS; Richard W. W. Lee, MBBS; and', 260, 17, 'main', 'b5', {}, 20, 'Italic'),
            ('Peter A. Cistulli, MBBS, PhD, FCCP', 282, 17, 'main', 'b5', {}, 20, 'Italic'),
            ('Oral appliances for the treatment of obstructive sleep apnea are worn during sleep', 340, 16, 'aside', 'b6', {}),
            ('*From the Centre for Sleep Health and Research, Royal North Shore Hospital, Sydney,', 1200, 14, 'other', 'b7', {}),
            ('NSW, Australia. Dr. Cistulli is on the Medical Advisory Board of SomnoMed.', 1218, 14, 'other', 'b7', {})], body=16)
        if rule: first['art'] = [dict(kind='rule', box_px=[100, 125, 900, 126])]
        later, lchars = page(2, [('Postgraduate Education Corner', 1300, 11, 'furniture', 'f1', {}, 600),
                                ('Body text of the second page continues here at length.', 200, 16, 'main', 'm1', {})])
        return [(first, chars), (later, lchars)]

    def test_lower_display_title_with_byline_is_the_title(self):
        a = parse(self.fixture())
        self.assertEqual(a['title']['text'], 'Dental Appliance Treatment for Obstructive Sleep Apnea')
        self.assertEqual([n['name'] for n in a['authors']], ['Andrew S. L. Chan', 'Richard W. W. Lee', 'Peter A. Cistulli'])
        self.assertEqual([n.get('degrees') for n in a['authors']], [['MBBS'], ['MBBS'], ['MBBS', 'PhD', 'FCCP']])
        self.assertTrue(all(n['name_ok'] for n in a['authors']))
        # the capitals-in-small-type row never became the byline
        self.assertNotIn('CONTEMPORARY', ' '.join(n['name'] for n in a['authors']))
        self.assertEqual(a['checks']['status'], 'authors found, no affiliation markers: not linked')

    def test_recurring_section_label_is_banner_evidence_without_a_rule(self):
        a = parse(self.fixture(rule=False))
        self.assertEqual(a['title']['text'], 'Dental Appliance Treatment for Obstructive Sleep Apnea')

    def test_from_the_footnote_is_the_unmarked_affiliation(self):
        a = parse(self.fixture())
        texts = [c['text'] for c in a.get('unmarked_affiliation_candidates', [])]
        self.assertEqual(texts, ['*From the Centre for Sleep Health and Research, Royal North Shore Hospital, Sydney, NSW, Australia.'])


class StarFootnote(unittest.TestCase):
    def test_symbol_led_institution_footnote_is_the_unmarked_affiliation(self):
        first, chars = page(1, [('Effectiveness of Periodontal Therapy in Patients. Long-Term Results*', 100, 30, 'title', 't', {}),
                                ('Tunç Ilgenli, Gül Atilla, and Haluk Baylas', 150, 18, 'authors', 'b', {}),
                                ('Background: Drug-induced gingival overgrowth is one of the well-recognized side effects.', 220, 16, 'main', 'm', {}),
                                ('* University of Ege, School of Dentistry, Department of Periodontology, Izmir, Turkey.', 1300, 12, 'other', 'f', {})])
        a = parse([(first, chars)])
        self.assertEqual([n['name'] for n in a['authors']], ['Tunç Ilgenli', 'Gül Atilla', 'Haluk Baylas'])
        self.assertEqual([c['text'] for c in a['unmarked_affiliation_candidates']],
                         ['* University of Ege, School of Dentistry, Department of Periodontology, Izmir, Turkey.'])


class Separators(unittest.TestCase):
    """R2: middle dots separate names; a glued marker and conjunction; degrees after a comma."""
    def test_middle_dot_separated_byline(self):
        text = 'Laura Benyei1,2 · Anton Friedmann1 · Thomas Ostermann3 · Daniel Diehl1'
        special = {i: (12, True) for i, ch in enumerate(text) if ch.isdigit()}
        first, chars = page(1, [('Non-surgical treatment of residual pockets', 100, 30, 'title', 't', {}),
                                (text, 150, 20, 'authors', 'b', special)])
        a = parse([(first, chars)])
        self.assertEqual([n['name'] for n in a['authors']], ['Laura Benyei', 'Anton Friedmann', 'Thomas Ostermann', 'Daniel Diehl'])
        self.assertEqual([n['markers'] for n in a['authors']], [['1', '2'], ['1'], ['3'], ['1']])
        self.assertEqual(a['checks']['byline_name_groups'], 4)

    def test_other_column_row_is_passed_over_and_glued_and_is_a_boundary(self):
        text = 'K.S. Kornmanaand P.J.'
        special = {text.index('aand'): (13, True)}
        aff1 = 'aDepartment of R&D, Interleukin Genetics, Waltham, MA, USA, and'
        aff2 = 'bDepartment of Pathology, University of Michigan, Ann Arbor, MI, USA'
        first, chars = page(1, [('Clinical application of genetics to guide prevention', 100, 40, 'title', 't', {}),
                                (text, 180, 20, 'authors', 'b', special, 600),
                                ('Kornman K.S., Polverini P.J. Clinical', 186, 22, 'authors', 'c', {}, 20),
                                ('Polverinib', 205, 20, 'authors', 'b', {9: (13, True)}, 600),
                                (aff1, 240, 15, 'other', 'd', {0: (10, True)}, 600),
                                (aff2, 258, 15, 'other', 'd', {0: (10, True)}, 600)], body=22)
        a = parse([(first, chars)])
        self.assertEqual([n['name'] for n in a['authors']], ['K.S. Kornman', 'P.J. Polverini'])
        self.assertEqual([n['markers'] for n in a['authors']], [['a'], ['b']])
        self.assertEqual([x['text'] for x in a['affiliations']],
                         ['Department of R&D, Interleukin Genetics, Waltham, MA, USA',
                          'Department of Pathology, University of Michigan, Ann Arbor, MI, USA'])
        self.assertEqual(a['checks']['status'], 'verified')

    def test_credentials_and_initials(self):
        self.assertTrue(boxer.AUTHOR_DEGREE.fullmatch('PhD'))
        first, chars = page(1, [('A title of some length here', 100, 30, 'title', 't', {}),
                                ('Ada Example, MBBS, FRCS(Ed); Ben Sample, DrPH', 150, 20, 'authors', 'b', {})])
        a = parse([(first, chars)])
        self.assertEqual([n['name'] for n in a['authors']], ['Ada Example', 'Ben Sample'])
        self.assertEqual(a['authors'][0]['degrees'], ['MBBS', 'FRCS(Ed)'])
        self.assertEqual(a['authors'][1]['degrees'], ['DrPH'])
        # period-separated initials after a comma stay a name, not a degree
        first, chars = page(1, [('A title of some length here', 100, 30, 'title', 't', {}),
                                ('Smith, J.R., Jones, A.B.', 150, 20, 'authors', 'b', {})])
        a = parse([(first, chars)])
        self.assertNotIn('degrees', a['authors'][0])


class BylineRowAddress(unittest.TestCase):
    """R3: a byline row continuing with the affiliation in another size is cut at it (AL03)."""
    def test_name_alone_and_address_band(self):
        first, chars = page(1, [('Pathophysiology of TMD pain and its implications', 100, 36, 'title', 't', {}),
                                ('B. E. CAIRNS', 160, 22, 'authors', 'b', {}, 20, 'Regular'),
                                ('Associate Professor, Canada Research Chair in Neuropharmacology, University of', 160, 17, 'authors', 'b', {}, 190, 'Italic'),
                                ('British Columbia, Vancouver, BC V6T 1Z3, Canada', 185, 17, 'authors', 'b', {}, 20, 'Italic'),
                                ('SUMMARY This article discusses the pathophysiology of pain at length here.', 300, 19, 'main', 'm', {})], body=19)
        a = parse([(first, chars)])
        self.assertEqual([n['name'] for n in a['authors']], ['B. E. CAIRNS'])
        self.assertTrue(a['authors'][0]['name_ok'])
        self.assertEqual([l['text'] for l in a['byline_lines']], ['B. E. CAIRNS'])
        c = a['unmarked_affiliation_candidates'][0]
        self.assertEqual(c['text'], 'Associate Professor, Canada Research Chair in Neuropharmacology, University of British Columbia, Vancouver, BC V6T 1Z3, Canada')
        self.assertEqual(c['run_ids'], ['run:2', 'run:3'])


class LaterPanels(unittest.TestCase):
    """R4 and R5: labelled end panels and next-page marked rows supply missing affiliations."""
    def first_page(self, byline='Laura Benyei1,2 · Anton Friedmann1 · Thomas Ostermann3'):
        special = {i: (12, True) for i, ch in enumerate(byline) if ch.isdigit()}
        return page(1, [('Non-surgical treatment of residual pockets', 100, 30, 'title', 't', {}),
                        (byline, 150, 20, 'authors', 'b', special),
                        ('Abstract The trial compares outcomes of two treatments over nine months.', 220, 16, 'main', 'm', {})])

    def end_panel(self, extra=()):
        specs = [('36. Some reference entry with its journal, year and pages.', 100, 14, 'main', 'r', {}),
                 ('Authors and Affiliations', 300, 20, 'main', 'h', {}),
                 ('Laura Benyei1,2 · Anton Friedmann1 · Thomas Ostermann3', 340, 17, 'main', 'bl', {i: (11, True) for i, ch in enumerate('Laura Benyei1,2 · Anton Friedmann1 · Thomas Ostermann3') if ch.isdigit()}),
                 ('* Anton Friedmann', 380, 14, 'main', 'c', {}, 20),
                 ('first.last@uni-example.de', 398, 14, 'main', 'c', {}, 40),
                 ('3', 378, 10, 'main', 'm3', {}, 520),
                 ('Department of Psychology, Faculty of Health,', 380, 14, 'main', 'a3', {}, 540),
                 ('Witten/Herdecke University, Witten, Germany', 398, 14, 'main', 'a3', {}, 540),
                 ('1', 428, 10, 'main', 'm1', {}, 20),
                 ('Department of Periodontology, Faculty of Health, Witten/', 430, 14, 'main', 'a12', {}, 40),
                 ('Herdecke University, Witten, Germany', 448, 14, 'main', 'a12', {}, 40),
                 ('2', 466, 10, 'main', 'm2', {}, 20),
                 ('Implantat Competence Centrum, Munich, Germany', 468, 14, 'main', 'a12', {}, 40)] + list(extra)
        return page(3, specs)

    def test_labelled_panel_with_separate_markers_and_two_columns(self):
        a = parse([self.first_page(), page(2, [('Body text of page two continues at length here.', 200, 16, 'main', 'm', {})]), self.end_panel()])
        self.assertEqual([x['marker'] for x in a['affiliations']], ['1', '2', '3'])
        self.assertEqual(a['affiliations'][0]['text'], 'Department of Periodontology, Faculty of Health, Witten/Herdecke University, Witten, Germany')
        self.assertEqual(a['affiliations'][2]['text'], 'Department of Psychology, Faculty of Health, Witten/Herdecke University, Witten, Germany')
        self.assertEqual([x['page'] for x in a['affiliations']], [3, 3, 3])
        src = a['affiliation_sources'][0]
        self.assertEqual((src['page'], src['label']), (3, 'Authors and Affiliations'))
        self.assertIn('run:1', src['run_ids']); self.assertIn('run:4', src['run_ids']); self.assertNotIn('run:0', src['run_ids'])
        self.assertEqual(a['checks']['status'], 'verified')

    def test_panel_with_a_marker_outside_the_byline_is_refused(self):
        extra = [('4', 486, 10, 'main', 'm4', {}, 20), ('Department of Nowhere, Elsewhere University, Germany', 488, 14, 'main', 'a4', {}, 40)]
        a = parse([self.first_page(), page(2, [('Body text of page two.', 200, 16, 'main', 'm', {})]), self.end_panel(extra)])
        self.assertEqual(a['affiliations'], [])
        self.assertNotIn('affiliation_sources', a)

    def next_page(self, rows):
        return page(2, [('CHAPPLE et al.', 30, 11, 'furniture', 'f', {})] + rows +
                       [('Abstract', 200, 18, 'main', 'm', {}, 400),
                        ('Periodontal health is defined by absence of inflammation and so on at length.', 230, 16, 'main', 'm', {}, 400)])

    def test_next_page_marked_rows_complete_the_list(self):
        byline = 'Ada Example2 | Ben Sample3 | Cy Toll1'
        special = {i: (12, True) for i, ch in enumerate(byline) if ch.isdigit()}
        first, chars = page(1, [('Periodontal health and gingival diseases on a reduced periodontium', 100, 30, 'title', 't', {}),
                                (byline, 150, 20, 'authors', 'b', special),
                                ('1Periodontal Research Group, University of Birmingham, UK', 190, 12, 'other', 'a', {0: (8, True)})])
        rows = [('2Orofacial Sciences, School of Dentistry, University of California, USA', 100, 12, 'other', 's', {0: (8, True)}),
                ('3Division of Periodontology, Niigata University, Japan', 120, 12, 'other', 's', {0: (8, True)})]
        a = parse([(first, chars), self.next_page(rows)])
        self.assertEqual([x['marker'] for x in a['affiliations']], ['1', '2', '3'])
        self.assertEqual([x.get('page') for x in a['affiliations']][1:], [2, 2])
        self.assertEqual(a['affiliations'][1]['text'], 'Orofacial Sciences, School of Dentistry, University of California, USA')
        self.assertTrue(a['affiliation_sources'][0]['continuation'])
        self.assertEqual(sorted(a['affiliation_sources'][0]['run_ids']), ['run:1', 'run:2'])
        self.assertEqual(a['checks']['status'], 'verified')
        # a row with another marker in the same stack refuses the continuation
        rows2 = rows + [('4Department of Something, Some University, Somewhere', 140, 12, 'other', 's', {0: (8, True)})]
        a = parse([(first, chars), self.next_page(rows2)])
        self.assertEqual([x['marker'] for x in a['affiliations']], ['1'])
        # unraised digits are not markers
        rows3 = [(t, y, s, c, b, {}) for t, y, s, c, b, _ in rows]
        a = parse([(first, chars), self.next_page(rows3)])
        self.assertEqual([x['marker'] for x in a['affiliations']], ['1'])


class CopierFront(unittest.TestCase):
    def test_front_info_signal(self):
        self.assertFalse(paper.front_info_signal(['Fundamentals of inflammation', 'It is now widely accepted that a major']))
        self.assertTrue(paper.front_info_signal(['Accepted for publication 14 November 2012']))
        self.assertTrue(paper.front_info_signal(['Correspondence: Dr. Example']))
        self.assertTrue(paper.front_info_signal(['Mail to someone@example.org']))

    def test_panel_lines_leave_blocks_by_run_id(self):
        paper.trace_reset()
        p = dict(page=10, elements=[dict(id='run:1', kind='text', text='35. A reference', box_px=[0, 0, 100, 10], angle=0),
                                    dict(id='run:2', kind='text', text='Authors and Affiliations', box_px=[0, 20, 100, 30], angle=0),
                                    dict(id='run:3', kind='text', text='Ada Example', box_px=[0, 40, 100, 50], angle=0)],
                 _late_front_run_ids=['run:2', 'run:3'])
        lines = [paper.trace_row(10, [p['elements'][0]], '35. A reference'),
                 paper.trace_row(10, [p['elements'][1]], 'Authors and Affiliations'),
                 paper.trace_row(10, [p['elements'][2]], 'Ada Example')]
        block = dict(lines=lines, lefts=[0, 0, 0], sizes=[10, 10, 10], row_boxes=[[0, 0, 100, 10], [0, 20, 100, 30], [0, 40, 100, 50]],
                     emphasis=[False]*3, faces=['R']*3, prefixes=['']*3, first=lines[0], meta=dict(lines=3, box_px=[0, 0, 100, 50]))
        per_page = [(([block]), [], [])]
        paper.remove_printed_front_rows(per_page, [p])
        self.assertEqual([str(l) for l in per_page[0][0][0]['lines']], ['35. A reference'])

    def test_leftover_conjunction_is_dropped(self):
        import re
        pattern = r'(?:and|&|[,;.])(?:\s+(?:and|&|[,;.]))*'
        self.assertTrue(re.fullmatch(pattern, 'and', re.I))
        self.assertTrue(re.fullmatch(pattern, ', and', re.I))
        self.assertFalse(re.fullmatch(pattern, 'and the authors', re.I))


if __name__ == '__main__':
    unittest.main()
