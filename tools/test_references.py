"""Reference boundary/ownership regressions: /usr/bin/python3 -I tools/test_references.py."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1] / 'copy_paper.py')
paper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paper)


class References(unittest.TestCase):
    def assemble(self, rows):
        page = dict(page=1, elements=[], blocks=[], tables=[], floats=[],
                    region_box_px=[0, 0, 500, 800], main_text={'blocks': [], 'columns': [[0, 400]]})
        blocks = []
        for i, (lines, first, in_refs) in enumerate(rows):
            boxes = [[0, 100+i*100+j*20, 400, 110+i*100+j*20] for j in range(len(lines))]
            meta = dict(id=str(i), cls='main', order=i, size_px=16, lines=len(lines),
                        in_refs=in_refs, box_px=paper.hull(boxes))
            blocks.append(dict(lines=lines, first=first, lefts=[0]*len(lines), sizes=[16]*len(lines),
                               row_boxes=boxes, meta=meta, page=1, page_height=800))
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as directory:
            (Path(directory)/'page-01.json').write_text(json.dumps(page))
            with patch.object(paper, 'load', return_value=([page], {'body_size_px': 16}, {})), \
                 patch.object(paper, 'read_page', return_value=(blocks, [], [])), \
                 patch.object(paper, 'table_pdf_path', return_value=None):
                result = paper.main(directory)
            return Path(result).read_text()

    def split(self, lines, lefts):
        return paper.split_references(dict(lines=lines, lefts=lefts, meta={'size_px': 16}), paper.Joiner([]))

    def test_unspaced_labels_and_inline_numbers(self):
        parts = self.split(['9. Able AB. A title with 10. in its text.',
                            'Journal 8:20-30.', '10.Baker CD. Another title.'], [100, 124, 100])
        self.assertEqual(len(parts), 2)
        self.assertIn('10. in its text.', parts[0][0])
        self.assertTrue(parts[1][1])

    def test_indented_numeric_continuations(self):
        parts = self.split(['7. Able AB. Journal 4:200-', '250. e3.',
                            '8. Baker CD. A condition of type', '1. Journal 5:10-20.',
                            '9. Carter EF. Next title.'], [100, 126, 100, 126, 100])
        self.assertEqual(len(parts), 3)
        self.assertIn('200-250. e3.', parts[0][0])
        self.assertIn('type 1. Journal', parts[1][0])

    def test_right_aligned_number_widths(self):
        parts = self.split(['98. Able AB. First title.', '99. Baker CD. Second title.',
                            '100. Carter EF. Third title.', '1. is a continuation.'], [109, 109, 100, 140])
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(start for _, start in parts))
        self.assertIn('1. is a continuation.', parts[-1][0])

    def test_labels_can_be_indented_from_continuation_lines(self):
        parts = self.split(['1. Able AB. First title.', 'Journal 1:2-3.',
                            '2. Baker CD. Next title.', 'Journal 2:4-5.'], [114, 100, 114, 100])
        self.assertEqual(len(parts), 2)
        self.assertTrue(all(start for _, start in parts))

    def test_detached_furniture_labels_need_baseline_and_sequence(self):
        lines = ['Able AB. First title.', 'Journal 4:5-6.', 'Baker CD. Next title.',
                 'Carter EF. Unrelated footer.']
        block = dict(lines=lines, lefts=[130]*4, meta={'size_px': 16},
                     row_boxes=[[130, y, 480, y+12] for y in (100, 120, 150, 190)])
        def label(i, value, y):
            return dict(id=i, kind='text', text=value, angle=0, box_px=[101, y, 120, y+12])
        page = dict(elements=[label('a', '21.', 100), label('b', '22.', 150), label('c', '42.', 190)],
                    blocks=[dict(id='furniture', members=['a', 'b', 'c'])],
                    main_text={'blocks': [dict(id='furniture', cls='furniture')]})
        parts = paper.split_references(block, paper.Joiner([]), source_page=page)
        self.assertEqual(len(parts), 2)
        self.assertTrue(parts[0][0].startswith('21. Able'))
        self.assertTrue(parts[1][0].startswith('22. Baker'))
        self.assertNotIn('42.', parts[1][0])
        self.assertEqual(block['lines'], lines)
        self.assertEqual(page['main_text']['blocks'][0]['cls'], 'furniture')

    def test_supplement_heading_is_a_boundary_not_a_title_mention(self):
        self.assertTrue(paper.REF_END.fullmatch('SUPPLEMENTAL MATERIAL'))
        self.assertTrue(paper.REF_END.fullmatch('Supplementary information:'))
        self.assertFalse(paper.REF_END.fullmatch('Supplemental material in a study.'))

    def test_detached_label_before_lowercase_author_after_unpunctuated_entry(self):
        block = dict(lines=['20. Able AB. First title without final punctuation',
                            'de Silva, A.; van Dijk, B. Next title.', '22. Baker CD. Last title.'],
                     lefts=[100,130,100],meta={'size_px':16},
                     row_boxes=[[100,100,480,112],[130,130,480,142],[100,160,480,172]])
        page = dict(elements=[dict(id='label',kind='text',text='21.',angle=0,box_px=[100,130,120,142])],
                    blocks=[dict(id='f',members=['label'])],main_text={'blocks':[dict(id='f',cls='furniture')]})
        parts=paper.split_references(block,paper.Joiner([]),source_page=page)
        self.assertEqual(len(parts),3)
        self.assertTrue(parts[1][0].startswith('21. de Silva'))
        self.assertTrue(all(start for text,start in parts))
        block['lines'][1]='World Health Organization. An institutional author.'
        parts=paper.split_references(block,paper.Joiner([]),source_page=page)
        self.assertEqual(len(parts),3)
        self.assertTrue(parts[1][0].startswith('21. World Health Organization.'))

    def test_equation_prefix_outside_references_is_unchanged(self):
        result = self.assemble([(['_ AB CD )EF', 'AB ~ GH'], '_', False)])
        self.assertIn('_ AB CD )EF AB ~ GH', result)
        self.assertNotIn('## _ AB', result)

    def test_supplement_notice_in_body_does_not_open_a_section(self):
        result = self.assemble([(['Notice for readers.', 'Supplemental material:'], 'Notice for readers.', False)])
        self.assertNotIn('## Supplemental material', result)

    def test_supplement_ends_reference_even_inside_its_block(self):
        result = self.assemble([(['References'], 'References', True),
                                (['1. Able AB. Journal 1:2-3.', 'SUPPLEMENTAL MATERIAL'], '1. Able AB.', True),
                                (['A supplementary title.'], 'A supplementary title.', True)])
        self.assertIn('- 1. Able AB. Journal 1:2-3.\n', result)
        self.assertIn('## SUPPLEMENTAL MATERIAL', result)
        self.assertNotIn('1:2-3. SUPPLEMENTAL', result)

    def test_reference_continues_across_blocks_before_a_backmatter_boundary(self):
        result = self.assemble([(['References'], 'References', True),
                                (['1. Able AB. A title. Journal'], '1. Able AB.', True),
                                (['2000;4:20-30.', '2. Baker CD. Next title.'], '2000;4:20-30.', True),
                                (['SUPPLEMENTAL MATERIAL'], 'SUPPLEMENTAL MATERIAL', True),
                                (['An independent supplement.'], 'An independent supplement.', False)])
        self.assertIn('- 1. Able AB. A title. Journal 2000;4:20-30.', result)
        self.assertIn('- 2. Baker CD. Next title.', result)
        self.assertNotIn('- An independent supplement.', result)
        self.assertNotIn('reference numbering expected', result)

    def test_reference_word_islands_stay_in_their_column_and_row(self):
        def run(name, text, x, y, width):
            return dict(id=name, kind='text', text=text, angle=0, box_px=[x, y, x+width, y+10])
        runs = {e['id']: e for e in [run('start', '7. Able AB. A', 0, 20, 45),
                run('middle', 'long title.', 60, 20, 35), run('journal', 'Journal.', 110, 20, 50),
                run('end', '8. Baker CD. Next title.', 0, 40, 170), run('other', 'Other column.', 240, 20, 100),
                run('float', 'Figure text.', 160, 20, 30) ]}
        blocks = {
            'refs': dict(cls='main', in_refs=True, box_px=[0, 20, 200, 50], _members=['start', 'end']),
            'island': dict(cls='main', in_refs=True, box_px=[110, 20, 160, 30], _members=['journal']),
            'loose': dict(cls='other', box_px=[60, 20, 95, 30], _members=['middle', 'float']),
            'right': dict(cls='main', in_refs=True, box_px=[240, 20, 440, 50], _members=['other'])}
        result = paper.reference_rows({'refs': ['start', 'end'], 'island': ['journal'], 'right': ['other']},
                                      runs, blocks, [[0, 200], [240, 440]], 16, {'float'})
        self.assertEqual(set(result['refs']), {'start', 'middle', 'journal', 'end'})
        self.assertEqual(result['right'], ['other'])
        self.assertNotIn('island', result)
        self.assertEqual(len([m for ms in result.values() for m in ms]), 5)

    def test_unplaced_aside_in_reference_row_uses_the_block_extent(self):
        def run(name,text,x,y,width):
            return dict(id=name,kind='text',text=text,angle=0,run_size_px=10,
                        box_px=[x,y,x+width,y+10])
        es=[run('start','7. Able AB. Journal',100,20,150),
            run('year','1999.',260,20,30),run('end','12:34-56.',120,40,60),
            run('different_row','2001.',260,60,30),run('other_column','Other.',320,20,30),
            run('float','Figure.',260,40,30)]
        runs={e['id']:e for e in es}
        blocks={'refs':dict(cls='main',in_refs=True,box_px=[100,20,295,50],_members=['start','end']),
                'aside':dict(cls='aside',_members=['year','different_row','other_column','float'])}
        result=paper.reference_rows({'refs':['start','end']},runs,blocks,[[110,280],[320,500]],10,{'float'})
        self.assertEqual(set(result['refs']),{'start','year','end'})
        self.assertEqual(' '.join(e['text'] for e in paper.text_rows([runs[m] for m in result['refs']])[0]),
                         '7. Able AB. Journal 1999.')


if __name__ == '__main__':
    unittest.main()
