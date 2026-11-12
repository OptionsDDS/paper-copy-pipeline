"""Front selection, contextual credentials, note boundaries and DOI underlays."""
import importlib.util
from pathlib import Path
import tempfile
import unittest


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


fixture = module('test_front5')
boxer, copy, page, parse = fixture.boxer, fixture.paper, fixture.page, fixture.parse


class Front(unittest.TestCase):
    def test_single_word_display_continues_reselected_title(self):
        a = parse([page(1,[
            ('by',500,34,'title','wrong',{}),
            ('Properties of novel surfaces',100,30,'main','title',{}),
            ('medicine',125,30,'main','title',{}),
            ('Ada Example1, Ben Sample1',165,20,'main','byline',{}),
            ('1Department of Science',200,12,'other','address',{})])])
        self.assertEqual(a['title']['text'],'Properties of novel surfaces medicine')
        self.assertEqual(a['checks']['status'],'verified')

    def test_same_size_name_row_is_not_a_title_continuation(self):
        a = parse([page(1,[('Properties of novel surfaces',100,30,'title','title',{}),
            ('Ada Example',125,30,'main','byline',{})])])
        self.assertEqual(a['title']['text'],'Properties of novel surfaces')
        self.assertEqual(a['authors'][0]['name'],'Ada Example')

    def test_by_introduces_detached_names_and_unmarked_address(self):
        for inline in (False, True):
            specs = [('Properties of novel surfaces',100,30,'other','title',{}),
                     ('by Ada Example, III, DDS' if inline else 'by',350,34 if not inline else 20,'title' if not inline else 'main','by',{})]
            if not inline: specs.append(('Ada Example, III, DDS',375,20,'main','panel',{}))
            specs += [('Accredited Member',375 if inline else 400,20,'main','panel',{}),
                      ('Example City, Country',395 if inline else 420,20,'main','panel',{})]
            if inline: specs[0] = (*specs[0][:3], 'title', *specs[0][4:])
            p, cs = page(1,specs)
            # The detached "by" touches the indented name, as in a portrait panel.
            if not inline:
                by=p['elements'][1]; name=p['elements'][2]
                shift=by['box_px'][2]-name['box_px'][0]
                for e in p['elements'][2:]:
                    e['box_px']=[v+shift if i in (0,2) else v for i,v in enumerate(e['box_px'])]
                    for cid in e['char_ids']:
                        for key in ('x0','x1','adv_x1'): cs[cid][key]+=shift
                        cs[cid]['origin']=(cs[cid]['origin'][0]+shift,cs[cid]['origin'][1])
            a=parse([(p,cs)])
            self.assertEqual(a['authors'][0]['name'],'Ada Example III')
            self.assertEqual(a['authors'][0]['degrees'],['DDS'])
            self.assertIn('Accredited Member',a['unmarked_affiliation_candidates'][0]['text'])
            self.assertEqual(a['checks']['byline_name_groups'],1)

    def test_credential_after_a_comma_is_a_degree(self):
        # lane front8: a credential-like acronym after a comma (three or more letters, two
        # capitals) is a degree even without an established degree list; a name-cased word is not
        for degrees, tail, expect in (('DDS, PhD, ', 'FABC2', ['DDS','PhD','FABC']), ('', 'FABC2', ['FABC']), ('', 'Fabc2', None)):
            text='Ada Example, '+degrees+tail
            a=parse([page(1,[('Properties of novel surfaces',100,30,'title','title',{}),
                (text,145,20,'authors','byline',{}),
                ('2Department of Science',190,12,'other','address',{})])])
            if expect:
                self.assertEqual(len(a['authors']),1)
                self.assertEqual(a['authors'][0]['degrees'],expect)
                self.assertEqual(a['authors'][0]['markers'],['2'])
            else:
                self.assertEqual(len(a['authors']),2)
                self.assertNotIn('degrees',a['authors'][0])

    def test_by_in_abstract_cannot_replace_a_byline(self):
        for cls in ('authors','main'):
            a=parse([page(1,[('Properties of novel surfaces',100,30,'title','title',{}),
                ('Ada Example1',145,20,cls,'byline',{}),
                ('1Department of Science',190,12,'other','address',{}),
                ('Abstract',230,16,'main','abstract',{}),
                ('by Other Investigator, Another Person',300,16,'main','abstract',{})])])
            self.assertEqual([x['name'] for x in a['authors']],['Ada Example'])

    def test_supplement_note_ends_address_without_losing_correspondence(self):
        a=parse([page(1,[('Properties of novel surfaces',100,30,'title','title',{}),
            ('Ada Example1',145,20,'authors','byline',{}),
            ('1Department of Science',190,12,'other','address',{}),
            ('A supplementary appendix is available online.',215,12,'other','address',{}),
            ('Corresponding Author: Ada Example',235,12,'other','address',{})])])
        self.assertEqual(a['affiliations'][0]['text'],'Department of Science')
        self.assertEqual(a['article_info'][0]['run_ids'],['3','4'])
        self.assertIn('Corresponding Author:',a['article_info'][0]['text'])

    def test_paired_abstract_panel_excludes_history_and_body(self):
        runs=[dict(id='info',kind='text',text='article info',box_px=[20,200,120,215],run_size_px=20),
              dict(id='abstract',kind='text',text='abstract',box_px=[300,200,410,215],run_size_px=20)]
        specs=[('info','main',runs[0]['box_px'],1,20),
               ('abstract','main',runs[1]['box_px'],1,20),
               ('history','other',[20,240,200,300],4,12),
               ('summary','other',[300,240,700,380],10,14),
               ('body','main',[300,430,700,600],10,16)]
        mt=[dict(id=i,cls=cls,box_px=box,lines=lines,size_px=size,order=None)
            for i,cls,box,lines,size in specs]
        p=dict(elements=runs,main_text=dict(body_size_px=16,blocks=mt),
               blocks=[dict(id=i,members=[i]) for i,*_ in specs])
        copy.prepare_front_abstract_panel(p,{})
        self.assertEqual([b['id'] for b in mt if b.get('side_abstract')],['abstract','summary'])
        self.assertEqual(mt[2]['cls'],'other')
        self.assertNotIn('abstract',mt[4])
        self.assertEqual(p['_front_info_run_ids'],['info'])


class Underlays(unittest.TestCase):
    def test_white_doi_underlay_needs_white_background_and_later_identical_value(self):
        pdf_fixture=module('test_ocrscan')
        for background, value, expected in [('', '123', 'DOI:10.1234/123'),
                                           ('0 g 5 65 90 20 re f ', '123', None),
                                           ('', '456', None)]:
            content=(background+'1 g BT /F 4 Tf 10 70 Td (https://doi.org/10.1234/123) Tj ET '
                     '0 g BT /F 4 Tf 10 70 Td (DOI:10.1234/'+value+') Tj ET')
            with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]) as temp:
                pdf=Path(temp)/'front.pdf'; pdf_fixture.pdf(pdf,content)
                p=dict(page=1,region_box_px=[0,0,209,209],_table_pdf=str(pdf),elements=[])
                chars=copy.table_characters(p)
                ids=sorted(range(len(chars)),key=lambda i:chars[i]['x0'])
                cs=[chars[i] for i in ids]
                e=dict(id='doi',kind='text',text=''.join(c['text'] for c in cs),
                       char_ids=ids,_chars=cs,run_size_px=4*150/72,box_px=[20,55,150,65])
                before=e['text']
                p['elements']=[e]
                copy.omit_unpainted_text([p])
                if background:
                    # white text on a black fill is printed: neither the reader nor the copier hides it
                    self.assertNotEqual(e['text'],'DOI:10.1234/'+value)
                    self.assertEqual(e['text'],before)
                else:
                    # lane claims R3: the reader hides a white text object that later glyphs overprint on the
                    # white page, whatever its value, so the copier finds no underlay left to omit
                    self.assertEqual(before,'DOI:10.1234/'+value)
                    self.assertEqual(e['text'],'DOI:10.1234/'+value)
                    self.assertNotIn('copy_omitted',p)


if __name__=='__main__': unittest.main()
