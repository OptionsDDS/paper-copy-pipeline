"""Source-position regressions for the second exporter polish."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import math
import sys

spec = importlib.util.spec_from_file_location('copy_paper', Path(__file__).resolve().parents[1] / 'copy_paper.py')
copy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copy)


def run(text, chars):
    return dict(kind='text', id='r', text=text, angle=0, box_px=[0, 0, 100, 20],
                char_ids=list(range(len(chars))), _chars=chars)


def char(text, x, y=5, width=5, height=10):
    return dict(text=text, x0=x, y0=y, x1=x+width, y1=y+height, size=15,
                adv_x1=x+width+1, font='Native')


class Polish2(unittest.TestCase):
    def test_affiliation_keeps_native_spaces_after_composed_accents(self):
        native=run('2 Université Example, Faculté de Médecine.', [])
        page=dict(elements=[native],blocks=[dict(id='b',members=['r'])],copy_prose_glyphs=[dict(run='r')])
        author=dict(affiliations=[dict(marker='2',block='b',text='Universite´Example, Faculte´de Me´decine.')])
        joiner=SimpleNamespace(lines=lambda lines:' '.join(lines))
        self.assertEqual(copy.front_matter([page],author,joiner), [('2','Université Example, Faculté de Médecine.',1)])
        native['text']='2 Lima, Perú'
        author['affiliations'][0]['text']='Lima, Peru´'
        self.assertEqual(copy.front_matter([page],author,joiner), [('2','Lima, Perú',1)])
        native['text']='2 Hong- Kong, China'
        author['affiliations'][0]['text']='Hong-Kong, China'
        self.assertEqual(copy.front_matter([page],author,copy.Joiner([])), [('2','Hong-Kong, China',1)])

    def test_repaired_affiliation_is_not_repeated(self):
        joiner = SimpleNamespace(lines=lambda lines: ' '.join(lines))
        raw = '5 Institute of Sau´de, Example City'
        repaired = '5 Institute of Saúde, Example City'
        note = 'Correspondence: Jane Doe.'
        self.assertEqual(copy.without_front_text([repaired, note], [raw], joiner), note)
        self.assertEqual(copy.without_front_text([note, repaired], [raw], joiner), note)
        self.assertEqual(copy.without_front_text(['Ofﬁce North', note], ['Office North'], joiner), note)
        self.assertEqual(copy.without_front_text(['The biology'], ['ology'], joiner), 'The biology')
        address='1 First Institute. • Second Institute.'
        self.assertEqual(copy.without_front_text(['1 First Institute.', '• Second Institute.'], [address], joiner, keep_lines=True), '')
        self.assertEqual(copy.without_front_text(['1 First Institute.', '• First topic', '• Second topic'], ['1 First Institute.'], joiner, keep_lines=True).splitlines(), ['• First topic','• Second topic'])

    def test_unknown_bullet_requires_one_closed_round_outline(self):
        class Glyph:
            contours=1
            def draw(self, pen):
                for _ in range(self.contours):
                    for i in range(32):
                        p=(100*math.cos(i*math.pi/16),100*math.sin(i*math.pi/16))
                        (pen.moveTo if i==0 else pen.lineTo)(p)
                    pen.closePath()
        glyph=Glyph()
        font=SimpleNamespace(basefont='Native',gmap={1:0},prog=SimpleNamespace(kind='cff',order=['unknown'],glyphs={'unknown':glyph}))
        reader=SimpleNamespace(sc_doc=lambda _:SimpleNamespace(fonts={'f':font}))
        c=dict(char('�',0,5,6,6),source_code=1)
        with patch.dict(sys.modules,{'_copy_table_reader':reader}):
            self.assertTrue(copy.round_bullet(c,{'_table_pdf':'fixture'}))
            glyph.contours=2
            self.assertFalse(copy.round_bullet(c,{'_table_pdf':'fixture'}))
            glyph.contours=1
            self.assertFalse(copy.round_bullet(dict(c,x1=10),{'_table_pdf':'fixture'}))

    def test_accent_position_beats_neighboring_vocabulary_and_keeps_word_space(self):
        cs=[char('a',0),char('´',2,1,2,2),char('n',6),char('E',18)]
        e=run('a´ nE',cs); p=dict(elements=[e])
        copy.restore_prose_glyphs([p])
        self.assertEqual(e['text'],'ánE')  # Only the accent-adjacent boundary is reconstructed.
        self.assertEqual(e['char_ids'],[0,2,3])
        cs=[char('e',0),char('´',2,1,2,2),char('E',13)]
        e=run('e´E',cs); p=dict(elements=[e])
        copy.restore_prose_glyphs([p])
        self.assertEqual(e['text'],'é E')

    def test_real_apostrophe_nonoverlapping_accent_and_table_are_untouched(self):
        for text,cs in [("a'n",[char('a',0),char("'",6,1,2,2),char('n',9)]),
                        ('a´n',[char('a',0),char('´',6,1,2,2),char('n',9)])]:
            e=run(text,cs);copy.restore_prose_glyphs([dict(elements=[e])])
            self.assertEqual(e['text'],text)
        e=run('a´n',[char('a',0),char('´',2,1,2,2),char('n',6)])
        copy.restore_prose_glyphs([dict(elements=[e],tables=[dict(box_px=[0,0,100,20])])])
        self.assertEqual(e['text'],'a´n')

    def test_bullet_needs_printed_line_start_not_sentence_punctuation(self):
        self.assertFalse(copy.list_item_start('Volume 7 • Number 2'))
        self.assertFalse(copy.list_item_start('A sentence. • A separator'))
        self.assertFalse(copy.list_item_start('• another term','an unfinished expression'))
        self.assertEqual(copy.list_block_starts(['An introduction','• First item','• Second item'],[0,15,15]),{1,2})

    def test_inflection_evidence_and_derivation_do_not_override_printed_compound(self):
        j=copy.Joiner(['These paintbrushes are useful; care matters; induced changes.'])
        self.assertEqual(j.lines(['paint-','brushing']),'paintbrushing')
        self.assertEqual(j.lines(['care-','less']),'careless')
        self.assertEqual(j.lines(['pressure-','induced']),'pressure-induced')
        j.prose=False
        self.assertEqual(j.lines(['pressure-','induced']),'pressureinduced')
        j=copy.Joiner(['These paintbrushes and paint-brushing are useful.'])
        self.assertEqual(j.lines(['paint-','brushing']),'paint-brushing')
        j=copy.Joiner(['Other words only.'])
        self.assertEqual(j.lines(['pressure-','induced']),'pressureinduced')

    def test_heading_font_requires_repeated_independent_heading_rows(self):
        blocks=[]
        for page in range(1,4):
            blocks.append(dict(page=page, lines=['A Short Heading','The next paragraph has enough ordinary words to establish prose.'],
                lefts=[0,0],row_boxes=[[0,100,180,112],[0,120,300,134]],sizes=[15,16],faces=['Opaque','Body'],
                emphasis=[False,False],meta=dict(box_px=[0,100,300,134],size_px=16),page_height=500))
        copy.heading_context([(blocks,[],[])],16)
        for b in blocks:
            parts=copy.paragraph_blocks(b,16)
            self.assertTrue(parts[0]['meta']['font_heading'])
            self.assertFalse(parts[-1]['meta']['font_heading'])
        blocks[-1]['lines'][0]='A complete sentence.'
        for b in blocks:b['emphasis']=[False,False]
        copy.heading_context([(blocks,[],[])],16)
        self.assertFalse(any(b['emphasis'][0] for b in blocks))
        for label in ['Figure S2 Description of the supporting analysis', 'A compound ending in A/']:
            for b in blocks:
                b['lines'][0]=label
                b['emphasis']=[False,False]
            copy.heading_context([(blocks,[],[])],16)
            self.assertFalse(any(b['emphasis'][0] for b in blocks))


if __name__ == '__main__': unittest.main()
