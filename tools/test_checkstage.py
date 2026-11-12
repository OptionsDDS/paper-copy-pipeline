"""Tests of the check stage (tools/checkstage): prep, ops builder, duplicate finder,
character map and trace gate, and the stage run without the GPU (code checks, saved answers).

/usr/bin/python3 -I tools/test_checkstage.py
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'checkstage'))
import build_ops  # noqa: E402
import dupfind  # noqa: E402
import prep  # noqa: E402
import tracemap  # noqa: E402

RA = tracemap.RA


def apply_one(text, op):
    new, log = RA.apply_operations(text, [op])
    return new, log[0]


def tiny_pdf(path, pages=2):
    """A valid PDF with one line of Helvetica text per page (for pdfinfo/pdftoppm)."""
    objs = ['<< /Type /Catalog /Pages 2 0 R >>',
            '<< /Type /Pages /Kids [%s] /Count %d >>' % (' '.join(f'{3 + 2 * i} 0 R' for i in range(pages)), pages)]
    font = 3 + 2 * pages
    for i in range(pages):
        stream = f'BT /F1 12 Tf 30 250 Td (Page {i + 1} text) Tj ET'
        objs.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents {4 + 2 * i} 0 R '
                    f'/Resources << /Font << /F1 {font} 0 R >> >> >>')
        objs.append(f'<< /Length {len(stream)} >>\nstream\n{stream}\nendstream')
    objs.append('<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    out = b'%PDF-1.4\n'
    offs = []
    for k, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f'{k} 0 obj\n{o}\nendobj\n'.encode()
    x = len(out)
    out += f'xref\n0 {len(objs) + 1}\n0000000000 65535 f \n'.encode()
    for o in offs:
        out += f'{o:010d} 00000 n \n'.encode()
    out += f'trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n'.encode()
    Path(path).write_bytes(out)


def make_trace(text, pieces):
    """A native trace: pieces = [(unit_id, group, unit_text, [(page, run, line_text)])]; spans found in text."""
    units, lines, seen = [], {}, 0
    for uid, group, ut, claims in pieces:
        a = text.index(ut, seen)
        seen = a + len(ut)
        units.append({'id': uid, 'kind': 'paragraph', 'group': group, 'group_units': [uid], 'span': [a, a + len(ut)],
                      'text': ut, 'status': 'traced', 'generated_reason': None, 'sources': [],
                      'claims': {'rows': [], 'runs': [[p, r, False] for p, r, _ in claims]}, 'unmatched': []})
        for p, r, lt in claims:
            lid = f'pdf:x:p{p}:{r}'
            line = lines.setdefault(lid, {'id': lid, 'export_id': f'p{p}.{r}', 'page': p, 'text': lt, 'runs': [r],
                                          'box_110dpi': [10.0, 20.0 + 15 * len(lines), 200.0, 32.0 + 15 * len(lines)],
                                          'units': [], 'groups': []})
            line['units'].append({'unit_id': uid, 'copy_span': [a, a + len(ut)]})
            if group not in line['groups']:
                line['groups'].append(group)
    for line in lines.values():
        line['groups'].sort()
        line['status'] = 'unit' if len(line['groups']) == 1 else 'duplicate'
    dup = [l for l in lines.values() if l['status'] == 'duplicate']
    return {'schema': 'copy-trace/2 (native)', 'pdf': {'path': None, 'sha256': None, 'pages': []},
            'copy': {'path': 'copy.md', 'sha256': hashlib.sha256(text.encode()).hexdigest(), 'characters': len(text)},
            'statistics': {}, 'accounting': {'lost_lines': [], 'duplicate_lines': dup, 'split_lines': [], 'untraced_units': []},
            'failed': bool(dup), 'units': units, 'lines': list(lines.values()), 'rows': [], 'furniture_runs': [],
            'uncertainty_runs': []}


class PrepTests(unittest.TestCase):
    def test_paragraphs_and_page_segments(self):
        text = 'Alpha one.\nAlpha two.\n\n<!-- end of page 1 -->\n\nBeta.\n\n```text\nx\n\ny\n```\n\n<!-- end of page 2 -->\n\nTail.\n'
        paras = prep.paragraphs(text)
        self.assertEqual([p[2] for p in paras], ['Alpha one.\nAlpha two.', '<!-- end of page 1 -->', 'Beta.',
                                                 '```text\nx\n\ny\n```', '<!-- end of page 2 -->', 'Tail.'])
        self.assertEqual(prep.segment_pages(paras), [1, 1, 2, 2, 2, 2])

    def test_sentence_helpers(self):
        self.assertTrue(prep.ends_open('the stent'))
        self.assertTrue(prep.ends_open('instrumen-'))
        self.assertFalse(prep.ends_open('obtained.'))
        self.assertTrue(prep.starts_lower('- root planing'))
        self.assertFalse(prep.starts_lower('Root'))

    def test_trace_regions_and_two_page_blocks(self):
        text = '# T\n\nFirst paragraph of the body text here.\n\nSecond paragraph that runs on.\n'
        tr = make_trace(text, [('u1', 'g1', 'First paragraph of the body text here.', [(1, 'run:1', 'First paragraph')]),
                               ('u2', 'g2', 'Second paragraph that runs on.', [(1, 'run:2', 'Second'), (2, 'run:1', 'runs on.')])])
        paras = prep.paragraphs(text)
        maps = prep.map_paragraphs_trace(paras, prep.segment_pages(paras), tr)
        self.assertEqual(maps[1]['source_page'], 1)
        self.assertEqual(maps[1]['on_pages'], [1])
        self.assertEqual(sorted(maps[2]['on_pages']), [1, 2])
        box = maps[1]['pages'][1]['rects_pt'][0]
        self.assertAlmostEqual(box[0], 10.0 * 72 / 110)

    def test_join_and_heading_candidates(self):
        recs = []
        for k, t in enumerate(['## Methods', 'Study design and setting', 'The study was done in a town where the',
                               'people were asked about it.', 'Results were good.']):
            recs.append({'id': k, 'text': t, 'source_page': 1})
        joins = prep.join_candidates(recs)
        self.assertEqual([(j['a'], j['b']) for j in joins], [(2, 3)])
        heads = prep.head_candidates(recs)
        self.assertEqual([h['line'] for h in heads], ['Study design and setting', 'The study was done in a town where the'])


def probs(letter):
    p = {c: 0.0 for c in 'ABCDEFGH'}
    p[letter] = 1.0
    return p


class BuildOpsTests(unittest.TestCase):
    TEXT = ('## Methods\n\nAll eligible patients received a full mouth scaling and\n\n'
            "* Perio-Chip, Perio Products, Jerusalem, Israel.\n\n"
            'root planing. In all instances the instrumentation was done.\n\n'
            'Statistical analysis of the data\n\nThe data were analysed with a test that was chosen for\n\n'
            'the purpose of the study.\n')

    def setUp(self):
        self.paras = [{'id': k, 'text': t, 'source_page': 1} for k, (_, _, t) in enumerate(prep.paragraphs(self.TEXT))]

    def answers(self, footnote='D', join_yes=0.95, head_yes=0.9, main=0.2):
        blocks = [{'num': i + 1, 'para': r['id'], 'multi': False, 'snippet': '', 'class': {'answer': 'A', 'probs': probs('A')}}
                  for i, r in enumerate(self.paras)]
        blocks[2]['class'] = {'answer': footnote, 'probs': probs(footnote)}
        return {'pages': {'1': {'page': 1, 'blocks': blocks, 'order': None, 'order_blocks': None}},
                'joins': [{'a': 5, 'b': 6, 'pa': 1, 'pb': 1, 'probs': {'yes': join_yes, 'no': 1 - join_yes}}],
                'heads': [{'para': 4, 'line': 'Statistical analysis of the data', 'core': 'Statistical analysis of the data',
                           'page': 1, 'probs': {'yes': head_yes, 'no': 1 - head_yes}, 'level': {'main': main, 'sub': 1 - main}}]}

    def test_footnote_moved_out_of_sentence_join_and_heading(self):
        ops, src, notes, cur = build_ops.build(self.TEXT, self.paras, self.answers(), apply_one)
        self.assertEqual([o['op'] for o in ops], ['move', 'join', 'join', 'markup'])
        self.assertIn('scaling and root planing.', cur)
        self.assertIn('was done.\n\n* Perio-Chip', cur)
        self.assertIn('### Statistical analysis of the data', cur)
        self.assertIn('chosen for the purpose', cur)
        self.assertEqual(src[0]['by'], 'class_move')

    def test_low_confidence_changes_nothing(self):
        ans = self.answers(footnote='A', join_yes=0.6, head_yes=0.7)
        ops, src, notes, cur = build_ops.build(self.TEXT, self.paras, ans, apply_one)
        self.assertEqual(ops, [])
        self.assertEqual(cur, self.TEXT)

    def test_veto_on_non_running_blocks(self):
        ans = self.answers(footnote='A')
        ans['pages']['1']['blocks'][4]['class'] = {'answer': 'G', 'probs': probs('G')}  # the heading line is table text
        ans['pages']['1']['blocks'][5]['class'] = {'answer': 'C', 'probs': probs('C')}
        ops, src, notes, cur = build_ops.build(self.TEXT, self.paras, ans, apply_one)
        self.assertEqual(ops, [])
        self.assertTrue(any('veto_join' in n for n in notes))
        self.assertTrue(any('veto_heading' in n for n in notes))

    def order_answer(self, alt_logprob):
        steps = [{'tok': 'no', 'alts': {'no': -0.01, 'yes': -5}}, {'tok': '\n', 'alts': {'\n': 0}},
                 {'tok': 'Order', 'alts': {'Order': 0}}, {'tok': ':', 'alts': {':': 0}},
                 {'tok': ' ', 'alts': {' ': 0}}, {'tok': '2', 'alts': {'2': -0.05, '1': alt_logprob}},
                 {'tok': ',', 'alts': {',': 0}}, {'tok': ' ', 'alts': {' ': 0}}, {'tok': '1', 'alts': {'1': 0}}]
        return {'answer': 'no\nOrder: 2, 1', 'probs': {'yes': 0.01, 'no': 0.99}, 'steps': steps}

    def test_reading_order_needs_a_confident_departure(self):
        text = '# Title of the paper\n\nSecond column paragraph comes here.\n\nFirst column paragraph should be first.\n'
        paras = [{'id': k, 'text': t, 'source_page': 1} for k, (_, _, t) in enumerate(prep.paragraphs(text))]
        blocks = [{'num': i, 'para': i, 'multi': False, 'snippet': '', 'class': {'answer': 'A', 'probs': probs('A')}} for i in (1, 2)]
        for alt, moved in ((-6.0, True), (-0.1, False)):
            ans = {'pages': {'1': {'page': 1, 'blocks': blocks, 'order': self.order_answer(alt),
                                   'order_blocks': [{'num': 1, 'para': 1}, {'num': 2, 'para': 2}]}}, 'joins': [], 'heads': []}
            ops, src, notes, cur = build_ops.build(text, paras, ans, apply_one)
            self.assertEqual(bool(ops), moved)
            if moved:
                self.assertTrue(cur.startswith('# Title of the paper\n\nFirst column'))

    def test_quote_paragraphs_join_and_list_items_do_not(self):
        text = ('> The first printed line of the manuscript runs on\n\n> into the second printed line of it.\n\n'
                'A paragraph that ends without a stop and\n\n- a list item that starts in lower case here\n')
        paras = [{'id': k, 'text': t, 'source_page': 1} for k, (_, _, t) in enumerate(prep.paragraphs(text))]
        yes = {'yes': 0.99, 'no': 0.01}
        ans = {'pages': {}, 'heads': [], 'joins': [{'a': 0, 'b': 1, 'pa': 1, 'pb': 1, 'probs': yes},
                                                   {'a': 2, 'b': 3, 'pa': 1, 'pb': 1, 'probs': yes}]}
        ops, src, notes, cur = build_ops.build(text, paras, ans, apply_one)
        self.assertEqual(len(ops), 1)
        self.assertIn('runs on into the second', cur)
        self.assertIn('stop and\n\n- a list item', cur)

    def test_class_move_goes_to_the_end_of_the_sentence(self):
        text = ('> Methods: this is a chart review on patient adherence for the\n\n> Deleted: a review balloon\n\n'
                '> treatment of the disease, which was defined as wearing the device\n\n'
                '> every night for at least four hours in the study.\n\n> Results: all went well in the end.\n')
        paras = [{'id': k, 'text': t, 'source_page': 1} for k, (_, _, t) in enumerate(prep.paragraphs(text))]
        blocks = [{'num': i + 1, 'para': i, 'multi': False, 'snippet': '', 'class': {'answer': 'A', 'probs': probs('A')}}
                  for i in range(len(paras))]
        blocks[1]['class'] = {'answer': 'E', 'probs': probs('E')}
        ans = {'pages': {'1': {'page': 1, 'blocks': blocks, 'order': None, 'order_blocks': None}}, 'heads': [],
               'joins': [{'a': 2, 'b': 3, 'pa': 1, 'pb': 1, 'probs': {'yes': 0.99, 'no': 0.01}}]}
        ops, src, notes, cur = build_ops.build(text, paras, ans, apply_one)
        self.assertIn('for the treatment of the disease', cur)
        self.assertIn('wearing the device every night', cur)
        self.assertIn('in the study.\n\n> Deleted: a review balloon\n\n> Results', cur)

    def test_order_move_never_lands_inside_a_sentence(self):
        text = ('# Title of the paper\n\n> Table 3. A caption without a stop\n\n> to the group after adjusting for it all.\n\n'
                '> Secondary analyses were done here as planned.\n')
        paras = [{'id': k, 'text': t, 'source_page': 1} for k, (_, _, t) in enumerate(prep.paragraphs(text))]
        blocks = [{'num': i, 'para': p, 'multi': False, 'snippet': '', 'class': {'answer': 'A', 'probs': probs('A')}}
                  for i, p in ((1, 2), (2, 3))]
        steps = [{'tok': 'no', 'alts': {'no': -0.01}}, {'tok': '\n', 'alts': {'\n': 0}}, {'tok': 'Order', 'alts': {'Order': 0}},
                 {'tok': ':', 'alts': {':': 0}}, {'tok': ' ', 'alts': {' ': 0}}, {'tok': '2', 'alts': {'2': -0.01, '1': -6}},
                 {'tok': ',', 'alts': {',': 0}}, {'tok': ' ', 'alts': {' ': 0}}, {'tok': '1', 'alts': {'1': 0}}]
        ans = {'pages': {'1': {'page': 1, 'blocks': blocks, 'order': {'answer': 'no\nOrder: 2, 1', 'probs': {'yes': 0.01, 'no': 0.99},
                                                                      'steps': steps},
                               'order_blocks': [{'num': 1, 'para': 2}, {'num': 2, 'para': 3}]}}, 'joins': [], 'heads': []}
        ops, src, notes, cur = build_ops.build(text, paras, ans, apply_one)
        self.assertEqual(ops, [])
        self.assertTrue(any('inside a sentence' in str(n.get('skipped')) for n in notes))

    def test_two_page_blocks_are_never_moved(self):
        text = '# Title of the paper\n\nSecond column paragraph comes here.\n\nFirst column paragraph should be first.\n'
        paras = [{'id': k, 'text': t, 'source_page': 1} for k, (_, _, t) in enumerate(prep.paragraphs(text))]
        blocks = [{'num': i, 'para': i, 'multi': i == 2, 'snippet': '', 'class': {'answer': 'A', 'probs': probs('A')}} for i in (1, 2)]
        ans = {'pages': {'1': {'page': 1, 'blocks': blocks, 'order': self.order_answer(-6.0),
                               'order_blocks': [{'num': 1, 'para': 1}, {'num': 2, 'para': 2}]}}, 'joins': [], 'heads': []}
        ops, *_ = build_ops.build(text, paras, ans, apply_one)
        self.assertEqual(ops, [])


AFFIL = ['Department of Conservative Dentistry, School of Dentistry, Universidad de Chile, Santiago, Chile',
         'Center for Craniofacial Research, University of Texas School of Dentistry at Houston, USA']


class DuplicateTests(unittest.TestCase):
    def test_affiliation_panel_printed_again_in_article_information(self):
        text = ('# Title\n\n**Authors:** A 1; B 2\n- 1 ' + AFFIL[0] + '\n- 2 ' + AFFIL[1] + '\n\n## Article information\n\n'
                '- Molecular Sciences\n- ' + AFFIL[0] + ' ' + AFFIL[1] + ' Correspondence: a@b.cl; Tel.: +56\n\n'
                '## Introduction\n\nBody text.\n')
        ops, ev, notes, cur = dupfind.find_all(text, apply_one)
        self.assertEqual(len(ops), 2)
        self.assertIn('\n- Correspondence: a@b.cl; Tel.: +56\n', cur)
        self.assertEqual(cur.count(AFFIL[0]), 1)
        self.assertEqual(cur.count(AFFIL[1]), 1)

    def test_lines_printed_again_as_one_line_go_whole(self):
        text = ('# T\n\n## Article information\n\n- Published in final edited form as:\n'
                '- Periodontol 2000. 2015 June ; 68(1): 7-20. doi:10.1111/prd.12091.\n'
                '- Published in final edited form as: Periodontol 2000. 2015 June ; 68(1): 7-20. doi:10.1111/prd.12091.\n\n'
                '## Abstract\n\nText.\n')
        ops, ev, notes, cur = dupfind.find_all(text, apply_one)
        self.assertEqual(len(ops), 2)
        self.assertEqual(cur, '# T\n\n## Article information\n\n- Published in final edited form as:\n'
                              '- Periodontol 2000. 2015 June ; 68(1): 7-20. doi:10.1111/prd.12091.\n\n## Abstract\n\nText.\n')

    def test_caption_printed_twice(self):
        cap = '**Figure 2. Mean probing depth at baseline and after six months of treatment.**'
        text = '## Results\n\n' + cap + '\n\nBody text here.\n\n' + cap + '\n\nMore text.\n'
        ops, ev, notes, cur = dupfind.find_all(text, apply_one)
        self.assertEqual(len(ops), 1)
        self.assertEqual(cur.count(cap), 1)
        self.assertTrue(cur.index(cap) < cur.index('Body text'))

    def test_body_repeats_without_trace_are_left(self):
        row = '- Outcome Intervention No. of studies difference (mm) 95% CI chi-square P'
        line = 'and the most coronal aspect of the bone crest'
        text = ('## Results\n\n' + row + '\n- a 1 2\n\nText.\n\n' + row + '\n- b 3 4\n\n'
                'First line of a paragraph\n' + line + '\nlast.\n\nOther\n' + line + '\nend.\n')
        ops, *_ = dupfind.find_all(text, apply_one)
        self.assertEqual(ops, [])

    def test_front_matter_as_printed_is_never_touched(self):
        text = ('# T\n\n**Authors:** Anton Sculean\n\n**Front matter as printed**\n\nPage 1:\n\n```text\n'
                + AFFIL[0] + '\n```\n\n- ' + AFFIL[0] + '\n\n## Article information\n\n- x\n')
        ops, *_ = dupfind.find_all(text, apply_one)
        self.assertEqual(ops, [])

    def test_caption_is_never_cut(self):
        piece = 'objective and self-reported mean rate of use data as assessed'
        text = ('## Results\n\n- Table 3 Median values of\n- ' + piece + '\n\n**Table 3. Median values of ' + piece + '**\n')
        tr = make_trace(text, [('u1', 'g1', piece, [(3, 'run:8', piece)]),
                               ('u2', 'g2', 'Table 3. Median values of ' + piece, [(3, 'run:8', piece)])])
        tr['units'][1]['kind'] = 'caption'
        tk = tracemap.Tracker(text, tr)
        ops, *_ = dupfind.find_all(text, tk.apply, lambda _c: tk.confirm_duplicate)
        self.assertEqual(ops, [])

    def test_one_unit_group_is_not_a_repeat(self):
        row = '- Variable median test statistic d.f. p value of it'
        text = '## Results\n\n' + row + '\n- a 1 2\n\n' + row + '\n- b 3 4\n'
        tr = make_trace(text, [('u1', 'g1', row[2:], [(8, 'run:1', 'Variable')]), ('u2', 'g1', row[2:], [(8, 'run:1', 'Variable')])])
        tk = tracemap.Tracker(text, tr)
        ops, *_ = dupfind.find_all(text, tk.apply, lambda _c: tk.confirm_duplicate)
        self.assertEqual(ops, [])

    def test_trace_decides(self):
        cap = 'Correspondence: Dr. A. Person, Department of Periodontics, Some University.'
        text = '# T\n\n## Article information\n\n- ' + cap + '\n\n## Introduction\n\nBody.\n\n- ' + cap + '\n'
        same = make_trace(text, [('u1', 'g1', cap, [(1, 'run:9', cap)]), ('u2', 'g2', 'Body.', [(1, 'run:2', 'Body.')]),
                                 ('u3', 'g3', cap, [(1, 'run:9', cap)])])
        other = make_trace(text, [('u1', 'g1', cap, [(1, 'run:9', cap)]), ('u2', 'g2', 'Body.', [(1, 'run:2', 'Body.')]),
                                  ('u3', 'g3', cap, [(5, 'run:1', cap)])])
        for tr, expect in ((same, 1), (other, 0)):
            tk = tracemap.Tracker(text, tr)
            ops, *_ = dupfind.find_all(text, tk.apply, lambda _c: tk.confirm_duplicate)
            self.assertEqual(len(ops), expect)


class TrackerTests(unittest.TestCase):
    BASE = ('# Title\n\n## Methods\n\nThe first sentence starts here and\n\n**Table 1. A caption that cuts the sentence.**\n\n'
            'continues here to the end.\n\n<!-- end of page 1 -->\n\nResults Text of the results paragraph follows.\n\n'
            '- Plain line to mark up as heading\n\n## Places the program is not sure of\n\n- none\n')

    def check_map(self, tk):
        for j, o in enumerate(tk.origin):
            if o >= 0:
                self.assertEqual(tk.text[j], tk.orig[o])

    def test_every_op_type_is_mirrored(self):
        ops = [{'op': 'move', 'start': '**Table 1. A caption that cuts the sentence.**',
                'end': '**Table 1. A caption that cuts the sentence.**', 'after': 'continues here to the end.', 'as': 'paragraph'},
               {'op': 'join', 'left': 'The first sentence starts here and', 'right': 'continues here to the end.'},
               {'op': 'split', 'text': 'Results Text of the results paragraph follows.', 'at': 'Text of the results paragraph', 'as': 'paragraph'},
               {'op': 'markup', 'text': 'Results ', 'as': 'heading3'},
               {'op': 'markup', 'text': '- Plain line to mark up as heading', 'as': 'heading2'},
               {'op': 'markup', 'text': '**Table 1. A caption that cuts the sentence.**', 'as': 'paragraph'},
               {'op': 'move', 'start': 'Table 1. A caption that cuts the sentence.', 'end': 'Table 1. A caption that cuts the sentence.',
                'after': 'Text of the results paragraph follows.', 'as': 'inline'},
               {'op': 'flag', 'note': 'page 1: a test flag'}]
        tk = tracemap.Tracker(self.BASE)
        cur = self.BASE
        for op in ops:
            new, entry = tk.apply(cur, op)
            self.assertEqual(entry['status'], 'accepted', (op, entry['reason']))
            cur = new
            self.check_map(tk)
        self.assertEqual(cur, RA.apply_operations(self.BASE, ops)[0])

    def test_duplicate_removal_and_markup_with_emphasis(self):
        line = 'A repeated line of the front block for removal.'
        text = '- ' + line + '\n\n**' + line + '**\n\nTail paragraph here.\n'
        tk = tracemap.Tracker(text)
        new, e = tk.apply(text, {'op': 'remove_duplicate', 'start': line, 'end': line, 'occurrence': 2})
        self.assertEqual(e['status'], 'accepted')
        self.check_map(tk)
        new, e = tk.apply(new, {'op': 'markup', 'text': '- ' + line, 'as': 'caption'})
        self.assertEqual(e['status'], 'accepted')
        self.check_map(tk)

    def traced(self):
        p1 = 'First printed paragraph of the body text.'
        p2 = 'Second printed paragraph of the body text.'
        text = '# T\n\n' + p1 + '\n\n' + p2 + '\n\n' + p1 + '\n'
        tr = make_trace(text, [('u1', 'g1', p1, [(1, 'run:1', p1)]), ('u2', 'g2', p2, [(1, 'run:2', p2)]),
                               ('u3', 'g3', p1, [(1, 'run:1', p1)])])
        return text, tr, p1, p2

    def test_trace_follows_ops_and_validates(self):
        text, tr, p1, p2 = self.traced()
        tk = tracemap.Tracker(text, tr)
        cur, e = tk.apply(text, {'op': 'remove_duplicate', 'start': p1, 'end': p1, 'occurrence': 2})
        self.assertEqual(e['status'], 'accepted')
        cur, e = tk.apply(cur, {'op': 'move', 'start': p2, 'end': p2, 'after': '# T', 'as': 'paragraph'})
        self.assertEqual(e['status'], 'accepted')
        out = tk.checked_trace()
        self.assertEqual([u['id'] for u in out['units']], ['u1', 'u2'])
        for u in out['units']:
            self.assertEqual(cur[u['span'][0]:u['span'][1]], u['text'])
        self.assertEqual({l['status'] for l in out['lines']}, {'unit'})
        tv = tracemap._trace_module()
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'copy.checked.md').write_text(cur, encoding='utf-8')
            Path(d, 'copy.checked.trace.json').write_text(json.dumps(out), encoding='utf-8')
            rep = tv.validate(d, None, False, 'copy.checked.md', 'copy.checked.trace.json')
            self.assertTrue(rep['valid'], rep['problems'])
            self.assertTrue(rep['ok'])
            self.assertEqual(rep['accounting']['duplicate_lines'], [])

    def test_gate_refuses_lost_lines_and_cut_units(self):
        p1 = 'One printed paragraph of the body text, said once.'
        other = 'Other text in a block of the copy, said first.'
        text = '# T\n\n' + p1 + '\n\n' + other + ' ' + p1 + '\n'
        tr = make_trace(text, [('u1', 'g1', p1, [(1, 'run:1', p1)]),
                               ('u2', 'g2', other + ' ' + p1, [(2, 'run:1', other + ' ' + p1)])])
        tk = tracemap.Tracker(text, tr)
        # removing the first copy would leave its printed line in no unit
        new, e = tk.apply(text, {'op': 'remove_duplicate', 'start': p1, 'end': p1, 'occurrence': 1})
        self.assertEqual(e['status'], 'rejected')
        self.assertIn('lost', e['reason'])
        # moving half of a unit away cuts it apart
        new, e = tk.apply(text, {'op': 'move', 'start': other, 'end': other,
                                 'after': '# T', 'as': 'paragraph'})
        self.assertEqual(e['status'], 'rejected')
        self.assertIn('cut apart', e['reason'])
        self.assertEqual(tk.text, text)


class StageRunTests(unittest.TestCase):
    def run_stage(self, d, *extra):
        return subprocess.run(['/usr/bin/python3', '-I', str(HERE / 'checkstage' / 'run.py'), str(d), str(Path(d) / 'paper.pdf'),
                               *extra], capture_output=True, text=True)

    def test_code_checks_only_with_trace(self):
        text, tr, p1, p2 = TrackerTests.traced(None)
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'copy.md').write_text(text, encoding='utf-8')
            Path(d, 'copy.trace.json').write_text(json.dumps(tr), encoding='utf-8')
            tiny_pdf(Path(d, 'paper.pdf'))
            r = self.run_stage(d, '--no-model')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(d, 'copy.md').read_text(encoding='utf-8'), text)
            checked = Path(d, 'copy.checked.md').read_text(encoding='utf-8')
            self.assertEqual(checked.count(p1), 1)
            ops = json.loads(Path(d, 'check.ops.json').read_text())
            self.assertEqual(ops['stage']['model']['status'], 'off')
            self.assertEqual(ops['op_sources'][0]['by'], 'duplicate')
            self.assertEqual(ops['stage']['trace']['duplicate_lines'], [1, 0])
            log = json.loads(Path(d, 'check.apply-log.json').read_text())
            self.assertEqual([e['status'] for e in log['ops']], ['accepted'])
            v = subprocess.run(['/usr/bin/python3', '-I', str(HERE / 'trace.py'), d, '--copy', 'copy.checked.md',
                                '--trace', 'copy.checked.trace.json'], capture_output=True, text=True)
            self.assertEqual(v.returncode, 0, v.stdout + v.stderr)
            self.assertFalse(Path(d, 'check.work').exists())

    def test_saved_answers_and_missing_model(self):
        t = BuildOpsTests('test_footnote_moved_out_of_sentence_join_and_heading')
        t.setUp()
        with tempfile.TemporaryDirectory() as d:
            Path(d, 'copy.md').write_text(t.TEXT, encoding='utf-8')
            tiny_pdf(Path(d, 'paper.pdf'))
            Path(d, 'answers.json').write_text(json.dumps(t.answers()), encoding='utf-8')
            r = self.run_stage(d, '--answers', str(Path(d, 'answers.json')))
            self.assertEqual(r.returncode, 0, r.stderr)
            ops = json.loads(Path(d, 'check.ops.json').read_text())
            self.assertEqual([o['op'] for o in ops['ops']], ['move', 'join', 'join', 'markup'])
            self.assertFalse(Path(d, 'copy.checked.trace.json').exists())
            r = self.run_stage(d, '--python', str(Path(d, 'no-such-python')))
            self.assertEqual(r.returncode, 0, r.stderr)
            ops = json.loads(Path(d, 'check.ops.json').read_text())
            self.assertEqual(ops['stage']['model']['status'], 'skipped')
            self.assertEqual(Path(d, 'copy.checked.md').read_text(encoding='utf-8'), t.TEXT)

    def test_bad_input(self):
        with tempfile.TemporaryDirectory() as d:
            r = self.run_stage(d)
            self.assertEqual(r.returncode, 2)


if __name__ == '__main__':
    unittest.main()
