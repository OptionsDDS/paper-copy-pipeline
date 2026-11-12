"""Side abstract, native citation and translation ownership regressions.

Run unit fixtures with unittest. Pass a completed S01 directory to check the
page-image-labelled acceptance sequence and repeatable rule-6 records.
"""
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    obj = importlib.util.module_from_spec(spec); spec.loader.exec_module(obj)
    return obj
copy = module('side_copy', 'copy_paper.py')
boxer = module('side_boxer', 'standalone/element_boxer_sc.py')

def block(name, text, box, size=10, lines=4):
    return dict(id=name, text=text, box_px=box, size=size, lines=lines, cls='main', members=[name])

def run(b, font='Times-Roman'):
    return dict(id=b['id'], text=b['text'], box_px=b['box_px'], run_size_px=b['size'],
                size_px=b['size'], kind='text', angle=0, font=font)


class SideColumn(unittest.TestCase):
    def test_keyword_column_and_coextensive_italic_opening_are_reserved(self):
        bs = [block('body','Body prose.',[0,20,90,160]),
              block('opening','This abstract describes how cells respond to changes in their environment.\n'
                    'The study compares several conditions and reports consistent results.\n'
                    'Those results are discussed in the following column.',[100,20,190,90]),
              block('ending','Its conclusion.\nKey Words: cells\nand tissue.',[200,20,290,90])]
        rs = [run(b,'Times-Italic' if b['id']!='body' else 'Times-Roman') for b in bs]
        region = boxer.side_abstract_blocks(bs,rs,10,lambda b:b['text'])
        self.assertEqual(region[0]['blocks'],['opening','ending'])
        self.assertFalse(bs[0].get('abstract'))
        self.assertTrue(all(b['abstract'] for b in bs[1:]))
        # An ordinary key-word sentence is insufficient evidence.
        for b in bs: b.pop('abstract',None); b.pop('side_abstract',None)
        self.assertEqual(boxer.side_abstract_blocks(bs,[run(b) for b in bs],10,lambda b:b['text']),[])
        strip = block('strip','Key words: cells\ntissue; biology; growth\ndevelopment.',[200,20,290,90],8)
        self.assertEqual(boxer.side_abstract_blocks([bs[0],strip],[rs[0],run(strip)],10,lambda b:b['text']),[])

    def test_translation_bands_split_whole_author_runs_without_loss(self):
        head=block('head','Abstract Translations [German, Spanish]',[0,0,290,15],14,1)
        a=block('a','AUTOR(EN): Example One.',[0,30,90,70])
        b=block('b','AUTOR(ES): Example Two.',[0,90,90,130])
        mixed=block('mixed','',[0,30,90,130]);mixed['members']=['a','b']
        title1=block('title1','First translated title',[110,30,290,40],10,1)
        title2=block('title2','Second translated title',[110,90,290,100],10,1)
        text1=block('text1','ZUSAMMENFASSUNG: First text.',[110,50,290,75])
        text2=block('text2','ABSTRACTO: Second text.',[110,110,290,140])
        rs=[run(x) for x in (head,a,b,title1,title2,text1,text2)]
        originals=[head,mixed,title1,title2,text1,text2]
        bs,ordered,splits=boxer.translated_abstract_blocks(originals,rs,lambda b:b['text'])
        self.assertEqual([b['translation_role'] for b in ordered],
                         ['heading','authors','title','text','authors','title','text'])
        self.assertEqual(len(splits),1)
        self.assertEqual(sorted(m for b in originals for m in b['members']),sorted(m for b in bs for m in b['members']))
        self.assertTrue(all(b['in_refs'] is False for b in ordered))

    def test_misassigned_citation_uses_native_predecessor_in_another_run(self):
        def char(t,x,y,size):
            return dict(text=t,x0=x,y0=y-size*.7,x1=x+size*.4,y1=y,
                        origin=(x,y),adv_x1=x+size*.4,size=size)
        first=dict(id='first',kind='text',angle=0,run_size_px=10,text='word1-3',
                   char_ids=[0,1,2,3,20,4,21],box_px=[0,0,50,15])
        first['_chars']=[char(t,i*4,10,10) for i,t in enumerate('word-')]
        target=dict(id='target',kind='text',angle=0,run_size_px=10,text='other.',
                    char_ids=list(range(14,20)),box_px=[0,12,24,22])
        target['_chars']=[char(t,i*4,22,10) for i,t in enumerate('other.')]
        digits=[char('1',24,17,5),char('3',26,17,5)]
        first['_chars'].insert(4,digits[0]);first['_chars'].append(digits[1])
        p=dict(elements=[first,target],blocks=[dict(id='b',members=['first','target'])],
               main_text=dict(blocks=[dict(id='b',cls='main')]))
        copy.restore_citation_ownership([p])
        self.assertEqual(first['text'],'word-')
        self.assertEqual(target['text'],'other.13')
        self.assertEqual(sorted(first['char_ids']+target['char_ids']),list(range(5))+list(range(14,22)))
        self.assertEqual(len(p['copy_citation_moves']),1)

    def test_image_notice_ignores_running_head_but_requires_substantial_image(self):
        b=block('head','JOURNAL 123',[0,280,180,290]);r=run(b)
        p=dict(elements=[r,dict(kind='image',box_px=[30,20,180,160])],region_box_px=[0,0,200,300],
               blocks=[b],main_text=dict(blocks=[dict(id='head',cls='furniture')]))
        self.assertTrue(copy.image_only_page(p))
        p['elements'][1]['box_px']=[0,290,200,298]
        self.assertFalse(copy.image_only_page(p))

    def test_image_notice_waits_for_a_cross_page_sentence(self):
        items=[dict(kind='para',text='The sentence is',page=1),
               dict(kind='page',page=1),dict(kind='unread_page',text='page 2 is an image; not read',page=2),
               dict(kind='page',page=2),dict(kind='para',text='continued here.',page=3)]
        joined=copy.rejoin_paragraphs(items,copy.Joiner([]))
        self.assertEqual(joined[0]['text'],'The sentence is continued here.')
        self.assertEqual([x['text'] for x in joined if x['kind']=='unread_page'],['page 2 is an image; not read'])


def acceptance(folder):
    text=(folder/'copy.md').read_text()
    anchors=['## Abstract','Failures of dental implants are detrimental','This review article discusses diagnosis',
             '## Key Words','use of dental implants','insufficient evidence for de-osseointegration',
             'still result in under or overestimation','facial, and lingual artery (Table 5).13',
             '- 72. Tarnow','## Reprint requests and correspondence to:',
             '## Abstract Translations','AUTOR(EN):','## Implantatreversible','ZUSAMMENFASSUNG:',
             'SCHLÜSSELWÖRTER:','AUTOR(ES):','## Complicaciones','ABSTRACTO:','PALABRAS CLAVES:',
             'AUTOR(ES):','## Complica','RESUMO:','PALAVRAS-CHAVE:',
             '[page 10 is an image; not read]','## Places the program is not sure of',
             '- page 10 is an image; not read']
    pos=0
    for anchor in anchors:
        at=text.find(anchor,pos)
        assert at>=0, (anchor,pos)
        pos=at+len(anchor)
    assert not re.search(r'fa1-3|still rediscusses',text)
    assert text.count('Failures of dental implants')==1
    for path in folder.glob('page-*.json'):
        p=json.loads(path.read_text()); ids=[cid for e in p['elements'] if e['kind']=='text' for cid in e['char_ids']]
        assert len(ids)==len(set(ids)),path
        assert p['counts']['characters_in_elements']==p['counts']['characters_in_region'],path
    print('S01 image-labelled acceptance: pages 1, 4, 8, 9, 10 pass; all 10 pages conserve character IDs')


if __name__=='__main__':
    if len(sys.argv)==2 and Path(sys.argv[1]).is_dir(): acceptance(Path(sys.argv[1]))
    else: unittest.main()
