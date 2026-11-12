"""PCL has source-faithful views, evidence-only styles and explicit failures."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('writer', ROOT/'tools/pcl_writer.py')
w = importlib.util.module_from_spec(spec); spec.loader.exec_module(w)


def glyph(text, x, y=100, size=10, font='Example-Regular', **kw):
    return dict(text=text, origin=[x,y], size=size, font=font,
                x0=x, x1=x+5, y0=y-8, y1=y, adv_x1=x+5, **kw)


def line(text, page=1, role='body', group='body-1', styles=None, **kw):
    return dict(page=page, role=role, group=group, box=[0,0,100,10],
                atoms=[dict(text=c, style=(styles or {}).get(i, ())) for i,c in enumerate(text)], **kw)


class Styles(unittest.TestCase):
    def test_ported_notation_boundaries(self):
        for ratio, offset, expected in [
                (.88, .12, 'sup'), (.88, -.12, 'sub'),
                (.88001, .3, None), (.87, .11999, None),
                (.87, -.11999, None), (.85, 0, None), (.7, 1.2, 'sup')]:
            self.assertEqual(w.classify_notation(ratio, offset), expected)

    def test_explicit_names_flags_angle_weight_and_opaque_abstention(self):
        for name, meta, expected in [
            ('ABCDEF+Example-BoldItalic', {}, ('bold','italic')),
            ('Opaque', {'weight':700}, ('bold',)),
            ('Opaque', {'italic_angle':-12}, ('italic',)),
            ('Opaque', {'flags':64}, ('italic',)),
            ('Opaque', {'flags':262144}, ('bold',)),
            ('Example-Regular', {}, ()),
            ('Opaque', {}, ())]:
            self.assertEqual(w.font_style(name, meta)[0], expected)
        self.assertIsNotNone(w.font_style('Opaque')[1])
        self.assertIn('unsupported', w.font_style('Example-SmallCaps')[1])
        self.assertIn('unsupported', w.font_style('Opaque', {'flags':131072})[1])

    def test_baseline_geometry_handles_citations_exponents_and_formulas(self):
        cs=[glyph('H',0),glyph('2',5,103,7),glyph('O',10),glyph('2',15,103,7),
            glyph(' ',20),glyph('x',25),glyph('2',30,96,7),glyph(',',34,96,7),glyph('3',38,96,7)]
        result=w.classify(cs,{})
        self.assertEqual([r[0] for r in result],[(),('sub',),(),('sub',),(),(),('sup',),('sup',),('sup',)])

    def test_semantics_size_alone_and_unverified_glyphs_cannot_supply_style(self):
        cs=[glyph(c,i*5) for i,c in enumerate('H2O2 CO2 P gingivalis p = 0.05')]
        self.assertTrue(all(not r[0] for r in w.classify(cs,{})))
        cs=[glyph('A',0),glyph('B',5),glyph('2',10,100,6)]
        self.assertFalse(w.classify(cs,{})[-1][0])
        cs[-1].update(origin=[10,96],_mark_unverified=True,font='Example-BoldItalic')
        self.assertFalse(w.classify(cs,{})[-1][0])

    def test_whole_small_raised_line_does_not_mark_itself(self):
        self.assertTrue(all(not r[0] for r in w.classify([glyph(c,i*3,96,6) for i,c in enumerate('123')],{})))

    def test_ported_alphabet_rejects_dividers_but_keeps_witnessed_connectors(self):
        chars = [glyph('A', 0), glyph('B', 5), glyph('|', 10, 103, 7),
                 glyph(',', 15, 96, 7), glyph('–', 20, 96, 7)]
        styles = w.classify(chars, {})
        self.assertEqual(styles[2][0], ())
        self.assertIn('alphabet', styles[2][1])
        self.assertEqual(styles[3][0], ('sup',))
        self.assertEqual(styles[4][0], ('sup',))

    def test_signed_notation_and_citation_brackets_keep_their_own_witness(self):
        for symbol in '-+−/[]∗':
            for baseline, size, expected in [(96, 7, ('sup',)), (104, 7, ('sub',)),
                                               (100, 7, ()), (96, 10, ())]:
                with self.subTest(symbol=symbol, baseline=baseline, size=size):
                    chars = [glyph('A', 0), glyph('B', 5), glyph(symbol, 10, baseline, size)]
                    self.assertEqual(w.classify(chars, {})[-1][0], expected)

    def test_conflicting_positions_preserve_source_and_missing_advance_is_safe(self):
        class Engine:
            @staticmethod
            def mark_reading_frame(cs, angle):return cs
        run=dict(id='run',text='abc',angle=0,_chars=[glyph('a',0),glyph('b',10),glyph('c',5)])
        atoms=w.row_atoms([run],{}, {},Engine)
        self.assertEqual(''.join(a['text'] for a in atoms),'abc')
        self.assertTrue(all(not a['style'] and 'contradict' in a['issue'] for a in atoms))
        run['_chars']=[glyph('a',0),glyph('b',5),glyph('c',10)]
        run['_chars'][0]['adv_x1']=None
        self.assertEqual(''.join(a['text'] for a in w.row_atoms([run],{}, {},Engine)),'abc')


@unittest.skipUnless(w.DEFAULT_VALIDATOR.is_file(), 'approved offline validator unavailable')
class Grammar(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.parser=w.module('_pcl_test_reference',w.DEFAULT_VALIDATOR)

    def render(self, lines):
        text,spans,unknown=w.serialize(lines,'a'*64)
        doc=self.parser.parse(text)
        analysis=self.parser.analyse(doc)
        return self.parser.printed(doc),analysis.text,spans,text

    def test_nesting_delimiters_control_and_ligature_roundtrip(self):
        p,r,s,encoded=self.render([line('ﬁ ⟦x⟧\x08',styles={3:('bold','italic'),4:('italic',)})])
        self.assertEqual(p,'ﬁ ⟦x⟧\x08\n')
        self.assertEqual(r,'fi ⟦x⟧ ')
        self.assertIn('⟦char U+27E6⟧',encoded)
        self.assertEqual([v['kind'] for v in s],['italic','bold','italic'])

    def test_notation_is_derived_and_plain_words_are_unchanged(self):
        p,r,_,_=self.render([line('CO2 and 109', styles={2:('sub',),10:('sup',)})])
        self.assertEqual(p,'CO2 and 109\n')
        self.assertEqual(r,'CO_{2} and 10^{9}')

    def test_furniture_cross_page_wrap_heading_and_float(self):
        lines=[line('micro-',group='body'),line('footer',role='furniture',group='foot'),
               line('biota',page=2,group='body',wrap={'from':1,'hyphen':'remove'}),
               line('Results',page=2,role='heading',group='head'),
               line('A caption',page=2,role='caption',group='caption'),
               line('Body.',page=2,group='new')]
        p,r,_,_=self.render(lines)
        self.assertEqual(p,'micro-\nfooter\nbiota\nResults\nA caption\nBody.\n')
        self.assertEqual(r,'microbiota\nResults\nBody.\nA caption')

    def test_multiline_heading_and_table_keep_source_baselines(self):
        p,r,_,_=self.render([line('Long',role='heading',group='h'),line('heading',role='heading',group='h'),
                            line('A 1',role='table',group='t'),line('B 2',role='table',group='t')])
        self.assertEqual(p,'Long\nheading\nA 1\nB 2\n')
        self.assertEqual(r,'Long heading\nA 1 B 2')

    def test_number_depth_and_unknown_levels_do_not_change_heading_text(self):
        for title, expected in [('1 | Introduction', 1), ('2.3 Methods', 2),
                                ('2.3.4. Results', 3), ('3) Discussion', 1),
                                ('Results', '?'), ('IV. Results', '?'),
                                ('a. Results', '?'), ('0 Results', '?')]:
            printed, _, _, encoded = self.render([line(title, role='heading')])
            self.assertEqual(printed, title+'\n')
            self.assertIn(f'heading level={expected} ', encoded)
        _, _, _, encoded = self.render([line('1. A reference')])
        self.assertNotIn('⟦heading', encoded)

    def test_number_alone_on_first_heading_line(self):
        _, reading, _, encoded = self.render([
            line('2.3.4', role='heading', group='h'),
            line('Methods', role='heading', group='h')])
        self.assertIn('heading level=3 ', encoded)
        self.assertEqual(reading, '2.3.4 Methods')

    def test_isolated_numeric_match_cannot_establish_a_heading_level(self):
        encoded, _, uncertain = w.serialize([line('1', role='heading', group='h'),
                                             line('A table row', group='body')], 'a'*64)
        self.assertIn('heading level=? ', encoded)
        self.assertEqual(uncertain[0]['reason'],
                         'numbered heading has no mapped title; level left unknown')

    def test_bad_pages_and_surrogate_fail_explicitly(self):
        with self.assertRaises(ValueError):self.render([line('x',page=2)])
        with self.assertRaises(ValueError):self.render([line('\ud800')])
        with self.assertRaises(ValueError):self.render([line('\x01')])


class Publishing(unittest.TestCase):
    def test_reference_parser_rejection_never_publishes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path/'paper.pdf').write_bytes(b'synthetic digest input')
            (path/'copy.md').write_text('original\n')
            (path/'copy.conservation.json').write_text('{}')
            (path/'copy.pcl').write_text('stale')
            bad = ('⟦paper-copy 1.2 source=' + '0'*64 + ' uses=pcl/1.2⟧'
                   '⟦page 1⟧⟦line 1⟧⟦sup⟧⟦/sup⟧\n')
            with patch.object(w, 'build_lines', return_value=([], {}, [])), \
                 patch.object(w, 'font_metadata', return_value={}), \
                 patch.object(w, 'serialize', return_value=(bad, [], [])), \
                 patch.dict(os.environ, {'COPY_PDF_PCL_VALIDATOR': str(w.DEFAULT_VALIDATOR)}):
                with self.assertRaises(Exception) as raised:
                    w.write(path, path/'paper.pdf', [], [], engine=object())
            self.assertEqual(type(raised.exception).__name__, 'PclError')
            self.assertFalse((path/'copy.pcl').exists())
            self.assertFalse((path/'copy.pcl.tmp').exists())
            self.assertEqual((path/'copy.md').read_text(), 'original\n')
            self.assertEqual(json.loads((path/'copy.pcl.audit.json').read_text())['status'], 'failed')

    def test_failure_removes_stale_pcl_and_preserves_markdown(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)
            (path/'copy.md').write_text('original\n')
            (path/'copy.pcl').write_text('stale')
            with self.assertRaises(ValueError):w.write(path,None,[],[])
            self.assertFalse((path/'copy.pcl').exists())
            self.assertEqual((path/'copy.md').read_text(),'original\n')
            self.assertEqual(json.loads((path/'copy.pcl.audit.json').read_text())['status'],'failed')

    def test_snapshot_does_not_alias_native_evidence(self):
        pages=[dict(elements=[dict(_chars=[glyph('x',0)])])]
        saved=w.snapshot(pages)
        pages[0]['elements'][0]['_chars'][0]['text']='y'
        self.assertEqual(saved[0]['elements'][0]['_chars'][0]['text'],'x')


class Engine:
    """The two geometry helpers the placement uses, for upright synthetic rows."""
    @staticmethod
    def frame(angle): return lambda b: (b[0], b[1], b[2], b[3])

    @staticmethod
    def hull(boxes):
        boxes = list(boxes)
        return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def row(text, y, page=1, x=0, role='body', block='b1', run='r1', owner=None, inferred=True):
    """A decoded row as source_lines makes it: 5-unit glyphs, spaces between words."""
    atoms = []
    for k, ch in enumerate(text):
        if ch == ' ':
            if k and text[k-1] == ' ':   # a second space: a cell gutter, no glyph
                x += 20; continue
            atoms.append(dict(text=' ', style=(), gap=inferred)); x += 3; continue
        atoms.append(dict(text=ch, style=(), evidence=dict(run=run, box=[x, y, x+5, y+8], size=10)))
        x += 5
    key, kat, spans = w.row_key(atoms)
    return dict(page=page, atoms=atoms, runs=[run], box=[0, y, x, y+8], angle=0, role=role,
                float_owner=owner, member=owner, key=key, kat=kat, block=block,
                ocr=False, pieces=[], run_spans=spans)


class TraceWindows(unittest.TestCase):
    """copy.trace.json decides where a source row may be printed."""

    def trace(self, status='flagged_repeat'):
        return dict(schema='copy-trace/2 (native)',
                    units=[dict(id='u1', kind='author'), dict(id='u2', kind='front_matter_printed')],
                    lines=[dict(page=1, page_line=1, runs=['r1'], status=status,
                                units=[dict(unit_id='u1', copy_span=[10, 20]),
                                       dict(unit_id='u2', copy_span=[100, 120])]),
                           dict(page=1, page_line=2, runs=['r2'], status='lost', units=[])])

    def test_flagged_repeat_prefers_the_parsed_destination(self):
        rows = [dict(page=1, page_line=1, runs=['r1'], key='printedbyline'),
                dict(page=1, page_line=2, runs=['r2'], key='lostprintedrow')]
        windows = w.trace_windows(self.trace(), rows)
        self.assertEqual(windows[0]['regions'], [(10, 20), (100, 120)])
        self.assertEqual(windows[0]['primary'], [(10, 20)])
        self.assertEqual(windows[1], dict(regions=[], primary=[]))

    def test_short_and_ocr_rows_keep_the_matching_fallback(self):
        rows = [dict(page=1, page_line=1, runs=['r1'], key='short'),
                dict(page=1, page_line=2, runs=['r2'], key='longprintedrow', ocr=True)]
        self.assertEqual(w.trace_windows(self.trace(), rows), {})

    def test_close_cells_of_one_row_are_one_region(self):
        trace = self.trace(status='unit')
        trace['lines'][0]['units'][0]['copy_span'] = [10, 20]
        trace['lines'][0]['units'][1]['copy_span'] = [22, 30]
        windows = w.trace_windows(trace, [dict(page=1, page_line=1, runs=['r1'], key='longprintedrow')])
        self.assertEqual(windows[0]['regions'], [(10, 30)])


@unittest.skipUnless(w.DEFAULT_VALIDATOR.is_file(), 'approved offline validator unavailable')
class CopyUnits(unittest.TestCase):
    """PCL lines come from the copy's own units: same words, same order."""
    @classmethod
    def setUpClass(cls): cls.parser=w.module('_pcl_test_reference_units',w.DEFAULT_VALIDATOR)

    def build(self, rows, text):
        index = w.copy_index(text)
        lines = w.place_lines(rows, index, Engine, sorted({r['page'] for r in rows}))
        encoded, spans, _ = w.serialize(lines, 'a'*64)
        document = self.parser.parse(encoded)
        analysis = self.parser.analyse(document)
        lettering = {i for i, l in enumerate(lines, 1) if l.get('unused') and l['role'] == 'figure'}
        reading, ordered = w.pcl_words(analysis, lettering)
        expected = w.copy_words(index)
        return lines, encoded, w.compare(expected, ordered, index, lines, rows, 'file'), \
            w.compare(expected, reading, index, lines, rows, 'reading'), self.parser.printed(document)

    def test_generated_labels_and_uncertainty_are_not_copy_words(self):
        text = ('Document kind: review\n\n# Title words\n\n**Authors:** Ann Bee 1\n\n'
                '**Table 1. Values**\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n\nImage file: figures/t.png (page 1)\n\n'
                'After text.\n\n---\n## Places the program is not sure of\n- page 1: secret words')
        index = w.copy_index(text)
        words = [t for t, _ in w.copy_words(index)]
        self.assertEqual(words, ['Title', 'words', 'Ann', 'Bee', '1', 'Table', '1', 'Values',
                                 'a', 'b', '1', '2', 'After', 'text'])
        kinds = [(u['kind'], u['group']) for u in index['units']]
        self.assertEqual(kinds, [('title', None), ('paragraph', None), ('caption', 1), ('table_row', 1),
                                 ('table_row', 1), ('paragraph', None)])

    def test_copy_order_hyphen_join_heading_and_para(self):
        rows = [row('The quick fox jum-', 0), row('ped over it.', 10), row('Results', 20, block='h'),
                row('Next part.', 30, block='b2')]
        text = '## Results\n\nThe quick fox jumped over it.\n\nNext part.\n'
        lines, encoded, file_order, reading, printed = self.build(rows, text)
        self.assertTrue(file_order['equal'] and reading['equal'], file_order['differences'])
        self.assertEqual(printed, 'Results\nThe quick fox jum-\nped over it.\nNext part.\n')
        self.assertIn('⟦wrap 3 hyphen=remove basis=rule ref=copy-joins/1.0⟧', encoded)
        self.assertIn('⟦heading level=? ', encoded)
        self.assertIn('⟦line 4⟧⟦para⟧Next', encoded)

    def test_kept_hyphen_follows_the_copy(self):
        rows = [row('an endo-', 0), row('perio lesion', 10)]
        lines, encoded, file_order, _, _ = self.build(rows, 'an endo-perio lesion\n')
        self.assertTrue(file_order['equal'])
        self.assertIn('hyphen=keep', encoded)

    def test_spaces_follow_the_copy_never_the_glyphs(self):
        # The copy splits a joined label and joins a letter-spaced word: an
        # inferred space is added, a printed space is kept but not read.
        rows = [row('see Fig.1 now', 0), row('W O R D S', 10, block='b2', inferred=False)]
        lines, encoded, file_order, _, printed = self.build(rows, 'see Fig. 1 now\n\nWORDS\n')
        self.assertTrue(file_order['equal'], file_order['differences'])
        self.assertIn('Fig.⟦gap⟧1', encoded)
        self.assertIn('⟦glyph U+0020 as=none rule=copy-joins/1.0 gap=', encoded)
        self.assertEqual(printed.splitlines()[1], 'W O R D S')

    def test_raised_line_end_hyphen_is_never_joined(self):
        rows = [row('dose 10-', 0), row('5 here', 10)]
        rows[0]['atoms'][-1]['style'] = ('sup',)
        lines, encoded, file_order, _, printed = self.build(rows, 'dose 10-5 here\n')
        self.assertNotIn('⟦wrap', encoded)
        self.assertEqual(printed, 'dose 10-\n5 here\n')

    def test_row_spanning_two_cells_is_cut_at_the_other_rows_text(self):
        rows = [row('alpha one  omega two', 0, block='t'), row('beta', 10, block='t', run='r2')]
        self.assertEqual(rows[0]['run_spans'], [(0, 8), (8, 16)])
        lines, encoded, file_order, _, printed = self.build(rows, 'alpha one beta omega two\n')
        self.assertTrue(file_order['equal'])
        self.assertEqual(printed, 'alpha one\nbeta\nomega two\n')

    def test_unused_rows_keep_their_glyphs_with_honest_roles(self):
        rows = [row('Body words here.', 10), row('Journal 2026', 0, role='furniture', block='f'),
                row('Panel label', 20, block='fig', owner=('Figure 1', 'figure', 'lettering')),
                row('Lost line.', 30, block='b2')]
        lines, encoded, file_order, _, printed = self.build(rows, 'Body words here.\n')
        self.assertIn('⟦furniture⟧Journal', encoded)
        self.assertIn('kind=figure', encoded)
        self.assertEqual(sorted(printed.splitlines()), sorted(['Body words here.', 'Journal 2026',
                                                              'Panel label', 'Lost line.']))
        self.assertEqual(file_order['pcl_only'], 2)
        self.assertEqual({c for d in file_order['differences'] for c in d['causes']}, {'lost'})

    def test_page_grouping_and_case_are_measured_causes(self):
        rows = [row('Text ends', 0, page=1), row('TABLE 1', 10, page=1, block='c',
                owner=('Table 1', 'table', 'caption')), row('here.', 0, page=2, block='b2')]
        text = 'Text ends here.\n\n**Table 1**\n'
        lines, encoded, file_order, reading, _ = self.build(rows, text)
        # Page 1's caption cannot follow page 2's text; its label keeps its printed case.
        self.assertEqual([l['text'] for l in lines], ['Text ends', 'TABLE 1', 'here.'])
        causes = {c for d in file_order['differences'] for c in d['causes']}
        self.assertEqual(causes, {'case', 'page_order'})
        self.assertFalse(file_order['equal_ignoring_case'])


if __name__=='__main__':unittest.main()
