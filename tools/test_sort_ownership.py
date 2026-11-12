"""Ownership boundaries: retain every source run and refuse ambiguous geometry."""
import copy
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('boxer_sort',Path(__file__).resolve().parents[1]/'standalone/element_boxer_sc.py')
b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)


def run(i,text,x,y,w=100,size=10):
    return dict(id=i,kind='text',text=text,line=y,angle=0,box_px=[x,y,x+w,y+size],
                size_px=size,run_size_px=size)


def block(i,es,cls='main'):
    return dict(id=i,members=[e['id'] for e in es],cls=cls,lines=len({e['line'] for e in es}),
                size=max(e['run_size_px'] for e in es),text=' '.join(e['text'] for e in es),
                box_px=[min(e['box_px'][0] for e in es),min(e['box_px'][1] for e in es),
                        max(e['box_px'][2] for e in es),max(e['box_px'][3] for e in es)])


def page(es,bs,tables=()):
    return dict(elements=es,blocks=copy.deepcopy(bs),tables=list(tables),region_box_px=[0,0,500,800])


class Ownership(unittest.TestCase):
    def test_separate_note_gap_and_table_exclusion(self):
        a=run('body','The procedure continues',0,690,200,10)
        n=run('note','† Instrument, Example, USA.',0,750,160,7)
        bs=[block('a',[a]),block('n',[n])];p=page([a,n],bs)
        after,ordered,_,notes,_,retained=b.sort_main_ownership(p,bs,bs,10)
        self.assertEqual([x['id'] for x in ordered],['a'])
        self.assertEqual(notes[0]['members'],['note'])
        self.assertEqual(after[-1]['role'],'footnote')
        self.assertEqual(len(retained),1)
        # Same glyphs owned by a table cannot become a page footnote.
        self.assertFalse(b.column_footnotes(bs,p['elements'],10,800,{'note'}))

    def test_body_size_list_and_nonfoot_notes_remain_body(self):
        for size,y in [(10,750),(7,400)]:
            es=[run('a','Ordinary paragraph',0,350,200),run('n','1 A numbered list item',0,y,160,size)]
            bs=[block('a',es[:1]),block('n',es[1:])]
            _,ordered,_,notes,_,_=b.sort_main_ownership(page(es,bs),bs,bs,10)
            self.assertEqual(len(ordered),2);self.assertFalse(notes)
        es=[run('a','Ordinary paragraph',0,690,200),run('n','2 i',0,750,30,7)]
        bs=[block('a',es[:1]),block('n',es[1:])]
        self.assertFalse(b.column_footnotes(bs,es,10,800))

    def test_owned_table_cell_and_overlapping_prose(self):
        es=[run('cell','Value 24',0,100,80,8),run('body','Continuing paragraph',100,90,180,10)]
        bs=[block('a',es[:1]),block('b',es[1:])]
        t=dict(id='table',box_px=[0,99,200,200],members=['cell','body'])
        after,ordered,ledger,notes,_,_=b.sort_main_ownership(page(es,bs,[t]),bs,bs,10)
        self.assertEqual(after[0]['role'],'table');self.assertEqual([x['id'] for x in ordered],['b'])
        self.assertIn('ownership_flags',ordered[0]);self.assertFalse(notes)
        self.assertEqual(ledger['accounting']['unaccounted'],0)
        self.assertFalse(ledger['accounting']['duplicate_ids'])
        self.assertEqual(ledger['objects'][1]['assignment']['role'],'unassigned')

    def test_two_table_owners_fail_closed_without_widening(self):
        e=run('c','Value',0,100,80,8);bs=[block('a',[e])]
        ts=[dict(id=i,box_px=[0,100,100,150],members=['c']) for i in ('t1','t2')]
        p=page([e],bs,ts);saved=copy.deepcopy(ts)
        _,ordered,ledger,_,_,_=b.sort_main_ownership(p,bs,bs,10)
        self.assertEqual(len(ordered),1);self.assertEqual(ts,saved)
        self.assertEqual(ledger['accounting']['enumerated'],1)
        self.assertEqual(ledger['objects'][0]['assignment']['role'],'unassigned')

    def test_contact_panel_is_header_but_abstract_is_preserved(self):
        es=[run('a','Department of Examples',0,100,size=7),run('b','E-mail: a@example.org',0,110,size=7)]
        for front,abstract,expected in [(True,False,'other'),(False,False,'main'),(True,True,'other')]:
            bs=[block('a',es)];bs[0]['abstract']=abstract
            after,_,_,_,_,_=b.sort_main_ownership(page(es,bs),bs,bs,10,front=front)
            self.assertEqual(after[0]['cls'],expected)

    def test_standalone_keyword_label_owns_only_nearby_small_list(self):
        es=[run('label','KEYWORDS',0,100,60,8),run('values','one, two, three',0,120,150,8),
            run('prose','The ordinary body begins.',0,160,220,10)]
        bs=[block(e['id'],[e]) for e in es]
        after,ordered,_,_,_,_=b.sort_main_ownership(page(es,bs),bs,bs,10,front=True)
        self.assertEqual([x['id'] for x in ordered],['prose'])
        self.assertEqual(after[1]['header_group'],'label')

    def test_inline_split_preserves_one_owner_per_run(self):
        es=[run('h','Identifiers',0,100,160),run('a','A Person',0,120,60),
            run('tail','1234',0,140,40),run('b','B Person https://example.org/id',0,160,250),
            run('url','https://example.org/part-',75,120,150)]
        bs=[block('host',es[:4]),block('fragment',es[4:])]
        p=page(es,bs);after,ordered,_,_,splits,_=b.sort_main_ownership(p,bs,bs,10)
        self.assertEqual([x['text'] for x in ordered],['Identifiers','A Person https://example.org/part-\n1234\nB Person https://example.org/id'])
        ms=[m for x in after for m in x['members']]
        self.assertEqual(sorted(ms),sorted(e['id'] for e in es))
        self.assertEqual(splits[0]['absorbed'],['fragment'])
        self.assertEqual(len(p['blocks']),4)  # originals retained for rule-6 replay

    def test_repeated_shading_owns_captioned_list_but_never_body_sized_prose(self):
        for size,expected in [(8,'caption'),(10,'main')]:
            es=[run('cap','TABLE 1',0,50,50),run('title','Findings',60,50,110)]
            es += [run(str(i),'A printed entry',10,100+25*i,170,size) for i in range(6)]
            es += [dict(id='fill'+str(i),kind='fill',box_px=[0,y,200,y+24]) for i,y in enumerate((90,150,210))]
            bs=[block('title',es[1:2]),block('cells',es[2:8])]
            p=page(es,bs);p['unpaired']=[dict(caption='TABLE 1',block='cap',box_px=es[0]['box_px'])]
            after,ordered,ledger,_,_,_=b.sort_main_ownership(p,bs,bs,10)
            self.assertEqual(after[1]['cls'],expected)
            self.assertEqual(len(ledger['regions']),int(size==8))
            self.assertFalse(p['tables'])  # ownership does not invent a table grid

    def test_footnote_placement_requires_unique_citation_and_preserves_order(self):
        spec=importlib.util.spec_from_file_location('copy_sort',Path(__file__).resolve().parents[1]/'copy_paper.py')
        c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
        es=[run('a','The calibrated instrument† was used.',0,100),run('n','† Supplier, City.',0,750,size=7)]
        bs=[block('body',es[:1]),block('note',es[1:],'other')];p=page(es,bs);p['page']=2
        p['main_text']=dict(blocks=bs,footnotes=[dict(members=['n'])])
        a=dict(kind='para',page=2,text='The calibrated instrument† was used. The paragraph finishes.')
        q=dict(kind='para',page=2,text='A later paragraph.')
        n=dict(kind='side',page=2,text='† Supplier, City.')
        self.assertEqual(c.place_owned_footnotes([a,q,n],[p]),[a,n,q])
        duplicate=dict(a)
        self.assertEqual(c.place_owned_footnotes([a,duplicate,q,n],[p]),[a,duplicate,q,n])
        es[0]['text']='Device† was calibrated before every measurement.'
        a['text']=es[0]['text'];p['elements']=es
        self.assertEqual(c.place_owned_footnotes([a,q,n],[p]),[a,n,q])

    def test_explicit_page_note_cannot_be_borrowed_by_table_growth(self):
        spec=importlib.util.spec_from_file_location('copy_sort',Path(__file__).resolve().parents[1]/'copy_paper.py')
        c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
        cells=[run(f'c{i}{j}',text,x,650+20*i,45,8)
               for i,text in enumerate(('Label','First','Second')) for j,x in enumerate((0,100))]
        cap=run('cap','Table 1. Measurements',0,620,170,10)
        note=run('note','† Supplier, City.',0,710,170,7)
        es=[cap,*cells,note]
        for e in es:e.update(char_ids=[],_faces={'Example-Regular':len(e['text'])})
        p=page(es,[]);p.update(page=2,floats=[],main_text=dict(blocks=[],columns=[[0,500]],
            footnotes=[dict(members=['note'])]))
        p['tables']=[dict(id='table',angle=0,box_px=[0,640,200,700],members=[e['id'] for e in cells])]
        p['blocks']=[dict(id='caption',members=['cap'],box_px=cap['box_px'])]
        p['floats']=[dict(id='float',caption=cap['text'],blocks=['table','caption'],box_px=[0,620,200,700])]
        _,floats,side=c.read_page(p,10,[])
        self.assertEqual(side,[[note['text']]])
        owned={item['id'] for f in floats for line in f[5]['table_source']['lines'] for item in line['items']}
        self.assertEqual(owned,{e['id'] for e in cells})
        p['blocks'].append(dict(id='cells',members=[e['id'] for e in cells],box_px=[0,650,145,698]))
        p['main_text']['blocks']=[dict(id='cells',cls='caption',role='table',owner='table',lines=3,size_px=8,box_px=[0,650,145,698])]
        _,floats,_=c.read_page(p,10,[])
        self.assertTrue(any('assembled' in warning for f in floats for warning in f[5]['table_source']['assembly_warnings']))

    def test_owned_note_block_keeps_separate_markers_and_wrapped_tails(self):
        spec=importlib.util.spec_from_file_location('copy_sort',Path(__file__).resolve().parents[1]/'copy_paper.py')
        c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
        es=[run('a','† First supplier,',0,700,size=7),run('b','another city.',10,710,size=7),
            run('c','‡ Second supplier.',0,720,size=7)]
        p=dict(main_text=dict(footnotes=[dict(members=['a','b','c'])]))
        groups=c.owned_note_groups(p,{e['id']:e for e in es})
        self.assertEqual([[e['id'] for e in g] for g in groups],[['a','b'],['c']])

    def test_keyword_label_without_unique_list_stays_with_its_words(self):
        es=[run('label','KEYWORDS',0,100,60,8),run('values','one, two, three',0,120,150,10)]
        bs=[block(e['id'],[e]) for e in es]
        after,ordered,_,_,_,_=b.sort_main_ownership(page(es,bs),bs,bs,10,front=True)
        self.assertEqual([x['id'] for x in ordered],['label','values'])
        self.assertNotIn('role',after[0]);self.assertNotIn('header_from_body',after[0])

    def test_key_words_read_after_abstract_record_their_place(self):
        es=[run('abs','Abstract The study measured outcomes.',0,100,220,10),
            run('kw','Key words: one, two',0,130,150,8),run('body','Introduction text.',0,170,200,10)]
        bs=[block(e['id'],[e]) for e in es]
        after,ordered,_,_,_,_=b.sort_main_ownership(page(es,bs),bs,bs,10,front=True)
        self.assertEqual([x['id'] for x in ordered],['abs','body'])
        self.assertEqual(after[1]['header_after'],'abs')
        # a key-word block keeps its place after an unlabelled abstract too
        es2=[run('para','Periodontitis is common in adults.',0,100,220,10),
             run('kw','Key words: one, two',0,130,150,8),run('body','Introduction text.',0,170,200,10)]
        bs=[block(e['id'],[e]) for e in es2]
        after,_,_,_,_,_=b.sort_main_ownership(page(es2,bs),bs,bs,10,front=True)
        self.assertEqual(after[1]['header_after'],'para')
        # read first on the page: no recorded place, the header keeps it
        bs=[block(e['id'],[e]) for e in es];bs=[bs[1],bs[0],bs[2]]
        after,_,_,_,_,_=b.sort_main_ownership(page(es,bs),bs,bs,10,front=True)
        self.assertNotIn('header_after',after[0])

    def test_inline_split_never_cuts_below_a_contained_block(self):
        es=[run('r0','Found at: one (0.04 MB',0,100,250),run('r1','Table S4',0,120,60),
            run('r2','Found at: two',0,140,100),run('frag','MB',105,140,20),
            run('h1','Primers used',120,120,100),run('h2','for this',120,130,100)]
        bs=[block('host',es[:3]),block('fragment',es[3:4]),block('hole',es[4:])]
        p=page(es,bs);after,ordered,_,_,splits,_=b.sort_main_ownership(p,bs,bs,10)
        self.assertEqual(len(splits[0]['parts']),1)
        self.assertEqual([x['id'] for x in ordered],['host:row1','hole'])
        self.assertEqual(sorted(m for x in after for m in x['members']),sorted(e['id'] for e in es))
        # without the contained block the host is cut at the repaired baseline
        bs=[block('host',es[:3]),block('fragment',es[3:4])]
        _,ordered,_,_,splits,_=b.sort_main_ownership(page(es[:4],bs),bs,bs,10)
        self.assertEqual(len(splits[0]['parts']),2)

    def test_deferred_key_words_follow_the_abstract(self):
        spec=importlib.util.spec_from_file_location('copy_sort',Path(__file__).resolve().parents[1]/'copy_paper.py')
        c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
        front=dict(page=1,_deferred_keywords=[dict(lines=['Key words','one, two'],after='abs')])
        a=dict(kind='para',page=1,text='The abstract.',source_blocks=[(1,'abs')])
        h=dict(kind='heading',page=1,text='Introduction');q=dict(kind='para',page=1,text='Body.')
        out=c.place_deferred_keywords([a,h,q],front,c.Joiner([]))
        self.assertEqual([x['text'] for x in out],['The abstract.','Key words: one, two','Introduction','Body.'])
        # no abstract in the copy: the words open the body
        out=c.place_deferred_keywords([h,q],front,c.Joiner([]))
        self.assertEqual(out[0]['text'],'Key words: one, two')



if __name__=='__main__':unittest.main()
