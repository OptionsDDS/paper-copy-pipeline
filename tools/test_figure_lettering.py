"""Figure ownership and caption gutters, using synthetic printed geometry.

Run with /usr/bin/python3 -I tools/test_figure_lettering.py.
"""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


boxer = module('boxer', ROOT/'standalone/element_boxer_sc.py')
copy = module('copy_paper', ROOT/'copy_paper.py')


def text(name, value, box, line, size=10):
    return dict(id=name, kind='text', text=value, box_px=box, line=line,
                angle=0, size_px=size, run_size_px=size, font='Regular')


def block(name, elements):
    return dict(id=name, members=[e['id'] for e in elements],
                box_px=copy.hull(e['box_px'] for e in elements),
                text_lines=len({e['line'] for e in elements if e['kind']=='text'}),
                kinds=sorted({e['kind'] for e in elements}),
                text=' '.join(e['text'] for e in elements if e['kind']=='text'))


class FigureOwnership(unittest.TestCase):
    def test_display_title_above_image_extends_frame_by_two_line_heights(self):
        title=text('title','Cell recruitment',[20,10,150,24],1,14)
        cap=text('cap','FIGURE 9. A caption.',[0,150,200,160],2)
        body=text('body','This ordinary body line establishes the smaller prose size.',[0,200,230,210],3)
        img=dict(id='image',kind='image',box_px=[0,50,200,140])
        es=[title,cap,body,img]
        bs=[block('title',[title]),block('caption',[cap]),block('body',[body]),block('image',[img])]
        fs=[dict(caption=cap['text'],blocks=['caption','image'],box_px=[0,50,200,160])]
        boxer.join_figure_lettering(es,bs,[],fs,[])
        self.assertEqual(fs[0]['lettering'],['title'])
        self.assertEqual(fs[0]['box_px'],[0,10,200,160])
        self.assertEqual(bs[0]['members'],[])

    def test_title_join_preserves_numbered_headings_sentences_and_body_barriers(self):
        for value,extra in [
            ('2 Results',[]),
            ('A sentence ends.',[]),
            ('This heading has more than four words',[]),
            ('Results',[text('number','2',[0,10,8,24],1,14)]),
            ('Cell recruitment',[text('prose','A body sentence intervenes between this title and its picture.',[0,28,200,38],2)]),
        ]:
            with self.subTest(value=value,extra=bool(extra)):
                title=text('title',value,[20,10,150,24],1,14)
                cap=text('cap','FIGURE 9. A caption.',[0,150,200,160],3)
                body=text('body','This ordinary body line establishes the smaller prose size.',[0,200,230,210],4)
                img=dict(id='image',kind='image',box_px=[0,50,200,140])
                es=[title,cap,body,img]+extra
                bs=[block(e['id'],[e]) for e in es]
                fs=[dict(caption=cap['text'],blocks=['cap','image'],box_px=[0,50,200,160])]
                boxer.join_figure_lettering(es,bs,[],fs,[])
                self.assertNotIn('title',fs[0].get('lettering',[]))

    def test_single_panel_letter_uses_two_line_heights_at_body_size(self):
        panel=text('panel','A',[20,10,28,20],1)
        cap=text('cap','FIGURE 9. A caption.',[0,150,200,160],2)
        img=dict(id='image',kind='image',box_px=[0,36,200,140])
        es=[panel,cap,img];bs=[block(e['id'],[e]) for e in es]
        fs=[dict(caption=cap['text'],blocks=['cap','image'],box_px=[0,36,200,160])]
        boxer.join_figure_lettering(es,bs,[],fs,[])
        self.assertEqual(fs[0]['lettering'],['panel'])
        self.assertEqual(fs[0]['box_px'],[0,10,200,160])

    def test_title_barrier_cannot_strand_upper_panel(self):
        title=text('title','Cell recruitment',[40,60,150,74],2,14)
        panel=text('panel','A',[50,0,58,10],1)
        cap=text('cap','FIGURE 9. A caption.',[0,200,200,210],3)
        body=text('body','This ordinary body line establishes the smaller prose size.',[0,240,230,250],4)
        upper=dict(id='upper',kind='image',box_px=[70,0,150,40])
        lower=dict(id='lower',kind='image',box_px=[0,90,200,190])
        es=[title,panel,cap,body,upper,lower]
        bs=[block(e['id'],[e]) for e in es]
        fs=[dict(caption=cap['text'],blocks=['cap','lower'],box_px=[0,90,200,210])]
        boxer.join_figure_lettering(es,bs,[],fs,[])
        self.assertEqual(set(fs[0]['lettering']),{'title','panel'})
        self.assertIn('upper',fs[0]['members'])
        self.assertEqual(fs[0]['box_px'],[0,0,200,210])

    def test_page_end_sentence_continues_before_figure(self):
        items=[dict(kind='para',text='Expression was dependent',page=1),
               dict(kind='page',page=1),dict(kind='figure',page=2),
               dict(kind='para',text='on the same pathway.',page=2)]
        class Joiner:
            def join(self,a,b): return a+' '+b
        result=copy.rejoin_paragraphs(items,Joiner())
        self.assertEqual(result[0]['text'],'Expression was dependent on the same pathway.')
        self.assertEqual([x['kind'] for x in result],['para','page','figure'])

    def test_display_title_inside_paired_frame_is_lettering(self):
        title=text('title','A chart title',[80,20,180,34],1,14)
        tick=text('tick','10',[180,100,190,110],2)
        cap=text('cap','FIGURE 9. A caption.',[0,150,100,160],3)
        body=text('body','This is the ordinary body line used to measure the text size.',[0,200,230,210],4)
        drawing=dict(id='frame',kind='fill',box_px=[70,18,200,140])
        es=[title,tick,cap,body,drawing]
        bs=[block('caption',[cap]),block('graphic',[drawing,title,tick]),block('body',[body])]
        fs=[dict(caption=cap['text'],blocks=['caption','graphic'],box_px=[0,18,200,160])]
        boxer.join_figure_lettering(es,bs,[],fs,[])
        self.assertEqual(set(fs[0]['lettering']),{'title','tick'})
        self.assertEqual(bs[2]['members'],['body'])

    def test_side_caption_preserves_lower_panels_beside_prose(self):
        cap=text('cap','FIGURE 9. A caption.',[130,20,240,30],1)
        panel=text('panel','(B)',[10,85,20,95],2)
        scale=text('scale','25 µm',[20,180,50,190],4)
        body=text('body','The body continues in the column beside the lower panel.',[130,100,300,110],3)
        imgs=[dict(id='image:1',kind='image',box_px=[10,20,100,80]),
              dict(id='image:2',kind='image',box_px=[10,100,100,200])]
        drawing=dict(id='frame',kind='fill',box_px=[8,18,102,202])
        es=[cap,panel,scale,body,drawing]+imgs
        bs=[block('caption',[cap]),block('graphic',[drawing,panel,scale]+imgs),block('body',[body])]
        fs=[dict(caption=cap['text'],blocks=['caption','graphic'],box_px=[8,18,240,202])]
        unpaired=[]
        boxer.join_figure_lettering(es,bs,[],fs,unpaired)
        self.assertEqual(set(fs[0]['lettering']),{'panel','scale'})
        self.assertEqual(fs[0]['box_px'],drawing['box_px'])
        self.assertEqual(unpaired[0]['kind'],'caption outside graphic rectangle')
        self.assertEqual(bs[2]['members'],['body'])

    def test_mixed_case_caption_below_axes_needs_a_drawing(self):
        axis=text('axis','0.5',[10,20,30,30],1)
        cap=text('cap','Fig. 9. The plotted result.',[0,80,150,90],2)
        cont=text('cont','The caption continues.',[0,92,150,102],3)
        drawing=dict(id='frame',kind='fill',box_px=[0,0,160,105])
        es=[axis,cap,cont,drawing];bs=[block('mixed',es)]
        boxer.split_figure_caption_blocks(es,bs)
        self.assertEqual(bs[1]['members'],['cap','cont'])
        bs=[block('mixed',[axis,cap,cont])]
        boxer.split_figure_caption_blocks(es,bs)
        self.assertEqual(len(bs),1)
        cap['text']='Figure 9 describes the result.'
        bs=[block('mixed',es)]
        boxer.split_figure_caption_blocks(es,bs)
        self.assertEqual(len(bs),1)

    def test_float_frame_vetoes_all_heading_style(self):
        meta=dict(size_px=18,font_heading=True,why='heading before main text in its column',
                  box_px=[20,20,90,40],float_frames=[[0,0,100,100]])
        self.assertFalse(copy.is_heading('A chart title',meta,10,1))
        self.assertTrue(copy.is_heading('A real heading',dict(meta,box_px=[20,120,90,140]),10,1))

    def test_caption_face_separates_side_labels_on_the_same_baseline(self):
        cap=text('cap','Fig. 4. Measured outcomes',[160,80,300,90],3)
        cap['font_spans']=[dict(font='Label',start=0,end=7),dict(font='Caption',start=8,end=26)]
        tail=text('tail','in the study population.',[160,94,300,104],5)
        tail['font']='Caption'
        labels=[text('above','A long chart label with several words identifying a plotted series',
                     [10,20,130,28],1,8),
                text('beside','Axis label',[10,80,90,88],3,8),
                text('below','Legend',[10,94,90,102],5,8)]
        drawing=dict(id='drawing',kind='fill',box_px=[0,0,310,110])
        es=labels+[cap,tail,drawing];bs=[block('mixed',es)]
        body=text('body','The ordinary body paragraph remains below the plotted results.',[0,150,300,162],6,12)
        es.append(body);bs.append(block('body',[body]))
        fs=boxer.floats_with_captions(es,bs,[])
        self.assertEqual(len(fs),1)
        self.assertEqual(fs[0]['caption_members'],['cap','tail'])
        self.assertEqual(set(fs[0]['lettering']),{e['id'] for e in labels})
        p=dict(page=1,elements=es,blocks=bs,tables=[],floats=fs,
               region_box_px=[0,0,310,200],main_text=dict(blocks=[
                   dict(id='body',cls='main',order=1,lines=1,size_px=12,box_px=body['box_px'])],columns=[]))
        _,figures,side=copy.read_page(p,10,[])
        self.assertEqual(figures[0][2],'Fig. 4. Measured outcomes\nin the study population.')
        self.assertFalse(side)

    def test_bold_title_can_introduce_a_regular_caption_continuation(self):
        axis=text('axis','Chart legend',[0,10,90,20],1,8)
        cap=text('cap','Fig. 4. Results in broth',[160,80,310,90],2)
        cap['font']='Bold'
        mixed=text('mixed','under both conditions. Cultures were',[160,94,310,104],3)
        mixed['font_spans']=[dict(font='Bold',start=0,end=22),dict(font='Regular',start=23,end=36)]
        tail=text('tail','grown for the indicated times.',[160,108,310,118],4)
        tail['font']='Regular'
        legend=text('legend','Different drawing face',[0,108,145,118],4)
        drawing=dict(id='drawing',kind='fill',box_px=[0,0,320,120])
        es=[axis,cap,mixed,tail,legend,drawing];bs=[block('mixed',es)]
        boxer.split_figure_caption_blocks(es,bs)
        self.assertEqual(bs[1]['members'],['cap','mixed','tail'])

    def test_centered_caption_can_continue_left_of_its_first_line(self):
        axis=text('axis','Panel A',[0,10,40,20],1,8)
        cap=text('cap','Fig. 4. Results',[60,40,160,50],2)
        wide=text('wide','A longer centered caption line.',[0,54,220,64],3)
        tail=text('tail','A short last line.',[70,68,150,78],4)
        label=text('label','Legend',[0,68,30,78],4)
        drawing=dict(id='drawing',kind='fill',box_px=[0,0,230,80])
        es=[axis,cap,wide,tail,label,drawing];bs=[block('mixed',es)]
        boxer.split_figure_caption_blocks(es,bs)
        self.assertEqual(bs[1]['members'],['cap','wide','tail'])

    def test_a_demoted_figure_grid_does_not_hide_its_caption(self):
        axis=text('axis','Axis',[10,10,40,20],1,8)
        cap=text('cap','Fig. 4. Results.',[160,80,290,90],2)
        drawing=dict(id='drawing',kind='fill',box_px=[0,0,310,100])
        es=[axis,cap,drawing];bs=[block('mixed',es)]
        grid=dict(id='table:1',box_px=[0,0,310,100],members=['axis','cap'])
        fs=boxer.floats_with_captions(es,bs,[grid])
        self.assertEqual(len(fs),1)
        self.assertEqual(fs[0]['caption_members'],['cap'])
        self.assertIn('demoted',grid)

    def test_rule_four_reads_native_faces_before_export(self):
        label=text('axis','A long series name with several words inside the drawing',
                   [0,10,140,18],1,8)
        cap=text('cap','Fig. 4. Caption',[160,80,300,90],2)
        tail=text('tail','continued.',[160,94,240,104],3)
        body=text('body','A normal body sentence supplies the page text size here.',[0,160,300,172],4,12)
        drawing=dict(id='drawing',kind='fill',box_px=[0,0,310,110])
        chars=[]
        for e,face in ((label,'Chart'),(cap,'Caption'),(tail,'Caption'),(body,'Body')):
            e.pop('font');e['char_ids']=[]
            for ch in e['text']:
                if ch.isspace():continue
                e['char_ids'].append(len(chars));chars.append(dict(text=ch,font=face))
        es=[label,cap,tail,body,drawing]
        bs=[block('mixed',[label,cap,tail,drawing]),block('body',[body])]
        fs=boxer.floats_with_captions(es,bs,[],chars)
        self.assertEqual(fs[0]['caption_members'],['cap','tail'])
        self.assertEqual(cap['font'],'Caption')

    def test_page_backing_cannot_turn_a_larger_body_column_into_drawing_labels(self):
        prose=text('prose','This long body sentence is above the caption in the other column.',
                   [180,20,350,32],1,12)
        cap=text('cap','Fig. 4. A caption.',[0,80,150,90],2)
        cap['font']='Caption'
        tail=text('tail','The caption continues.',[0,94,150,104],3)
        tail['font']='Caption'
        backing=dict(id='backing',kind='fill',box_px=[0,0,400,500])
        es=[prose,cap,tail,backing];bs=[block('mixed',es)]
        boxer.split_figure_caption_blocks(es,bs)
        self.assertEqual(len(bs),1)
        self.assertEqual(bs[0]['members'],[e['id'] for e in es])

    def test_long_picture_text_larger_than_the_caption_is_lettering_when_its_picture_ends_above(self):
        # Sentence-length text written inside a picture, in the picture's own face and larger
        # than the caption, above a two-column caption: the caption is split off whole.
        note=text('note','Activation and deposition of the protein on the bacterial surfaces',
                  [60,20,300,30],1,11)
        note['font']='Picture'
        tag=text('tag','Panel',[10,20,40,30],1,11)
        tag['font']='Picture'
        cap=text('cap','Fig. 5. Effects of the proteases on the',[0,80,150,90],2)
        cap['font']='Caption'
        right=text('right','complement cascade, released early in',[170,80,320,90],2)
        right['font']='Caption'
        tail=text('tail','the colonization process.',[0,94,150,104],3)
        tail['font']='Caption'
        picture=dict(id='picture',kind='image',box_px=[50,10,320,60])
        backing=dict(id='backing',kind='fill',box_px=[0,0,330,106])
        es=[tag,note,cap,right,tail,picture,backing];bs=[block('mixed',es)]
        boxer.split_figure_caption_blocks(es,bs)
        self.assertEqual(len(bs),2)
        self.assertEqual(bs[1]['members'],['cap','right','tail'])
        self.assertEqual(set(bs[0]['members']),{'tag','note','picture','backing'})
        # On this page the note is the only long run, so its face is the body face: the same
        # text over a backing that also covers the caption witnesses nothing.
        es=[tag,note,cap,right,tail,backing];bs=[block('mixed',es)]
        boxer.split_figure_caption_blocks(es,bs)
        self.assertEqual(len(bs),1)
        # A picture reaching down over the caption label witnesses nothing either (body face).
        low=dict(picture,box_px=[50,10,320,85])
        es=[tag,note,cap,right,tail,low,backing];bs=[block('mixed',es)]
        boxer.split_figure_caption_blocks(es,bs)
        self.assertEqual(len(bs),1)
        # Text running outside its picture is not inside it (and is in the body face here).
        out=dict(note,box_px=[60,20,340,30])
        es=[tag,out,cap,right,tail,picture,backing];bs=[block('mixed',es)]
        boxer.split_figure_caption_blocks(es,bs)
        self.assertEqual(len(bs),1)
        # Text in the caption's own face stays protected even inside its picture.
        same=dict(note,font='Caption')
        es=[tag,same,cap,right,tail,picture,backing];bs=[block('mixed',es)]
        boxer.split_figure_caption_blocks(es,bs)
        self.assertEqual(len(bs),1)

    def test_lettering_on_a_backing_or_past_a_picture_edge_is_lettering_outside_the_body_face(self):
        # Body columns of the page, in their own blocks below the figure.
        body=[text('body%d'%i,'Body column text of the page set in its own regular face %d'%i,
                   [0,130+14*i,150,140+14*i],10+i) for i in range(4)]
        for e in body: e['font']='Body'
        note=text('note','Lettering written large across the drawing of the figure',[60,20,300,30],1,11)
        note['font']='Picture'
        cap=text('cap','Fig. 2. A caption set in two columns',[0,80,150,90],2)
        cap['font']='Caption'
        right=text('right','under the drawing and its backing',[170,80,320,90],2)
        right['font']='Caption'
        backing=dict(id='backing',kind='fill',box_px=[0,0,330,106])
        def split(es,members):
            bs=[block('mixed',[e for e in es if e['id'] in members])]
            boxer.split_figure_caption_blocks(es,bs)
            return [sorted(b['members']) for b in bs]
        # Lettering on a backing with no picture: the backing begins above the label.
        es=[note,cap,right,backing]+body
        self.assertEqual(split(es,{'note','cap','right','backing'}),[['backing','note'],['cap','right']])
        # Lettering running past a narrow picture's edge, with no backing.
        narrow=dict(id='narrow',kind='image',box_px=[50,10,200,60])
        es=[note,cap,right,narrow]+body
        self.assertEqual(split(es,{'note','cap','right','narrow'}),[['narrow','note'],['cap','right']])
        # The same text in the page's body face is never lettering.
        plain=dict(note,font='Body')
        es=[plain,cap,right,backing]+body
        self.assertEqual(len(split(es,{'note','cap','right','backing'})),1)
        es=[plain,cap,right,narrow]+body
        self.assertEqual(len(split(es,{'note','cap','right','narrow'})),1)
        # A backing behind body columns above the caption (page-sized, also covering
        # the caption) witnesses nothing, even with the columns in their own blocks.
        page=dict(id='page',kind='fill',box_px=[0,0,330,200])
        cols=[dict(e,id='col%d'%i,box_px=[e['box_px'][0],e['box_px'][1]-125,e['box_px'][2],e['box_px'][3]-125],
                   line=0) for i,e in enumerate(body[:3])]
        low=dict(note,box_px=[60,56,300,66],line=1)
        es=[low,cap,right,page]+cols+body
        self.assertEqual(len(split(es,{'note','cap','right','page'})),1)
        # A shape that begins at or below the caption label witnesses nothing.
        under=dict(id='under',kind='fill',box_px=[0,80,330,106])
        es=[note,cap,right,under]+body
        self.assertEqual(len(split(es,{'note','cap','right','under'})),1)

    def test_justified_caption_chain_keeps_final_word_but_stops_at_body_face(self):
        cap=text('cap','FIGURE 4. A caption',[0,80,80,90],2)
        mid=text('middle','with a separated',[98,80,170,90],2)
        end=text('end','word.',[188,80,220,90],2)
        prose=text('body','The other column continues.',[240,80,390,90],2)
        prose['font']='Body'
        tick=text('tick','0',[10,20,18,30],1,8)
        img=dict(id='img',kind='image',box_px=[0,0,220,70])
        es=[cap,mid,end,prose,tick,img];bs=[block(e['id'],[e]) for e in es]
        fs=[dict(caption=cap['text'],blocks=['cap','img'],box_px=[0,0,220,90])]
        boxer.join_figure_lettering(es,bs,[],fs,[])
        self.assertEqual(fs[0]['caption_members'],['cap','middle','end'])
        self.assertNotIn('end',fs[0]['lettering'])
        self.assertNotIn('body',fs[0]['members'])

    def test_caption_split_stops_at_a_gap_and_preserves_real_tables(self):
        axis=text('axis','Axis',[0,0,30,10],1,8)
        cap=text('cap','Fig. 4. Results.',[0,40,100,50],2)
        distant=text('distant','A separate paragraph.',[0,100,150,110],3)
        drawing=dict(id='drawing',kind='fill',box_px=[0,0,160,120])
        es=[axis,cap,distant,drawing];bs=[block('mixed',es)]
        boxer.split_figure_caption_blocks(es,bs)
        self.assertEqual(bs[1]['members'],['cap'])
        bs=[block('mixed',es)]
        boxer.split_figure_caption_blocks(es,bs,[dict(members=['axis'])])
        self.assertEqual(len(bs),1)

    def test_copy_recovers_framed_title_from_stale_body_class(self):
        title=text('title','A chart title',[20,20,150,34],1,14)
        cap=text('cap','FIGURE 9. A caption.',[0,110,200,120],2)
        body=text('body','The body remains outside the figure.',[0,150,200,160],3)
        drawing=dict(id='frame',kind='fill',box_px=[0,10,200,100])
        es=[title,cap,body,drawing]
        bs=[block('graphic',[title,drawing]),block('caption',[cap]),block('body',[body])]
        p=dict(page=1,elements=es,blocks=bs,tables=[],region_box_px=[0,0,220,300],
               main_text=dict(columns=[[0,200]],blocks=[
                   dict(id=bid,cls='main',order=i+1,lines=1,size_px=e['size_px'],box_px=e['box_px'])
                   for i,(bid,e) in enumerate([('graphic',title),('body',body)])]),
               floats=[dict(id='figure',caption=cap['text'],blocks=['caption','graphic'],box_px=[0,10,200,120])])
        prose,floats,side=copy.read_page(p,10,[])
        self.assertEqual(p['copy_figure_lettering'],['title'])
        self.assertEqual([b['lines'] for b in prose],[[body['text']]])
        self.assertEqual(floats[0][2],cap['text'].replace('FIGURE 9.','Figure 9.'))
        self.assertFalse(side)

    def test_unpaired_long_title_keeps_the_original_prose_boundary(self):
        cap=text('cap','FIGURE 9',[0,200,50,210],3)
        title=text('title','A detached title long enough to resemble ordinary body prose.',[60,200,200,210],3)
        panel=text('panel','A',[0,10,8,20],1)
        img=dict(id='image',kind='image',box_px=[0,0,200,180])
        es=[cap,title,panel,img]
        bs=[block('caption',[cap]),block('title',[title]),block('graphic',[panel,img])]
        fs=[]
        boxer.join_figure_lettering(es,bs,[],fs,[])
        self.assertFalse(fs)
        # Pairing with a vector fragment is provisional until trimming. It
        # must not turn the same ambiguous title into a new surviving float.
        img['kind']='outline'
        bs=[block('caption',[cap]),block('title',[title]),block('graphic',[panel,img])]
        fs=[dict(caption=cap['text'],blocks=['caption','graphic'],box_px=[0,0,200,210])]
        boxer.join_figure_lettering(es,bs,[],fs,[])
        self.assertNotIn('lettering',fs[0])

    def test_panel_band_omits_letters_and_stars_and_records_ownership(self):
        panel=text('panel','A',[0,0,8,10],1)
        star=text('star','***',[40,3,50,8],1)
        cap=text('cap','FIGURE 9. A caption.',[0,80,100,90],3)
        body=text('body','The body remains.',[0,110,100,122],4,12)
        es=[panel,star,cap,body];bs=[block(e['id'],[e]) for e in es]
        p=dict(page=1,elements=es,blocks=bs,tables=[],region_box_px=[0,0,220,300],
               _figure_regions=[[5,10,100,70]],main_text=dict(columns=[[0,100]],blocks=[
                   dict(id=e['id'],cls='main',order=i+1,lines=1,size_px=e['size_px'],box_px=e['box_px'])
                   for i,e in enumerate([panel,star,body])]),
               floats=[dict(id='figure',caption=cap['text'],blocks=['cap'],box_px=[0,10,100,90])])
        with patch.object(copy,'table_float_regions',lambda p,body:p):
            prose,floats,side=copy.read_page(p,12,[])
        self.assertEqual(p['copy_figure_lettering'],['panel','star'])
        self.assertEqual(len(prose),1)
        self.assertIn(body['text'],str(prose))
        self.assertFalse(side)

    def test_thin_diagram_labels_belong_below_the_preceding_caption(self):
        upper=text('upper','FIGURE 1. The preceding picture.',[0,30,200,40],1)
        lower=text('lower','FIGURE 2. The following diagram.',[0,180,200,190],5)
        img=dict(id='image',kind='image',box_px=[0,0,200,20])
        labels=[text(f'label:{i}','gene',[40,60+40*i,60,67+40*i],i+2) for i in range(3)]
        shapes=[dict(id=f'fill:{i}',kind='fill',box_px=[40,70+40*i,100,77+40*i]) for i in range(3)]
        es=[upper,lower,img]+labels+shapes
        bs=[block('upper',[upper]),block('lower',[lower]),block('image',[img])]
        bs += [block(f'panel:{i}',[shapes[i],labels[i]]) for i in range(3)]
        fs=[dict(caption=upper['text'],blocks=['upper','image'],box_px=[0,0,200,40]),
            dict(caption=lower['text'],blocks=['lower','panel:2'],box_px=[0,140,200,190])]
        boxer.join_figure_lettering(es,bs,[],fs,[])
        self.assertEqual(set(fs[1]['lettering']),{e['id'] for e in labels})
        self.assertNotIn('lettering',fs[0])

    def test_caption_split_preserves_labels_and_stops_at_larger_prose(self):
        axis=text('axis','10', [40,10,50,20],1)
        cap=text('cap','FIGURE 9. A plotted result.',[0,30,100,40],2)
        cont=text('cont','The caption continues.',[0,42,100,52],3)
        prose=text('prose','The following body paragraph has a different larger face.',[0,60,100,72],4,12)
        es=[axis,cap,cont,prose];bs=[block('mixed',es)]
        boxer.split_figure_caption_blocks(es,bs)
        self.assertEqual(bs[1]['members'],['cap','cont'])
        self.assertEqual(bs[0]['members'],['axis','prose'])
        self.assertEqual(bs[0]['before_caption']['members'],[e['id'] for e in es])
        # Table-owned mixtures remain the table reader's responsibility.
        bs=[block('mixed',es)]
        boxer.split_figure_caption_blocks(es,bs,[dict(members=['axis'])])
        self.assertEqual(len(bs),1)

    def test_caption_mention_after_prose_is_not_split(self):
        before=text('body','This ordinary prose line describes the result in detail.',[0,0,100,10],1)
        mention=text('mention','FIGURE 9. A discussion reference.',[0,12,100,22],2)
        es=[before,mention];bs=[block('body',es)]
        boxer.split_figure_caption_blocks(es,bs)
        self.assertEqual(len(bs),1)

    def test_caption_cannot_borrow_the_next_column_on_its_baseline(self):
        cap=text('cap','FIGURE 9. A caption.',[0,80,100,90],1)
        cont=text('cont','Its final sentence.',[0,92,100,102],2)
        body=text('body','The other column begins here.',[115,80,215,92],1,12)
        img=dict(id='img',kind='image',box_px=[0,0,100,70])
        bs=[block('caption',[cap,cont]),block('body',[body]),block('graphic',[img])]
        mt=dict(id='body',cls='main',order=1,lines=1,size_px=12,box_px=body['box_px'])
        p=dict(page=1,elements=[cap,cont,body,img],blocks=bs,tables=[],
               region_box_px=[0,0,230,300],main_text=dict(blocks=[mt],columns=[[0,100],[115,215]]),
               floats=[dict(id='figure',caption=cap['text'],blocks=['caption','graphic'],box_px=[0,0,100,102])])
        prose,floats,side=copy.read_page(p,12,[])
        self.assertEqual(floats[0][2],'Figure 9. A caption.\nIts final sentence.')
        self.assertIn(body['text'],str(prose))
        self.assertFalse(side)

        # On a page with no body columns, the next figure's own label still
        # establishes a caption boundary.
        body['text']='FIGURE 10. The neighboring caption.'
        p['main_text']=dict(blocks=[],columns=[])
        p['floats'].append(dict(id='neighbor',caption=body['text'],blocks=['body'],box_px=body['box_px']))
        prose,floats,side=copy.read_page(p,12,[])
        self.assertEqual(floats[0][2],'Figure 9. A caption.\nIts final sentence.')
        self.assertEqual(floats[1][2],'Figure 10. The neighboring caption.')

    def test_explicit_lettering_overrides_stale_main_classification(self):
        panel=text('panel','B',[0,0,8,10],1)
        cap=text('cap','FIGURE 9. A caption.',[0,40,100,50],2)
        bs=[block('panel',[panel]),block('caption',[cap])]
        p=dict(page=1,elements=[panel,cap],blocks=bs,tables=[],region_box_px=[0,0,220,300],
               main_text=dict(columns=[[0,100]],blocks=[dict(id='panel',cls='main',order=1,lines=1,size_px=10,box_px=panel['box_px'])]),
               floats=[dict(id='figure',caption=cap['text'],blocks=['caption'],box_px=[0,20,100,50],lettering=['panel'])])
        prose,floats,side=copy.read_page(p,10,[])
        self.assertFalse(prose)
        self.assertFalse(side)
        self.assertEqual(len(floats),1)

    def test_caption_math_fragments_inside_a_column_are_preserved(self):
        cap=text('cap','FIGURE 9. Ratio E',[0,80,70,90],1)
        doi=text('doi','doi:example',[0,104,65,114],3)
        math=text('math','/ F',[90,80,110,90],1)
        img=dict(id='img',kind='image',box_px=[0,0,150,70])
        bs=[block('caption',[cap,doi]),block('math',[math]),block('graphic',[img])]
        p=dict(page=1,elements=[cap,doi,math,img],blocks=bs,tables=[],
               region_box_px=[0,0,350,300],main_text=dict(blocks=[],columns=[[0,150],[180,330]]),
               floats=[dict(id='figure',caption=cap['text'],blocks=['caption','graphic'],box_px=[0,0,150,114])])
        prose,floats,side=copy.read_page(p,12,[])
        self.assertIn('Ratio E / F',floats[0][2])
        self.assertFalse(side)
        # A separately typeset one-line title can carry an earlier main-text
        # class. Matching caption size and column still establish ownership.
        p['main_text']['blocks']=[dict(id='math',cls='main',order=1,lines=1,size_px=10,box_px=math['box_px'])]
        prose,floats,side=copy.read_page(p,12,[])
        self.assertIn('Ratio E / F',floats[0][2])
        self.assertFalse(side)


if __name__=='__main__':
    unittest.main()
