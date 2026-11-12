"""A drawn end box retains its citation even in a running-footer band."""
import unittest
import test_pagetops as fixtures
page, run = fixtures.page, fixtures.run


class CitationBox(unittest.TestCase):
    classify=fixtures.PageTops.classify

    def test_drawn_end_box_survives_footer_matching_and_repeated_pass(self):
        pages=[]
        for i,word in enumerate(['Red','Green','Blue'],1):
            body=[run(f'body{j}',f'{word} paragraph supplies ordinary words.',40,200+15*j) for j in range(6)]
            footer=run('foot','2001;12:34-56. doi:10.1234/example',40,950,width=220)
            groups=[('body',body),('footer',[footer])]
            if i==3:
                groups=[('body',body),('box',[run('label','How to cite this article: Author AB.',40,900),
                         run('title','A title and its journal.',40,915),footer]),
                        ('folio',[run('folio','999',285,950,width=20)])]
            p=page(i,groups)
            if i==3:
                drawing=dict(id='border',kind='fill',box_px=[35,890,265,970])
                p['elements'].append(drawing);p['blocks'][1]['members'].append('border')
                p['blocks'][1]['kinds'].append('fill')
            pages.append(p)
        result=self.classify(pages)
        for p in result[:2]:
            self.assertIn('foot',{m for f in p['main_text']['furniture'] for m in f['members']})
        furniture={m for f in result[-1]['main_text']['furniture'] for m in f['members']}
        self.assertFalse(furniture & {'label','title','foot'})
        self.assertIn('folio',furniture)


if __name__=='__main__':unittest.main()
