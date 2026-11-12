"""A two-column figure caption continues into a body block only in smaller type than the body."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('caption_tail_copy', ROOT/'copy_paper.py')
copy = importlib.util.module_from_spec(spec); spec.loader.exec_module(copy)


def rows(left, first, last, size=10, prefix='r'):
    texts=[first,'several ordinary words forming the middle of a long explanation',last]
    return [dict(id=f'{prefix}{left}{i}',kind='text',text=t,angle=0,line=i,font='Caption',
                 size_px=size,run_size_px=size,box_px=[left,110+i*14,left+200,120+i*14]) for i,t in enumerate(texts)]


class CaptionTailBody(unittest.TestCase):
    def setUp(self):
        self.left=rows(10,'Fig. 2. A long explanation of these scientific illustrations','the remaining cells form')
        self.right=rows(230,'continuous layers across the specimen and its surrounding structures','the last visible layer of the specimen.')
        self.runs={e['id']:e for e in self.left+self.right}
        self.blocks={'block:1':[e['id'] for e in self.left],'block:2':[e['id'] for e in self.right]}
        self.members=lambda bid:self.blocks.get(bid,[])
        self.page=dict(elements=[dict(kind='image',box_px=[10,0,430,100])]+self.left+self.right)
        self.cap=[e['id'] for e in self.left]

    def groups(self, body=12, excluded=frozenset(), blocked=frozenset(), ordered=None):
        return copy.caption_tail_body_groups(self.runs, ordered or {'block:2':{}}, self.members, self.cap, body, set(excluded), set(blocked))

    def test_smaller_caption_type_offers_the_whole_body_block(self):
        groups=self.groups(body=12)
        self.assertEqual(groups,[self.right])
        self.assertEqual(copy.caption_column_tail(self.page,self.left,groups),self.right)

    def test_body_sized_caption_offers_nothing(self):
        self.assertEqual(self.groups(body=10),[])
        self.assertEqual(self.groups(body=10.4),[])

    def test_owned_runs_and_blocked_blocks_are_not_offered(self):
        self.assertEqual(self.groups(blocked={'block:2'}),[])
        self.assertEqual(self.groups(excluded={self.right[1]['id']}),[[self.right[0],self.right[2]]])
        self.assertFalse(copy.caption_column_tail(self.page,self.left,self.groups(excluded={self.right[1]['id']})))

    def test_the_caption_block_itself_is_never_a_candidate(self):
        self.assertEqual(self.groups(ordered={'block:1':{},'block:2':{}}),[self.right])

    def test_body_paragraph_in_body_type_beside_a_caption_stays_body(self):
        for e in self.right: e['size_px']=e['run_size_px']=12
        groups=self.groups(body=12)
        self.assertEqual(groups,[self.right])
        self.assertFalse(copy.caption_column_tail(self.page,self.left,groups))


if __name__=='__main__': unittest.main()
