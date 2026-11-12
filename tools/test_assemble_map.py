"""Schema, conservation and adversarial line-map assembly checks."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('assemble_map_tests', ROOT/'tools/assemble_map.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def document(*texts):
    return dict(paper='example', pages=[dict(page=1, width_px=200, height_px=300, image='pages/p01.png',
        lines=[dict(id=f'p1.l{i:03}', text=text, box=[10, 10+i*12, 190, 20+i*12], size=10,
                    bold=False, italic=False, program_role='body') for i, text in enumerate(texts, 1)])])


def paragraph(*ids):
    return dict(paper='example', body=[dict(kind='paragraph', lines=list(ids))])


class Validation(unittest.TestCase):
    def test_duplicate_and_missing_are_errors(self):
        d = document('one', 'two')
        with self.assertRaisesRegex(a.MapError, 'used twice'):
            a.render(d, paragraph('p1.l001', 'p1.l001', 'p1.l002'))
        with self.assertRaisesRegex(a.MapError, 'unused line ids: p1.l002'):
            a.render(d, paragraph('p1.l001'))

    def test_unknown_and_replacement_text_are_errors(self):
        with self.assertRaisesRegex(a.MapError, 'unknown line id'):
            a.render(document('one'), paragraph('invented text'))
        m = paragraph('p1.l001'); m['body'][0]['text'] = 'fabricated'
        with self.assertRaisesRegex(a.MapError, 'unknown fields'):
            a.render(document('one'), m)

    def test_split_inside_word_rejected(self):
        m = paragraph('p1.l001a', 'p1.l001b')
        m['split_lines'] = [dict(id='p1.l001', at='nation', new_ids=['p1.l001a', 'p1.l001b'])]
        with self.assertRaisesRegex(a.MapError, 'word boundary'):
            a.render(document('examination result'), m)

    def test_split_preserves_text_and_retires_parent(self):
        m = paragraph('p1.l001a', 'p1.l001b')
        m['split_lines'] = [dict(id='p1.l001', at='Second column', new_ids=['p1.l001a', 'p1.l001b'])]
        text, audit = a.render(document('First column   Second column'), m)
        self.assertIn('First column Second column', text)
        self.assertEqual(audit['conservation']['used_once'], 2)
        m['body'][0]['lines'].append('p1.l001')
        with self.assertRaisesRegex(a.MapError, 'unknown line id'):
            a.render(document('First column   Second column'), m)

    def test_ambiguous_anchor_and_new_id_collision_rejected(self):
        m = paragraph('p1.l001a', 'p1.l001b')
        m['split_lines'] = [dict(id='p1.l001', at='x', new_ids=['p1.l001a', 'p1.l001b'])]
        with self.assertRaisesRegex(a.MapError, 'exactly once'):
            a.render(document('a x b x'), m)
        m['split_lines'][0].update(at='b', new_ids=['p1.l001a', 'p1.l001a'])
        with self.assertRaisesRegex(a.MapError, 'collision'):
            a.render(document('a b'), m)

    def test_duplicate_source_and_wrong_paper_rejected(self):
        d = document('one'); d['pages'][0]['lines'] *= 2
        with self.assertRaisesRegex(a.MapError, 'duplicate source'):
            a.render(d, paragraph('p1.l001'))
        m = paragraph('p1.l001'); m['paper'] = 'another'
        with self.assertRaisesRegex(a.MapError, 'paper does not match'):
            a.render(document('one'), m)

    def test_invalid_geometry_and_nonfinite_numbers(self):
        for field, value in [('box', [-1, 0, 5, 5]), ('box', [0, 0, float('nan'), 5]), ('size', 0), ('bold', 1)]:
            with self.subTest(field=field, value=value):
                d = document('one'); d['pages'][0]['lines'][0][field] = value
                with self.assertRaises(a.MapError): a.render(d, paragraph('p1.l001'))

    def test_failed_validation_writes_nothing_and_preserves_old_copy(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            folder = Path(tmp); lines = folder/'lines.json'; mapping = folder/'map.json'; out = folder/'out'
            lines.write_text(json.dumps(document('one', 'two')))
            mapping.write_text(json.dumps(paragraph('p1.l001')))
            with self.assertRaises(a.MapError): a.assemble(lines, mapping, out)
            self.assertFalse(out.exists())
            out.mkdir(); (out/'copy.md').write_text('previous success')
            with self.assertRaises(a.MapError): a.assemble(lines, mapping, out)
            self.assertEqual((out/'copy.md').read_text(), 'previous success')


class Rendering(unittest.TestCase):
    def test_printed_end_matter_label_is_not_duplicated(self):
        m=dict(paper='example',end_matter=[dict(label='Acknowledgments',lines=['p1.l001','p1.l002'])])
        text,_=a.render(document('Acknowledgments','Thanks to the authors.'),m)
        self.assertEqual(text.count('Acknowledgments'),1)
        self.assertIn('## Acknowledgments\n\nThanks to the authors.',text)

    def test_caption_uses_current_copy_label_convention(self):
        m=dict(paper='example',body=[dict(kind='caption',of='Figure 2',lines=['p1.l001'])])
        text,_=a.render(document('F I G U R E 2 A printed caption'),m)
        self.assertIn('**Figure 2. A printed caption**',text)

    def test_empty_table_cell_degrades_without_invented_values(self):
        d = document('Table 1', 'First', 'Value', 'note')
        m = dict(paper='example', body=[dict(kind='table', caption=['p1.l001'],
            rows=[[['p1.l002'], []], [['p1.l003'], []]], header_rows=1, notes=[['p1.l004']])])
        text, audit = a.render(d, m)
        self.assertIn('2 printed lines', text)
        self.assertNotIn('| ---', text)
        self.assertIn('no whole line ids', text)
        self.assertIn('\nnote\n', text)
        self.assertEqual(audit['conservation']['used_once'], 4)
        self.assertEqual(audit['tables'][0]['decision'], 'table_lines')

    def test_spanning_header_is_repeated_but_owned_once(self):
        d = document('Combined header', 'A', 'B', '1', '2')
        m = dict(paper='example', body=[dict(kind='table', caption=[],
            rows=[[['p1.l001']], [['p1.l002'], ['p1.l003']], [['p1.l004'], ['p1.l005']]],
            header_rows=2, notes=[])])
        text, audit = a.render(d, m)
        self.assertIn('| Combined header<br>A | Combined header<br>B |', text)
        self.assertIn('| --- | --- |\n| 1 | 2 |', text)
        self.assertEqual(audit['conservation']['used_once'], 5)

    def test_zero_headers_does_not_promote_data_to_header(self):
        m = dict(paper='example', body=[dict(kind='table', caption=[],
            rows=[[['p1.l001']]], header_rows=0, notes=[])])
        text, _ = a.render(document('value'), m)
        self.assertIn('|  |\n| --- |\n| value |', text)

    def test_furniture_count_notes_and_shared_hyphen_policy(self):
        d = document('exami-', 'nation examination', '12')
        m = paragraph('p1.l001', 'p1.l002'); m.update(furniture=dict(page_number=['p1.l003']), notes=['Page 1: check formula'])
        text, audit = a.render(d, m)
        self.assertIn('examination examination', text)
        self.assertNotIn('\n12\n', text)
        self.assertIn('- Page 1: check formula', text)
        self.assertEqual(audit['furniture']['page_number'], 1)
        self.assertEqual(audit['conservation']['used_once'], 3)

    def test_all_schema_kinds_have_renderers(self):
        d = document(*['printed ' + str(i) for i in range(17)])
        ids = [line['id'] for line in d['pages'][0]['lines']]
        m = dict(paper='example', front=dict(title=ids[:1], subtitle=ids[1:2], authors=ids[2:3],
            affiliations=[ids[3:4]], article_info=[ids[4:5]], abstract=ids[5:6], keywords=ids[6:7]),
            body=[dict(kind='heading', level=3, lines=ids[7:8]), dict(kind='list_item', lines=ids[8:9]),
                  dict(kind='caption', of='Figure 2', lines=ids[9:10]), dict(kind='formula', lines=ids[10:11]),
                  dict(kind='footnote', lines=ids[11:12]), dict(kind='box', title=ids[12:13], items=[ids[13:14]]),
                  dict(kind='table_lines', caption=[], lines=ids[14:15], reason='Page 1: merged cells')],
            references=[ids[15:16]], end_matter=[dict(label='Acknowledgments', lines=ids[16:])])
        text, audit = a.render(d, m)
        for i in range(17): self.assertIn('printed ' + str(i), text)
        self.assertEqual(audit['conservation']['used_once'], 17)
        self.assertIn('### printed 7', text)


if __name__ == '__main__': unittest.main()
