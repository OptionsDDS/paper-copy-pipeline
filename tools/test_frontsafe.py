"""Source-line fallback, multiline names, and detached affiliation ownership."""
import importlib.util
import sys
from pathlib import Path
import unittest
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod
boxer=module('frontsafe_boxer',ROOT/'standalone/element_boxer_sc.py')
paper=module('frontsafe_copy',ROOT/'copy_paper.py')
def page(number,specs):
    runs=[dict(id=str(i),kind='text',text=text,box_px=[10,y,900,y+14],line=i,angle=0,
               size_px=size,run_size_px=size) for i,(text,y,size,cls) in enumerate(specs)]
    return dict(page=number,elements=runs,art=[],region_box_px=[0,0,1000,1400],
        blocks=[dict(id=str(i),members=[str(i)],box_px=e['box_px']) for i,e in enumerate(runs)],
        main_text=dict(body_size_px=16,blocks=[dict(id=str(i),cls=specs[i][3],order=None,
            box_px=e['box_px'],lines=1,size_px=e['size_px']) for i,e in enumerate(runs)]))
def parse(lines):
    p=page(1,[('Properties of novel surfaces',100,30,'title')]
        +[(line,150+30*i,20,'authors') for i,line in enumerate(lines)]
        +[('1Department of Science',200+30*len(lines),12,'other')])
    chars=[]
    for e in p['elements']:
        x=10; y=e['box_px'][1]; size=e['size_px']; ids=[]
        for c in e['text']:
            if not c.isspace():
                ids.append(len(chars)); chars.append(dict(text=c,x0=x,x1=x+.45*size,y0=y,y1=y+14,
                    size=size,font='Regular',origin=(x,y+14),adv_x1=x+.5*size))
            x+=.5*size
        e.update(char_ids=ids,box_px=[10,y,x,y+14])
        p['blocks'][int(e['id'])]['box_px']=e['box_px']
    with patch.object(boxer,'page_files',return_value=['page-01.json']), \
         patch.object(boxer,'read_json',return_value=p), \
         patch.object(boxer,'pdfium_characters',return_value=chars),patch.object(boxer,'write_json'):
        return boxer.authors_and_affiliations('unused','unused')
class Byline(unittest.TestCase):
    def test_fallback_preserves_live_pdf_reader_classes(self):
        import pdfminer.pdftypes
        original = pdfminer.pdftypes.PDFObjRef
        p=page(1,[('Ada Example',100,20,'authors')])
        with patch.dict(sys.modules, {'_copy_table_reader':boxer}):
            paper.printed_front_matter([p],dict(author_run_ids=['0'],authors=[]))
            import pdfminer.pdftypes as after
            self.assertIs(after.PDFObjRef,original)
    def test_same_style_continues_across_three_rows(self):
        a=parse(['Ada Example1 | Ben Sample1 |','Carlos Fernando de Almeida Barros Silva1 |',
                 'Carla Third1 | David Fourth1'])
        self.assertEqual(len(a['authors']),5)
        self.assertEqual(a['authors'][2]['name'],'Carlos Fernando de Almeida Barros Silva')
        self.assertEqual(a['checks']['byline_name_groups'],5)
        self.assertEqual(len(a['byline_lines']),3)
    def test_slash_after_degrees_and_at_end_of_line(self):
        a=parse(['Ada Example, DMD/Ben Sample, DDS, PhD, Prof Dr med dent/',
                 'Carla Third, DDS/David Fourth, DMD, MSc'])
        self.assertEqual([n['name'] for n in a['authors']],['Ada Example','Ben Sample','Carla Third','David Fourth'])
        self.assertIn('Prof Dr med dent',a['authors'][1]['degrees'])
        self.assertEqual(a['checks']['byline_name_groups'],4)
    def test_count_is_independent_and_ignores_degrees(self):
        self.assertEqual(len(boxer.byline_name_groups(['1,2Ada Example and 3Ben Sample / Carla Third, DDS, PhD | David Fourth*'])),4)
        self.assertEqual(boxer.byline_name_groups(['Department of Science']),[])
        self.assertEqual(boxer.byline_name_groups(['Ada','Q. Example1']),['Ada Q. Example'])
    def test_unverified_rows_survive_without_author_run_ids(self):
        p=page(1,[('Ada Example1 / Ben Sample2',100,20,'authors'),
                  ('1Department of Science',140,12,'other'),('2Example University',160,12,'other')])
        records,count=paper.printed_front_matter([p],dict(author_box_px=[10,100,900,114],
            affiliation_box_px=[10,140,900,174],authors=[]))
        self.assertEqual(count,2)
        self.assertEqual(records[0]['lines'],[e['text'] for e in p['elements']])
    def test_independent_check_sees_an_unparsed_same_style_next_row(self):
        p=page(1,[('Ada Example1 | Ben Sample1 |',100,20,'authors'),
                  ('Carla Third1 | David Fourth1',130,20,'other'),('1Department of Science',170,12,'other')])
        records,count=paper.printed_front_matter([p],dict(author_run_ids=['0'],authors=[]))
        self.assertEqual(count,4)
        self.assertEqual(records[0]['run_ids'],['0','1'])
    def test_unmarked_names_on_separate_rows_and_labelled_affiliations(self):
        self.assertEqual(len(boxer.byline_name_groups(['Ada Example','Ben Sample','Carla Third'])),3)
        p=page(1,[('Ada Example',100,20,'authors'),("Authors’ affiliations:",140,12,'aside'),
                  ('Ada Example, Example University',160,12,'aside')])
        p['blocks']=[p['blocks'][0],dict(id='address',members=['1','2'],box_px=[10,140,900,174])]
        records,_=paper.printed_front_matter([p],dict(author_run_ids=['0'],authors=[]))
        self.assertEqual(records[0]['lines'],[e['text'] for e in p['elements']])
    def test_unmarked_address_prefix_is_kept_above_marked_address(self):
        p=page(1,[('Ada Example1',100,20,'authors'),('Academic Unit of Science',140,12,'other'),
                  ('Clinical Care, 1Department of Science',160,12,'other'),('Example University',180,12,'other'),
                  ('† Another School of Science',200,12,'other')])
        p['blocks']=[p['blocks'][0],dict(id='address',members=['1','2','3','4'],box_px=[10,140,900,214])]
        p['main_text']['blocks'].append(dict(id='address',cls='other'))
        records,_=paper.printed_front_matter([p],dict(author_run_ids=['0'],
            affiliation_box_px=[10,160,900,194],authors=[]))
        self.assertEqual(records[0]['lines'],[e['text'] for e in p['elements']])
    def test_descriptive_institution_below_byline_is_still_an_address(self):
        for address in ['Zoological Institute, Example University',
                        'Département de Physique, Université de Montréal',
                        'Departamento de Biologia, Universidade de São Paulo',
                        'Example & Partners LLP, Example City']:
            with self.subTest(address=address):
                p=page(1,[('Ada Example / Ben Sample',100,20,'authors'),
                          (address,130,12,'other')])
                records,_=paper.printed_front_matter([p],dict(author_run_ids=['0'],authors=[]))
                self.assertEqual(records[0]['lines'],[e['text'] for e in p['elements']])
                p['blocks']=[dict(id='byline',members=['0','1'],box_px=[10,100,900,144])]
                p['main_text']['blocks']=[dict(id='byline',cls='authors',order=None)]
                records,_=paper.printed_front_matter([p],dict(author_run_ids=['0'],authors=[]))
                self.assertEqual(records[0]['lines'],[e['text'] for e in p['elements']])
    def test_unverified_prose_box_cannot_be_quoted_as_a_byline(self):
        p=page(1,[('The results of the study are discussed below.',100,20,'main'),
                  ('Several measurements show considerable variation.',130,20,'main')])
        records,count=paper.printed_front_matter([p],dict(author_box_px=[10,100,900,144],
            byline_lines=[dict(run_ids=['0','1'])],authors=[dict(name='The Results',name_ok=True)]))
        self.assertEqual(records,[])
        self.assertEqual(count,0)
    def test_publication_history_above_marked_byline(self):
        p=page(1,[('Received for publication, January 1, 2020',100,12,'title'),
                  ('Ada Example‡, Ben Sample§,',130,20,'title'),
                  ('and Carla Third‡',160,20,'title'),
                  ('From the ‡Institute of Science',190,12,'title'),
                  ('Departments of §Chemistry and Biology, Example University',210,12,'title')])
        p['blocks']=[dict(id='front',members=[str(i) for i in range(5)],box_px=[10,100,900,224])]
        records,count=paper.printed_front_matter([p],dict(author_run_ids=['0'],authors=[]))
        self.assertEqual(count,3)
        self.assertEqual(records[0]['lines'],[e['text'] for e in p['elements'][1:]])
    def test_unmarked_sidebar_address_sharing_the_byline_block(self):
        p=page(1,[('Ada Example',100,20,'authors'),('University of Science',130,12,'other'),
                  ('Department of Biology, Example City',150,12,'other'),('Correspondence',180,12,'other')])
        p['blocks']=[dict(id='sidebar',members=['0','1','2','3'],box_px=[10,100,900,194])]
        records,count=paper.printed_front_matter([p],dict(author_run_ids=['0'],authors=[]))
        self.assertEqual(records[0]['run_ids'],['0','1','2'])
    def test_unmarked_foot_address_stops_at_email(self):
        p=page(1,[('Ada Example',100,20,'authors'),('Disclosure: nothing to disclose.',1100,12,'aside'),
                  ('A. B. Example University, School of Dentistry',1120,12,'aside'),
                  ('Example City 12345, Country',1140,12,'aside'),
                  ('E-mail address: a@example.org',1160,12,'aside'),('Published 2020',1180,12,'aside')])
        p['blocks']=[p['blocks'][0],dict(id='foot',members=[str(i) for i in range(1,6)],box_px=[10,1100,900,1194])]
        records,_=paper.printed_front_matter([p],dict(author_run_ids=['0'],authors=[]))
        self.assertEqual(records[0]['run_ids'],['0','2','3','4'])
    def test_late_panel_is_front_matter_but_reference_is_not(self):
        first=page(1,[('Ada Example / Ben Sample',100,20,'authors')])
        last=page(4,[('Ada Example Professor, Department of Science',900,12,'aside'),
                    ('Ben Sample Example University',920,12,'aside'),('Correspondence: Ada Example',940,12,'aside')])
        last['blocks']=[dict(id='panel',members=['0','1','2'],box_px=[10,900,900,954])]
        last['main_text']['blocks']=[dict(id='panel',cls='main',order=1)]
        refs=page(3,[('12. Ada Example and Ben Sample. University research.',100,12,'main')])
        records,count=paper.printed_front_matter([first,refs,last],dict(author_run_ids=['0'],authors=[]))
        self.assertEqual([r['page'] for r in records],[1,4])
        self.assertEqual(last['_late_front_run_ids'],['0','1','2'])
        self.assertEqual(last['main_text']['blocks'][0]['cls'],'main')
        self.assertEqual(last['main_text']['blocks'][0]['order'],1)
        self.assertNotIn('_late_front_run_ids',refs)
    def test_named_foot_address_is_once_and_excludes_shared_copyright(self):
        p=page(1,[('Ada Example',100,20,'authors'),('Ada Example',1100,12,'aside'),
                  ('Example University, School of Science',1120,12,'aside'),
                  ('Example University, Example City, Country',1140,12,'aside'),('E-mail: a@example.org',1160,12,'aside'),
                  ('ORCID: https://orcid.org/0000',1180,12,'aside'),
                  ('CC This is an open-access article distributed under the terms',1200,12,'aside'),
                  ('of the Creative Commons license.',1220,12,'aside')])
        p['blocks']=[p['blocks'][0],dict(id='foot',members=[str(i) for i in range(1,8)],box_px=[10,1100,900,1234])]
        records,_=paper.printed_front_matter([p],dict(author_run_ids=['0'],authors=[]))
        self.assertEqual([r['run_ids'] for r in records],[['0'],['1','2','3','4','5']])
        self.assertEqual(p['_late_front_run_ids'],['1','2','3','4','5'])
    def test_address_removal_preserves_layout_evidence_and_adjacent_prose(self):
        p=page(1,[('Ada Example',100,12,'main'),('Example University',120,12,'main'),
                  ('The study supports tissue formation.',140,12,'main')])
        p['_late_front_run_ids']=['0','1']
        b=dict(lines=[e['text'] for e in p['elements']],row_boxes=[e['box_px'] for e in p['elements']],
               sizes=[12]*3,first='Ada Example',meta=dict(cls='main'))
        result=[([b],[],[])]
        paper.remove_printed_front_rows(result,[p])
        self.assertEqual(result[0][0][0]['lines'],['The study supports tissue formation.'])
        self.assertEqual(p['main_text']['blocks'][0]['order'],None)
    def test_detached_single_author_signature_and_address(self):
        p=page(1,[('Ada Example',100,20,'authors'),('Ada Example (E-mail: a@example.org)',600,12,'aside'),
                  ('Example City, Country',620,12,'aside')])
        p['blocks']=[p['blocks'][0],dict(id='signature',members=['1','2'],box_px=[10,600,900,634])]
        p['main_text']['blocks'].append(dict(id='signature',cls='aside',order=2))
        records,_=paper.printed_front_matter([p],dict(author_run_ids=['0'],authors=[]))
        self.assertEqual(records[-1]['lines'],[p['elements'][i]['text'] for i in (1,2)])
        self.assertTrue(records[-1]['late'])
        p['blocks']=[dict(id='prose',members=['0','1','2'],box_px=[10,100,900,634])]
        p['main_text']['blocks']=[dict(id='prose',cls='main',order=1)]
        p.pop('_late_front_run_ids',None)
        records,_=paper.printed_front_matter([p],dict(author_run_ids=['0'],authors=[]))
        self.assertEqual(records[-1]['run_ids'],['1','2'])
        self.assertEqual(p['main_text']['blocks'][0]['cls'],'main')
    def test_label_stays_with_a_long_detached_postal_address(self):
        first=page(1,[('Ada Example',100,20,'authors')])
        lines=['Address:', 'Ada Example', 'Example University', 'School of Science',
               'Department of Biology', 'Research Centre', '123 Science Road',
               'Example City', 'Country', 'E-mail: a@example.org']
        last=page(4,[(text,800+20*i,12,'aside') for i,text in enumerate(lines)])
        last['blocks']=[dict(id='address',members=[str(i) for i in range(len(lines))],box_px=[10,800,900,994])]
        records,_=paper.printed_front_matter([first,last],dict(author_run_ids=['0'],authors=[]))
        self.assertEqual(records[-1]['lines'],lines)
        self.assertEqual(len(records),2)
    def test_translated_author_biography_stays_with_its_abstract(self):
        first=page(1,[('Ada Example',100,20,'authors')])
        last=page(4,[('Author biography',800,12,'main'),('Ada Example',820,12,'main'),
                     ('Example University',840,12,'main'),('E-mail: a@example.org',860,12,'main')])
        last['blocks']=[dict(id='original',members=['0','1','2','3'],box_px=[10,800,900,874]),
                        dict(id='translated',members=['0','1','2','3'],box_px=[10,800,900,874])]
        last['main_text']['blocks']=[dict(id='translated',cls='main',translation_role='authors')]
        records,_=paper.printed_front_matter([first,last],dict(author_run_ids=['0'],authors=[]))
        self.assertEqual(len(records),1)
        self.assertNotIn('_late_front_run_ids',last)
if __name__=='__main__': unittest.main()
