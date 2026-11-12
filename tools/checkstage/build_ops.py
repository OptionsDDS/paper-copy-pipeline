"""Check stage, step 3 (CPU, standard library): turn the model's scored answers into
placement-only repair operations (OPS-SCHEMA-v2), exactly as the local-checker trial's
best design ("B+ with (ii) veto", post.py ops_design_b) did.

Every op is built against the copy as it stands after the earlier ops and is kept only if
the safe applier accepts it on that text (simulation with the applier itself). Rules:
- (ii) a paragraph read as non-running text (P(non-running) >= T_CLASS, the least
  non-running reading over the pages it is boxed on), not a two-page block, that sits
  between two halves of a sentence (previous content paragraph ends without sentence
  punctuation, the next starts in lower case, and the previous one is itself running text)
  is moved, with any directly following non-running paragraphs, after the continuing
  paragraph; the two halves are joined; a running head (class E) is also flagged.
- (i) a page whose reading-order answer is "no" (P(no) >= T_ORDER) with a non-identity
  permutation is reordered only if the model's first departure from the copy's order is
  confident against keeping that order (share >= T_DIV): the longest increasing
  subsequence stays, the other blocks are moved after their predecessor in the answer;
  a page whose moves would touch a two-page block is skipped, no block is placed against
  a two-page block (its place on this page is not one point), and no block lands between
  the two halves of a sentence.
- (iii) a join candidate answered yes (P >= T_PLUS) is joined; (iv) a heading candidate
  answered yes (P >= T_PLUS) is marked heading2 (P(main) >= 0.5) or heading3.
- veto: joins and headings are dropped when either paragraph was read as non-running text
  (P(non-running) >= 0.5) by question (ii).
"""
import bisect
import math
import re

from prep import ends_open, starts_lower

T_ORDER, T_CLASS, T_DIV, T_PLUS = 0.5, 0.8, 0.8, 0.8
RUNNING = {'A', 'B'}


def para_spans(text):
    """Blank-line paragraphs of the current text: list of (start, end)."""
    pos = 0
    spans = []
    for blk in re.split(r'(\n[ \t]*\n)', text):
        if blk and not re.fullmatch(r'\n[ \t]*\n', blk):
            s = pos + (len(blk) - len(blk.lstrip()))
            e = pos + len(blk.rstrip())
            if e > s:
                spans.append((s, e))
        pos += len(blk)
    return spans


def unique_head(text, para, minlen=25):
    t = para.strip()
    first_line = t.split('\n')[0]
    n = min(len(first_line), max(minlen, 40))
    while n <= len(t):
        qq = t[:n]
        if qq.strip() == qq and text.count(qq) == 1 and (len(qq) >= 25 or len(first_line) < 25):
            return qq
        n += 10
    return t if text.count(t) == 1 else None


def unique_tail(text, para, minlen=25):
    t = para.strip()
    last_line = t.split('\n')[-1]
    n = min(len(last_line), max(minlen, 40))
    while n <= len(t):
        qq = t[-n:]
        if qq.strip() == qq and text.count(qq) == 1 and (len(qq) >= 25 or len(last_line) < 25):
            return qq
        n += 10
    return t if text.count(t) == 1 else None


def content_head(text, para):
    """unique_head of a paragraph without its quote prefix ("> "): a join's right piece starts at
    the words (the applier keeps the prefix in the joint's gap; quoting it would leave a stray
    "> " inside the joined line, which the applier refuses). A list item ("- ") is never joined
    into the paragraph before it (measured: AF03, a bullet of a two-column list)."""
    t = para.strip()
    if re.match(r'^(?:>[ \t]+)*-[ \t]', t):
        return None
    return unique_head(text, re.sub(r'^(?:>[ \t]+)+', '', t))


def find_para(text, ptxt):
    """Current span of an original paragraph text (only when it occurs once)."""
    t = ptxt.strip()
    i = text.find(t)
    if i >= 0 and text.count(t) == 1:
        return i, i + len(t)
    return None


def is_marker(s):
    return bool(re.fullmatch(r'<!-- (?:end of )?page \d+ -->', s.strip()))


def strip_markers(t):
    return '\n'.join(l for l in t.split('\n') if not is_marker(l)).strip()


def neighbours(text, span):
    """Previous and next content paragraphs (skipping page-marker lines) around a span."""
    prev = nxt = None
    for s, e in para_spans(text):
        if e <= span[0]:
            if strip_markers(text[s:e]):
                prev = (s, e)
        elif s >= span[1] and nxt is None:
            if strip_markers(text[s:e]):
                nxt = (s, e)
    return prev, nxt


def lis_keep(seq):
    """Values of seq forming a longest increasing subsequence."""
    tails, tails_idx, prev = [], [], [-1] * len(seq)
    for i, x in enumerate(seq):
        j = bisect.bisect_left(tails, x)
        if j == len(tails):
            tails.append(x)
            tails_idx.append(i)
        else:
            tails[j] = x
            tails_idx[j] = i
        prev[i] = tails_idx[j - 1] if j else -1
    out = []
    k = tails_idx[-1] if tails_idx else -1
    while k != -1:
        out.append(k)
        k = prev[k]
    return set(seq[i] for i in out)


def divergence_conf(o, perm):
    """Probability share of the model's first departure from the copy's order, against keeping the copy's order there."""
    steps = o.get('steps')
    if not steps:
        return None
    ans = ''.join(st['tok'] for st in steps)
    j = ans.find('Order:')
    if j < 0:
        return None
    ident = ans[:j] + 'Order: ' + ', '.join(str(i) for i in range(1, len(perm) + 1))
    i = next((k for k in range(min(len(ans), len(ident))) if ans[k] != ident[k]), None)
    if i is None:
        return None
    pos = 0
    for st in steps:
        t = st['tok']
        if pos <= i < pos + len(t):
            ch = st['alts'].get(t)
            if ch is None:
                return None
            idl = max((v for kk, v in st['alts'].items() if kk and ident.startswith(kk, pos)), default=None)
            if idl is None:
                return 1.0
            return math.exp(ch) / (math.exp(ch) + math.exp(idl))
        pos += len(t)
    return None


def build(text, paras, answers, apply_one, t_order=T_ORDER, t_class=T_CLASS, t_div=T_DIV, t_plus=T_PLUS, veto=True):
    """ops (accepted in simulation, in order), notes, final text.

    apply_one(text, op) -> (new_text, log_entry) is the safe applier (optionally with trace checks)."""
    byid = {r['id']: r for r in paras}
    recs = [answers['pages'][k] for k in sorted(answers.get('pages', {}), key=int)]
    cur = text
    ops, notes, kinds = [], [], []  # kinds: per op, the question and scores behind it

    def emit(op, kind, ev):
        nonlocal cur
        new, log = apply_one(cur, op)
        if log['status'] == 'accepted':
            cur = new
            ops.append(op)
            kinds.append(dict(ev, by=kind))
            return True
        notes.append({'op': op, 'by': kind, 'evidence': ev, 'sim_rejected': log['reason']})
        return False

    # paragraph classification (least non-running reading over the pages it is boxed on)
    pcls = {}
    for rec in recs:
        for b in rec['blocks']:
            pr = b['class']['probs'] or {}
            if not pr:
                continue
            nonrun = sum(v for k, v in pr.items() if k not in RUNNING)
            top = max(pr, key=pr.get)
            old = pcls.get(b['para'])
            if old is None or nonrun < old[0]:
                pcls[b['para']] = (nonrun, top, rec['page'], b.get('multi', False))

    def para_id(t):
        return next((r['id'] for r in paras if strip_markers(r['text']) == t), None)

    # ---- (ii) non-running blocks that split a sentence
    for rec in recs:
        for b in rec['blocks']:
            c = pcls.get(b['para'])
            if not c or c[0] < t_class or c[3]:
                continue
            ptxt = strip_markers(byid[b['para']]['text'])
            loc = find_para(cur, ptxt)
            if not loc:
                continue
            prev, nxt = neighbours(cur, loc)
            span = loc
            while nxt is not None:  # extend over consecutive non-running paragraphs
                nid = para_id(strip_markers(cur[nxt[0]:nxt[1]]))
                if nid is not None and pcls.get(nid, (0,))[0] >= t_class:
                    span = (span[0], nxt[1])
                    _, nxt = neighbours(cur, span)
                else:
                    break
            if prev is None or nxt is None:
                continue
            ptext = strip_markers(cur[prev[0]:prev[1]])
            ntext = strip_markers(cur[nxt[0]:nxt[1]])
            pid = para_id(ptext)
            if pid is not None and pcls.get(pid, (0,))[0] >= 0.5:
                continue
            if not (ends_open(ptext) and starts_lower(ntext)):
                continue
            # destination: the end of the sentence the block cut, which may run over several
            # paragraphs of the copy (one per printed line in some copies)
            dest, hops = nxt, 0
            while hops < 8 and ends_open(strip_markers(cur[dest[0]:dest[1]])):
                _, after = neighbours(cur, dest)
                if after is None or not starts_lower(strip_markers(cur[after[0]:after[1]])):
                    break
                dest, hops = after, hops + 1
            span_text = cur[span[0]:span[1]]
            st = unique_head(cur, span_text.split('\n\n')[0])
            en = unique_tail(cur, span_text.split('\n\n')[-1])
            af = unique_tail(cur, strip_markers(cur[dest[0]:dest[1]]))
            if not (st and en and af):
                continue
            ev = {'question': '(ii) block class', 'page': rec['page'], 'para': b['para'], 'class': c[1],
                  'p_nonrunning': round(c[0], 4)}
            if not emit({'op': 'move', 'start': st, 'end': en, 'after': af, 'as': 'paragraph'}, 'class_move', ev):
                continue
            lt = unique_tail(cur, ptext)
            rt = content_head(cur, ntext)
            if lt and rt:
                emit({'op': 'join', 'left': lt, 'right': rt}, 'class_join', ev)
            if c[1] == 'E':
                emit({'op': 'flag', 'note': f"page {rec['page']}: running head or page number '{span_text[:60]}' is in the copy "
                                            "(moved out of a sentence); it is not text of the paper"}, 'class_flag', ev)

    # ---- (i) reading order of running blocks
    for rec in recs:
        o = rec.get('order')
        if not o or not o.get('probs'):
            continue
        p_no = o['probs'].get('no', 0.0)
        m = re.search(r'Order:\s*([0-9, ]+)', o['answer'])
        if not m:
            continue
        perm = [int(x) for x in re.findall(r'\d+', m.group(1))]
        blocks = rec['order_blocks']
        k = len(blocks)
        if sorted(perm) != list(range(1, k + 1)) or perm == list(range(1, k + 1)):
            continue
        if p_no < t_order:
            continue
        dc = divergence_conf(o, perm)
        if dc is not None and dc < t_div:
            notes.append({'page': rec['page'], 'skipped': f'order departure confidence {dc:.2f} < {t_div}'})
            continue
        num2para = {b['num']: b['para'] for b in blocks}
        multi = {b['para'] for b in rec['blocks'] if b.get('multi')}
        keep = lis_keep(perm)
        moved = [x for x in perm if x not in keep]
        if any(num2para[x] in multi for x in moved):
            notes.append({'page': rec['page'], 'skipped': 'would move a paragraph that spans pages'})
            continue

        for i, x in enumerate(perm):
            if x in keep:
                continue
            xt = strip_markers(byid[num2para[x]]['text'])
            loc = find_para(cur, xt)
            if not loc:
                continue
            ref = perm[i - 1] if i > 0 else perm[1]
            if num2para[ref] in multi:
                # a two-page block has no single place on this page to be placed against
                # (measured: AI10 p8, a block put before a two-page paragraph landed three pages back)
                notes.append({'page': rec['page'], 'skipped': 'the block would be placed against a paragraph that spans pages'})
                continue
            if i > 0:
                pt = strip_markers(byid[num2para[perm[i - 1]]]['text'])
                ploc = find_para(cur, pt)
                if not ploc:
                    continue
                anchor_text = cur[ploc[0]:ploc[1]]
                aloc = ploc
            else:
                st_ = strip_markers(byid[num2para[perm[1]]]['text'])
                sloc = find_para(cur, st_)
                if not sloc:
                    continue
                pp, _ = neighbours(cur, sloc)
                if pp is None or pp == loc:
                    continue
                anchor_text = strip_markers(cur[pp[0]:pp[1]])
                aloc = pp
            # never land between the two halves of a sentence (measured: AI10 p6, a block put
            # before a paragraph that continues the previous page's sentence)
            _, after_anchor = neighbours(cur, aloc)
            if after_anchor is not None and after_anchor != loc and ends_open(strip_markers(anchor_text)) \
                    and starts_lower(strip_markers(cur[after_anchor[0]:after_anchor[1]])):
                notes.append({'page': rec['page'], 'skipped': 'the block would land inside a sentence'})
                continue
            st = unique_head(cur, xt.split('\n\n')[0])
            en = unique_tail(cur, xt.split('\n\n')[-1])
            af = unique_tail(cur, anchor_text)
            if not (st and en and af):
                continue
            ev = {'question': '(i) reading order', 'page': rec['page'], 'para': num2para[x], 'order': perm,
                  'p_no': round(p_no, 4), 'departure_share': None if dc is None else round(dc, 4)}
            if not emit({'op': 'move', 'start': st, 'end': en, 'after': af, 'as': 'paragraph'}, 'order_move', ev):
                continue
            # rejoin a sentence the moved block now continues
            if i > 0 and ends_open(anchor_text) and starts_lower(xt):
                lt, rt = unique_tail(cur, anchor_text), content_head(cur, xt)
                if lt and rt:
                    emit({'op': 'join', 'left': lt, 'right': rt}, 'order_join', ev)
            # (the trial's rejoin of the sentence the block used to split was disabled; kept so)

    # ---- (iii) sentence continuation joins, (iv) heading markups
    for j in answers.get('joins', []):
        if not j.get('probs') or j['probs']['yes'] < t_plus:
            continue
        ta, tb = strip_markers(byid[j['a']]['text']), strip_markers(byid[j['b']]['text'])
        lt, rt = unique_tail(cur, ta.split('\n\n')[-1]), content_head(cur, tb.split('\n\n')[0])
        if veto and (pcls.get(j['a'], (0,))[0] >= 0.5 or pcls.get(j['b'], (0,))[0] >= 0.5):
            notes.append({'veto_join': [j['a'], j['b']]})
            continue
        if lt and rt:
            emit({'op': 'join', 'left': lt, 'right': rt}, 'join',
                 {'question': '(iii) sentence continues', 'paras': [j['a'], j['b']], 'p_yes': round(j['probs']['yes'], 4)})
    for h in answers.get('heads', []):
        if not h.get('probs') or h['probs']['yes'] < t_plus:
            continue
        if veto and pcls.get(h['para'], (0,))[0] >= 0.5:
            notes.append({'veto_heading': h['line'], 'class': pcls[h['para']][1]})
            continue
        lvl = h.get('level') or {'main': 0.0, 'sub': 1.0}
        if cur.count(h['line']) != 1:
            continue
        emit({'op': 'markup', 'text': h['line'], 'as': 'heading2' if lvl['main'] >= 0.5 else 'heading3'}, 'heading',
             {'question': '(iv) heading', 'para': h['para'], 'page': h['page'], 'p_yes': round(h['probs']['yes'], 4),
              'p_main': round(lvl['main'], 4)})
    return ops, kinds, notes, cur
