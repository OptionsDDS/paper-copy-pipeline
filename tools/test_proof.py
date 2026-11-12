"""Geometry and preservation tests for repository-wrapped watermarked proofs."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

copy = module('proof_copy', 'copy_paper.py')
boxer = module('proof_boxer', 'standalone/element_boxer_sc.py')

def char(text, x, y, size=12, angle=0, serial=0):
    return dict(text=text,x0=x,y0=y-size,x1=x+size/2,y1=y,origin=(x,y),
                angle=angle,size=size,font='Test',paint_order=(0,serial),fill_color=.85)

def body():
    return [char('a',100+i%60*5,100+i//60*16) for i in range(600)]

def page(*rows):
    return dict(elements=[dict(kind='text',text=t) for t in rows])

class Proofs(unittest.TestCase):
    def test_large_diagonal_overlay_uses_native_angle_and_keeps_characters(self):
        overlay=[char(t,100+i*30,700-i*40,60,38,i) for i,t in enumerate('UNCORRECTEDPROOF')]
        found=boxer.diagonal_watermarks(body()+overlay,[0,0,700,800])
        self.assertEqual(found,[overlay])
        self.assertEqual(''.join(c['text'] for c in found[0]),'UNCORRECTEDPROOF')

    def test_sideways_body_keeps_existing_orientation_ownership(self):
        sideways=[dict(c,angle=270) for c in body()]
        overlay=[char(t,100+i*30,100+i*40,60,309,i) for i,t in enumerate('JOURNALWATERMARK')]
        self.assertFalse(boxer.diagonal_watermarks(sideways+overlay,[0,0,700,800]))

    def test_small_diagonal_labels_and_horizontal_titles_survive(self):
        for size,angle in [(12,38),(60,0),(60,90)]:
            overlay=[char('X',100+i*30,700-i*40,size,angle,i) for i in range(15)]
            self.assertFalse(boxer.diagonal_watermarks(body()+overlay,[0,0,700,800]))

    def test_scattered_large_plot_letters_are_not_one_watermark(self):
        overlay=[char('X',100+i*30,700-i*40+(30 if i%2 else 0),60,38,i) for i in range(15)]
        self.assertFalse(boxer.diagonal_watermarks(body()+overlay,[0,0,700,800]))

    def test_black_diagonal_display_type_is_not_a_watermark(self):
        overlay=[dict(char('X',100+i*30,700-i*40,60,38,i),fill_color=0) for i in range(15)]
        self.assertFalse(boxer.diagonal_watermarks(body()+overlay,[0,0,700,800]))

    def test_cover_requires_controls_and_a_following_article(self):
        wrapper=page('ResearchGate', 'See discussions, stats', 'CITATIONS 12 READS 30', 'A shortened title...')
        article=page('Article title', 'A B S T R A C T', 'The experiment was performed.')
        self.assertTrue(boxer.repository_cover(wrapper,article))
        self.assertFalse(boxer.repository_cover(wrapper,page('References')))
        self.assertFalse(boxer.repository_cover(page('ResearchGate is cited in this Abstract'),article))
        self.assertFalse(boxer.repository_cover(page('University Library', 'Department of science'),article))

    def test_dense_numbers_establish_sparse_later_margin_without_touching_values(self):
        def digits(start,count,x=20,y=100,step=25):
            return [char(t,x+j*5,y+i*step) for i in range(count) for j,t in enumerate(str(start+i))]
        known=[]
        labels=digits(100,20)
        content=body()+digits(100,20,x=200)
        removed=boxer.proof_margin_numbers(content+labels,[0,0,700,800],known)
        self.assertEqual({id(c) for group,_ in removed for c in group},{id(c) for c in labels})
        sparse=digits(120,4,y=600)
        self.assertEqual(sum(len(g) for g,_ in boxer.proof_margin_numbers(body()+sparse,[0,0,700,800],known)),len(sparse))
        self.assertFalse(boxer.proof_margin_numbers(body()+sparse,[0,0,700,800],[]))
        self.assertFalse(boxer.proof_margin_numbers(body()+digits(80,4,y=600),[0,0,700,800],known))

    def test_table_proof_labels_are_not_table_values(self):
        labels=[char(t,660+j*4,200+i*20,8) for i in range(12)
                for j,t in enumerate(f't2:{i+1}')]
        removed=boxer.proof_margin_numbers(body()+labels,[0,0,700,800],[])
        self.assertEqual({id(c) for row,_ in removed for c in row},{id(c) for c in labels})
        interior=[dict(c,x0=c['x0']-250,x1=c['x1']-250,origin=(c['origin'][0]-250,c['origin'][1])) for c in labels]
        self.assertFalse(boxer.proof_margin_numbers(body()+interior,[0,0,700,800],[]))

    def test_symbol_note_does_not_hide_later_proof_authors(self):
        proof=page('⁎ Corresponding author: laboratory')
        proof['elements'].append(dict(kind='text',text='UNCORRECTEDPROOF',furniture_reason='large diagonal watermark crossing the page body'))
        authors=dict(authors=[dict(name='Alice Example'),dict(name='⁎'),dict(name='Bob Example')])
        copy.prepare_proof([proof],authors)
        self.assertEqual([a['name'] for a in authors['authors']],['Alice Example','Bob Example'])
        self.assertEqual(authors['authors'][0]['notes'],['⁎'])
        self.assertEqual(copy.document_kind([proof])[0], 'uncorrected proof (line numbers and watermark removed; check against the published version)')

if __name__=='__main__': unittest.main()
