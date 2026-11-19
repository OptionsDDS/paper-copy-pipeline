"""Round 8, lane r8-overlay: the spreadsheet grid laid over a table (rules TG1-TG7, overlay.py) and its use in table_rows.

Every table here is made up. Pixels are at 150 dpi (k = 150/72 pixels per point), as in the page records.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('copy_paper', ROOT / 'copy_paper.py')
c = importlib.util.module_from_spec(spec); spec.loader.exec_module(c)
ov = c.overlay_module()
K = 150 / 72
CH = 5.0 * K   # one character's width


def line(y, cells):
    """a printed line: cells [(x_pt, text)], each word its own item, words one space apart"""
    items = []
    for x, text in cells:
        x = x * K
        for w in text.split():
            run = dict(id=f'{x:.0f}:{y}:{w}', text=w, angle=0, box_px=[x, y * K, x + CH * len(w), (y + 8) * K])
            items.append(([x, y * K, x + CH * len(w), (y + 8) * K], w, run))
            x += CH * (len(w) + 1)
    return dict(items=items, top=y * K, bot=(y + 8) * K, vc=(y + 4) * K, h=8 * K)


LABELS = ['Age', 'Smoking status', 'Body mass', 'Diabetes', 'Former smokers', 'Sex']


def table(stub_indent=False, wrap=False):
    rows = [line(100, [(50, 'Item'), (200, 'n'), (260, '%')])]
    y = 112
    for i in range(6):
        x = 58 if stub_indent and i % 2 else 50
        rows.append(line(y, [(x, LABELS[i]), (200, str(10 + i)), (260, f'{i}.5')])); y += 12
        if wrap and i == 2:
            rows.append(line(y, [(x, 'goes on')])); y += 12
    return rows


class Fit(unittest.TestCase):
    def test_clean_three_columns(self):
        f = ov.fit(table(), [], K)
        self.assertEqual(f['counts']['cols'], 3)
        self.assertTrue(f['clean'])
        self.assertEqual(len(f['col_lines']), 2)
        self.assertTrue(all(f['cell_row'][1:]))   # one printed line to a row (the header boundary is not the overlay's)

    def test_nested_labels_keep_one_setting(self):
        f = ov.fit(table(stub_indent=True), [], K)
        self.assertTrue(f['clean'])

    def test_wrapped_label_is_not_a_new_cell_row(self):
        f = ov.fit(table(wrap=True), [], K)
        self.assertEqual(f['cell_row'][1:], [True, True, False, True, True, True])

    def test_value_under_value_starts_a_cell(self):
        f = ov.fit([line(100, [(50, 'Per patient'), (200, '33.53 ± 11.19')]), line(112, [(50, 'Per year'), (200, '1.58 ± 0.49')]),
                    line(124, [(50, 'Number of visits per year'), (200, '2.1 ± 0.3')])], [], K)
        self.assertTrue(all(f['cell_row']))

    def test_drawn_rule_parts_rows(self):
        t = table(wrap=True)
        y = (t[4]['bot'] + t[5]['top']) / 2
        f = ov.fit(t, [([40 * K, y - 1, 300 * K, y], 'rule')], K)
        self.assertEqual([i for i, d in enumerate(f['drawn']) if d], [4])
        self.assertTrue(f['cell_row'][4])

    def test_prose_is_not_clean(self):
        f = ov.fit([line(100 + 12 * i, [(50, 'a sentence of running prose that fills the line')]) for i in range(5)], [], K)
        self.assertTrue(f is None or not f['test'])

    def test_shared_cell_is_not_clean(self):
        t = table()
        t[3] = line(136, [(50, 'Body mass'), (200, '12'), (226, 'x'), (260, '2.5')])   # two groups in one column
        f = ov.fit(t, [], K)
        self.assertFalse(f['clean'])


    def test_word_gap_column_cuts_groups_not_clean(self):
        # values with a qualifier one word space after them, the same on every line (AQ21 p6 form): the aligned word
        # gap makes a white strip, but a line through it cuts groups (TG2): not clean
        t = [line(100, [(50, 'Group'), (200, 'Test'), (300, 'Control')])]
        for i, lab in enumerate(LABELS):
            t.append(line(112 + 12 * i, [(50, lab), (200, f'{10 + i} ({i}.5)'), (300, f'{20 + i} ({i}.1)')]))
        f = ov.fit(t, [], K)
        self.assertGreater(f['counts']['groups_cut'], 0)
        self.assertFalse(f['clean'])

    def test_columns_never_level_not_clean(self):
        # a column of P values set between two value columns, on rows of their own (AY20 p4 form)
        t = [line(100, [(50, 'Group'), (200, 'Short'), (300, 'Long')])]
        y = 112
        for i in range(4):
            t.append(line(y, [(50, LABELS[i]), (200, f'{i}.{i}%'), (300, f'{i + 3}.0%')])); y += 12
            t.append(line(y, [(50, 'P value'), (255, f'.{i}31')])); y += 12
        f = ov.fit(t, [], K)
        self.assertFalse(f['counts']['columns_level'])
        self.assertFalse(f['clean'])


class Columns(unittest.TestCase):
    def test_differ(self):
        t = table(); f = ov.fit(t, [], K)
        cuts = list(f['col_lines'])
        col = lambda b: sum(1 for x in cuts if (b[0] + b[2]) / 2 > x)
        self.assertFalse(c.overlay_columns_differ(f, t, col))
        col1 = lambda b: 0 if (b[0] + b[2]) / 2 < cuts[1] else 1   # the two value columns read as one
        self.assertTrue(c.overlay_columns_differ(f, t, col1))


if __name__ == '__main__':
    unittest.main()


class Forms(unittest.TestCase):
    """lane r8-overlay2: the loosening forms of overlay_grid (made-up tables)"""
    def grid(self, t, forms=()):
        f = ov.fit(t, [], K)
        return c.overlay_grid(f, t, [0], [], K, frozenset(forms))

    def test_label_row_over_all_columns(self):
        # a group-label row whose one group reaches over the value columns, between rows of values
        t = [line(100, [(50, 'Item'), (200, 'n'), (260, '%')])]
        y = 112
        for i in range(6):
            if i == 3:
                t.append(line(y, [(50, 'Smoking and other habits of the patients over time')])); y += 12
            t.append(line(y, [(50, LABELS[i]), (200, str(10 + i)), (260, f'{i}.5')])); y += 12
        g0 = self.grid(t); g1 = self.grid(t, ('label',))
        self.assertFalse(g0['g'] and g0['d'])
        self.assertIn(4, g1['label_lines'])
        self.assertTrue(g1['g'] and g1['d'] and g1['decided'])
        self.assertEqual(sum(1 for r in g1['rows'] if r.get('group')), 1)

    def test_two_groups_in_one_cell_is_not_s(self):
        t = table()
        t[2] = line(112, [(50, 'Age'), (200, '10'), (226, 'x'), (260, '0.5')])
        g = self.grid(t)
        self.assertFalse(g['s'])
        self.assertTrue(self.grid(table())['s'])


class HeaderSpan(unittest.TestCase):
    """lane r8-overlay2 pass 2: a header label takes its span from the lower header cells it is centred over"""
    def test_label_centred_over_lower_cells(self):
        t = [line(88, [(190, 'Test group values')]), line(100, [(50, 'Item'), (200, 'n'), (260, '%')])]
        for i in range(6): t.append(line(112 + 12 * i, [(50, LABELS[i]), (200, str(10 + i)), (260, f'{i}.5')]))
        f = ov.fit(t, [], K)
        g0 = c.overlay_grid(f, t, [0, 1], [], K, frozenset(('label',)))
        g1 = c.overlay_grid(f, t, [0, 1], [], K, frozenset(('label', 'hspan')))
        self.assertGreaterEqual(g1['spanned'], 1)
        self.assertTrue(g1['g'] and g1['d'])
        self.assertEqual(g1['rows'][0]['cells'][1][0], g1['rows'][0]['cells'][2][0])   # repeated over both columns


class Pass3(unittest.TestCase):
    """lane r8-overlay2 pass 3: values centred beside a row label set on two lines are one row (mark cent)"""
    def test_values_beside_two_line_label(self):
        t = [line(100, [(50, 'Source'), (200, 'df'), (260, 'F')]), line(112, [(50, 'Age'), (200, '2'), (260, '6.962')]),
             line(124, [(50, 'Treatment')]), line(129, [(200, '2'), (260, '201.206')]), line(134, [(50, 'duration')]),
             line(148, [(50, 'Error'), (200, '96'), (260, '1.0')])]
        f = ov.fit(t, [], K)
        g = c.overlay_grid(f, t, [0], [], K, frozenset(('cent',)))
        self.assertTrue(any(x['marks2'].get('cent') == 'cont' for x in g['cellrows']))


def memo1_table(foot=True):
    """memo 1 H1 geometry (made-up text): stub at 52, eight value columns, a three-line header (group labels over four
    columns, labels over two, column labels), three blocks of a first-column label, three data lines and one long
    closing line (h 11), and foot notes in a smaller type (h 7.2) 18 pt under the last body line"""
    def ln(y, cells, h=8.1):
        L = line(y, cells); k = h / 8
        for b, w, e in L['items']:
            b[3] = b[1] + h * K; e['box_px'][3] = b[3]
        L['bot'] = L['top'] + h * K; L['h'] = h * K; L['vc'] = L['top'] + h * K / 2
        return L
    cols = [125, 184, 237, 295, 353, 412, 465, 524]
    t = [ln(422.6, [(125, 'Alpha group'), (353, 'Beta group total')], 11.0),
         ln(436.3, [(125, 'Sites'), (237, 'Teeth'), (353, 'Sites'), (465, 'Teeth')], 8.2),
         ln(448.0, [(52, 'Measure')] + [(x, s) for x, s in zip(cols, 'n % n % n % n %'.split())], 8.2)]
    y = 461.9
    for b, lab in enumerate(('Baseline', 'Three months', 'Six months')):
        t.append(ln(y, [(52, lab)])); y += 13
        for i, r in enumerate(('Shallow', 'Moderate', 'Deep')):
            t.append(ln(y, [(60, r)] + [(x, str(10 + b + i + j) if j % 2 == 0 else '%d.%d' % (20 + j, i)) for j, x in enumerate(cols)])); y += 13
        t.append(ln(y, [(52, 'Mean change over the visit was small in both of the groups here')], 11.0)); y += 17
    if foot:
        y = t[-1]['bot'] / K + 18
        for x, s in ((58, 'Data are numbers of sites and teeth.'), (57, 'a Values compared between groups with the chi-squared test at the level 0.05 in all'),
                     (78, 'b Sites of the second visit only.'), (51, 'c Teeth lost at the visit.')):
            t.append(ln(y, [(x, s)], 7.2)); y += 10.5
    return t


class Memo1(unittest.TestCase):
    """lane r8-overlay2 memo 1: notes under the last row are notes, not label rows; every line above the first body row
    is the header, and a header whose spans are not settled on every line keeps the part a flagged list"""
    def grid(self, t, head=(0,)):
        f = ov.fit(t, [], K)
        return c.overlay_grid(f, t, list(head), [], K, frozenset(('label', 'a2', 'hspan', 'shade2', 'cent')))

    def test_foot_notes_are_not_label_rows(self):
        g = self.grid(memo1_table())
        self.assertFalse(any(r.get('group') and 'chi-squared' in ' '.join(sum(r['cells'], [])) for r in g['rows']))

    def test_header_lines_are_never_body_rows(self):
        g = self.grid(memo1_table())
        body_text = ' '.join(' '.join(sum(r['cells'], [])) for r in g['rows'] if not r['header'])
        self.assertNotIn('Measure', body_text)

    def test_unsettled_header_keeps_the_list(self):
        g = self.grid(memo1_table())
        self.assertFalse(g.get('header_settled', True))
        self.assertFalse(g.get('foot_ok', True))   # the closing long line after the last value row: note or label row is not certain


class RowClues(unittest.TestCase):
    """lane r9-rowclues: TW1 (user's words): in the leftmost column only, a new line starting with a bracket is a wrapped
    line of the leftmost cell above; a range in brackets under a value in another column is not decided by TW1"""
    def test_bracket_in_leftmost_column(self):
        t = [line(100, [(50, 'Item'), (200, 'Test'), (300, 'Control')]),
             line(112, [(50, 'Interleukin 6'), (200, '82.7'), (300, '83.3')]),
             line(124, [(50, '(pg/ml)')]),
             line(136, [(50, 'Aesthetics'), (200, '77.9'), (300, '81.4')]),
             line(148, [(200, '(70.1-85.0)'), (300, '(75.0-88.2)')])]
        f = ov.fit(t, [], K)
        g = c.overlay_grid(f, t, [0], [], K, frozenset(('TW1',)))
        m = {x['lines'][1][:6]: x['marks2'] for x in g['cellrows']}
        d = {x['lines'][1][:6]: x['decision'] for x in g['cellrows']}
        self.assertEqual(m['(pg/ml'].get('TW1'), 'cont')
        self.assertEqual(d['(pg/ml'], 'cont')
        self.assertNotIn('TW1', m['(70.1-'])   # a range under values in other columns: not TW1's business

    def clues(self, t, forms=('PROC',)):
        f = ov.fit(t, [], K)
        g = c.overlay_grid(f, t, [0], [], K, frozenset(forms))
        return {x['lines'][1][:6]: x['decision'] for x in g['cellrows']}, g

    def test_user_order_capital_opens_a_row(self):
        t = [line(100, [(50, 'Item'), (200, 'Test'), (300, 'Control')]),
             line(112, [(50, 'Interleukin 6'), (200, '82.7'), (300, '83.3')]),
             line(124, [(50, 'Aesthetics'), (200, '77.9'), (300, '81.4')])]
        d, g = self.clues(t)
        self.assertEqual(d['Aesthe'], 'new')

    def test_open_end_exception_is_a_switch(self):
        t = [line(100, [(50, 'Item'), (200, 'Test'), (300, 'Control')]),
             line(112, [(50, 'Interleukin and'), (200, '82.7'), (300, '83.3')]),
             line(124, [(50, 'Tumour factor')]),
             line(136, [(50, 'Aesthetics'), (200, '77.9'), (300, '81.4')])]
        d, _ = self.clues(t)
        self.assertEqual(d['Tumour'], 'new')      # TW2 as the user wrote it (built)
        do, _ = self.clues(t, ('PROC', 'PROCo'))
        self.assertNotEqual(do['Tumour'], 'new')  # the builder's exception, a recorded form only

    def test_indented_line_under_a_row_border_holds_the_part(self):
        t = [line(100, [(50, 'Interventions'), (200, 'Funding'), (330, 'Rank')]),
             line(112, [(50, 'Control: flap'), (200, 'University based;'), (330, '4')]),
             line(124, [(50, 'Test: flap and acid'), (215, 'Foundation of the school')]),
             line(136, [(50, 'Control: graft'), (200, 'Federal based'), (330, '3')])]
        d, g = self.clues(t)
        self.assertIsNone(d['Test: '])
        self.assertFalse(g['decided'])

    def test_low_line_alone_holds_the_part(self):
        t = [line(100, [(50, 'No'), (200, 'Surgery'), (300, 'Year')]),
             line(112, [(50, '5'), (200, '67'), (300, '68')]),
             line(124, [(300, '*')]),
             line(128, [(50, '6'), (200, '78'), (300, '')]),
             line(140, [(50, '7'), (200, '83'), (300, '81')])]
        t[2]['bot'] = t[2]['top'] + 3 * K; t[2]['vc'] = t[2]['top'] + 1.5 * K
        t[2]['items'] = [([b[0], b[1], b[2], b[1] + 3 * K], w, r) for b, w, r in t[2]['items']]
        d, g = self.clues(t)
        self.assertFalse(g['decided'])

    def test_bracket_line_with_values_joins_the_leftmost_cell(self):
        """TW8 (picture 7): '(pg/site)' is a wrap of the leftmost cell above; its values are a sub-row beside that cell"""
        t = [line(100, [(50, 'Marker'), (150, 'Time'), (250, 'Test'), (350, 'Control')]),
             line(112, [(50, 'TGF-beta'), (150, 'Baseline'), (250, '15.20'), (350, '16.85')]),
             line(124, [(50, '(pg/site)'), (150, 'Third day'), (250, '11.93'), (350, '6.34')]),
             line(136, [(150, 'Seventh day'), (250, '12.54'), (350, '6.35')]),
             line(148, [(50, 'IL-6'), (150, 'Baseline'), (250, '1.20'), (350, '1.85')])]
        f = ov.fit(t, [], K)
        g = c.overlay_grid(f, t, [0], [], K, frozenset(('PROC',)))
        body = [[' '.join(x) for x in r['cells']] for r in g['rows'] if not r['header']]
        self.assertEqual(body[0][0], 'TGF-beta (pg/site)')
        self.assertEqual(body[1][:2], ['', 'Third day'])
        self.assertEqual(body[-1][0], 'IL-6')

    def test_wrap_line_without_values_goes_on_in_the_row(self):
        """a leftmost wrap whose other texts are wraps too joins the row above (AR20 p7)"""
        t = [line(100, [(50, 'Property'), (250, 'Example')]),
             line(112, [(50, 'Protection from host'), (250, 'Production of polymers; protection from')]),
             line(124, [(50, 'dessication, etc.'), (250, 'phagocytosis')]),
             line(136, [(50, 'Open architecture'), (250, 'Presence of channels')])]
        f = ov.fit(t, [], K)
        g = c.overlay_grid(f, t, [0], [], K, frozenset(('PROC',)))
        body = [[' '.join(x) for x in r['cells']] for r in g['rows'] if not r['header']]
        self.assertEqual(len(body), 2)
        self.assertTrue(body[0][1].endswith('phagocytosis'))

    def test_memo_mark_inside_the_run_does_not_join_rows(self):
        """memo clues-1 (with its addition): the bracket lines are set in from the capital lines and end in a letter
        inside the same run, at the run's size ('(mn)a'); the capital line under one opens a row (TW2 as the user wrote
        it), even with rules parting the table elsewhere (TW6 would join them)"""
        vals = lambda y, lab: line(y, [(50, lab)] + [(160 + 45 * i, f'{i}.{i}') for i in range(7)])
        t = [line(100, [(50, 'Item')] + [(160 + 45 * i, f'H{i}') for i in range(7)]), line(114, [(46, 'Group one')]),
             vals(126, 'Alpha'), line(138, [(62, '(mn)a')]), vals(150, 'Beta'), line(162, [(62, '(sd)')]),
             line(176, [(46, 'Group two')]), vals(188, 'Gamma')]
        G = [([40 * K, yy * K, 480 * K, (yy + 0.5) * K], 'rule') for yy in (111.5, 173, 197.5)]
        f = ov.fit(t, G, K)
        g = c.overlay_grid(f, t, [0], G, K, frozenset(('label', 'a2', 'hspan', 'shade2', 'cent', 'PROC')))
        body = [' '.join(r['cells'][0]) for r in g['rows'] if not r['header']]
        self.assertIn('Alpha (mn)a', body)
        self.assertIn('Beta (sd)', body)

    def test_bracketed_number_with_text_is_a_label(self):
        """TW9: '(3) OFD vs. PRF' under a leftmost text opens a row of its own; '(72)' alone stays a wrap (TW1);
        '(4)*' with only an asterisk after it is no label"""
        t = [line(100, [(50, 'Study'), (250, 'Design')]),
             line(112, [(50, 'Group II: protocols')]),
             line(124, [(50, '(3) OFD vs. PRF')]),
             line(136, [(50, 'Chatterjee et al.'), (250, 'RCT')]),
             line(148, [(50, '(72)')]),
             line(160, [(50, 'Mehta et al.'), (250, 'RCT')]),
             line(172, [(50, '(4)*')])]
        f = ov.fit(t, [], K)
        g = c.overlay_grid(f, t, [0], [], K, frozenset(('label', 'a2', 'hspan', 'shade2', 'cent', 'PROC')))
        m = {x['lines'][1][:4]: x for x in g['cellrows']}
        self.assertEqual(m['(3) '].get('marks2', {}).get('TW9'), 'new')
        self.assertEqual(m['(3) ']['decision'], 'new')
        self.assertNotIn('TW9', m['(72)']['marks2'])
        self.assertEqual(m['(72)']['decision'], 'cont')
        self.assertNotIn('TW9', m['(4)*']['marks2'])

    def test_text_region_is_one_row(self):
        """TW17: between two row lines, the next column's text runs on over two lines: the region is one row, though a
        leftmost line inside starts with a capital; in a region of values the capital opens a row as before"""
        t = [line(100, [(50, 'Study'), (200, 'Findings')]),
             line(112, [(50, 'Nielsen et al.'), (200, 'Adult patients presenting for treatment at a')]),
             line(124, [(50, 'Denmark'), (200, 'university clinic were examined')]),
             line(140, [(50, 'Age'), (200, '12.5')]),
             line(152, [(50, 'Weight'), (200, '70.1')])]
        G = [([40 * K, yy * K, 480 * K, (yy + 0.5) * K], 'rule') for yy in (109.5, 133, 161)]
        f = ov.fit(t, G, K)
        g = c.overlay_grid(f, t, [0], G, K, frozenset(('label', 'a2', 'hspan', 'shade2', 'cent', 'PROC', 'RG', 'RGN', 'RGK2', 'RGG200')))
        body = [' '.join(r['cells'][0]) for r in g['rows'] if not r['header']]
        self.assertIn('Nielsen et al. Denmark', body)
        self.assertIn('Age', body)


class TW18Items(unittest.TestCase):
    F0 = ('label', 'a2', 'hspan', 'shade2', 'cent', 'PROC', 'RG', 'RGN', 'RGK2', 'RGG200')

    def test_a1_clear_gap_is_two_cells(self):
        """A1 (switch): a group the column line passes through at a clear gap is two cells, not a cut group (g holds)"""
        t = [line(100, [(50, 'Item'), (120, 'Value')])] + [line(112 + 12 * i, [(50, f'Row{i}'), (120, f'{i}.5')]) for i in range(5)]
        t.append(line(172, [(50, 'Long label'), (100, 'runs on')]))
        f = ov.fit(t, [], K)
        g = c.overlay_grid(f, t, [0], [], K, frozenset(self.F0 + ('T10A',)))
        self.assertTrue(g['g'])

    def test_a3_few_lines_judged_on_whole_body(self):
        """A3 (switch): with too few body lines for two halves, condition a is judged on the whole body"""
        t = [line(100, [(50, 'Item'), (200, 'n')]), line(112, [(50, 'Age'), (200, '12')]), line(124, [(50, 'Sex'), (200, '14')])]
        f = ov.fit(t, [], K)
        self.assertFalse(c.overlay_grid(f, t, [0], [], K, frozenset(self.F0))['a'])
        self.assertTrue(c.overlay_grid(f, t, [0], [], K, frozenset(self.F0 + ('T10C',)))['a'])

    def test_d9_two_lifted_lines_join_the_entry_cell(self):
        """D9 (audit): two bracket wrap lines with values after one leftmost text: both leftmost texts join the entry's cell"""
        t = [line(100, [(50, 'Marker'), (150, 'Time'), (250, 'Test')]),
             line(112, [(50, 'TGF-beta'), (150, 'Baseline'), (250, '15.20')]),
             line(124, [(50, '(pg/site)'), (150, 'Third'), (250, '11.93')]),
             line(136, [(50, '(median)'), (150, 'Fifth'), (250, '12.54')]),
             line(148, [(50, 'IL-6'), (150, 'Baseline'), (250, '1.20')])]
        f = ov.fit(t, [], K)
        g = c.overlay_grid(f, t, [0], [], K, frozenset(self.F0 + ('D9',)))
        body = [[' '.join(x) for x in r['cells']] for r in g['rows'] if not r['header']]
        self.assertEqual(body[0][0], 'TGF-beta (pg/site) (median)')

    def test_d8_bracket_line_under_empty_leftmost(self):
        """D8 (audit): TW1 as the user wrote it: a leftmost line starting with a bracket is a wrap, whatever the line above"""
        t = [line(100, [(50, 'Item'), (200, 'n')]), line(112, [(50, 'Weight'), (200, '12')]), line(124, [(200, '13')]),
             line(136, [(50, '(kg)')]), line(148, [(50, 'Height'), (200, '14')])]
        f = ov.fit(t, [], K)
        g = c.overlay_grid(f, t, [0], [], K, frozenset(self.F0 + ('D8',)))
        m = {x['lines'][1][:4]: x['marks2'] for x in g['cellrows']}
        self.assertEqual(m['(kg)'].get('TW1'), 'cont')

    def test_memo2_entry_lines_stay_paired(self):
        """memo clues-2: under one numbered leftmost text, lines with text in column 2 and their own entry in column 3
        (nothing in the leftmost column) stay lines of their own beside the one leftmost cell; a line of column 2 that
        goes on (small letter) joins the line it continues; no cell holds the entries of two lines"""
        t = [line(100, [(50, 'Item'), (150, 'Feature'), (300, 'Entry')]),
             line(112, [(50, '1. Alpha'), (150, 'Bone level'), (300, '2.1')]),
             line(125, [(150, 'Soft tissue'), (300, '3.4')]),
             line(138, [(150, 'Probing depth over'), (300, '1.2')]),
             line(148, [(150, 'six sites')]),
             line(161, [(50, '2. Beta'), (150, 'Bone level'), (300, '5.6')]),
             line(174, [(150, 'Soft tissue'), (300, '7.8')])]
        f = ov.fit(t, [], K)
        g = c.overlay_grid(f, t, [0], [], K, frozenset(self.F0 + ('D7',)))
        body = [[' '.join(x) for x in r['cells']] for r in g['rows'] if not r['header']]
        entries = [sum(1 for w in cell.split() if w.replace('.', '').isdigit() and '.' in w) for row in body for cell in row]
        self.assertTrue(max(entries) <= 1, body)
        self.assertTrue(any('Probing depth over six sites' in cell for row in body for cell in row), body)

    def test_t1_outside_title_leaves_the_grid(self):
        """T1 (TW20): a wide title above the table's first drawn line leaves the grid; a heading under that line stays"""
        t = [line(100, [(50, 'Characteristics of the included studies in the review')]),
             line(114, [(150, 'Outcome'), (250, 'Scores')]),
             line(126, [(50, 'Item'), (150, 'Test'), (250, 'Control')]),
             line(138, [(50, 'Age'), (150, '12.1'), (250, '13.2')]),
             line(150, [(50, 'Weight'), (150, '70.1'), (250, '71.2')])]
        G = [([40 * K, 110 * K, 330 * K, 110.5 * K], 'rule'), ([40 * K, 135 * K, 330 * K, 135.5 * K], 'rule')]
        f = ov.fit(t, G, K)
        g = c.overlay_grid(f, t, [0, 1, 2], G, K, frozenset(self.F0 + ('T1',)))   # the title stands above the top line
        self.assertEqual(g['trim_top'], ['Characteristics of the included studies in the review'])
        self.assertIn('Outcome', ' '.join(' '.join(x) for r in g['rows'] for x in r['cells']))

    def test_t1_heading_under_the_line_stays(self):
        """T1: a narrow heading over some columns, below the first drawn line, is not taken out (AT05 p5 kind)"""
        t = [line(100, [(150, 'Quality scale')]), line(112, [(50, 'Study'), (150, 'Selection'), (250, 'Exposure')]),
             line(124, [(50, 'Alpha'), (150, '3'), (250, '2')]), line(136, [(50, 'Beta'), (150, '2'), (250, '1')])]
        G = [([40 * K, 98 * K, 330 * K, 98.5 * K], 'rule'), ([40 * K, 121 * K, 330 * K, 121.5 * K], 'rule')]
        f = ov.fit(t, G, K)
        g = c.overlay_grid(f, t, [0, 1], G, K, frozenset(self.F0 + ('T1',)))
        self.assertEqual(g['trim_top'], [])

    def test_t2_lone_top_header_is_no_fault(self):
        """T2 (TW20): a lone top header line over the whole table stays a header row and does not fail d"""
        t = [line(100, [(50, 'Periodontal outcomes over time, all groups')]),
             line(112, [(50, 'Parameter'), (150, 'Test'), (250, 'Control')]),
             line(124, [(50, 'BOP'), (150, '24.2'), (250, '26.1')]),
             line(136, [(50, 'PD'), (150, '12.6'), (250, '17.8')]),
             line(148, [(50, 'CAL'), (150, '12.0'), (250, '17.3')]),
             line(160, [(50, 'GI'), (150, '1.0'), (250, '1.3')])]
        f = ov.fit(t, [], K)
        g = c.overlay_grid(f, t, [0, 1], [], K, frozenset(self.F0 + ('T2',)))
        self.assertTrue(g['d'] and g['header_settled'])
        self.assertIn('Periodontal outcomes over time, all groups', ' '.join(' '.join(x) for r in g['rows'] for x in r['cells']))

    def test_t1l_heading_over_some_columns_stays(self):
        """T1L (recorded): a wide heading above the first drawn line that starts inside the columns (AX04 p4 kind) stays"""
        t = [line(100, [(150, 'Resonance frequency analysis at all time points')]),
             line(114, [(50, 'Implant'), (150, 'Surgery'), (250, 'One year')]),
             line(126, [(50, '1'), (150, '80'), (250, '81')]), line(138, [(50, '2'), (150, '88'), (250, '64')])]
        G = [([40 * K, 111 * K, 330 * K, 111.5 * K], 'rule'), ([40 * K, 123 * K, 330 * K, 123.5 * K], 'rule')]
        f = ov.fit(t, G, K)
        self.assertEqual(c.overlay_grid(f, t, [0, 1], G, K, frozenset(self.F0 + ('T1', 'T1L')))['trim_top'], [])

    def test_t1_heading_under_top_drawn_line_stays(self):
        """T1 (send-back): a wide heading below the table's top drawn line is in the table: it stays (AX04 p4 kind)"""
        t = [line(100, [(150, 'Resonance frequency analysis at all time points')]),
             line(114, [(50, 'Implant'), (150, 'Surgery'), (250, 'One year')]),
             line(126, [(50, '1'), (150, '80'), (250, '81')]), line(138, [(50, '2'), (150, '88'), (250, '64')])]
        G = [([40 * K, 96 * K, 330 * K, 96.5 * K], 'rule'), ([40 * K, 123 * K, 330 * K, 123.5 * K], 'rule')]
        f = ov.fit(t, G, K)
        self.assertEqual(c.overlay_grid(f, t, [0, 1], G, K, frozenset(self.F0 + ('T1',)))['trim_top'], [])

    def test_t1_heading_inside_shading_stays(self):
        """T1 (send-back): a line inside the table's shading (its top edge above the line) stays (AT01 p9 kind)"""
        t = [line(100, [(150, 'Crude weighted analysis across the whole set')]),
             line(114, [(50, 'Item'), (150, 'Difference'), (250, 'p-Value')]),
             line(126, [(50, 'Alpha'), (150, '0.58'), (250, '.22')]), line(138, [(50, 'Beta'), (150, '0.67'), (250, '.16')])]
        G = [([40 * K, 97 * K, 330 * K, 121 * K], 'fill')]
        f = ov.fit(t, G, K)
        self.assertEqual(c.overlay_grid(f, t, [0, 1], G, K, frozenset(self.F0 + ('T1',)))['trim_top'], [])
