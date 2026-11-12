"""Tests for layout/rules.py (the layout sort's decisions)."""
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'layout'))
import rules as RL   # noqa: E402


def word(text, x0, y0, x1, y1, font='Body', size=8.3, run='r1'):
    return dict(text=text, box=[x0, y0, x1, y1], fonts=[[font, size, len(text)]], run=run)


class Census(unittest.TestCase):
    def test_main_size_merges_letter_faces_not_symbols(self):
        ws = [word('body', 0, 0, 10, 10) for _ in range(50)] + [word('italic', 0, 0, 10, 10, 'Body-I') for _ in range(5)] + \
             [word('≥±', 0, 0, 10, 10, 'Symbol') for _ in range(5)] + [word('small', 0, 0, 10, 10, 'Body', 6.6) for _ in range(30)]
        size, fonts = RL.main_class([dict(words=ws)])
        self.assertEqual(size, 8.3); self.assertEqual(fonts, ['Body', 'Body-I'])
        RL.relabel([dict(words=ws)], size, fonts)
        self.assertEqual(RL.cls(ws[52]), (RL.MAIN, 8.3)); self.assertEqual(RL.cls(ws[56]), ('Symbol', 8.3)); self.assertEqual(RL.cls(ws[70]), ('Body', 6.6))


class Groups(unittest.TestCase):
    def test_wide_gap_inside_a_run_splits_the_segment(self):
        em = 8.3 * 150 / 72                 # about 17 px
        ws = [word('left', 0, 0, 40, 15), word('right', 40 + 2 * em, 0, 120, 15)]
        self.assertEqual(len(RL.segments(ws)), 2)
        ws = [word('one', 0, 0, 40, 15), word('two', 40 + 0.4 * em, 0, 100, 15)]
        self.assertEqual(len(RL.segments(ws)), 1)

    def test_no_link_across_a_gutter(self):
        a, b = [0, 0, 100, 15], [110, 0, 200, 15]
        self.assertTrue(RL.link(a, b, 8.3))
        self.assertFalse(RL.link(a, b, 8.3, cuts=[105]))

    def test_next_line_links_with_overlap_only(self):
        self.assertTrue(RL.link([0, 0, 100, 15], [0, 20, 100, 35], 8.3))
        self.assertFalse(RL.link([0, 0, 100, 15], [120, 20, 200, 35], 8.3))
        self.assertFalse(RL.link([0, 0, 100, 15], [0, 60, 100, 75], 8.3))


class Frame(unittest.TestCase):
    def test_least_move(self):
        self.assertEqual(RL.least_move(-5, 3), 0); self.assertEqual(RL.least_move(10, 30), 10)
        self.assertEqual(RL.least_move(-30, -12), -12); self.assertIsNone(RL.least_move(5, 2))

    def test_largest_box_moves_per_page(self):
        best, B, moves, nofit = RL.frame_moves({1: [140, 500, 1590, 2000], 2: [108, 180, 1558, 2060], 3: [142, 180, 1592, 2060]})
        self.assertEqual(best, 2); self.assertEqual(moves[2], (0, 0)); self.assertEqual(moves[3][0], 30); self.assertEqual(nofit, [])
        self.assertEqual(RL.fill_moves(moves, [1, 2, 3, 4, 5])[5], moves[3] if moves[3] == moves[1] else RL.fill_moves(moves, [5])[5])

    def test_box_that_cannot_hold_a_page(self):
        _, _, _, nofit = RL.frame_moves({1: [0, 0, 100, 200], 2: [0, 0, 150, 100]})
        self.assertEqual(nofit, [2])


class Gutters(unittest.TestCase):
    def test_strips_split_by_a_hairline_are_one(self):
        votes = [0] * 100 + [5] * 38 + [0] * 2 + [5] * 8 + [0] * 100
        self.assertEqual(RL.recurring_gutters(votes, 4, 4, 14, len(votes)), [(100, 148)])

    def test_majority_strip_not_at_the_edges(self):
        votes = [5] * 20 + [0] * 100 + [5] * 40 + [0] * 100 + [5] * 20
        self.assertEqual(RL.recurring_gutters(votes, 4, 12, 14, len(votes)), [(120, 160)])


class Order(unittest.TestCase):
    def u(self, name, box): return dict(name=name, box=box)

    def test_columns_then_next_column_and_spans(self):
        units = [self.u('right1', [760, 300, 1400, 600]), self.u('left1', [10, 300, 700, 900]), self.u('header', [10, 10, 1400, 250]),
                 self.u('right2', [760, 650, 1400, 900]), self.u('fig', [10, 950, 1400, 1200]), self.u('left2', [10, 1250, 700, 1800])]
        names = [x['name'] for x in RL.reading_order(units, [(712, 756)], 1450)]
        self.assertEqual(names, ['header', 'left1', 'right1', 'right2', 'fig', 'left2'])

    def test_a_unit_across_two_of_three_columns_orders_only_those(self):
        units = [self.u('table', [480, 950, 1400, 1800]), self.u('col3', [940, 10, 1400, 900]), self.u('col1b', [10, 1000, 430, 1800]),
                 self.u('col2', [480, 10, 890, 900]), self.u('col1a', [10, 10, 430, 900])]
        names = [x['name'] for x in RL.reading_order(units, [(440, 470), (900, 930)], 1450)]
        self.assertEqual(names, ['col1a', 'col1b', 'col2', 'col3', 'table'])

    def test_section_break_under_every_column(self):
        m = lambda n, b: dict(name=n, box=b, kind=RL.MAIN); r = lambda n, b: dict(name=n, box=b, kind='non-main text')
        units = [m('m1', [10, 10, 430, 600]), m('m2', [480, 10, 890, 600]), m('m3', [940, 10, 1400, 600]),
                 r('head', [10, 640, 120, 660]), r('r1', [10, 690, 430, 1800]), r('r2', [480, 690, 890, 1800]), r('r3', [940, 690, 1400, 1800])]
        names = [x['name'] for x in RL.reading_order(units, [(440, 470), (900, 930)], 1450)]
        self.assertEqual(names, ['m1', 'm2', 'm3', 'head', 'r1', 'r2', 'r3'])

    def test_common_white_line_is_not_a_break_under_a_spanning_table(self):
        units = [self.u('table', [10, 10, 1400, 300]), self.u('l1', [10, 330, 700, 800]), self.u('r1', [760, 330, 1400, 790]),
                 self.u('l2', [10, 840, 700, 1500]), self.u('r2', [760, 830, 1400, 1500])]
        self.assertEqual([x['name'] for x in RL.reading_order(units, [(712, 756)], 1450)], ['table', 'l1', 'l2', 'r1', 'r2'])

    def test_references_running_on_across_a_white_line_are_no_break(self):
        m = lambda n, b: dict(name=n, box=b, kind=RL.MAIN); r = lambda n, b: dict(name=n, box=b, kind='non-main text')
        units = [r('refs10', [760, 10, 1400, 900]), m('body', [10, 10, 700, 700]), m('head', [10, 800, 200, 830]),
                 r('refs1', [10, 950, 700, 1800]), r('refs19', [760, 930, 1400, 1800])]
        names = [x['name'] for x in RL.reading_order(units, [(712, 756)], 1450)]
        self.assertEqual(names, ['body', 'head', 'refs1', 'refs10', 'refs19'])

    def test_unit_beside_a_spanning_unit_is_kept(self):
        units = [self.u('span', [10, 100, 1400, 900]), self.u('beside', [10, 500, 300, 520])]
        self.assertEqual(sorted(x['name'] for x in RL.reading_order(units, [(712, 756)], 1450)), ['beside', 'span'])


class Captions(unittest.TestCase):
    def test_caption_or_sentence(self):
        self.assertTrue(RL.is_caption([('FIGURE', 'Sans-Bold'), ('1', 'Sans-Bold')], ['Serif'] * 20))
        self.assertTrue(RL.is_caption([('Fig.', 'Serif'), ('2.', 'Serif')], ['Serif'] * 20))
        self.assertTrue(RL.is_caption([('Table', 'Serif'), ('3:', 'Serif')], ['Serif'] * 20))
        self.assertFalse(RL.is_caption([('Table', 'Serif'), ('1', 'Serif')], ['Serif'] * 20))      # "Table 1 summarizes ..."
        self.assertFalse(RL.is_caption([('The', 'Serif'), ('table', 'Serif')], ['Serif'] * 20))


class AltMain(unittest.TestCase):
    def test_one_to_five_word_text_floats(self):
        self.assertTrue(RL.alt_main('float', False, 1)); self.assertTrue(RL.alt_main('float', False, 5))
        self.assertFalse(RL.alt_main('float', False, 6)); self.assertFalse(RL.alt_main('float', True, 3))
        self.assertFalse(RL.alt_main('references', False, 3)); self.assertFalse(RL.alt_main('float', False, 0))


class Furniture(unittest.TestCase):
    def test_block_repeated_on_many_pages(self):
        blocks = [(n, f'Thorax: first published as 10.1136 on {n} September 2012. Downloaded from', [10, 100, 30, 900]) for n in range(1, 7)] + [(2, 'A table caption', [0, 0, 9, 9])]
        self.assertEqual(len(RL.repeated_blocks(blocks, 6)), 1)

    def test_same_table_heads_in_other_places_are_not_furniture(self):
        blocks = [(5, 'Treatment n Mean SD Minimum Maximum F P Simvastatin Baseline', [55, 603, 297, 720]), (6, 'Treatment n Mean SD Minimum Maximum F P Simvastatin Baseline', [54, 204, 296, 318])]
        self.assertEqual(RL.repeated_blocks(blocks, 6), [])

    def test_turned_text_is_not_main(self):
        ws = [dict(word('body', 0, 0, 10, 10), angle=0) for _ in range(50)] + [dict(word('Downloaded', 0, 0, 10, 10), angle=90)]
        size, fonts = RL.main_class([dict(words=ws)]); RL.relabel([dict(words=ws)], size, fonts)
        self.assertEqual(RL.cls(ws[0])[0], RL.MAIN); self.assertNotEqual(RL.cls(ws[-1])[0], RL.MAIN)

    def test_repeated_top_lines_are_furniture(self):
        lines = [(n, 'top', ('Head', 7.0)) for n in range(1, 8)] + [(1, 'top', ('Title', 14.0))]
        f = RL.recurring_outside(lines, 7)
        self.assertIn(('top', ('Head', 7.0)), f); self.assertNotIn(('top', ('Title', 14.0)), f)


class References(unittest.TestCase):
    def test_styles(self):
        self.assertEqual(RL.style_of('1. Albrektsson T, Donos N. Implant survival. Clin Oral Implants Res. 2012;23:63-65.'), 'numbered')
        self.assertEqual(RL.style_of('[12] Marshall TA, Warren JJ. Oral health. J Am Diet Assoc 2002;102:1.'), 'numbered')
        self.assertEqual(RL.style_of('Akiyama, H., Barger, S., 2000. Inflammation and Alzheimer’s disease. Neurobiol. Aging 21, 383–421.'), 'author-year (APA/Harvard)')
        self.assertEqual(RL.style_of('Amulic B, Cazalet C, Hayes GL (2012). Neutrophil function. Annu Rev Immunol 30:459-489.'), 'Vancouver')
        self.assertEqual(RL.style_of('Dickinson DP (2002). Cysteine peptidases of mammals. Crit Rev Oral Biol Med 13:238-275.'), 'Vancouver')
        self.assertIsNone(RL.style_of('incidence, prevalence, and years lived with disability for 328 diseases 2017.', need_year=False))
        self.assertEqual(RL.style_of('van Charante, E. P. M., Richard, E. (2016). Effectiveness of a nurse-led trial. Lancet, 388, 797-805.'), 'author-year (APA/Harvard)')
        self.assertIsNone(RL.style_of('How to cite this article: Herrera D, Molina A. Periodontitis and diabetes.'))
        self.assertIsNone(RL.style_of('The results were consistent with the hypothesis that inflammation matters.'))

    def test_hanging_indent_entries_and_cut_block(self):
        lines = [(0, 'Akiyama, H., Barger, S., 2000. Inflammation and'), (34, 'Alzheimer’s disease. Neurobiol. Aging 21, 383–421.'),
                 (0, 'Anstey, K.J., von Sanden, C., 2007. Smoking as a'), (34, 'risk factor. Am. J. Epidemiol. 166, 367–378.'),
                 (0, 'Beck, J.D., Offenbacher, S., Williams, R., Gibbs, P.,')]
        score, style, n, note = RL.ref_score(lines)
        self.assertEqual(n, 3); self.assertEqual(score, 1.0); self.assertEqual(style, 'author-year (APA/Harvard)')

    def test_first_line_indented_rest_flush(self):
        lines = [(221, 'REFERENCES'), (234, '1. Nyman S, Karring T, Lindhe J, et al.'), (221, 'Healing following implantation of periodon-'),
                 (221, 'tissue. J Clin Periodontol. 1980;7:394-401.'), (233, '2. Nyman S, Lang NP, Buser D, et al.'), (221, 'J Oral Maxillofac Implants. 1990;5:9-14.')]
        score, style, n, note = RL.ref_score(lines)
        self.assertEqual(n, 2); self.assertEqual(score, 1.0); self.assertEqual(style, 'numbered')

    def test_trailing_correspondence_note(self):
        lines = [(332, '26. Nemcovsky CE, Artzi Z, Moses O. Rotated palatal flap. Int J Periodontics'), (350, 'Restorative Dent 1999;19:221-229.'),
                 (332, '27. Hertel RC, Blijdorp PA, Kalk W. Stage 2 surgical techniques. Int J Oral Maxillofac Surg 1994;23:2-5.'),
                 (332, 'Send reprint requests to: Dr. Carlos E. Nemcovsky, Depart-'), (332, 'ment of Periodontology, Tel Aviv University,'),
                 (332, 'Accepted for publication June 21, 1999.')]
        score, style, n, note = RL.ref_score(lines)
        self.assertEqual((score, n, note), (1.0, 2, 3))

    def test_find_references_heading_inside_or_before(self):
        body = dict(page=5, kind='main text', lines=[(0, 'The conclusion of the paper.')], words=200)
        refs = dict(page=6, kind='non-main text', lines=[(0, '1. Young T, Palta M. Sleep. N Engl J Med 1993;328:1230.'), (0, '2. Peppard PE. Sleep. JAMA 2000;284:3015.')], words=40)
        head_line = dict(page=6, kind='main text', lines=[(0, 'References')], words=1)
        idx, info = RL.find_references([body, head_line, refs], 4)
        self.assertEqual(idx, [2]); self.assertEqual(info['heading_where'], 'line just before the block')
        inside = dict(refs, lines=[(0, 'REFERENCES')] + refs['lines'])
        idx, info = RL.find_references([body, inside], 4)
        self.assertEqual(idx, [1]); self.assertEqual(info['heading_where'], 'first line of the block')

    def test_heading_inside_a_block(self):
        blk = dict(page=11, kind='float', words=80, lines=[(0, 'Acknowledgments'), (0, 'We thank the reviewers for their help with this study.'), (0, 'References'),
                   (0, '1. Wikesjo UM, Selvig KA. Periodontal wound healing. Periodontol 2000 1999;19:21-39.'), (0, '2. Sculean A, Chapple IL. Wound models. J Clin Periodontol 2015;42:1-9.')])
        idx, info = RL.find_references([dict(page=10, kind='main text', words=300, lines=[(0, 'Body.')]), blk], 9)
        self.assertEqual(idx, [1]); self.assertEqual(info['split'], [1, 2])

    def test_heading_before_a_stray_piece(self):
        body = dict(page=7, kind='main text', words=52, lines=[(0, 'of minor reparations was 1.9.'), (0, 'REFERENCES')])
        stray = dict(page=7, kind='float', words=1, lines=[(0, 'also')])
        refs = dict(page=7, kind='float', words=49, lines=[(0, '1. Obin JN, Arvins AN. Resin splints. J Prosthet Dent 1975;34:1-9.'), (0, '2. Sa W. Splints. J Dent 1977;5:1-2.')])
        self.assertEqual(RL.find_references([body, stray, refs], 4)[0], [2])

    def test_cut_off_entry_end_joins_the_list(self):
        refs = dict(page=11, kind='float', words=200, lines=[(0, 'References'), (0, 'Prince, M., Wimo, A. (2015). World Alzheimer Report. London: ADI, 1-87.'), (0, 'Rolim, T., Fabri, G. (2014). Oral infections. J Oral Pathol 43, 1-6.')])
        piece = dict(page=11, kind='float', words=20, lines=[(0, 'ple living with dementia. Coverage, Quality and costs now and in the future. London, UK: ADI, 1-140.')])
        more = dict(page=11, kind='float', words=200, lines=[(0, 'Sato, T., Ito, K. (2016). Teeth and memory. Gerodontology 33, 1-9.'), (0, 'Wu, Y., Chan, K. (2016). The changing prevalence of dementia. Lancet Neurol 15, 116-124.')])
        self.assertEqual(RL.find_references([refs, piece, more], 9)[0], [0, 1, 2])

    def test_list_ends_at_a_block_that_is_not_references(self):
        refs = dict(page=6, kind='non-main text', lines=[(0, 'References'), (0, '1. Young T. Sleep. N Engl J Med 1993;328:1230.'), (0, '2. Peppard PE. Sleep. JAMA 2000;284:3015.')], words=40)
        cite = dict(page=6, kind='non-main text', lines=[(0, 'How to cite this article: Herrera D, Molina A. Periodontitis. 2020.')] * 6, words=60)
        idx, info = RL.find_references([refs, cite], 4)
        self.assertEqual(idx, [0]); self.assertEqual(info['ended_at'], 1)

    def test_no_heading_no_references(self):
        refs = dict(page=6, kind='non-main text', lines=[(0, '1. Young T. Sleep. N Engl J Med 1993;328:1230.')], words=40)
        self.assertEqual(RL.find_references([refs], 4)[0], [])


if __name__ == '__main__':
    unittest.main()
