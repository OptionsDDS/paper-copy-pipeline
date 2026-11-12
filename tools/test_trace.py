"""Exact tracing, offsets, ambiguity, normalization, PCL and source ID contracts."""
import importlib.util
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('trace_tests',ROOT/'tools/trace.py')
t=importlib.util.module_from_spec(spec);sys.modules[spec.name]=t;spec.loader.exec_module(t)


def line(mid,text,page=1,**extra):
    return dict(id=mid,text=text,page=page,number=1,box_pdf_points=[1,2,3,4],box_110dpi=[1,2,3,4],**extra)


def match(text,lines):return t.match_units(t.units_from_markdown(text),lines)


class Trace(unittest.TestCase):
    def test_normalisation_preserves_scientific_values_case_and_punctuation(self):
        self.assertNotEqual(t.normalise('0.05')[0],t.normalise('005')[0])
        self.assertNotEqual(t.normalise('A')[0],t.normalise('a')[0])
        self.assertNotEqual(t.normalise('−1')[0],t.normalise('-1')[0])
        self.assertNotEqual(t.normalise('é')[0],t.normalise('e')[0])
        self.assertNotEqual(t.normalise('ﬁ')[0],t.normalise('fi')[0])
        self.assertEqual(t.normalise(r'**x** ^{2} H_{2}O \*')[0],'x2H2O*')
        self.assertEqual(t.normalise('line-\n',source=True,drop_hyphen=True)[0],'line')
        self.assertEqual(t.normalise('non-linear',source=True,drop_hyphen=True)[0],'non-linear')

    def test_units_offsets_and_all_required_common_types(self):
        text='# Title\n\n**Authors:** Ana One; Bea Two\n- 1 University\n\n## Article information\n- Received now\n\n## Abstract\nPurpose text\n\n## Methods\nParagraph.\n\n- item\n\n**Table 1. Values**\n\n| Name | Value |\n| --- | --- |\n| X | 2 |\n\nNote here.\n\n> footnote\n\n## References\n- 1. Paper\n\n## ORCID\n- Author URL\n\n## Places the program is not sure of\n- none\n'
        units=t.units_from_markdown(text);kinds=[u['kind'] for u in units]
        for kind in ('title','author','affiliation','article_information','abstract_part','heading','paragraph','list_item','caption','table_cell','table_note','footnote','reference','end_matter','uncertainty_item'):
            self.assertIn(kind,kinds)
        self.assertEqual(kinds.count('author'),2)
        self.assertEqual(kinds.count('table_cell'),4)
        for u in units:self.assertEqual(u['text'],text[slice(*u['span'])])
        self.assertTrue(all(a['span'][1]<=b['span'][0] for a,b in zip(units,units[1:])))

    def test_exact_wrapping_reverse_and_order(self):
        text='A sufficiently distinctive sentence ends here.\n'
        units,lines=match(text,[line('p1.l001','A sufficiently distinctive'),line('p1.l002','sentence ends here.')])
        self.assertEqual(units[0]['status'],'fully_traced')
        self.assertEqual([s['line_id'] for s in units[0]['sources']],['p1.l001','p1.l002'])
        self.assertTrue(all(l['status']=='placed' for l in lines))
        self.assertEqual(lines[1]['units'][0]['unit_id'],units[0]['id'])

    def test_terminal_hyphen_and_markup_only(self):
        units,lines=match('A very distinctive continuous word.',[line('p1.l001','A very distinctive con-'),line('p1.l002','tinuous word.')])
        # A short unique continuation is found as a complete line by anchors
        # only if sufficient context exists; unresolved text stays explicit.
        self.assertTrue(units[0]['sources'])
        self.assertFalse(any('guess' in w['method'] for s in units[0]['sources'] for w in s['witnesses']))
        units,lines=match('The measured value was 5.1.',[line('p1.l001','The measured value was 5.2.')])
        self.assertNotEqual(units[0]['status'],'fully_traced')
        self.assertEqual(lines[0]['status'],'not placed')
        self.assertIn('1',''.join(x['text'] for x in units[0]['unmatched']))

    def test_repeated_values_are_never_assigned_arbitrarily(self):
        units,lines=match('| 1.2 | 1.2 |\n',[line('p1.l001','1.2'),line('p1.l002','1.2')])
        self.assertTrue(all(u['status']=='unmatched' for u in units))
        self.assertTrue(all(l['status']=='not placed' for l in lines))

    def test_wrapped_table_cell_cannot_take_identical_body_phrase(self):
        body=line('body','Distinct growth factor is important.',contexts=['body'])
        first=line('cell1','Distinct growth',contexts=['table'])
        second=line('cell2','factor',contexts=['table'])
        first['box_110dpi']=[10,10,80,20]
        second['box_110dpi']=[10,25,40,35]
        body['box_110dpi']=[100,100,200,110]
        units,lines=match('| Distinct growth factor |\n',[body,first,second])
        self.assertEqual(units[0]['status'],'fully_traced')
        self.assertEqual({s['line_id'] for s in units[0]['sources']},{'cell1','cell2'})
        self.assertFalse(lines[0]['units'])

    def test_duplicate_copy_use_is_visible_in_reverse(self):
        units,lines=match('A distinctive printed sentence.\n\nA distinctive printed sentence.',[line('p1.l001','A distinctive printed sentence.')])
        self.assertEqual(len(lines[0]['units']),2)
        self.assertTrue(all(u['status']=='fully_traced' for u in units))

    def test_no_false_furniture(self):
        units,lines=match('A distinctive body sentence.',[line('p1.l001','A distinctive body sentence.'),line('p1.l002','Missing important sentence.'),line('p1.l003','Journal Header',furniture_evidence=['running head'])])
        self.assertEqual(lines[1]['status'],'not placed')
        self.assertEqual(lines[2]['status'],'furniture')
        self.assertEqual(lines[2]['furniture_reason'],'running head')

    def test_generated_unit_is_not_a_false_source_match(self):
        units,lines=match('## Places the program is not sure of\n- none\n',[line('p1.l001','none')])
        self.assertTrue(all(u['status']=='generated' for u in units))
        self.assertEqual(lines[0]['status'],'not placed')

    def test_empty_and_escaped_table_cells(self):
        units=t.units_from_markdown('| | A\\|B |\n| --- | --- |\n')
        self.assertEqual(len(units),2)
        self.assertEqual(units[0]['text'],'')
        self.assertEqual(t.normalise(units[1]['text'])[0],'A|B')

    def test_pcl_global_numbering_printed_glyphs_and_page_scope(self):
        digest='a'*64
        pcl=f'⟦paper-copy 1.2 source={digest} uses=pcl/1.2⟧⟦page 1⟧⟦line 1⟧⟦bold⟧First⟦/bold⟧\n⟦page 2⟧⟦line 2⟧⟦glyph U+03B1 as=U+0061 rule=test/1.0⟧\n'
        result=t.pcl_markers(pcl,[line('p1.l009','First'),line('p2.l003','α',2)],digest)
        markers=[r for r in result['markers'] if r['kind']=='line']
        self.assertEqual([r['sources'][0]['line_id'] for r in markers],['p1.l009','p2.l003'])
        self.assertEqual(result['unmatched'],0)
        self.assertFalse(t.pcl_markers(pcl,[], 'b'*64)['ok'])
        self.assertEqual(result['annotations']['reading_map'][-1]['source_line_id'],'p2.l003')
        self.assertEqual(result['annotations']['reading_map'][-1]['substituted'],'U+03B1')

    def test_pcl_ambiguous_and_unknown_commands_are_unmatched(self):
        digest='a'*64
        prefix=f'⟦paper-copy 1.2 source={digest} uses=pcl/1.2⟧⟦page 1⟧⟦line 1⟧'
        for body,lines in [('1.2',[line('p1.l001','1.2'),line('p1.l002','1.2')]),('⟦unknown⟧value',[line('p1.l001','value')])]:
            result=t.pcl_markers(prefix+body+'\n',lines,digest)
            self.assertFalse(result['ok'])
            self.assertTrue(result['errors'] or result['unmatched'])
            self.assertEqual(len(result['markers']),2)
            for marker in result['markers']:
                self.assertTrue((prefix+body+'\n')[slice(*marker['span'])].startswith('⟦'))

    def test_ported_ids_and_strict_membership(self):
        self.assertEqual(t.accounting.source_id('a'*64,2,0),'pdf:'+'a'*64+':p2:c0')
        with self.assertRaises(ValueError):t.accounting.source_id('x',1,0)
        units,lines=match('A distinctive printed sentence.\n\nA distinctive printed sentence.',[line('l1','A distinctive printed sentence.')])
        audit=t.accounting.account(lines,units)
        self.assertFalse(audit['ok'])
        self.assertEqual(len(audit['lines_in_multiple_units']),1)
        units,lines=match('Known sentence.',[line('l1','Known sentence.'),line('l2','Lost sentence.')])
        self.assertFalse(t.accounting.account(lines,units)['ok'])
        lines[1]['furniture_evidence']=['running head']
        self.assertTrue(t.accounting.account(lines,units)['ok'])

    def test_split_line_also_fails_literal_revision_rule(self):
        units,lines=match('**Authors:** Ada One; Bea Two',[line('l1','Ada One Bea Two')])
        self.assertEqual(len(t.accounting.account(lines,units)['lines_in_multiple_units']),1)

    def test_ported_character_annotations_and_ambiguity(self):
        text='# Distinctive text.'
        units,lines=match(text,[line('l1','Distinctive text.')])
        mapping=t.accounting.annotations(text,units,lines,t.normalise)
        self.assertEqual(''.join(e['char'] for e in mapping),text)
        self.assertEqual(mapping[0]['derived'],'copy whitespace or markup')
        for entry in mapping[2:]:
            if 'derived' not in entry:
                self.assertEqual(lines[0]['text'][entry['column']],entry['char'])
        units[0]['sources'].append(dict(units[0]['sources'][0],line_id='l2'))
        mapping=t.accounting.annotations(text,units,lines+[line('l2','Distinctive text.')],t.normalise)
        self.assertEqual(len(mapping[2]['candidates']),2)

    def test_cli_fails_findings_after_report_is_written(self):
        with patch.object(sys,'argv',['trace.py','--legacy','folder','pdf']),patch.object(t,'build',return_value={'statistics':{},'ok':False}):
            with self.assertRaises(SystemExit) as failure:t.main()
            self.assertEqual(failure.exception.code,1)

    def test_cli_validates_the_native_trace_by_default(self):
        report={'ok':False,'valid':True,'problems':[],'statistics':{}}
        with patch.object(sys,'argv',['trace.py','folder']),patch.object(t,'validate',return_value=report) as validate:
            with self.assertRaises(SystemExit) as failure:t.main()
            self.assertEqual(failure.exception.code,1)
            validate.assert_called_once_with('folder',None,False)
        with patch.object(sys,'argv',['trace.py','folder']),patch.object(t,'validate',return_value=dict(report,ok=True)):
            t.main()


if __name__=='__main__':unittest.main()
