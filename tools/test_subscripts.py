"""Detached lowered digits must remain inside their printed formulas."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('copy_subscripts', Path(__file__).resolve().parents[1]/'copy_paper.py')
copy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(copy)


def runs(text, lowered, detached):
    chars = []
    for i, ch in enumerate(text):
        small = i in lowered
        chars.append(dict(text=ch, size=6 if small else 10,
            origin=(i*5, 104 if small else 100), x0=i*5, x1=i*5+4,
            adv_x1=i*5+5, y0=100 if small else 93, y1=104 if small else 100, font='Body'))
    marks=[]
    for i in sorted(detached):
        if marks and marks[-1][-1]+1==i: marks[-1].append(i)
        else: marks.append([i])
    groups = [[i for i in range(len(text)) if i not in detached]]+marks
    result = []
    for n, indices in enumerate(groups):
        cs = [chars[i] for i in indices if not text[i].isspace()]
        if not cs: continue
        saved = ' '.join(''.join(text[i] if i in indices else ' ' for i in range(len(text))).split())
        result.append(dict(id=str(n), text=saved, kind='text', angle=0,
            box_px=copy.hull([c['x0'],c['y0'],c['x1'],c['y1']] for c in cs),
            _chars=cs, char_ids=[i for i in indices if not text[i].isspace()]))
    return result


class Subscripts(unittest.TestCase):
    def render(self, source):
        page = dict(_citation_numbers=set(range(1,100)), _raised_marks=[])
        rows = copy.text_rows(source)
        return ' / '.join(copy.prose_row(row,page)[0] for row in rows), page

    def test_internal_terminal_and_multidigit_subscripts(self):
        for text, small, detached in [
                ('gas (H2O2) is formed', {6,8}, {8}),
                ('gas CO2 is formed', {6}, {6}),
                ('1,25(OH)2D3 acts', {8,10}, {8}),
                ('C12H22O11 is present', {1,2,4,5,7,8}, {7,8})]:
            source=runs(text,small,detached)
            original=[dict(e) for e in source]
            result,page=self.render(source)
            self.assertEqual(result,text)
            self.assertEqual(source,original)
            self.assertEqual(set(page['copy_line_order'][0]['runs']),{'0','1'})

    def test_formula_at_end_of_line_keeps_its_digit(self):
        result,_=self.render(runs('dissolved CO2',{12},{12}))
        self.assertEqual(result,'dissolved CO2')

    def test_two_detached_digits_and_following_line(self):
        source=runs('gas (H2O2) is formed',{6,8},{6,8})
        following=runs('and measured',set(),set())[0]
        following['id']='next'
        following['box_px']=[v+(16 if i%2 else 0) for i,v in enumerate(following['box_px'])]
        for c in following['_chars']:
            c['origin']=(c['origin'][0],c['origin'][1]+16)
            c['y0']+=16;c['y1']+=16
        result,page=self.render(source+[following])
        self.assertEqual(result,'gas (H2O2) is formed / and measured')
        self.assertEqual(set(page['copy_line_order'][0]['runs']),{'0','1','2'})

    def test_baseline_digit_after_subscript_cannot_become_one_number(self):
        result,_=self.render(runs('x23 is measured',{1},{1}))
        self.assertEqual(result,'x_2 3 is measured')

    def test_no_move_without_exact_unambiguous_native_evidence(self):
        for mode in ('missing','mismatch','raised','ordinary','wide_gap','short_ink','ambiguous','unverified','superscript'):
            source=runs('gas CO2 ends',{6},{6})
            mark=source[1]['_chars'][0]
            if mode=='missing':source[1].pop('_chars')
            elif mode=='mismatch':source[1]['text']='3'
            elif mode=='raised':mark['origin']=(30,96)
            elif mode=='ordinary':mark.update(size=10,origin=(30,100))
            elif mode=='wide_gap':mark['origin']=(33,104)
            elif mode=='short_ink':mark['y1']=100.5
            elif mode=='ambiguous':source.append(dict(source[0],id='other'))
            elif mode=='unverified':mark['_mark_unverified']=True
            elif mode=='superscript':source[1]['_superscript']=True
            self.assertEqual(copy.lowered_digit_runs(source),source,mode)

    def test_flat_units_and_existing_inline_subscripts_are_unchanged(self):
        for text,small in [('kg/m2', {4}),('mm3',{2}),('H2O2',{1,3})]:
            source=runs(text,small,set())
            self.assertEqual(self.render(source)[0],text)
        for text,raised in [('kg/m2',{4}),('mm3',{2})]:
            source=runs(text,raised,set())
            for i in raised:source[0]['_chars'][i]['origin']=(i*5,96)
            self.assertEqual(self.render(source)[0],text)


if __name__=='__main__': unittest.main()
