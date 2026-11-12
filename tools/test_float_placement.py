"""Paragraph/list boundaries and caption ownership, independent of any paper.

Run: /usr/bin/python3 -I tools/test_float_placement.py
"""
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


copy = module('copy_paper', ROOT / 'copy_paper.py')
boxer = module('boxer', ROOT / 'standalone/element_boxer_sc.py')


def paragraph(text, page=1, listed=False):
    return dict(kind='para', text=text, page=page, list=listed, box=[0, 200, 100, 250])


def table(page=1, continued=False):
    return dict(kind='table', id=f'table:{page}', page=page, top=10,
                caption='Table 1. ' + ('Continued.' if continued else 'Findings'),
                rows=[[['A'], ['B']]], notes=[])


def pages(*numbers):
    return [dict(page=n, elements=[], tables=[], region_box_px=[0, 0, 300, 500]) for n in numbers]


class Placement(unittest.TestCase):
    def test_citation_in_list_introduction_waits_for_all_items(self):
        intro = paragraph('Table 1 describes the following requirements:')
        one = paragraph('1. First requirement.', listed=True)
        two = paragraph('2. Second requirement.', page=2, listed=True)
        end = paragraph('The next paragraph.', page=2)
        floating = table()
        records = pages(1, 2)
        self.assertEqual(copy.arrange_floats([intro, one, floating, two, end], records, []),
                         [intro, one, two, floating, end])
        self.assertEqual(records[0]['copy_flow_moves'][0]['to'], 3)

    def test_continued_table_and_preceding_table_only_page_keep_order(self):
        intro = paragraph('What findings are needed?')
        one = paragraph('1. First finding.', listed=True)
        extra = paragraph('An additional symptom;')
        two = paragraph('2. Second finding;', page=3, listed=True)
        end = paragraph('The next paragraph.', page=3)
        first, continuation = table(2), table(3, True)
        result = copy.arrange_floats([intro, one, extra, first, two, end, continuation], pages(1, 2, 3), [])
        self.assertEqual(result, [first, continuation, intro, one, extra, two, end])

    def test_top_continuation_precedes_the_first_paragraphs_heading(self):
        heading=dict(kind='heading',page=1,text='Discussion')
        first=paragraph('The opening paragraph.')
        floating=table(1,True)
        self.assertEqual(copy.arrange_floats([heading,first,floating],pages(1),[]),[floating,heading,first])

    def test_additional_columns_follow_earlier_parts_before_the_resumed_list(self):
        intro=paragraph('The following steps:',page=2)
        one=paragraph('1. An earlier step.',page=2,listed=True)
        two=paragraph('2. The step completed on the following page.',page=2,listed=True)
        two['pages']={2,3}
        after=paragraph('The ordinary paragraph following the list.',page=3)
        first=table(1)
        middle=table(2,True)
        extra=dict(table(3),caption='Table 1 (additional columns, page 3)')
        result=copy.arrange_floats([first,middle,intro,one,two,extra,after],pages(1,2,3),[])
        self.assertEqual(result,[first,middle,extra,intro,one,two,after])

    def test_same_page_continued_column_never_overtakes_its_first_part(self):
        prose=paragraph('The next paragraph.')
        first=dict(table(),left=0,top=10.1)
        continued=dict(table(1,True),left=150,top=10)
        result=copy.arrange_floats([prose,continued,first],pages(1),[])
        self.assertEqual(result,[prose,first,continued])

    def test_continuation_does_not_jump_before_cross_page_paragraph(self):
        resumed = paragraph('A completed paragraph spanning the page break.')
        resumed['pages'] = {1, 2}
        following = paragraph('A new paragraph.', page=2)
        floating = table(2, True)
        self.assertEqual(copy.arrange_floats([resumed, floating, following], pages(1, 2), []),
                         [resumed, floating, following])

    def test_ordinary_citation_keeps_its_anchor(self):
        first = paragraph('Earlier text.')
        citing = paragraph('Table 1 gives the findings.')
        floating = table()
        records = pages(1)
        self.assertEqual(copy.arrange_floats([first, citing, floating], records, []), [first, citing, floating])
        self.assertNotIn('copy_flow_moves', records[0])

    def test_detected_float_follows_the_interrupted_sentence_before_a_later_citation(self):
        first=paragraph('The experiment established an effect in the')
        first['box']=[0,300,100,400]
        resumed=paragraph('next phase of the experiment.')
        resumed['box']=[120,150,220,200]
        citing=paragraph('Table 1 is discussed in a later paragraph.')
        floating=dict(table(),box=[120,10,220,100])
        joined=copy.rejoin_paragraphs([first,resumed,citing,floating],copy.Joiner([]))
        self.assertEqual(len(joined),3)
        self.assertEqual(copy.arrange_floats(joined,pages(1),[]),[first,floating,citing])

    def test_an_earlier_safe_citation_is_not_deferred_into_later_material(self):
        citing=paragraph('Table 1 is introduced here.')
        resumed=paragraph('A later paragraph has finished.')
        resumed['float_gaps']=[(1,[0,300,100,400],1,[120,150,220,200])]
        floating=dict(table(),box=[120,10,220,100])
        self.assertEqual(copy.arrange_floats([citing,resumed,floating],pages(1),[]),[citing,floating,resumed])

    def test_cross_page_geometry_alone_does_not_override_a_citation(self):
        resumed=paragraph('A paragraph continued on the next page.')
        resumed['pages']={1,2}
        resumed['float_gaps']=[(1,[0,300,100,400],2,[120,150,220,200])]
        citing=paragraph('Table 1 is introduced here.',page=2)
        floating=dict(table(2),box=[120,10,220,100])
        self.assertEqual(copy.arrange_floats([resumed,citing,floating],pages(1,2),[]),[resumed,citing,floating])

    def test_captioned_unit_uses_rule_seven_boundary(self):
        first = paragraph('An interrupted sentence has now finished.')
        first['source_blocks'] = [(1, 'finish')]
        citing = paragraph('Table 1 is cited in this later paragraph.')
        floating = dict(table(), after_block='finish', text_lines=['1. A', '2. B'])
        result = copy.arrange_floats([first, citing, floating], pages(1), [])
        self.assertEqual(result, [first, floating, citing])

    def test_captioned_list_requires_multiple_entries_and_respects_existing_ownership(self):
        cap = dict(id='caption', cls='caption', size=10, box_px=[0, 0, 100, 10],
                   members=['c'], text='TABLE 8 A classification')
        contents = dict(id='contents', cls='main', size=10, box_px=[0, 20, 100, 80],
                        members=['a', 'b', 'd'], text='1 First\n2 Second\n3 Third')
        larger = dict(id='body', cls='main', size=12, box_px=[0, 90, 100, 130],
                      members=['e'], text='Following prose must remain outside.')
        detect = lambda blocks, **kw: boxer.reading_order_captioned_lists(
            blocks, [[0, 100]], 10, lambda b: b['text'], **kw)
        group = detect([cap, contents, larger])[0]
        self.assertEqual(group['blocks'], ['contents'])
        self.assertEqual(group['caption_blocks'], ['caption'])
        self.assertEqual(set(group['members']), {'c', 'a', 'b', 'd'})
        self.assertFalse(detect([cap, dict(contents, text='Ordinary prose mentions a list.')]))
        self.assertFalse(detect([cap, contents], floats=[dict(blocks=['caption', 'contents'])]))

    def test_rule_seven_defers_an_atomic_group_past_a_whole_list(self):
        def block(name, text, top):
            row=[dict(id=name+':run',text=text,box_px=[0,top,100,top+10])]
            return dict(id=name,text=text,members=[row[0]['id']],box_px=row[0]['box_px'],rows=[row],size=10)
        intro=block('intro','The requirements are:',0)
        floating=block('float','A captioned unit',20)
        one=block('one','1. First requirement;',40)
        two=block('two','2. Second requirement;',60)
        following=block('following','A new heading',80)
        group=dict(id='unit',blocks=['float'],kind='table')
        before=[intro,floating,one,two,following]
        result,splits=boxer.reading_order_defer_panels(before,[group],10,lambda b:b['text'],lambda b:b['rows'])
        self.assertEqual([b['id'] for b in result],['intro','one','two','float','following'])
        self.assertFalse(splits)
        self.assertEqual(group['move']['from_order'],2)
        self.assertEqual(group['move']['to_order'],4)
        self.assertEqual({m for b in result for m in b['members']},{m for b in before for m in b['members']})

    def test_capitalized_column_continuation_is_not_a_short_heading(self):
        def block(name, lines):
            rows = [[dict(id=f'{name}:{i}', text=t, box_px=[x, 30*i, right, 30*i+10])]
                    for i, (t, x, right) in enumerate(lines)]
            return dict(id=name, text='\n'.join(r[0]['text'] for r in rows), rows=rows,
                        members=[r[0]['id'] for r in rows], size=10,
                        box_px=[0, 0, 100, rows[-1][0]['box_px'][3]])
        before = block('before', [('The report follows the agreed international reporting standards for', 0, 100)])
        panel = block('panel', [('A boxed summary.', 0, 100)])
        after = block('after', [('Comparative Intervention Research', 0, 100),
                                ('and its registered protocol.', 0, 80),
                                ('The next paragraph begins here.', 10, 100)])
        group = dict(id='panel', blocks=['panel'])
        result, splits = boxer.reading_order_defer_panels(
            [before, panel, after], [group], 10, lambda b:b['text'], lambda b:b['rows'])
        self.assertEqual([b['id'] for b in result],
                         ['before', 'after:paragraph:1', 'panel', 'after:paragraph:2'])
        self.assertEqual(len(splits), 1)
        # A short, narrow heading and an indented paragraph remain boundaries.
        for x, right in [(0, 40), (10, 100)]:
            after['rows'][0][0]['box_px'] = [x, 0, right, 10]
            result, splits = boxer.reading_order_defer_panels(
                [before, panel, after], [dict(id='panel', blocks=['panel'])], 10,
                lambda b:b['text'], lambda b:b['rows'])
            self.assertEqual([b['id'] for b in result], ['before', 'panel', 'after'])
            self.assertFalse(splits)


if __name__ == '__main__':
    unittest.main()
