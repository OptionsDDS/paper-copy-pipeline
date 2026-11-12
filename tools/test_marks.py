"""Raised marks must not become values, units must not become citations."""
import importlib.util
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('copy_marks',Path(__file__).resolve().parents[1]/'copy_paper.py')
copy=importlib.util.module_from_spec(spec);spec.loader.exec_module(copy)


def glyphs(text, raised):
    return [dict(text=ch,size=7 if i in raised else 10,
                 origin=(i*5,96 if i in raised else 100),x0=i*5,x1=i*5+5,adv_x1=i*5+5)
            for i,ch in enumerate(text)]


class Marks(unittest.TestCase):
    def render(self, text, start, end, numbers=range(1,101)):
        return copy.raised_mark_text(text,glyphs(text,range(start,end)),set(numbers))

    def test_citations_after_values_and_words(self):
        for text,start,end,want in [('0.3611',4,6,'0.36[11]'),
                ('factor 212,26',8,13,'factor 2[12,26]'),
                ('periodontitis12',13,15,'periodontitis[12]'),
                ('et al32',5,7,'et al[32]'),('word21–25',4,9,'word[21–25]'),
                ('(40%)47',5,7,'(40%)[47]'),('rhPDGF-BB17',9,11,'rhPDGF-BB[17]')]:
            self.assertEqual(self.render(text,start,end),want)

    def test_baseline_number_after_citation_is_separate(self):
        self.assertEqual(self.render('months,203 months',7,9),'months,[20] 3 months')

    def test_scientific_and_ordinal_marks(self):
        self.assertEqual(self.render('109 cells',2,3),'10^9 cells')
        self.assertEqual(self.render('2.3X103 cells',6,7),'2.3X10^3 cells')
        self.assertEqual(self.render('2.3x103 cells',6,7),'2.3x10^3 cells')
        self.assertEqual(self.render('1024',2,4),'10^24')
        self.assertEqual(self.render('m2',1,2),'m2')
        self.assertEqual(self.render('mm2',2,3),'mm2')
        self.assertEqual(self.render('Km2',2,3),'Km2')
        self.assertEqual(self.render('R2 = 0.98',1,2),'R2 = 0.98')
        self.assertEqual(self.render('allele sw1 (short wing)',9,10),'allele sw1 (short wing)')
        self.assertEqual(self.render('2 2 ln )2',8,9),'2 2 ln )2')
        self.assertEqual(self.render('� ( ^ )2 �',7,8),'� ( ^ )2 �')
        self.assertEqual(self.render('p ~ (si� sj )2',13,14),'p ~ (si� sj )2')
        self.assertEqual(self.render('per (kbp)2',9,10),'per (kbp)2')
        self.assertEqual(self.render('given by zy2(t)',11,12),'given by zy2(t)')
        self.assertEqual(self.render('states, 13P-NMR',8,10),'states, 13P-NMR')
        self.assertEqual(self.render('by 31P-',3,5),'by 31P-')
        self.assertEqual(self.render('�2u',1,2),'�2u')
        self.assertEqual(self.render('5�UTR',1,2),'5�UTR')
        self.assertEqual(self.render('OH•18',2,5),'OH•[18]')
        self.assertEqual(self.render('Ca2+',2,4),'Ca2+')
        self.assertEqual(self.render('21st',2,4),'21^st')
        self.assertEqual(self.render('299',1,3,numbers=[]),'2^99')

    def test_unwitnessed_citation_and_baseline_numbers(self):
        self.assertEqual(self.render('word99',4,6,numbers=[1,2]),'word99')
        self.assertEqual(copy.raised_mark_text('0.3611',glyphs('0.3611',[]),{11}),'0.3611')
        self.assertEqual(copy.raised_mark_text('word12',glyphs('word13',[4,5]),{12}),'word12')
        # An omitted minus occupies a visible glyph-width gap. Do not turn
        # the remaining exponent digit into a citation or a positive power.
        cs=glyphs('104',[2]);cs[2]['origin']=(16,96)
        self.assertEqual(copy.raised_mark_text('10 4',cs,{4}),'10 4')
        cs=glyphs('4.42n',[4]);cs[4]['_mark_unverified']=True
        self.assertEqual(copy.raised_mark_text('4.42n',cs,{1,2}),'4.42n')
        cs=glyphs('CT12',range(2,4))
        for c in cs:c['_body_font']=True
        self.assertEqual(copy.raised_mark_text('CT12',cs,{12}),'CT[12]')

    def test_existing_front_ownership_preserves_affiliation_markers(self):
        text='USA; 2College';cs=glyphs(text,[5])
        run=dict(id='address',kind='text',text=text,box_px=[0,90,65,100],_chars=cs)
        pages=[dict(page=1,elements=[run])]
        copy.prepare_front_mark_labels(pages,dict(affiliation_box_px=[0,90,65,100]))
        self.assertEqual(copy.raised_mark_text(text,cs,{1,2,3}),text)

    def test_rendered_numeric_token_is_not_reported_missing(self):
        import conserve
        run=dict(id='year',text='200158')
        page=dict(_raised_marks=[dict(runs=['year'],before='200158',after='2001[58]')])
        placed=conserve.CopyIndex('| Smith 2001[58] |')
        self.assertTrue(copy.raised_mark_placed(run,page,placed,conserve.CopyIndex))
        self.assertFalse(copy.raised_mark_placed(run,page,conserve.CopyIndex('2001'),conserve.CopyIndex))
        self.assertFalse(copy.raised_mark_placed(dict(id='elsewhere',text='200158'),page,placed,conserve.CopyIndex))

    def test_unresolved_glyph_veto_survives_font_view_rebuild(self):
        cs=glyphs('4.42n',[4])
        for c in cs:c['font']='Body'
        run=dict(id='value',kind='text',angle=0,text='4.42n',char_ids=list(range(5)),
                 font_subs=[dict(char_id=4,status='layout-protected')])
        page=dict(_table_chars=cs,elements=[run])
        copy.source_typography([page])
        # The font hook reconstructs the native array even for a retained glyph.
        page['_table_chars']=[dict(c,text=c['text']) for c in page['_table_chars']]
        run['_chars']=[page['_table_chars'][i] for i in run['char_ids']]
        self.assertEqual(copy.raised_mark_text(run['text'],run['_chars'],{1,2}),run['text'])

    def test_detached_mark_and_sentence_boundary(self):
        cs=glyphs('factor 212,26',range(8,13))
        row=[dict(text='factor 2',angle=0,box_px=[0,90,40,100],_chars=cs[:8]),
             dict(text='12,26',angle=0,box_px=[40,89,65,96],_chars=cs[8:],_superscript=True)]
        self.assertEqual(copy.prose_row(row,{'_citation_numbers':{12,26}})[0],'factor 2[12,26]')
        self.assertFalse(copy.sentence_end('An existing sentence.[12,26]'))
        text='A sentence.12,26'
        row=[dict(text=text,angle=0,box_px=[0,90,80,100],_chars=glyphs(text,range(11,16)))]
        rendered=copy.prose_row(row,{'_citation_numbers':{12,26}})[0]
        self.assertTrue(copy.sentence_end(rendered))
        self.assertFalse(copy.sentence_end('An existing sentence.[12,26]'))
        self.assertFalse(copy.sentence_end('A phrase[12,26]'))

    def test_reference_numbering_keeps_both_columns(self):
        runs=[dict(id=str(i),kind='text',angle=0,text=f'{i}. Author AB. Title.',
                   box_px=[x,y,x+100,y+10],run_size_px=10)
              for i,x,y in [(1,0,0),(2,0,20),(3,200,0),(4,200,20)]]
        page=dict(elements=runs,blocks=[dict(id='refs',members=[r['id'] for r in runs])],
                  main_text=dict(blocks=[dict(id='refs',in_refs=True)]))
        self.assertEqual(copy.citation_numbers([page]),{1,2,3,4})
        labels=[]
        for r in runs:
            label=dict(r,id='label'+r['id'],text=r['id']+'.',box_px=[r['box_px'][0]-20,r['box_px'][1],r['box_px'][0]-5,r['box_px'][3]])
            labels.append(label);r['text']='Author AB. Title.'
        page['elements']=runs+labels
        self.assertEqual(copy.citation_numbers([page]),{1,2,3,4})

    def test_wrapped_citation_is_one_mark(self):
        left='word17,1';right='8 month'
        a=glyphs(left,range(4,8));b=glyphs(right,[0])
        for c in b:c['origin']=(c['origin'][0]-20,c['origin'][1]+16);c['x0']-=20;c['x1']-=20;c['adv_x1']-=20
        runs=[dict(id='a',kind='text',angle=0,_chars=a,char_ids=list(range(len(a)))),
              dict(id='b',kind='text',angle=0,_chars=b,char_ids=list(range(len(a),len(a)+len(b))))]
        page=dict(elements=runs,blocks=[dict(id='body',members=['a','b'])])
        copy.prepare_wrapped_citations([page],{17,18})
        first=copy.raised_mark_text(left,a,{17,18});second=copy.raised_mark_text(right,b,{17,18})
        self.assertEqual(copy.Joiner([]).join(first,second),'word[17,18] month')

    def test_wrapped_commas_ranges_and_entire_small_rows(self):
        for texts,want in [(['word17,','18 next'],'word[17,18] next'),
                           (['word17-','18 next'],'word[17-18] next'),
                           (['word17,','18,19,','20 next'],'word[17,18,19,20] next'),
                           (['m17,','18 next'],'m17, 18 next')]:
            runs=[];offset=0
            for i,text in enumerate(texts):
                start=len(text.rstrip('0123456789,-')) if not i else 0
                end=text.index(' ') if ' ' in text else len(text)
                cs=glyphs(text,range(start,end))
                for c in cs:
                    c['origin']=(c['origin'][0]-20*i,c['origin'][1]+16*i)
                    c['x0']-=20*i;c['x1']-=20*i;c['adv_x1']-=20*i
                runs.append(dict(id=str(i),kind='text',text=text,angle=0,_chars=cs,
                                 char_ids=list(range(offset,offset+len(cs)))))
                offset+=len(cs)
            page=dict(elements=runs,blocks=[dict(id='body',members=[r['id'] for r in runs])])
            copy.prepare_wrapped_citations([page],set(range(1,30)))
            result=''
            for r in runs:result=copy.Joiner([]).join(result,copy.raised_mark_text(r['text'],r['_chars'],set(range(1,30))))
            self.assertEqual(result,want)

    def test_table_marks_do_not_change_values_or_ambiguous_words(self):
        def run(id,text,raised):
            return dict(id=id,kind='text',text=text,angle=0,box_px=[0,0,100,10],_chars=glyphs(text,raised))
        page=dict(elements=[run('a','Smith12',range(5,7)),run('b','0.36',[]),
                            run('c','code12',range(4,6)),run('d','code12',[])],
                  _citation_numbers={12},_raised_marks=[])
        item=dict(table_source=dict(lines=[dict(items=[dict(id=r['id']) for r in page['elements']])]))
        lines=['| Smith12 | 0.36 | code12 |']
        self.assertEqual(copy.table_raised_marks(lines,item,page),['| Smith[12] | 0.36 | code12 |'])

    def test_table_note_stays_identical_to_source_until_gate(self):
        text='Adapted from Smith12'
        run=dict(id='note',kind='text',text=text,angle=0,box_px=[0,0,100,10],
                 _chars=glyphs(text,range(18,20)))
        page=dict(elements=[run],_citation_numbers={12},_raised_marks=[])
        note=copy.prose_row([run],page,render_marks=False)[0]
        source=dict(lines=[dict(text=text,items=[dict(id='note')])],caption_ids=[])
        self.assertEqual(copy.table_printed_lines(source,[note]),[])
        self.assertEqual(copy.table_raised_marks([note],dict(table_source=source),page),['Adapted from Smith[12]'])

    def test_numbered_table_notes_are_not_bibliography_citations(self):
        header=dict(id='h',kind='text',text='systems1',angle=0,box_px=[0,0,100,10],
                    _chars=glyphs('systems1',[7]))
        note=dict(id='n',kind='text',text='1 A definition of the table heading.',band='body',
                  _chars=glyphs('1 A definition of the table heading.',[0]))
        pages=[dict(page=1,elements=[header],_citation_numbers={1,2},_raised_marks=[]),
               dict(page=2,elements=[note])]
        items=[dict(kind='table',page=1,caption='Table 3. Measurements.',table_source=dict(lines=[dict(items=[dict(id='h')])])),
               dict(kind='table',page=2,caption='Table 3. Continued.',table_source=dict(lines=[dict(items=[dict(id='n')])]))]
        copy.prepare_table_mark_notes(items,pages)
        self.assertEqual(copy.table_raised_marks(['systems1'],items[0],pages[0]),['systems1'])


if __name__=='__main__':unittest.main()
