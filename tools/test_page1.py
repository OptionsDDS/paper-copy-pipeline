"""Front-panel ownership must preserve an adjacent continuing body column."""
import copy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
def module(name, file):
    spec = importlib.util.spec_from_file_location(name, ROOT / file)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

boxer = module('page1_boxer', 'standalone/element_boxer_sc.py')
paper = module('page1_copy', 'copy_paper.py')


def fixture():
    blocks, runs = [], []
    def add(name, lines, x, y, width, size, face, cls):
        members = []
        for i, text in enumerate(lines):
            rid = f'{name}:{i}'; members.append(rid)
            runs.append(dict(id=rid, text=text, kind='text', line=round(y+15*i), angle=0,
                             box_px=[x,y+15*i,x+width,y+15*i+size],
                             font=face, size_px=size, run_size_px=size))
        b = dict(id=name, members=members, box_px=[x,y,x+width,y+15*(len(lines)-1)+size],
                 cls=cls, size=size, lines=len(lines))
        blocks.append(b)
    add('names',['Ada Example, DDS1','Ben Sample, DDS, DMSc2'],30,80,130,10,'Test-Oblique','authors')
    prose = ['These ordinary words describe the study and its outcomes.']
    add('body',prose*24,250,80,120,10,'Test-Regular','authors')
    add('abstract',prose*8,0,125,220,9,'Test-Oblique','authors')
    add('address',['1Department of Science, Example University.'],0,390,220,8,'Test-Regular','authors')
    add('contact',['Correspondence to: Ada Example.','Email: ada@example.edu'],0,410,210,8,'Test-Regular','authors')
    next_blocks, next_runs = copy.deepcopy(blocks[1:2]), copy.deepcopy(runs[2:26])
    for b in next_blocks: b['cls']='main'
    return blocks, runs, dict(blocks=next_blocks,elements=next_runs,tables=[],floats=[])


class FrontColumns(unittest.TestCase):
    def apply(self, blocks, runs, following):
        return boxer.reading_order_front_columns(blocks,runs,following,[0,10,340,50])

    def test_summary_body_and_addresses_have_separate_ownership(self):
        blocks,runs,following=fixture(); original=copy.deepcopy(runs)
        record=self.apply(blocks,runs,following)
        self.assertEqual(record['body_blocks'],['body'])
        self.assertEqual(record['author_blocks'],['names'])
        self.assertEqual(record['abstract_blocks'],['abstract'])
        self.assertEqual([b['cls'] for b in blocks],['authors','main','main','other','other'])
        self.assertTrue(blocks[2]['side_abstract'])
        self.assertEqual(runs,original)

    def test_without_next_page_typography_no_reclassification(self):
        for key,value in [('font','Another-Regular'),('run_size_px',7)]:
            blocks,runs,following=fixture(); original=copy.deepcopy(blocks)
            for e in following['elements']: e[key]=value
            self.assertIsNone(self.apply(blocks,runs,following))
            self.assertEqual(blocks,original)

    def test_a_table_cannot_witness_continuing_body(self):
        blocks,runs,following=fixture()
        following['tables']=[dict(members=following['blocks'][0]['members'])]
        self.assertIsNone(self.apply(blocks,runs,following))

    def test_plain_adjacent_prose_is_not_an_unlabelled_summary(self):
        blocks,runs,following=fixture()
        for e in runs:
            if e['id'].startswith('abstract:'): e['font']='Test-Regular'
        self.assertIsNone(self.apply(blocks,runs,following))

    def test_fallback_cannot_reimport_body_from_a_bad_author_box(self):
        blocks,runs,following=fixture()
        record=self.apply(blocks,runs,following)
        p=dict(page=1,elements=runs,blocks=blocks,region_box_px=[0,0,400,500],
               main_text=dict(front_columns=record,blocks=blocks))
        au=dict(author_box_px=[0,70,380,450],authors=[],
                byline_lines=[dict(run_ids=['names:0','body:0'])])
        records,count=paper.printed_front_matter([p],au)
        lines='\n'.join(line for r in records for line in r['lines'])
        self.assertIn('Ada Example',lines)
        self.assertIn('Ben Sample',lines)
        self.assertNotIn('ordinary words',lines)

    def test_degree_suffix_is_not_an_extra_author(self):
        for degree in ['DMSc','MDS','MSD']:
            self.assertTrue(boxer.AUTHOR_DEGREE.fullmatch(degree))
            self.assertEqual(boxer.byline_name_groups([f'Ada Example, DDS, {degree}1']),['Ada Example'])


if __name__=='__main__': unittest.main()
