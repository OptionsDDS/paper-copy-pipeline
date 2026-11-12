"""Checker (r3): the token ledger claims at a run's own position, matches the two halves of
a printed word together and respects word boundaries; the completeness share counts copied
words only, the same for a table rendered as a grid or as its printed lines."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,ROOT/path)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
a=module('audit_r3checker','tools/conserve.py')
c=module('copy_r3checker','copy_paper.py')


def run(name,text,x0,y0,x1,y1,page=1,**extra):
    return dict(page=page,id=name,text=text,box=[x0,y0,x1,y1],**extra)


def missing(ledger):
    return [(t['run'],t['text']) for t in ledger['tokens'] if t['status']=='missing']


class HyphenHalves(unittest.TestCase):
    def test_line_end_hyphen_and_next_line_head_are_one_word(self):
        # Justified spacing set the continuation as a run of its own.
        text='Lamps burned over the shoreline netmaker seagrass. A shoreline path.'
        runs=[run('a','Lamps burned over the shor-',0,0,300,12),
              run('b','eline',0,16,40,28),run('c','netmaker seagrass.',70,16,300,28),
              run('d','A shoreline path.',0,40,200,52)]
        self.assertEqual(missing(a.token_ledger(text,runs)),[])

    def test_word_broken_at_a_column_end_continues_at_the_next_column_top(self):
        # The left column's last line ends 'weath-'; the word goes on at the
        # top of the right column, level with the top of the left block.
        text=('Lead line of the left block Note one harbour weathervane quayside keepers. '
              'Note two lanterns morning. Quiet weather today.')
        runs=[run('l0','Lead line of the left block',0,100,200,112),run('l1','Note one harbour weath-',0,116,200,128),
              run('r1a','ervane',240,100,290,112),run('r1b','quayside keepers.',300,100,440,112),
              run('r2','Note two lanterns morning.',240,116,440,128),run('w','Quiet weather today.',0,300,200,312)]
        self.assertEqual(missing(a.token_ledger(text,runs)),[])

    def test_two_runs_on_one_baseline_without_word_space_are_one_word(self):
        text='Department of Surgery, University of the Coast'
        runs=[run('a','Department of Surgery, Unive',0,0,250,12),run('b','rsity',252,0,290,12),
              run('c','of the Coast',300,0,400,12)]
        self.assertEqual(missing(a.token_ledger(text,runs)),[])

    def test_a_head_that_only_starts_a_longer_word_is_not_the_other_half(self):
        # 'heal-' + 'In' spells the start of 'healing', not a whole word; the
        # true continuation 'ing' heads the next column.
        text='Rates of wound healing complications. In the trial the healing was quick.'
        runs=[run('a','Rates of wound heal-',0,200,200,212),run('b','In the trial the',240,180,440,192),
              run('c','ing complications.',240,100,440,112),run('d','healing was quick.',240,196,440,208)]
        ledger=a.token_ledger(text,runs)
        self.assertEqual(missing(ledger),[])

    def test_two_separate_words_are_not_joined_as_halves(self):
        # Neighbouring runs whose words the copy prints with a space between.
        text='adhesion molecule and adhesion'
        runs=[run('a','adhesion',0,0,60,12),run('b','molecule',64,0,120,12),run('c','and adhesion',130,0,220,12)]
        self.assertEqual(missing(a.token_ledger(text,runs)),[])

    def test_halves_that_are_runs_of_their_own_do_not_block_each_other(self):
        # Justified spacing: every word a run; 'Unive'+'rsity' on one baseline
        # and 'shor-' / 'eline' across a line end are each one word.
        text='Faculty of Science University of the Coast. The shoreline path.'
        words=[('Faculty',0),('of',70),('Science',100),('Unive',180),('rsity',222),('of',290),('the',320),('Coast.',360)]
        runs=[run('w%d'%i,t,x,0,x+(40 if t!='Unive' else 41),12) for i,(t,x) in enumerate(words)]
        runs+=[run('h1','The',0,16,30,28),run('h2','shor-',300,16,350,28),run('h3','eline',0,32,40,44),run('h4','path.',300,32,350,44)]
        self.assertEqual(missing(a.token_ledger(text,runs)),[])

    def test_a_kept_line_end_break_is_claimed_as_printed(self):
        # The copy keeps 'maxi- mal' (a scan's text); the joined 'maximal'
        # elsewhere belongs to another run.
        text='with maxi- mal strength. The maximal force.'
        runs=[run('a','with maxi-',0,0,100,12),run('b','mal strength.',0,16,120,28),
              run('c','The maximal force.',0,40,160,52)]
        ledger=a.token_ledger(text,runs)
        self.assertEqual(missing(ledger),[])
        spans={t['run']:t['output'] for t in ledger['tokens'] if t['text'] in ('maxi-','maximal')}
        self.assertLess(spans['a'][0],text.index('The'))
        self.assertGreater(spans['c'][0],text.index('The'))

    def test_sideways_halves_are_one_word(self):
        # A rotated table cell: lines stacked along x, each read along y.
        text='| reassessment complete | other |'
        runs=[run('a','re-',800,174,807,189),run('b','assessment',819,121,828,189),
              run('c','complete',838,110,848,189),run('d','other',900,150,910,189)]
        self.assertEqual(missing(a.token_ledger(text,runs)),[])

    def test_halves_need_the_joined_word_in_the_copy(self):
        # Copy lost the continuation: the first half stays unverified.
        text='Lamps burned over the netmaker seagrass.'
        runs=[run('a','Lamps burned over the shor-',0,0,300,12),run('b','eline',0,16,40,28),
              run('c','netmaker seagrass.',70,16,300,28)]
        self.assertEqual(missing(a.token_ledger(text,runs)),[('a','shor-'),('b','eline')])


class OwnPosition(unittest.TestCase):
    def test_run_claims_inside_the_unit_that_cites_it(self):
        line='The orchard trial followed every plot through three harvests'
        text='Intro words here.\n\n'+line+' and more.'
        at=text.index(line)
        lost=run('lost',line,0,0,500,12)
        kept=run('kept',line,0,300,500,312,anchors=[[at,len(text)]])
        ledger=a.token_ledger(text,[lost,run('i','Intro words here.',0,280,200,292),kept])
        self.assertEqual({r for r,_ in missing(ledger)},{'lost'})

    def test_page_section_is_preferred_without_anchors(self):
        text='Alpha beta gamma delta.\n\n<!-- end of page 1 -->\n\nAlpha beta gamma delta.\n\n<!-- end of page 2 -->'
        runs=[run('p2','Alpha beta gamma delta.',0,0,200,12,page=2),run('p1','Alpha beta gamma delta.',0,0,200,12,page=1)]
        ledger=a.token_ledger(text,runs)
        self.assertEqual(missing(ledger),[])
        first,second=[t['output'][0] for t in ledger['tokens'] if t['token']==0]
        self.assertGreater(first,text.index('end of page 1'))   # page 2's run claims page 2's text
        self.assertLess(second,text.index('end of page 1'))

    def test_repeated_vocabulary_in_a_box_does_not_take_body_words(self):
        body='harbour weathervane quayside keepers'
        box='Box: harbour weathervane'
        text=body+'\n\n'+box
        runs=[run('box1','Box: harbour',0,200,100,212,anchors=[[len(body)+2,len(text)]]),
              run('box2','weathervane',110,200,200,212,anchors=[[len(body)+2,len(text)]]),
              run('body','harbour weathervane quayside keepers',0,0,300,12,anchors=[[0,len(body)]])]
        ledger=a.token_ledger(text,runs)
        self.assertEqual(missing(ledger),[])
        spans={t['run']:t['output'] for t in ledger['tokens'] if t['text']=='weathervane'}
        self.assertGreater(spans['box2'][0],len(body))


class StepThree(unittest.TestCase):
    def test_a_lost_line_keeps_words_found_only_on_another_page(self):
        # A line the copy reports as not placed may not borrow a spare
        # 'diseases' printed on another page (here the title repeated as a
        # heading); found on its own page it would count.
        text=('Chronic diseases of the gums\n\n# Chronic diseases of the gums\n\n<!-- end of page 1 -->\n\n'
              'The study of teeth.\n\n<!-- end of page 2 -->')
        title=run('t','Chronic diseases of the gums',0,0,300,12,page=1,anchors=[[0,28]])
        body=run('b','The study of teeth.',0,0,200,12,page=2,anchors=[[text.index('The study'),text.index('The study')+19]])
        lost=run('l','inflammatory diseases',0,20,200,32,page=2,unplaced=True)
        self.assertEqual(missing(a.token_ledger(text,[title,body,lost])),[('l','inflammatory'),('l','diseases')])
        lost.pop('unplaced')
        self.assertEqual(missing(a.token_ledger(text,[title,body,lost])),[('l','inflammatory')])

    def test_numbers_of_table_cells_are_counted_in_their_table(self):
        text='| Group | n | Score 1 |\n| --- | --- | --- |\n| A | 1 | 2 |\n| B | 2 | 1 |'
        span=[[0,len(text)]]
        runs=[run('h','Group n Score 1',0,0,300,12,anchors=span),run('a','A',0,20,10,32,anchors=span),
              run('a1','1',100,20,110,32,anchors=span),run('a2','2',200,20,210,32,anchors=span),
              run('b','B',0,40,10,52,anchors=span),run('b2','2',100,40,110,52,anchors=span),run('b1','1',200,40,210,52,anchors=span)]
        self.assertEqual(missing(a.token_ledger(text,runs)),[])

    def test_a_number_is_not_matched_across_a_cell_bar_or_a_space(self):
        # '32.4' must not take '3) | 24'; '24.5' must not take '24 (5'.
        text='| 27 (3) | 24 (5) | 32.4 | 24.5 |'
        span=[[0,len(text)]]
        runs=[run('a','27 (3)',0,0,40,12,anchors=span),run('b','24 (5)',50,0,90,12,anchors=span),
              run('c','32.4',100,0,140,12,anchors=span),run('d','24.5',150,0,190,12,anchors=span)]
        ledger=a.token_ledger(text,runs)
        self.assertEqual(missing(ledger),[])
        self.assertEqual({t['run']:text[t['output'][0]:t['output'][1]] for t in ledger['tokens'] if t['run'] in 'cd'},
                         {'c':'32.4','d':'24.5'})

    def test_both_halves_unclaimed_are_present_in_the_recovered_word(self):
        text='Protocols of Echeverría and García-Gargallo; steps of Martínez.'
        P=[[0,len(text)]]
        runs=[run('a','Protocols of Echeverr a and Garc a-Gargallo;',0,0,300,12,anchors=P),
              run('b','steps of Mart nez.',0,16,200,28,anchors=P)]
        self.assertEqual(missing(a.token_ledger(text,runs)),[])
        # An unrecovered letter (the replacement mark) is no diacritic letter:
        # the halves are only the literal text on either side of the mark, as
        # the ordinary passes already find them (unchanged from BASE).
        bad='Protocols of Echeverr\ufffda and Garc\ufffda-Gargallo; steps of Mart\ufffdnez.'
        runs=[dict(r,anchors=[[0,len(bad)]]) for r in runs]
        ledger=a.token_ledger(bad,runs)
        self.assertEqual({bad[t['output'][0]:t['output'][1]] for t in ledger['tokens'] if t['text'] in ('Echeverr','Mart')},{'Echeverr','Mart'})
        recovered='Protocols of Echeverria and Garcia-Gargallo; steps of Martinez.'
        runs=[dict(r,anchors=[[0,len(recovered)]]) for r in runs]
        self.assertIn(('a','Echeverr'),missing(a.token_ledger(recovered,runs)))   # a plain 'i' is not a recovered diacritic
        # A truly missing half stays listed.
        gone='Protocols of and García-Gargallo; steps of Martínez.'
        runs=[dict(r,anchors=[[0,len(gone)]]) for r in runs]
        self.assertIn(('a','Echeverr'),missing(a.token_ledger(gone,runs)))

    def test_a_mixed_token_is_not_a_number_and_keeps_its_letters(self):
        text='| Panel | Size |\n| --- | --- |\n| Biobank panel | n=1M |\n| Clinic | 1 |\n| Registry | 1M |'
        T=[[0,len(text)]]
        runs=[run('h','Panel Size',0,0,90,12,anchors=T),run('x','Biobank panel n=1M',0,20,90,32,anchors=T),
              run('c','Clinic',0,40,90,52,anchors=T),run('c1','1',200,40,290,52,anchors=T),
              run('r','Registry',0,60,90,72,anchors=T),run('r1','1M',200,60,290,72,anchors=T)]
        self.assertEqual(missing(a.token_ledger(text,runs)),[])
        # The cell truly dropped from the copy stays listed.
        drop=text.replace(' n=1M','')
        runs=[dict(r,anchors=[[0,len(drop)]]) for r in runs]
        self.assertEqual(missing(a.token_ledger(drop,runs)),[('x','n=1M')])

    def test_numbers_in_a_cell_with_a_row_key_and_a_range(self):
        # Stacked cells: '3-4: -0.52 (-0.71–' wraps to '-0.33)'; '5-6:' and '0.71' are runs of their own.
        t='| Outcome | Effect |\n| --- | --- |\n| PD | 3-4: -0.52 (-0.71–-0.33) |\n| CAL | 5-6: 0.71 (0.48–0.94) |'
        T=[[0,len(t)]]
        R=lambda i,x,y:run(i,x,0,y,100,y+12,anchors=T)
        runs=[R('h','Outcome Effect',0),R('a','PD',20),R('b','3-4: -0.52 (-0.71–',20),R('c','-0.33)',34),
              R('d','CAL',50),R('e','5-6:',50),R('f','0.71',50),R('g','(0.48–0.94)',50)]
        self.assertEqual(missing(a.token_ledger(t,runs)),[])

    def test_a_bare_number_does_not_take_digits_of_a_longer_printed_number(self):
        # The bare numbers '12', '38', '13', '43' are cells of a table elsewhere; the copy holds them only inside
        # 'IL-12', '(N=38)', '99:13–19' and '37–43.', so they stay unverified.
        t='| A | B |\n| --- | --- |\n| IL-12 (N=38) | 2004;99:13–19 and 37–43. |'
        T=[[0,len(t)]]
        runs=[run('h','A B',0,0,90,12,anchors=T),run('w','IL-12 (N=38) 2004;99:13–19 and',0,20,300,32,anchors=T),
              run('p','37–43.',300,20,350,32,anchors=T)]+[run('n%d'%k,v,0,40+20*k,20,52+20*k,anchors=T) for k,v in enumerate(['12','38','13','43.'])]
        self.assertEqual(sorted(r for r,_ in missing(a.token_ledger(t,runs))),['n0','n1','n2','n3'])

    def test_a_number_is_printed_mark_for_mark(self):
        # '♂20/♀16' is not '(2016)'; an unread glyph next to a digit belongs to that word ('IL-\ufffd2').
        t='| Study | Sex |\n| --- | --- |\n| Chadwick (2016)[72] | IL-\ufffd2 |'
        T=[[0,len(t)]]
        runs=[run('h','Study Sex',0,0,90,12,anchors=T),run('c','Chadwick',0,20,60,32,anchors=T),run('y','(2016)72',62,20,120,32,anchors=T),
              run('s','\u264220/\u264016',200,20,260,32,anchors=T),run('i','IL-\ufffd2',300,20,340,32,anchors=T),run('n','2',0,60,10,72,anchors=T)]
        miss=missing(a.token_ledger(t,runs))
        self.assertIn(('s','\u264220/\u264016'),miss)
        self.assertIn(('n','2'),miss)

    def test_year_and_raised_citation_numbers_printed_in_brackets(self):
        # Source cell run '(2008)26,45' (raised numbers); the copy prints '(2008)[26,45]'. Plain year and number
        # cells sharing those digits must not take them, and the cell token still verifies.
        t='| Study | Year | n |\n| --- | --- | --- |\n| Smith (2008)[26,45] | 2008 | 26 |\n| Jones (2012)[67,68] | 2012 | 45 |'
        T=[[0,len(t)]]
        runs=[run('h','Study Year n',0,0,90,12,anchors=T),run('s','Smith',0,20,40,32,anchors=T),run('sc','(2008)26,45',42,20,90,32,anchors=T),
              run('y1','2008',100,20,120,32,anchors=T),run('n1','26',150,20,160,32,anchors=T),
              run('j','Jones',0,40,40,52,anchors=T),run('jc','(2012)67,68',42,40,90,52,anchors=T),
              run('y2','2012',100,40,120,52,anchors=T),run('n2','45',150,40,160,52,anchors=T)]
        self.assertEqual(missing(a.token_ledger(t,runs)),[])
        # The raised numbers truly missing from the copy: the cell token is listed.
        gone=t.replace('(2012)[67,68]','(2012)')
        runs=[dict(r,anchors=[[0,len(gone)]]) for r in runs]
        self.assertEqual(missing(a.token_ledger(gone,runs)),[('jc','(2012)67,68')])

    def test_legacy_ledger_is_the_earlier_one(self):
        # The trace is told the earlier ledger's unverified runs; that ledger keeps its earlier allocation (a
        # multi-word run may take letters inside a longer word), which the checker's own ledger no longer does.
        text='Alpha beta gamma deltas. Alpha beta gamma delta.'
        runs=[run('a','Alpha beta gamma delta.',0,40,200,52),run('b1','Alpha beta',0,0,90,12),run('b2','gamma deltas.',100,0,200,12)]
        self.assertEqual(missing(a.legacy_token_ledger(text,runs)),[('b2','deltas.')])
        self.assertEqual(missing(a.token_ledger(text,runs)),[])

    def test_name_split_by_an_unencoded_accent_is_present_when_recovered(self):
        text='Rodriguez and Echeverría reported the case.'
        runs=[run('a','Rodriguez and Echeverr',0,0,200,12),run('b','a',202,0,210,12),run('c','reported the case.',220,0,400,12)]
        self.assertEqual(missing(a.token_ledger(text,runs)),[])
        # Without the recovered letter the split token stays unverified.
        self.assertEqual(missing(a.token_ledger('Rodriguez and Echeverr reported the case.',runs)),[('b','a')])


class BylineJoin(unittest.TestCase):
    TEXT='# Bone and Tissue Healing\n\n**Authors:** Anna Berg 1; Carl Dahl 2; Eva Lund 1\n\nThe teams recorded depth and bleeding.'
    def runs(self, **byline):
        at=self.TEXT.index('**Authors:**');end=self.TEXT.index('\n\nThe');body=self.TEXT.index('The teams')
        return [run('t','Bone and Tissue Healing',0,0,300,14,anchors=[[0,at]]),
                dict(run('b','Anna Berg1, Carl Dahl2 and Eva Lund1',0,20,300,32,anchors=[[at,end]]),**byline),
                run('x','The teams recorded depth and bleeding.',0,60,300,72,anchors=[[body,len(self.TEXT)]])]

    def test_conjunction_between_two_held_names_is_consumed_by_the_join(self):
        ledger=a.token_ledger(self.TEXT,self.runs(byline=True))
        self.assertEqual(missing(ledger),[])
        self.assertEqual([t['status'] for t in ledger['tokens'] if t['run']=='b' and t['text']=='and'],['joined'])
        # Not a byline run (no Authors line cites it): the 'and' stays unverified.
        self.assertEqual(missing(a.token_ledger(self.TEXT,self.runs())),[('b','and')])

    def test_conjunction_before_a_lost_author_stays_listed(self):
        text=self.TEXT.replace('; Eva Lund 1','')
        ledger=a.token_ledger(text,[dict(r,anchors=[[0,len(text)]]) for r in self.runs(byline=True)])
        self.assertIn(('b','and'),missing(ledger))
        self.assertIn(('b','Eva'),missing(ledger))

    def test_title_and_and_unplaced_byline_keep_their_words(self):
        text=self.TEXT.replace('**Authors:** Anna Berg 1; Carl Dahl 2; Eva Lund 1','')
        runs=self.runs(byline=True,unplaced=True);runs[1]['anchors']=[]
        ledger=a.token_ledger(text,runs)
        self.assertEqual(sorted(t for r,t in missing(ledger) if r=='b'),sorted(['Anna','Berg1,','Carl','Dahl2','and','Eva','Lund1']))
        self.assertEqual([t['status'] for t in ledger['tokens'] if t['run']=='t' and t['text']=='and'],['placed'])

    def test_joiners_are_read_from_the_author_parse(self):
        self.assertTrue({'and','AND','&',';'}<=a.name_joiners())


class WordBoundaries(unittest.TestCase):
    def test_multiword_run_does_not_claim_letters_inside_a_longer_word(self):
        text='Alpha beta gamma deltas. Alpha beta gamma delta.'
        runs=[run('a','Alpha beta gamma delta.',0,40,200,52),run('b1','Alpha beta',0,0,90,12),
              run('b2','gamma deltas.',100,0,200,12)]
        self.assertEqual(missing(a.token_ledger(text,runs)),[])

    def test_a_genuinely_missing_word_stays_missing(self):
        text='Alpha beta delta. The harbour keepers.'
        runs=[run('a','Alpha beta gamma delta.',0,0,200,12),run('b','The harbour keepers.',0,16,200,28)]
        self.assertEqual(missing(a.token_ledger(text,runs)),[('a','gamma')])

    def test_audit_rechecks_saved_spans_and_still_finds_edits(self):
        text='Alpha beta gamma delta.\n\nAlpha beta gamma delta.'
        runs=[run('x','Alpha beta gamma delta.',0,0,200,12,anchors=[[25,len(text)]]),
              run('y','Alpha beta gamma delta.',0,40,200,52,anchors=[[0,23]])]
        saved=dict(token_ledger=a.token_ledger(text,runs))
        self.assertEqual(a.audit_run_tokens(text,'',{},{},saved)['missing_tokens'],0)
        self.assertEqual(a.audit_run_tokens(text.replace('gamma','',1),'',{},{},saved)['missing_tokens'],1)


class CompletenessShare(unittest.TestCase):
    def setUp(self):c.trace_reset()

    def traced(self,pieces):
        """pieces: (text, generated reason or None); returns the stripped body with the trace set."""
        out=[]
        for text,generated in pieces:out.append(c.trace_mark(text,'notice' if generated else 'paragraph',generated=generated))
        body,spans=c.trace_strip('\n\n'.join(out))
        c._TRACE.update(body_text=body,body_spans=spans)
        return body

    def test_program_notices_are_not_copied_words(self):
        body=self.traced([('[table structure not recovered: 3 printed lines follow as printed]','program table fallback explanation'),
                          ('Oak trees grow slowly here','')])
        self.assertEqual(c.copied_word_count(body),5)

    def test_grid_and_printed_lines_count_the_same(self):
        lines=self.traced([('[table structure not recovered: 3 printed lines follow as printed]','program table fallback explanation'),
                           ('- Wood Tensile Stress (MPa) Elastic Modulus (GPa)\n- Mean (SD) Mean (SD)\n- Oak strong wood','')])
        lines_count=c.copied_word_count(lines)
        grid=self.traced([('| Wood | Tensile Stress (MPa) | Tensile Stress (MPa) | Elastic Modulus (GPa) | Elastic Modulus (GPa) |\n'
                           '| --- | --- | --- | --- | --- |\n|  | Mean | (SD) | Mean | (SD) |\n| Oak strong wood | 1 | 2 | 3 | 4 |','')])
        self.assertEqual(c.copied_word_count(grid),lines_count)

    def test_cell_repeating_the_cell_above_counts_once(self):
        grid=self.traced([('| Group | Item |\n| --- | --- |\n| Shared category label | first |\n| Shared category label | second |','')])
        self.assertEqual(c.copied_word_count(grid),7)

    def test_prepended_banner_text_is_counted_as_before(self):
        body=self.traced([('Copied words only','')])
        self.assertEqual(c.copied_word_count('Document kind: x\n\n'+body),2+3)


class Anchors(unittest.TestCase):
    def test_units_citing_a_run_give_its_spans(self):
        c.trace_reset()
        page=dict(page=2,elements=[dict(id='run:5',kind='text',text='Alpha beta')])
        src=c.trace_runs_text(page,['run:5'],'Alpha beta')
        marked=c.trace_mark(src,'paragraph',[src])
        body,spans=c.trace_strip('Lead\n\n'+marked)
        c._TRACE.update(body_text=body,body_spans=spans)
        self.assertEqual(c.trace_run_anchors('> notice\n\n'+body),{(2,'run:5'):[[16,26]]})
        self.assertEqual(c.trace_run_anchors('different text'),{})

    def test_cells_of_one_table_share_the_table_span(self):
        c.trace_reset()
        group=c.trace_group()
        first=c.trace_mark('Oak','table_cell',group=group,runs=[(1,'run:7',False),(1,'run:8',False)])
        second=c.trace_mark('61.2','table_cell',group=group)
        body,spans=c.trace_strip('| '+first+' | '+second+' |')
        c._TRACE.update(body_text=body,body_spans=spans)
        anchors=c.trace_run_anchors(body)
        self.assertEqual(anchors[(1,'run:8')],[[2,body.index('61.2')+4]])


if __name__=='__main__':
    unittest.main()
