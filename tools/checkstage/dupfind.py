"""Check stage, code duplicate finder (no model): blocks the copy prints twice.

A block printed twice is found by exact text, never by similarity:
- whole duplicates: a later paragraph, line or list item whose text (Markdown line
  prefixes and outer ** removed) is exactly the text of an earlier paragraph, line or list
  item, at least MIN_WHOLE characters and MIN_WORDS words long (a caption printed twice, a
  correspondence line twice); a line counts only when it is a block of its own (a list
  item, a quote line or a one-line paragraph), never a printed line inside a paragraph;
  without a trace only in the front of the copy or for captions;
- contained duplicates: an earlier whole line or list item (an affiliation line; a leading
  affiliation marker such as "1 " or "*" is not part of it) printed again inside a later
  line or paragraph, at word boundaries, at least MIN_PIECE characters and MIN_WORDS words
  (an affiliation panel printed in the byline block and again inside an Article
  information item); without a trace this is looked for only in the front of the copy
  (before the first section heading other than "Article information"), where the copier
  assembles blocks; or the reverse: a later whole line printed earlier inside a longer
  block (the later copy is removed).
The second (later) copy is removed with one remove_duplicate op (OPS-SCHEMA-v2), which the
safe applier accepts only when the exact text still occurs once afterwards. When a later
line holds only duplicated pieces, the first piece is quoted with its line prefix so the
emptied line goes with it.

Never touched: fenced blocks, the flagged "Front matter as printed" block (it repeats the
byline's source lines on purpose), table rows and tables printed as lines, page markers,
headings, and the "Places the program is not sure of" list.

With the copy's native trace, a candidate is kept only when the trace confirms it: a
unit holding the later copy claims a printed line that a unit holding the earlier copy also
claims (the copier printed the same source line twice). Text the PDF itself prints twice
(different source lines) is left alone.
"""
import re

MIN_WHOLE, MIN_PIECE, MIN_WORDS = 30, 40, 5
UNCERTAINTY_TITLE = 'Places the program is not sure of'
PREFIX = re.compile(r'^[ \t]*(?:(?:#{1,6}|>|-)[ \t]+)*')
MARKER = re.compile(r'^(?:[0-9]{1,2}|[a-z]|[*†‡§¶#]{1,3})[ \t]+(?=\S)')
PAGE_MARK = re.compile(r'^<!-- (?:end of )?page \d+ -->$')
CAPTION = re.compile(r'^(?:Figure|Fig\.|Table|Scheme|Plate|Box)\s*[A-Z]?\d+')


def _segments(text):
    """Candidate blocks: (kind, start, end, front) for lines and paragraphs, with content offsets."""
    m = re.search(r'^#+ *' + re.escape(UNCERTAINTY_TITLE) + r'\s*$', text, re.M)
    body_end = m.start() if m else len(text)
    lines = []
    pos = 0
    in_fence = in_printed = in_table = False
    front = True
    for raw in text[:body_end].splitlines(keepends=True):
        ln = raw.rstrip('\r\n')
        s = ln.strip()
        start = pos
        pos += len(raw)
        if s.startswith('```'):
            in_fence = not in_fence
            lines.append(None)
            continue
        if in_fence:
            lines.append(None)
            continue
        if s.startswith('## ') or s.startswith('# '):
            in_printed = False
            if s.startswith('## ') and 'Article information' not in s:
                front = False
            lines.append(None)
            continue
        if s == '**Front matter as printed**':
            in_printed = True
        if not s:
            in_table = False
            lines.append('blank')
            continue
        if s.startswith('[table structure not recovered') or s.startswith('|'):
            in_table = True
        if in_printed or in_table or PAGE_MARK.match(s) or s.startswith('['):
            lines.append(None)
            continue
        p = PREFIX.match(ln).end()
        a, b = start + p, start + len(ln)
        c = text[a:b]
        lead = len(c) - len(c.lstrip())
        a += lead
        c = text[a:b].rstrip()
        b = a + len(c)
        while c.startswith('**') and c.endswith('**') and len(c) >= 4:
            a, b = a + 2, b - 2
            c = text[a:b]
        if b > a:
            lines.append(('line', a, b, front, start, p > 0))
        else:
            lines.append(None)
    # a line is a block of its own when it is a list item or quote line, or a one-line paragraph
    segs = []
    for i, x in enumerate(lines):
        if not isinstance(x, tuple):
            continue
        alone = x[5] or ((i == 0 or not isinstance(lines[i - 1], tuple)) and
                         (i + 1 == len(lines) or not isinstance(lines[i + 1], tuple)))
        if alone:
            segs.append(x[:5])
    # paragraphs of two or more lines (all plain, consecutive)
    run = []
    for x in lines + ['blank']:
        if isinstance(x, tuple):
            run.append(x)
            continue
        if len(run) >= 2 and x == 'blank' and not any(r[5] for r in run):
            segs.append(('para', run[0][1], run[-1][2], run[0][3], run[0][4]))
        run = []
    return segs, body_end


def _words(s):
    return len(s.split())


def _core(text, seg):
    """The piece of a line used for contained matching: without a leading affiliation marker."""
    a, b = seg[1], seg[2]
    m = MARKER.match(text[a:b])
    return (a + m.end(), b) if m else (a, b)


def _occurrence(text, quote, pos):
    k, i = 0, text.find(quote)
    while i != -1:
        k += 1
        if i == pos:
            return k
        i = text.find(quote, i + 1)
    return None


def _bounded(text, i, j):
    left_ok = i == 0 or not (text[i - 1].isalnum())
    right_ok = j >= len(text) or not text[j].isalnum()
    return left_ok and right_ok


def find_one(text, confirm=None, front_only_contained=True):
    """The first duplicate (later copy) in the current text, as (op, evidence), or None.

    confirm(earlier_span, later_span, later_is_part_of_a_block) -> bool is the trace check (None: text only)."""
    segs, body_end = _segments(text)
    segs.sort(key=lambda s: (s[1], -s[2]))
    # ---- whole duplicates: the first later copy in text order (a paragraph before its own lines)
    by_text = {}
    for sg in segs:
        by_text.setdefault(text[sg[1]:sg[2]], []).append(sg)
    whole = []
    for t, group in by_text.items():
        if len(group) < 2 or len(t) < MIN_WHOLE or _words(t) < MIN_WORDS:
            continue
        first = group[0]
        for later in group[1:]:
            if later[1] < first[2]:
                continue
            if confirm is None and not ((first[3] and later[3]) or CAPTION.match(t)):
                continue  # without a trace: only the front of the copy, or a caption printed twice
            if confirm is not None and not confirm((first[1], first[2]), (later[1], later[2]), False):
                continue
            whole.append((later[1], -(later[2] - later[1]), first, later))
            break
    for _, _, first, later in sorted(whole, key=lambda w: (w[0], w[1])):
        a, b = later[1], later[2]
        quote = text[a:b]
        with_prefix = text[later[4]:b]
        if with_prefix != quote and text[first[4]:first[2]] == with_prefix:
            quote, a = with_prefix, later[4]  # the whole later line goes, prefix and all
            # the last line of a block: take its line break before it instead, so the blank
            # line that ends the block stays (the applier removes a whole line with the blank
            # lines after it)
            nxt = text[b + 1:text.find('\n', b + 1) if text.find('\n', b + 1) != -1 else len(text)]
            if text[b:b + 1] == '\n' and not nxt.strip() and a >= 2 and text[a - 1] == '\n' and text[a - 2] != '\n' \
                    and text.count('\n' + quote) >= 2:
                quote, a = '\n' + quote, a - 1
        k = _occurrence(text, quote, a)
        if k is not None and k >= 2:
            return ({'op': 'remove_duplicate', 'start': quote, 'end': quote, 'occurrence': k},
                    {'rule': 'whole', 'earlier': [first[1], first[2]], 'later': [a, a + len(quote)], 'text': quote[:160]})
    # ---- contained duplicates: an earlier whole line inside a later block, or the reverse
    cands = []
    for sg in segs:
        if sg[0] != 'line':
            continue
        ca, cb = _core(text, sg)
        piece = text[ca:cb]
        if len(piece) < MIN_PIECE or _words(piece) < MIN_WORDS:
            continue
        for bl in segs:
            if bl is sg or (bl[1] <= ca and cb <= bl[2]) or (bl[2] - bl[1]) <= len(piece):
                continue
            seg_text = text[bl[1]:bl[2]]
            i = seg_text.find(piece)
            while i != -1:
                pa, pb = bl[1] + i, bl[1] + i + len(piece)
                if _bounded(text, pa, pb) and (pb <= sg[1] or pa >= sg[2]):
                    inside_later = pa > cb
                    earlier, later = ((ca, cb), (pa, pb)) if inside_later else ((pa, pb), (sg[1], sg[2]))
                    front_ok = sg[3] and bl[3]
                    later_text = text[bl[1]:bl[2]] if inside_later else piece
                    if inside_later and (CAPTION.match(later_text) or text[bl[4]:bl[1]].lstrip().startswith('#')):
                        pass  # never cut words out of a caption or heading
                    elif (front_ok or not front_only_contained or confirm is not None) and (
                            confirm is None or confirm(earlier, later, inside_later)):
                        # the earliest later block first; inside it, its last piece first, so that
                        # every removal leaves the rest of the line as it was printed
                        blk = bl if inside_later else sg
                        cands.append(((blk[1], -later[0]), later, earlier, piece, inside_later))
                i = seg_text.find(piece, i + 1)
    for _, later, earlier, piece, inside_later in sorted(cands, key=lambda c: c[0]):
        a, b = later
        options = []
        if inside_later:
            if a > 0 and text[a - 1] == ' ':
                options.append((a - 1, b))  # with the space before it: no double space left
            options.append((a, b))
        else:
            options.append((a, b))
        for qa, qb in options:
            quote = text[qa:qb]
            k = _occurrence(text, quote, qa)
            if k is not None and k >= 2:
                return ({'op': 'remove_duplicate', 'start': quote, 'end': quote, 'occurrence': k},
                        {'rule': 'contained', 'earlier': list(earlier), 'later': [qa, qb], 'text': quote[:160]})
    return None


def find_all(text, apply_one, confirm_factory=None, limit=200):
    """Duplicate ops in order, each accepted by apply_one on the text left by the previous ones."""
    ops, evidence, notes = [], [], []
    cur = text
    tried = set()
    for _ in range(limit):
        confirm = confirm_factory(cur) if confirm_factory else None
        found = find_one(cur, confirm)
        if not found:
            break
        op, ev = found
        key = (op['start'], op['occurrence'], len(cur))
        if key in tried:
            break
        tried.add(key)
        new, log = apply_one(cur, op)
        if log['status'] != 'accepted':
            notes.append({'op': op, 'evidence': ev, 'sim_rejected': log['reason']})
            break
        cur = new
        ops.append(op)
        evidence.append(ev)
    return ops, evidence, notes, cur
