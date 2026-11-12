#!/usr/bin/env python3
"""Lane f5stream (F5-GENERAL-FIX R1-R4): floats, captions, notes, side blocks and front-matter rows
stand only at a witnessed boundary, decided by one shared witness.

R4 one witness: element_boxer_sc.py::boundary_witness is the function rule 9, the copier and the
   second pass use (the copier and the second pass compile it from the boxer's own source).
R1 joins: rejoin_paragraphs joins two body pieces only on a text witness (lowercase or hyphen
   start, closed bracket) or a layout witness (next line, column turn); unterminated + capital
   without either is undecided and joins nothing.
R2 stream: lift_inserted_blocks lifts a set-apart block between an open end and a lowercase
   resume; front_return_rows / front_resume_entry return article-information rows that belong
   to a body sentence.
R3 slots: witness_slots joins halves separated only by objects and moves the objects after the
   completed paragraph.
R4 checks: copy_trace.check_sentence_slots lists what is left; r03 lists the merged-inside form.
All texts are invented; no literal from any paper.
"""
import importlib.util
import os
import sys
import unittest
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = Path(HERE).parent
sys.path.insert(0, str(ROOT))
import copy_paper as copy

sys.path.insert(0, str(ROOT/'tools'/'secondpass'))
import common as sp_common
import r03_foreign
spec = importlib.util.spec_from_file_location('f5_trace', ROOT/'tools/copy_trace.py')
trace = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trace)
spec = importlib.util.spec_from_file_location('f5_boxer', ROOT/'standalone/element_boxer_sc.py')
boxer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boxer)
sys.meta_path[:] = [f for f in sys.meta_path if type(f).__name__ != 'SCImportGuard']   # the boxer's guard is for the boxer


def J(): return copy.Joiner([])


def para(text, page=1, col=0, top=100, bottom=200, full=True, flush=True, size=20.0, face='ABCDEF+Serif-Roman', **kw):
    left = 100 + col*500
    return dict(kind='para', text=text, page=page, box=[left, top, left+450, bottom], flow_parts=[(page, [left, top, left+450, bottom])],
                flow_start=(page, col, flush), flow_end=(page, col, full), style=(size, face), **kw)


class SharedWitness(unittest.TestCase):
    def test_verdicts(self):
        w = boxer.boundary_witness
        self.assertEqual(w('the samples were', 'stored at room temperature')['verdict'], 'continuation')
        self.assertEqual(w('the samples were', 'Figure 2 shows')['verdict'], 'undecided')
        self.assertEqual(w('the samples were', 'Figure 2 shows', layout=dict(column_turn=True))['verdict'], 'layout')
        self.assertEqual(w('were stored.', 'Then they')['verdict'], 'sentence')
        self.assertEqual(w('were stored (Fig.', '4) at night')['verdict'], 'continuation')
        self.assertEqual(w('a well-con-', 'trolled trial')['reason'], 'attached hyphen + lowercase')
        self.assertTrue(w('were stored.12', 'Then')['verdict'] == 'sentence')
        self.assertEqual(w('follow-up lasted', '5.6 years on average.')['verdict'], 'continuation')
        self.assertEqual(w('the following groups', '2. Methods were')['verdict'], 'undecided')
        self.assertFalse(boxer.body_order_grammar('follow-up lasted', '5.6 years')['confirms_continuation'])

    def test_open_end_and_resume(self):
        self.assertTrue(boxer.boundary_open_end('the results of the'))
        self.assertTrue(boxer.boundary_open_end('as measured by the PCR'))
        self.assertTrue(boxer.boundary_open_end('control–'))
        self.assertFalse(boxer.boundary_open_end('mail: someone@example.org'))
        self.assertFalse(boxer.boundary_open_end('as shown [12]'))
        self.assertFalse(boxer.boundary_open_end('in 2019'))
        self.assertTrue(boxer.boundary_resumes('patients who were'))
        self.assertFalse(boxer.boundary_resumes('mRNA levels rose'))
        self.assertFalse(boxer.boundary_resumes('p53 expression'))

    def test_one_function_everywhere(self):
        """The copier and the second pass run the boxer's own source of the witness."""
        pairs = [('the samples were', 'stored'), ('the samples were', 'Stored'), ('stored.', 'Then'), ('(Fig.', '4) now')]
        for a, b in pairs:
            self.assertEqual(copy.boundary_functions()['boundary_witness'](a, b)['verdict'], boxer.boundary_witness(a, b)['verdict'])
            self.assertEqual(sp_common.boundary_witness(a, b)['verdict'], boxer.boundary_witness(a, b)['verdict'])

    def test_rule9_grammar_keeps_its_reasons(self):
        g = boxer.body_order_grammar('the samples were', 'stored here')
        self.assertTrue(g['confirms_continuation']); self.assertEqual(g['reason'], 'no terminal punctuation + lowercase')
        g = boxer.body_order_grammar('the samples were', 'Stored here')
        self.assertFalse(g['confirms_continuation']); self.assertEqual(g['reason'], 'none')
        g = boxer.body_order_grammar('a hyphen-', 'Capital')
        self.assertEqual(g['reason'], 'none (literal or nonqualifying hyphen)')


class WitnessedJoins(unittest.TestCase):
    def test_unterminated_before_capital_after_a_gap_is_not_joined(self):
        items = [para('An abbreviation line listing what the index changes with treatment', top=100, bottom=130, full=False),
                 para('Obstructive breathing during sleep is a common condition in adults.', top=235, bottom=400)]
        out = copy.rejoin_paragraphs(items, J(), 20)
        self.assertEqual(len([x for x in out if x['kind'] == 'para']), 2)

    def test_column_turn_and_lowercase_still_join(self):
        items = [para('measured in the serum of all patients and in the', col=0, top=1300, bottom=1500),
                 para('Group B samples, which were stored apart.', col=1, top=100, bottom=300)]
        self.assertEqual(len(copy.rejoin_paragraphs(items, J(), 20)), 1)
        items = [para('measured in the serum of all patients and in the', col=0, top=1300, bottom=1500, full=False),
                 para('samples, which were stored apart.', col=1, top=100, bottom=300, flush=False)]
        self.assertEqual(len(copy.rejoin_paragraphs(items, J(), 20)), 1)

    def test_column_foot_to_next_column_head_joins_a_capital_start(self):
        items = [para('treatment was tested on antigen-activated', col=0, top=1300, bottom=1540, full=False),
                 para('Th1 clone cells, which were then counted.', col=1, top=150, bottom=400, flush=False),
                 para('Further text lower in the second column.', col=1, top=420, bottom=900)]
        out = copy.rejoin_paragraphs(items, J(), 20)
        self.assertEqual(out[0]['text'], 'treatment was tested on antigen-activated Th1 clone cells, which were then counted.')
        # A band change (the body's columns below a panel) is no column turn.
        items = [para('An abbreviation list that ends with treatment', col=1, top=1048, bottom=1108, full=False),
                 para('Obstructive breathing in sleep is common.', col=0, top=1213, bottom=1486)]
        self.assertEqual(len(copy.rejoin_paragraphs(items, J(), 20)), 2)

    def test_page_turn_to_a_block_without_column(self):
        items = [para('The authors wish to thank Drs. A. Bee and', col=1, top=1372, bottom=1442, page=8),
                 dict(kind='heading', text='REFERENCES', page=9),
                 dict(para('Cee Dee for their helpful assistance.', page=9, top=45, bottom=85), flow_start=None, flow_end=None)]
        out = copy.rejoin_paragraphs(items, J(), 20)
        self.assertEqual(out[0]['text'], 'The authors wish to thank Drs. A. Bee and')   # a heading between: no join
        items = [items[0], items[2]]
        self.assertEqual(copy.rejoin_paragraphs(items, J(), 20)[0]['text'],
                         'The authors wish to thank Drs. A. Bee and Cee Dee for their helpful assistance.')

    def test_heading_line_is_not_glued_to_its_paragraph(self):
        items = [para('Hormonal factors', top=100, bottom=125, full=False),
                 para('It is well known that most patients attending these clinics are adults.', top=150, bottom=400)]
        out = copy.rejoin_paragraphs(items, J(), 20)
        self.assertEqual(out[0]['text'], 'Hormonal factors')


class Sandwich(unittest.TestCase):
    def pages(self): return [dict(page=1, elements=[], unpaired=[])]

    def test_caption_in_another_face_between_halves_moves_after_the_paragraph(self):
        items = [para('Most of the enrolled participants in this sample were predominantly', col=0, top=900, bottom=1500),
                 para('Figure 4—Flow of participants through the trial.', col=1, top=80, bottom=105, flush=False,
                      face='GHIJKL+Sans-Narrow', size=22.0),
                 para('older men, who were followed for a year. The follow-up was complete.', col=1, top=150, bottom=400)]
        out = copy.lift_inserted_blocks(items, self.pages(), 20.0, J())
        self.assertEqual([x['kind'] for x in out], ['para', 'para', 'figure'])
        joined = copy.rejoin_paragraphs(out, J(), 20.0)
        self.assertTrue(joined[0]['text'].endswith('predominantly older men, who were followed for a year. The follow-up was complete.'))
        self.assertEqual(joined[1]['kind'], 'figure')

    def test_heading_between_halves_moves_after(self):
        small = dict(size=18.0, face='ABCDEF+Serif-Bold', barrier=True)
        items = [para('SUMMARY Of these reviews, two were based on case–', col=0, top=900, bottom=1500, **small),
                 dict(kind='heading', text='Background', page=1),
                 para('Earlier surveys were rare and covered few subjects in all.', col=0, top=1550, bottom=1600, full=False),
                 para('control studies, and the rest were mixed designs.', col=1, top=80, bottom=300, full=False, **small)]
        out = copy.lift_inserted_blocks(items, self.pages(), 20.0, J())
        self.assertEqual(out[0]['text'], 'SUMMARY Of these reviews, two were based on case–control studies, and the rest were mixed designs.')
        self.assertEqual([x.get('text', '')[:10] for x in out[1:]], ['Background', 'Earlier su'])

    def test_short_heading_line_is_never_the_open_half(self):
        items = [para('Changes in pain regulating pathways', col=0, top=100, bottom=125, full=False),
                 para('It has been proposed that the excitability of central neurons in the joint and', col=0, top=150, bottom=1500),
                 para('tissues remote from the source rises as well.', col=1, top=80, bottom=300)]
        out = copy.lift_inserted_blocks(items, self.pages(), 20.0, J())
        self.assertEqual([x['text'][:10] for x in out], [x['text'][:10] for x in items])

    def test_resume_that_continues_the_block_itself_is_not_a_sandwich(self):
        items = [para('Most of the enrolled participants in this sample were predominantly', col=0, top=900, bottom=1500),
                 para('Another body paragraph in the same face that stops in the', col=1, top=80, bottom=300, flush=False),
                 para('middle and resumes here.', col=1, top=310, bottom=400, flush=False)]
        out = copy.lift_inserted_blocks(items, self.pages(), 20.0, J())
        self.assertEqual([x['text'][:12] for x in out], [x['text'][:12] for x in items])

    def test_small_type_panel_halves_join_around_body_text(self):
        small = dict(size=18.0, face='ABCDEF+Serif-Bold', barrier=True)
        items = [para('SUMMARY The disorder is reviewed and its sex-related differ-', col=0, top=500, bottom=1050, **small),
                 dict(kind='heading', text='Introduction', page=1),
                 para('The purpose of this review is to discuss new research', col=0, top=1200, bottom=1450),
                 para('ences in prevalence are discussed in turn.', col=1, top=500, bottom=890, full=False, **small),
                 para('KEYWORDS: pain, joint, muscle', col=1, top=900, bottom=970, full=False, **small)]
        out = copy.lift_inserted_blocks(items, self.pages(), 20.0, J())
        self.assertEqual(out[0]['text'], 'SUMMARY The disorder is reviewed and its sex-related differences in prevalence are discussed in turn.')
        self.assertEqual([x.get('text', '')[:8] for x in out[1:]], ['KEYWORDS', 'Introduc', 'The purp'])


class Slots(unittest.TestCase):
    def test_object_between_halves_follows_the_completed_paragraph(self):
        items = [para('the measurements were repeated in all of the', col=0, top=900, bottom=1500, list=False),
                 dict(kind='table', caption='Table 1. Values', page=1, top=100),
                 dict(kind='side', text='* A table note.', page=1),
                 para('remaining samples one week later.', page=2, col=0, top=80, bottom=200, starts_paragraph=False)]
        items[3]['barrier'] = False
        out = copy.witness_slots(items, J(), [dict(page=1), dict(page=2)], [], None)
        self.assertEqual(out[0]['text'], 'the measurements were repeated in all of the remaining samples one week later.')
        self.assertEqual([x['kind'] for x in out[1:]], ['table', 'side'])

    def test_list_or_abstract_boundary_is_left_for_the_check(self):
        items = [para('the measurements were repeated in all of the', abstract=True),
                 dict(kind='figure', caption='Figure 1. A view', page=1, top=100),
                 para('remaining samples one week later.')]
        out = copy.witness_slots(items, J(), [dict(page=1)], [], None)
        self.assertEqual([x['kind'] for x in out], ['para', 'figure', 'para'])


class FrontRows(unittest.TestCase):
    def setUp(self):
        copy.trace_reset()
        self.page = dict(page=1, elements=[
            dict(id='h', kind='text', text='Background', box_px=[100, 100, 300, 130], size_px=27, run_size_px=27),
            dict(id='a', kind='text', text='Complete repair of the tissues remains a distant goal today.', box_px=[100, 140, 600, 160], size_px=20.8, run_size_px=20.8),
            dict(id='b', kind='text', text='A number of new', box_px=[100, 165, 300, 185], size_px=20.8, run_size_px=20.8),
            dict(id='c', kind='text', text='develop higher rates of distress, and of abuse.', box_px=[100, 900, 600, 920], size_px=20.8, run_size_px=20.8)])

    def rows(self, ids):
        es = {e['id']: e for e in self.page['elements']}
        return [copy.trace_row(1, [es[i]], es[i]['text']) for i in ids]

    def test_body_rows_return_with_their_heading(self):
        txt = self.rows('hab'); flat = J().lines(txt)
        back = copy.front_return_rows(txt, flat, 'methods are being studied that improve', self.page, 20.8, J())
        self.assertEqual(str(back['heading']), 'Background')
        self.assertEqual(str(back['text']), 'Complete repair of the tissues remains a distant goal today. A number of new')
        self.assertIsNone(back['rest'])
        self.assertIsNone(copy.front_return_rows(txt, flat, 'Methods are being studied', self.page, 20.8, J()))

    def test_lowercase_led_entry_is_held_for_the_body(self):
        txt = self.rows('c'); flat = J().lines(txt)
        held = copy.front_resume_entry(txt, flat, self.page, 20.8, J())
        self.assertEqual(str(held['text']), 'develop higher rates of distress, and of abuse.')
        items = [para('Compared with other groups, patients with both disorders', top=700, bottom=880, col=0)]
        items[0]['box'] = [100, 700, 600, 880]
        self.assertEqual(copy.place_front_resume(items, held, 1, 20.8), 0)


class InsetsNotesScans(unittest.TestCase):
    def run_(self, rid, text, x, y, w, size=20.8, face='ABCDEF+Serif-Roman'):
        return dict(id=rid, kind='text', text=text, angle=0, box_px=[x, y, x+w, y+size*.9], size_px=size, run_size_px=size,
                    _faces={face: len(text)})

    def test_inset_box_beside_wrapped_body_rows_leaves_the_block(self):
        runs = {}
        for i in range(10):   # body rows wrapped to the right of a box for rows 2-7
            x = 350 if 2 <= i <= 7 else 120
            runs[f'b{i}'] = self.run_(f'b{i}', 'body text of the paragraph runs on here', x, 100+25*i, 540-x)
        for i in range(5):
            runs[f'i{i}'] = self.run_(f'i{i}', 'a boxed notice line', 120, 152+20*i, 180, size=14.6, face='GHIJKL+Sans-Regular')
        runs['sup'] = self.run_('sup', '12', 541, 100, 8, size=12)
        self.assertEqual(copy.inset_box_runs(list(runs), runs, 20.8), {f'i{i}' for i in range(5)})
        # The same small runs set apart below the text (no body row beside them) are not an inset.
        for i in range(5): runs[f'i{i}']['box_px'][1] += 400; runs[f'i{i}']['box_px'][3] += 400
        self.assertEqual(copy.inset_box_runs(list(runs), runs, 20.8), set())

    def test_lowercase_piece_under_an_unterminated_note_joins_it(self):
        copy.trace_reset()
        page = dict(page=2, elements=[self.run_('n1', '§ A cocktail of drugs: one (2 mg), a supplier; and', 700, 1400, 480, size=14.6)])
        note = dict(kind='side', text=copy.trace_row(2, [page['elements'][0]], page['elements'][0]['text']), page=2)
        piece = dict(kind='para', text='another drug (5 mg), its supplier, a city.', page=2, box=[700, 1417, 1180, 1430],
                     style=(14.6, 'ABCDEF+Serif-Roman'))
        out = copy.join_note_pieces([note, dict(kind='page', page=2), piece], [page], J())
        self.assertEqual([x['kind'] for x in out], ['side', 'page'])
        self.assertTrue(str(out[0]['text']).endswith('; and another drug (5 mg), its supplier, a city.'))

    def test_scan_block_in_another_column_between_halves_is_lifted(self):
        def line(text, x, y, page, w=480):
            return dict(kind='line', page=page, runs=[dict(text=text, box_px=[x, y, x+w, y+27], size_px=20)], box_px=[x, y, x+w, y+27])
        stream = [line('osteocyte processes ended near the surface. A layer of', 660, 1500, 5),
                  line('DRAWING LETTERING IN CAPITALS', 220, 120, 6, w=270),
                  dict(kind='figure', page=6, runs=[dict(text='Fig. 8. A drawing.', box_px=[137, 536, 619, 560], size_px=20)], box_px=[137, 536, 619, 560]),
                  line('amorphous material separated the cells from it', 660, 120, 6),
                  line('and from the marrow.', 660, 148, 6)]
        out = copy.scan_inserted_blocks(stream)
        self.assertEqual(out[1]['kind'], 'side')
        self.assertTrue(out[1].get('inserted'))


class CopyCheck(unittest.TestCase):
    def unit(self, uid, kind, text, page=1):
        return dict(id=uid, kind=kind, text=text, status='traced', sources=[dict(page=page)])

    def test_between_and_torn(self):
        w = copy.TraceWitness()
        units = [self.unit('u1', 'paragraph', 'the measurements were repeated on all of the stored'),
                 self.unit('u2', 'caption', 'Figure 2. A view.'),
                 self.unit('u3', 'paragraph', 'samples a week later in the same laboratory.')]
        f = trace.check_sentence_slots(units, w)['findings']
        self.assertEqual([(x['kind'], x['kinds']) for x in f], [('between', ['caption'])])
        units = [self.unit('u1', 'article_information', 'A number of new methods are being'),
                 self.unit('u2', 'heading', 'Introduction'),
                 self.unit('u3', 'paragraph', 'studied that improve the outcome of repair.')]
        self.assertEqual(trace.check_sentence_slots(units, w)['findings'][0]['kind'], 'torn')
        units[2]['text'] = 'Studied methods improve the outcome of repair.'
        self.assertEqual(trace.check_sentence_slots(units, w)['findings'], [])


class R03Merged(unittest.TestCase):
    class Paper:
        def __init__(self, units, lines, sizes):
            self.content_units = units; self._lines = lines; self._sizes = sizes
        def unit_lines(self, u): return self._lines[u['id']]
        @staticmethod
        def line_box(l): return l['box']
        def line_size(self, l): return self._sizes[l['export_id']]
        def body_size(self, n): return 20

    def line(self, i, text, box, page=1):
        return dict(export_id=f'p{page}.l{i:03}', text=text, box=box, page=page)

    def test_caption_merged_inside_a_sentence(self):
        ls = [self.line(1, 'The trial enrolled a sample of patients who', [100, 100, 550, 120]),
              self.line(2, 'were followed and who were predominantly', [100, 130, 550, 150]),
              self.line(3, 'Figure 1—Flow chart of the trial', [600, 80, 1000, 100]),
              self.line(4, 'older men in their fifties at the time.', [600, 400, 1050, 420]),
              self.line(5, 'They were all seen again a year later.', [600, 430, 1050, 450])]
        sizes = {l['export_id']: 20 for l in ls}; sizes['p1.l003'] = 23
        u = dict(id='u1', kind='paragraph', span=[0, 10], text=' '.join(l['text'] for l in ls))
        found = r03_foreign.merged(self.Paper([u], {'u1': ls}, sizes))
        self.assertEqual([(b['export_id'], why) for u_, b, r, why in found], [('p1.l003', 'a float label')])

    def test_capital_continuation_at_a_column_turn_is_not_listed(self):
        ls = [self.line(1, 'The trial measured the levels of serum lipids and', [100, 100, 550, 120]),
              self.line(2, 'found that the means were raised in serum', [100, 130, 550, 150]),
              self.line(3, 'LDL levels as well as in the other groups.', [600, 80, 1050, 100]),
              self.line(4, 'the values fell after one year.', [600, 400, 1050, 420])]
        sizes = {l['export_id']: 20 for l in ls}
        u = dict(id='u1', kind='paragraph', span=[0, 10], text=' '.join(l['text'] for l in ls))
        self.assertEqual(r03_foreign.merged(self.Paper([u], {'u1': ls}, sizes)), [])


if __name__ == '__main__':
    unittest.main()
