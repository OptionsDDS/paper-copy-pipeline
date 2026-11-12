"""Lane r2-frag: tables side by side in the page columns, where the detector seed runs on past the shorter
table into the next table's caption in that column (the other column's table is longer). The caption whose
own flowing block runs below the seed heads the next table: the side ends above it, its lines are no cell
of either part, and a float that named it over the seed is dropped. Fixtures are synthetic (invented text)."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('tablesub',Path(__file__).with_name('test_tablesub.py'))
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
c,run,page=t.c,t.run,t.page

COLS=((0,230),(250,480))


def side_by_side(short_left=True,short_rows=3,long_rows=6,tail_inside=False,block_inside=False):
    """Two captioned tables side by side; under the shorter one the next caption (label, then a title
    running three lines). The seed holds both tables' rows, the next label and its first title line."""
    xs,xl=(0,250) if short_left else (250,0)
    caps=[run('Table 1.',0,0,50),run('Table 2.',250,0,50)]
    titles=[run('Scores of the first clinic',0,12,180),run('Scores of the second clinic',250,12,180)]
    def rows(x,n,k):
        out=[]
        for i in range(n):
            y=40+15*i
            out+=[run(f'site {k}{i}',x,y,50),run(f'0.{k}{i}',x+120,y,20),run(f'0.0{i}',x+170,y,20)]
        return out
    short,long_=rows(xs,short_rows,1),rows(xl,long_rows,2)
    for e in short+long_:e['run_size_px']=8;e['size_px']=8
    ny=40+15*short_rows+8
    nlab=run('Table 3.',xs,ny,50)
    nlines=[run(s,xs,ny+14+13*i,200) for i,s in enumerate(['Adjusted change by status for the first',
                                                            'clinic with the factors named in the',
                                                            'methods of the invented study'])]
    es=caps+titles+short+long_+[nlab]+nlines
    extra=[]
    if tail_inside:   # the next table's rows follow inside the seed: an ordinary stacked caption
        extra=[run(f'group {i}',xs,ny+14+13*3+6+15*i,50) for i in range(3)]+[run(f'0.5{i}',xs+120,ny+14+13*3+6+15*i,20) for i in range(3)]
        for e in extra:e['run_size_px']=8;e['size_px']=8
        es+=extra
    p=page(es,COLS)
    p['blocks']=[dict(id='block:a',members=[caps[0]['id'],titles[0]['id']],box_px=c.hull([caps[0]['box_px'],titles[0]['box_px']])),
                 dict(id='block:b',members=[caps[1]['id'],titles[1]['id']],box_px=c.hull([caps[1]['box_px'],titles[1]['box_px']])),
                 dict(id='block:n',members=[nlab['id']]+[e['id'] for e in nlines],box_px=c.hull([nlab['box_px']]+[e['box_px'] for e in nlines]))]
    if block_inside:   # the seed runs on past the longer table: the whole next caption lies inside it
        long_+=[run(f'site 9{i}',xl,40+15*long_rows+15*i,50) for i in range(4)]
        for e in long_:e['run_size_px']=8;e['size_px']=8
        es+=long_[-4:]
    inseed=short+long_+[nlab,nlines[0]]+(nlines[1:]+extra if tail_inside or block_inside else [])
    seed=dict(id='table:1',angle=0,members=[e['id'] for e in inseed],box_px=c.hull(e['box_px'] for e in inseed))
    p['tables']=[seed]
    p['floats']=[dict(id='float:1',caption='Table 3.',blocks=['table:1'],box_px=list(seed['box_px']))]
    return p,caps+[nlab],short,long_,[nlab]+nlines,extra


class NextCaptionBelowTheSeed(unittest.TestCase):
    def check(self,short_left,block_inside=False):
        p,caps,short,long_,nxt,_=side_by_side(short_left=short_left,block_inside=block_inside)
        c.split_gutter_tables(p,caps,10)
        self.assertEqual(sorted(sorted(x['members']) for x in p['tables']),
                         sorted([sorted(e['id'] for e in short),sorted(e['id'] for e in long_)]))
        self.assertEqual(sorted(f['caption'] for f in p['floats']),['Table 1. Scores of the first clinic','Table 2. Scores of the second clinic'])
        held=[m for x in p['tables'] for m in x['members']]
        self.assertFalse({e['id'] for e in nxt}&set(held))           # the next caption's lines are no cells
        self.assertEqual(len(held),len(set(held)))                    # no line in two tables

    def test_shorter_table_on_the_left(self):
        self.check(True)

    def test_shorter_table_on_the_right(self):
        self.check(False)

    def test_whole_caption_inside_the_seed_with_no_rows_under_it_shorter_left(self):
        self.check(True,block_inside=True)

    def test_whole_caption_inside_the_seed_with_no_rows_under_it_shorter_right(self):
        self.check(False,block_inside=True)

    def test_a_stacked_caption_whose_block_ends_inside_the_seed_still_cuts_its_own_table(self):
        for short_left in (True,False):
            self.stacked(short_left)

    def stacked(self,short_left):
        p,caps,short,long_,nxt,extra=side_by_side(short_left=short_left,tail_inside=True)
        c.split_gutter_tables(p,caps,10)
        got=sorted(f['caption'].split('.')[0] for f in p['floats'])
        self.assertEqual(got,['Table 1','Table 2','Table 3'])
        third=next(x for x in p['tables'] if any(f['id']==x['id'] and f['caption'].startswith('Table 3') for f in p['floats']))
        self.assertEqual(sorted(third['members']),sorted(e['id'] for e in extra))


if __name__=='__main__':
    unittest.main()
