#!/usr/bin/env python3
"""Audit printed PDF lines against a Markdown copy, without altering either.

Usage: /usr/bin/python3 -I tools/conserve.py COPY_DIR PDF [--json PATH]
       [--evidence-dir BOXER_DIR]

pdftotext -bbox-layout supplies page/line/word coordinates. Only words covered
by the exporter's recorded furniture or figure-lettering runs are excluded;
there is no independent margin crop. Older copies use the same rule-6 furniture
and explicit float lettering evidence. Missing evidence never exempts a line.
Whitespace, Unicode compatibility forms and punctuation are ignored for word
conservation (this is not a value or table-placement score). A line must occur
in order inside one output paragraph/list/table, permitting intervening cell
text but not a search for its individual words across unrelated paragraphs.
Missing body lines and lines quoted only under uncertainty are distinguished.
Duplicate paragraphs include a whole paragraph repeated within a longer one.
Every finding retains its page, original text and box; nothing is truncated.
Standard library only. Exit 0 means the audit ran, not that it found no losses.
"""
import argparse
import bisect
import collections
import importlib.util
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import threading
import unicodedata
import xml.etree.ElementTree as ET

UNCERTAINTY = '## Places the program is not sure of'
_GEOMETRY_LOCK=threading.Lock()
CHECKER_CODE_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def token_ledger(text, runs):
    """Allocate output character occurrences, never reusable substring hits.

    Each source whitespace token has a stable page/run/token identity. A token
    is claimed at its own position first: a saved output span that still holds
    its letters ('hints', the recheck of a delivered copy), the copy units that
    cite its run ('anchors'), else its printed page's section of the copy; any
    other unclaimed occurrence is the fallback. Long intact runs claim their
    output first, as whole words; split/reordered runs then claim remaining
    whole words (or the unclaimed suffix of a joined word/URL). The two halves
    of one printed word (a line-end hyphen and the first token of the next
    line, or two runs on one baseline with no word space between) are matched
    together as that word. Unicode compatibility, case, accents and word-break
    punctuation use the same lexical normalization as the line audit.
    Punctuation-only tokens require literal ink, with the explicit Markdown
    bullet equivalence. This proves lexical multiplicity, not semantic
    placement or glyph values. Original tokens, output offsets and
    normalization are retained for review.
    """
    visible=re.sub(r'<!--.*?-->',lambda m:' '*len(m[0]),text,flags=re.S)
    key=[];positions=[]
    for i,ch in enumerate(visible):
        for c in normalise(ch):key.append(c);positions.append(i)
    key=''.join(key);used=bytearray(len(key));raw_used=set();records=[];groups=[]
    def key_range(span):
        return bisect.bisect_left(positions,span[0]),bisect.bisect_left(positions,span[1])
    sections=collections.defaultdict(list);start=0
    for marker in re.finditer(r'<!-- end of page (\d+) -->',text):
        sections[int(marker[1])].append(key_range((start,marker.start())));start=marker.end()
    for run in runs:
        group=[]
        for i,m in enumerate(re.finditer(r'\S+',run['text'])):
            rec=dict(page=run['page'],run=run['id'],token=i,text=m[0],box=run.get('box'),
                     key=normalise(m[0]),status='missing')
            group.append(len(records));records.append(rec)
        # Own positions, nearest first: the copy units citing the run, then
        # its printed page's section; 'any' is every unclaimed occurrence.
        windows=dict(anchor=[w for a in run.get('anchors') or () for w in [key_range(a)] if w[0]<w[1]],
                     page=[w for w in sections.get(run['page'],[]) if w[0]<w[1]])
        groups.append((run,group,windows))
    # A run the copy reports as not placed ('unplaced': read text not placed)
    # and no copy unit cites is proved only by its own page, never by an
    # occurrence anywhere.
    # A run some copy unit cites is placed, whatever else is reported.
    for run,_,windows in groups:
        windows['unplaced']=bool(run.get('unplaced')) and not windows['anchor']
    lexical=lambda group:[i for i in group if records[i]['key']]
    ends={}   # record index -> key index just after its claimed letters
    def joined(at, end):
        before=(at and (positions[at-1]+1==positions[at] or key[at].isdigit() and
            not re.search(r'\s',visible[positions[at-1]+1:positions[at]])))
        after=(end<len(key) and (positions[end-1]+1==positions[end] or key[end-1].isdigit() and
            not re.search(r'\s',visible[positions[end-1]+1:positions[end]])))
        return before,after
    def free(at, end):return 0<=at<=end<=len(key) and not any(used[at:end])
    def glued(cut):
        """No space in the copy between the letters before and after key index cut."""
        return 0<cut<len(key) and not re.search(r'\s',visible[positions[cut-1]+1:positions[cut]])
    def find(target, whole=False, lo=0, hi=None, before='', after='', ok=None):
        """The first unclaimed occurrence in key[lo:hi]. 'before'/'after' are
        the letters of the other half of the printed word, accepted as a join
        only where the copy prints them with no space between; 'ok' is a
        further test of the position."""
        hi=len(key) if hi is None else hi;start=lo
        while target:
            at=key.find(target,start,hi)
            if at<0:return None
            end=at+len(target);start=at+1
            if any(used[at:end]) or ok and not ok(at):continue
            if whole:
                # A short word cannot be proved by letters inside another
                # word. Already claimed neighbours prove a legitimate join.
                before_joined,after_joined=joined(at,end)
                if (before_joined and not used[at-1] and key[at-1].isdigit()==target[0].isdigit() and
                    not (before and key[max(0,at-len(before)):at]==before and free(at-len(before),at) and glued(at))):continue
                if (after_joined and not used[end] and key[end].isdigit()==target[-1].isdigit() and
                    not (after and key[end:end+len(after)]==after and free(end,end+len(after)) and glued(end))):continue
            return at
        return None
    def claim(i,at):
        rec=records[i];end=at+len(rec['key']);used[at:end]=b'\1'*(end-at);ends[i]=end
        rec.update(status='placed',output=[positions[at],positions[end-1]+1])
        raw_used.update(range(*rec['output']))
    TIERS=('anchor','page','any')
    def in_tier(target, windows, tier, **kw):
        if tier=='any':return None if windows.get('unplaced') else find(target,**kw)
        for a,b in windows[tier]:
            at=find(target,lo=a,hi=b,**kw)
            if at is not None:return at
        return None
    def own_then_any(target, windows, **kw):
        for tier in TIERS:
            at=in_tier(target,windows,tier,**kw)
            if at is not None:return at
        return None
    # A saved span (the recheck of a delivered copy) is a position, not proof:
    # its letters must still be there, unclaimed, as the token's whole key.
    for (run,group,_) in groups:
        for i,h in zip(group,run.get('hints') or ()):
            if not h or not records[i]['key']:continue
            lo,hi=key_range(h)
            if key[lo:hi]==records[i]['key'] and free(lo,hi):claim(i,lo)
    # The two halves of one printed word: a line-end hyphen continues on the
    # first token of the next printed line; two runs on one baseline with no
    # word space between are one word. The copy must hold them as one word.
    heads=collections.defaultdict(list)
    for gi,(run,group,_) in enumerate(groups):
        lx=lexical(group)
        if lx and run.get('box'):heads[run['page']].append((run['box'][1],gi,lx[0]))
    for v in heads.values():v.sort()
    column_boxes=collections.defaultdict(list)   # (bottom, x0, top, x1) of every run with a box
    for run,group,_ in groups:
        if run.get('box'):o=run['box'];column_boxes[run['page']].append((o[3],o[0],o[1],o[2]))
    for v in column_boxes.values():v.sort()
    def upright(run):
        """A run set sideways: its box much taller than wide for its letters."""
        o=run.get('box');n=len(run['text'].strip())
        return bool(o) and n>=2 and o[3]-o[1]>1.5*(o[2]-o[0])
    def one_word(left, right):
        start=0
        while True:
            at=key.find(left+right,start)
            if at<0:return False
            start=at+1;cut=at+len(left)
            if glued(cut) and find(left+right,whole=True,lo=at,hi=cut+len(right)) is not None:
                return True
    partner={};mate={};beside=[]   # beside: last token of a run and the head of the run just after it on its baseline
    for gi,(run,group,_) in enumerate(groups):
        lx=lexical(group);b=run.get('box')
        if not lx or not b or lx[-1] in partner:continue
        a=lx[-1];h=max(1,b[3]-b[1]);cy=(b[1]+b[3])/2;hyphen=records[a]['text'][-1] in '-‐‑­'
        page=heads.get(run['page'],[]);options=[]
        for top,gj,first in page[bisect.bisect_left(page,(b[1]-2*h,)):bisect.bisect_right(page,(b[3]+1.5*h,float('inf')))]:
            if gj==gi or first in mate:continue
            o=groups[gj][0]['box'];oh=max(1,o[3]-o[1])
            if abs((o[1]+o[3])/2-cy)<.4*max(h,oh):
                if -.3*h<=o[0]-b[2]<=h:options.append((0,o[0]-b[2],0,first));beside.append((a,first))
            elif hyphen and .5*h<o[1]-b[1] and o[1]-b[3]<1.5*h and o[0]<b[2]:options.append((1,o[1],o[0],first))
        if upright(run):
            # Sideways text (a rotated table or page): the same tests in the
            # frame of its reading direction, either way round.
            for turn in (lambda o:(-o[3],o[0],-o[1],o[2]),lambda o:(o[1],-o[2],o[3],-o[0])):
                tb=turn(b);th=max(1,tb[3]-tb[1]);tcy=(tb[1]+tb[3])/2
                for top,gj,first in page:
                    if gj==gi or first in mate or not upright(groups[gj][0]):continue
                    o=turn(groups[gj][0]['box']);oh=max(1,o[3]-o[1])
                    if abs((o[1]+o[3])/2-tcy)<.4*max(th,oh):
                        if -.3*th<=o[0]-tb[2]<=th:options.append((0,o[0]-tb[2],0,first))
                    elif hyphen and .5*th<o[1]-tb[1] and o[1]-tb[3]<1.5*max(th,oh) and o[0]<tb[2]:options.append((1,o[1],o[0],first))
        if hyphen:
            # A word broken at a column end continues on the top line of the
            # next column to the right: the line nearest the level of the top
            # of this column's block (the lines above this one without a
            # blank line between). A page end continues on the first lines of
            # the next page.
            top=b[1];boxes=column_boxes[run['page']]
            while True:
                lo=bisect.bisect_left(boxes,(top-h,));up=[o for o in boxes[lo:bisect.bisect_right(boxes,(top+.5*h,))]
                    if o[2]<top and o[1]<b[2] and o[3]>b[0]]
                if not up:break
                top=min(o[2] for o in up)
            options+=sorted((2,abs(t-top),groups[gj][0]['box'][0],first) for t,gj,first in page
                            if t<b[1] and groups[gj][0]['box'][0]>=b[2]-h and first not in mate)[:4]
            options+=[(3,t,groups[gj][0]['box'][0],first) for t,gj,first in heads.get(run['page']+1,[])
                      if first not in mate][:4]
        for *_,first in sorted(options):
            # The copy must hold the two halves as one whole word: no space
            # between them (a kept compound hyphen is not a space).
            if one_word(records[a]['key'],records[first]['key']):partner[a]=first;mate[first]=a;break
    def claim_partners(first, last):
        b=partner.get(last);a=mate.get(first)
        if b is not None and records[b]['status']=='missing':
            end=ends[last];n=len(records[b]['key'])
            if key[end:end+n]==records[b]['key'] and free(end,end+n) and glued(end):claim(b,end)
        if a is not None and records[a]['status']=='missing':
            at=ends[first]-len(records[first]['key']);n=len(records[a]['key'])
            if key[at-n:at]==records[a]['key'] and free(at-n,at) and glued(at):claim(a,at-n)
    def url_tail(run):return re.fullmatch(r'https?://\S+[-/._]',run['text'].strip())
    ordered=sorted(groups,key=lambda g:-len(normalise(g[0]['text'])))
    # First reserve contiguous source runs, at their own position and as whole
    # words. A repeated printed run requires another unclaimed occurrence,
    # even on the same page.
    def place_runs(tier):
        for run,group,windows in ordered:
            lx=lexical(group);pending=[i for i in lx if records[i]['status']=='missing']
            if len(pending)<2 or pending!=lx[lx.index(pending[0]):lx.index(pending[0])+len(pending)]:continue
            k=lx.index(pending[0]);lo=ends[lx[k-1]] if k else 0
            target=''.join(records[i]['key'] for i in pending)
            kw=dict(whole=True,before=records[mate[pending[0]]]['key'] if pending[0] in mate else '',
                    after=records[partner[pending[-1]]]['key'] if pending[-1] in partner else '')
            at=None
            if lo:at=find(target,lo=lo,hi=min(len(key),lo+len(target)+8),**kw)
            if at is None:
                at=in_tier(target,windows,tier,**kw)
            if at is None:continue
            for i in pending:claim(i,at);at+=len(records[i]['key'])
            claim_partners(pending[0],pending[-1])
    # Runs joined by a broken word form one chain (the lines of a hyphenated
    # passage); a chain is claimed whole first, so neither half can take the
    # other half of a similar word elsewhere.
    group_of={i:gi for gi,(_,group,_) in enumerate(groups) for i in group}
    following={group_of[x]:group_of[y] for x,y in partner.items()}
    chains=[]
    for gi in following:
        if gi in following.values():continue
        chain=[gi]
        while chain[-1] in following and following[chain[-1]] not in chain:chain.append(following[chain[-1]])
        chains.append(chain)
    chains.sort(key=lambda ch:-sum(len(records[i]['key']) for gi in ch for i in groups[gi][1]))
    def place_chains(tier, lines):
        # lines: only chains of runs that each hold two words or more (lines
        # of a passage, each a strong witness); otherwise the other chains.
        for chain in chains:
            if lines!=all(len(lexical(groups[gi][1]))>=2 for gi in chain):continue
            members=[i for gi in chain for i in lexical(groups[gi][1])]
            if any(records[i]['status']!='missing' for i in members):continue
            # Offsets of the joins (the start of each continuation) in the chain's letters.
            joins=[sum(len(records[i]['key']) for i in members[:members.index(b)]) for b in members if b in mate]
            at=in_tier(''.join(records[i]['key'] for i in members),groups[chain[0]][2],tier,whole=True,
                       ok=lambda at:all(glued(at+j) for j in joins))
            if at is None:continue
            for i in members:claim(i,at);at+=len(records[i]['key'])
    def place_unbounded(tier):
        # A run printed with joined numbers ('1113-1123' ranges, decimals)
        # cannot meet the whole-word test; an intact run still proves itself.
        # The rest of a run whose first words were claimed with the other
        # half of a broken word must follow those words directly.
        for run,group,windows in ordered:
            lx=lexical(group);pending=[i for i in lx if records[i]['status']=='missing']
            if not pending or pending!=lx[lx.index(pending[0]):lx.index(pending[0])+len(pending)]:continue
            # Reserve complete words before isolated digits/letters. Otherwise a
            # separate footnote '1' can steal the suffix of an author's 'Name1'.
            if len(group)==1 and not url_tail(run):continue
            target=''.join(records[i]['key'] for i in pending);k=lx.index(pending[0])
            whole=sum(bool(records[i]['key']) for i in group)<2 and not url_tail(run)
            if len(pending)<len(lx):
                if not k:continue
                at=find(target,lo=ends[lx[k-1]],hi=min(len(key),ends[lx[k-1]]+len(target)+8),whole=whole)
            else:at=in_tier(target,windows,tier,whole=whole)
            if at is None:continue
            for i in pending:claim(i,at);at+=len(records[i]['key'])
            claim_partners(pending[0],pending[-1])
    def place_glyph_rows():
        # Some PDFs paint one character per run in content-stream order. A long
        # same-baseline sequence in native x order supplies an intact-run witness
        # for those characters without pretending each is a separate output word.
        glyph_rows=[]
        for i in sorted((i for i,r in enumerate(records) if len(r['text'])==1 and r['box'] and r['status']=='missing'),
                        key=lambda i:(records[i]['page'],records[i]['box'][1],records[i]['box'][0])):
            rec=records[i];b=rec['box'];h=max(1,b[3]-b[1]);cy=(b[1]+b[3])/2
            row=next((g for g in glyph_rows[-4:] if g[0]==rec['page'] and abs(g[1]-cy)<.4*max(g[2],h)),None)
            if row is None:glyph_rows.append([rec['page'],cy,h,[i]])
            else:row[3].append(i)
        for _,_,h,row in glyph_rows:
            chunks=[]
            for i in sorted(row,key=lambda i:records[i]['box'][0]):
                if not chunks or records[i]['box'][0]-records[chunks[-1][-1]]['box'][2]>1.5*h:chunks.append([])
                chunks[-1].append(i)
            for chunk in chunks:
                target=''.join(records[i]['key'] for i in chunk)
                if len(target)<12:continue
                at=find(target)
                if at is None:continue
                for i in chunk:
                    if records[i]['key']:claim(i,at);at+=len(records[i]['key'])
    def place_pairs(tier):
        # Both halves of one printed word still free: claim them together.
        for a,b in partner.items():
            if records[a]['status']!='missing' or records[b]['status']!='missing':continue
            at=in_tier(records[a]['key']+records[b]['key'],window_of[a],tier,whole=True,ok=lambda at,n=len(records[a]['key']):glued(at+n))
            if at is not None:claim(a,at);claim(b,at+len(records[a]['key']))
    def place_words(tier):
        for i in sorted(range(len(records)),key=lambda i:-len(records[i]['key'])):
            rec=records[i]
            if rec['status']=='placed' or not rec['key']:continue
            at=in_tier(rec['key'],window_of[i],tier,whole=True)
            if at is not None:claim(i,at)
    # Every kind of claim is tried at the nearest positions first: a token
    # takes an occurrence elsewhere only after every token has been tried
    # at its own unit and then at its own page.
    def place_halves_alone(tier):
        # A half the copy prints as a word of its own (a kept line-end break
        # such as 'maxi- mal') is claimed there, not as part of a joined word.
        for i in sorted(set(partner)|set(mate),key=lambda i:-len(records[i]['key'])):
            if records[i]['status']!='missing':continue
            k=records[i]['key'];b=records[partner[i]]['key'] if i in partner else None;a=records[mate[i]]['key'] if i in mate else None
            # Not where the other half follows (or precedes) with no space: that is the joined word.
            def alone(at,k=k,a=a,b=b):
                end=at+len(k)
                return not (b and key[end:end+len(b)]==b and glued(end)) and not (a and key[max(0,at-len(a)):at]==a and glued(at))
            at=in_tier(k,window_of[i],tier,whole=True,ok=alone)
            if at is not None:claim(i,at)
    window_of={i:windows for run,group,windows in groups for i in group}
    # Pure numbers (tokens with digits and no letters: '12', '0.005', '(4.1)',
    # '1.27-9.24') of a cited run that holds only such tokens are claimed whole
    # in the citing unit first: inside a table unit the counts decide, not which
    # equal number comes first. A token mixing letters and digits ('n=1M',
    # '23andMe's', '3mm') is not a number here and keeps the ordinary passes.
    # A number counts as present where the copy prints it as one number:
    # - inside: printed mark for mark as the token prints it, so no cell bar
    #   or space ('32.4' is not '3) | 24', '20/16' is not '2016');
    # - its printed form: the token's own leading and trailing signs, brackets
    #   or dashes are matched with it ('-0.33)', '(-0.71–');
    # - the marks the copier adds around digits are not the token's: raised
    #   citations in square brackets ('2008)26,45' printed '2008)[26,45]'),
    #   powers '^' and lowered digits '_';
    # - outside that form, on each side: a space, a bar, or the text's edge,
    #   or marks that reach no letter or digit beyond them; marks glued to a
    #   word or number beyond them join ('12' is not in 'IL-12', '38' not in
    #   '(N=38)', '13' not in '99:13–19', '2008' not in '(2008)[26,45]');
    # - except a range split between two tokens: a token printed with its own
    #   leading sign after a range dash ('-0.33)' in '(-0.71–-0.33)'), or the
    #   token's own trailing dash before a digit ('2007;77:542–' before '548');
    #   a bare number after a range dash is the range's end, not that number
    #   ('43.' is not in '37–43.');
    # - no word beside it across one space ('3 mm', 'Grade 3').
    numbers=[i for run,group,windows in groups if windows['anchor'] and lexical(group)
             and all(records[i]['key'].isdigit() for i in lexical(group)) for i in lexical(group)]
    DASHES='-\u2010\u2011\u2012\u2013\u2014\u2212'
    same=lambda x,y:x==y or x in DASHES and y in DASHES
    INSERTED='[]^_'   # marks the copier adds around digits: raised citations '[26,45]', powers '10^5', lowered '_2'
    def touches(k, step):
        # Walk over the marks touching the number on one side (no space, no bar); glued when they reach a
        # letter or digit (an unread glyph counts as a letter).
        while 0<=k<len(visible) and not visible[k].isspace() and visible[k]!='|' and not visible[k].isalnum() and visible[k]!='\ufffd':
            k+=step
        return 0<=k<len(visible) and (visible[k].isalnum() or visible[k]=='\ufffd')
    def alone_number(at, end, text):
        a,z=positions[at],positions[end-1]+1
        inner=visible[a:z]
        if '|' in inner or re.search(r'\s',inner):return False
        lead=re.match(r'[^\w]*',text)[0];trail=re.search(r'[^\w]*$',text)[0]
        core=text[len(lead):len(text)-len(trail)]
        # printed as the token prints it, mark for mark ('20/16' is not '2016'), apart from the marks the
        # copier inserts around digits ('2008)26,45' printed '2008)[26,45]')
        shown=''.join(ch for ch in inner if ch not in INSERTED or ch in core)
        if len(core)!=len(shown) or not all(same(x,y) for x,y in zip(core,shown)):return False
        while z<len(visible) and visible[z] in INSERTED and visible[z] not in core:z+=1
        own=bool(lead) and len(lead)<=a and all(same(x,y) for x,y in zip(visible[a-len(lead):a],lead))
        if own:a-=len(lead)
        if trail and len(visible[z:z+len(trail)])==len(trail) and all(same(x,y) for x,y in zip(visible[z:z+len(trail)],trail)):z+=len(trail)
        form=visible[a:z]
        # left: nothing glued, except a range split between tokens (own sign after a range dash)
        if touches(a-1,-1) and not (own and visible[a-1:a] in DASHES and visible[a-2:a-1].isdigit()):return False
        # right: nothing glued, except the token's own trailing range dash before the next number
        if touches(z,1) and not (form[-1:] in DASHES and visible[z:z+1].isdigit()):return False
        return not re.search(r'[^\W\d_]\s$',visible[max(0,a-3):a]) and not re.match(r'\s[^\W\d_]',visible[z:z+3])
    for i in sorted(numbers,key=lambda i:-len(records[i]['key'])):
        if records[i]['status']!='missing':continue
        k=records[i]['key']
        at=in_tier(k,window_of[i],'anchor',ok=lambda at,n=len(k),t=records[i]['text']:alone_number(at,at+n,t))   # its edges are tested here
        if at is not None:claim(i,at)
    for tier in ('anchor','page'):
        place_chains(tier,True);place_runs(tier);place_unbounded(tier)
        place_chains(tier,False);place_pairs(tier);place_halves_alone(tier);place_words(tier)
    place_chains('any',True);place_runs('any');place_unbounded('any');place_glyph_rows()
    place_chains('any',False);place_pairs('any');place_halves_alone('any');place_words('any')
    # A word split in the source by a letter with a diacritic it could not
    # encode ('Echeverr' 'a') is present when the copy holds the word with
    # that letter recovered ('Echeverría'): the other token's letters follow
    # (or precede) after one or two copy letters carrying a diacritic.
    def accented(j):return j<len(key) and ord(visible[positions[j]])>127 and normalise(visible[positions[j]])!=visible[positions[j]].casefold()
    def word_end(end):return end>=len(key) or not (positions[end-1]+1==positions[end] and not used[end])
    neighbours=[p for run,group,windows in groups for p in zip(lexical(group),lexical(group)[1:])]+beside
    def accent_word(x, y):
        # Both tokens unclaimed: the citing unit (the page if none cites the
        # run) holds an
        # unclaimed word made of x's letters, one or two letters carrying a
        # diacritic, then y's letters, with nothing else between.
        kx,ky=records[x]['key'],records[y]['key']
        for tier in (('anchor',) if window_of[x]['anchor'] else ('page',)):
            for lo,hi in window_of[x][tier]:
                at=key.find(kx,lo,hi)
                while 0<=at:
                    for skip in (1,2):
                        j=at+len(kx);end=j+skip+len(ky)
                        if (end<=hi and all(accented(j+k) for k in range(skip)) and key[j+skip:end]==ky and free(at,end)
                                and all(positions[q]+1==positions[q+1] for q in range(at,j+skip))
                                and (not at or positions[at-1]+1!=positions[at] or used[at-1]) and word_end(end)):
                            return at,j+skip
                    at=key.find(kx,at+1,hi)
        return None
    for x,y in neighbours:
            ax,ay=records[x],records[y]
            if ax['status']=='missing' and ay['status']=='missing' and ax['key'] and ay['key']:
                hit=accent_word(x,y)
                if hit:claim(x,hit[0]);claim(y,hit[1])
                continue
            if (ax['status']=='placed')==(ay['status']=='placed'):continue
            if ax['status']=='placed':
                j=ends[x]
                for skip in (1,2):
                    if all(accented(j+k) for k in range(skip)) and key[j+skip:j+skip+len(ay['key'])]==ay['key'] \
                       and free(j+skip,j+skip+len(ay['key'])) and word_end(j+skip+len(ay['key'])):claim(y,j+skip);break
            else:
                b=ends[y]-len(ay['key'])
                for skip in (1,2):
                    at=b-skip-len(ax['key'])
                    if at>=0 and all(accented(b-skip+k) for k in range(skip)) and key[at:at+len(ax['key'])]==ax['key'] \
                       and free(at,at+len(ax['key'])) and (not at or not positions[at-1]+1==positions[at] or used[at-1]):claim(x,at);break
    # Punctuation-only tokens have no lexical characters. Keep a literal
    # occurrence ledger too, so isolated signs cannot silently disappear.
    for rec in records:
        if rec['key']:continue
        choices=[rec['text']]
        if rec['text'] in ('•','●','◦'):choices.append('-')
        for target in choices:
            pattern=''.join((r'\\?' if ch in '*_<>[]()#|' else '')+re.escape(ch) for ch in target)
            match=next((m for m in re.finditer(pattern,visible) if not any(i in raw_used for i in range(*m.span()))),None)
            if match:
                rec.update(status='placed',output=list(match.span()))
                raw_used.update(range(*match.span()));break
    # The Authors line writes the parsed names joined by '; '. A joiner the
    # author parse consumes between names (rule 8's separators and
    # conjunction) is not lost text when it stands between two tokens of its
    # byline run that the Authors line holds.
    if any(run.get('byline') for run,_,_ in groups):
        joiners=name_joiners()
        # The byline's tokens in printed order across its runs (lines top to
        # bottom, runs left to right), so a joiner opening a run sits between
        # the name ending the run before it and the name after it.
        bylines=collections.defaultdict(list)
        for run,group,windows in groups:
            if run.get('byline') and run.get('box'):bylines[run['page']].append((run,group,windows))
        for page_runs in bylines.values():
            h=sorted(max(1,r['box'][3]-r['box'][1]) for r,_,_ in page_runs)[len(page_runs)//2]
            page_runs.sort(key=lambda g:(round((g[0]['box'][1]+g[0]['box'][3])/2/h),g[0]['box'][0]))
            seq=[(i,windows) for run,group,windows in page_runs for i in group]
            held=lambda i,w:records[i]['status']=='placed' and any(positions[a]<=records[i]['output'][0] and records[i]['output'][1]<=positions[b-1]+1
                                                                  for a,b in w['anchor'])
            for k,(i,windows) in enumerate(seq):
                rec=records[i]
                if rec['status']!='missing' or rec['text'] not in joiners:continue
                before=[q for q in seq[:k] if records[q[0]]['key']];after=[q for q in seq[k+1:] if records[q[0]]['key']]
                if before and after and held(*before[-1]) and held(*after[0]):
                    rec.update(status='joined',reason='consumed by the Authors line join between two names')
    extra=[]
    for run,group,_ in sorted(groups,key=lambda g:-len(normalise(g[0]['text']))):
        target=normalise(run['text'])
        if len(target)<20 or len(words(run['text']))<3:continue
        at=find(target,whole=True)
        while at is not None:
            end=at+len(target);used[at:end]=b'\1'*(end-at)
            extra.append(dict(page=run['page'],run=run['id'],text=run['text'],
                              output=[positions[at],positions[end-1]+1]))
            at=find(target,whole=True)
    for rec in records:rec.pop('key')
    return dict(version=1,normalization='NFKD casefold alphanumeric; literal isolated punctuation',
                source_tokens=len(records),placed_tokens=sum(r['status']=='placed' for r in records),
                missing_tokens=sum(r['status']=='missing' for r in records),tokens=records,
                extra_run_occurrences=extra)


def legacy_token_ledger(text, runs):
    """The ledger of bdb3542, unchanged, kept only to decide which runs the native trace may count as held in the
    uncertainty list (copy_paper). Its allocation is not the checker's: token_ledger writes the list items.

    Allocate output character occurrences, never reusable substring hits.

    Each source whitespace token has a stable page/run/token identity. Long
    intact runs claim their output first; split/reordered runs then claim
    remaining whole words (or the unclaimed suffix of a joined word/URL).
    Unicode compatibility, case, accents and word-break punctuation use the
    same lexical normalization as the line audit. Punctuation-only tokens
    require literal ink, with the explicit Markdown bullet equivalence.
    This proves lexical multiplicity, not semantic placement or glyph values.
    Original tokens, output offsets and normalization are retained for review.
    """
    visible=re.sub(r'<!--.*?-->',lambda m:' '*len(m[0]),text,flags=re.S)
    key=[];positions=[]
    for i,ch in enumerate(visible):
        for c in normalise(ch):key.append(c);positions.append(i)
    key=''.join(key);used=bytearray(len(key));raw_used=set();records=[];groups=[]
    for run in runs:
        group=[]
        for i,m in enumerate(re.finditer(r'\S+',run['text'])):
            rec=dict(page=run['page'],run=run['id'],token=i,text=m[0],box=run.get('box'),
                     key=normalise(m[0]),status='missing')
            group.append(len(records));records.append(rec)
        groups.append((run,group))
    def find(target, whole=False):
        start=0
        while target:
            at=key.find(target,start)
            if at<0:return None
            end=at+len(target);start=at+1
            if any(used[at:end]):continue
            if whole:
                # A short word cannot be proved by letters inside another
                # word. Already claimed neighbours prove a legitimate join.
                before_joined=(at and (positions[at-1]+1==positions[at] or target[0].isdigit() and
                    not re.search(r'\s',visible[positions[at-1]+1:positions[at]])))
                after_joined=(end<len(key) and (positions[end-1]+1==positions[end] or target[-1].isdigit() and
                    not re.search(r'\s',visible[positions[end-1]+1:positions[end]])))
                if (before_joined and not used[at-1]
                    and key[at-1].isdigit()==target[0].isdigit()):continue
                if (after_joined and not used[end]
                    and key[end].isdigit()==target[-1].isdigit()):continue
            return at
        return None
    def claim(rec,at):
        end=at+len(rec['key']);used[at:end]=b'\1'*(end-at)
        rec.update(status='placed',output=[positions[at],positions[end-1]+1])
        raw_used.update(range(*rec['output']))
    # First reserve contiguous source runs. A repeated printed run requires
    # another unclaimed occurrence, even on the same page.
    for run,group in sorted(groups,key=lambda g:-len(normalise(g[0]['text']))):
        target=''.join(records[i]['key'] for i in group)
        if not target:continue
        # Reserve complete words before isolated digits/letters. Otherwise a
        # separate footnote '1' can steal the suffix of an author's 'Name1'.
        if len(group)==1 and not re.fullmatch(r'https?://\S+[-/._]',run['text'].strip()):continue
        at=find(target,whole=sum(bool(records[i]['key']) for i in group)<2 and
                not re.fullmatch(r'https?://\S+[-/._]',run['text'].strip()))
        if at is None:continue
        for i in group:
            rec=records[i]
            if rec['key']:claim(rec,at);at+=len(rec['key'])
    # Some PDFs paint one character per run in content-stream order. A long
    # same-baseline sequence in native x order supplies an intact-run witness
    # for those characters without pretending each is a separate output word.
    glyph_rows=[]
    for rec in sorted((r for r in records if len(r['text'])==1 and r['box'] and r['status']=='missing'),
                      key=lambda r:(r['page'],r['box'][1],r['box'][0])):
        b=rec['box'];h=max(1,b[3]-b[1]);cy=(b[1]+b[3])/2
        row=next((g for g in glyph_rows[-4:] if g[0]==rec['page'] and abs(g[1]-cy)<.4*max(g[2],h)),None)
        if row is None:glyph_rows.append([rec['page'],cy,h,[rec]])
        else:row[3].append(rec)
    for _,_,h,row in glyph_rows:
        chunks=[]
        for rec in sorted(row,key=lambda r:r['box'][0]):
            if not chunks or rec['box'][0]-chunks[-1][-1]['box'][2]>1.5*h:chunks.append([])
            chunks[-1].append(rec)
        for chunk in chunks:
            target=''.join(r['key'] for r in chunk)
            if len(target)<12:continue
            at=find(target)
            if at is None:continue
            for rec in chunk:
                if rec['key']:claim(rec,at);at+=len(rec['key'])
    for rec in sorted(records,key=lambda r:-len(r['key'])):
        if rec['status']=='placed' or not rec['key']:continue
        at=find(rec['key'],whole=True)
        if at is not None:claim(rec,at)
    # Punctuation-only tokens have no lexical characters. Keep a literal
    # occurrence ledger too, so isolated signs cannot silently disappear.
    for rec in records:
        if rec['key']:continue
        choices=[rec['text']]
        if rec['text'] in ('•','●','◦'):choices.append('-')
        for target in choices:
            pattern=''.join((r'\\?' if ch in '*_<>[]()#|' else '')+re.escape(ch) for ch in target)
            match=next((m for m in re.finditer(pattern,visible) if not any(i in raw_used for i in range(*m.span()))),None)
            if match:
                rec.update(status='placed',output=list(match.span()))
                raw_used.update(range(*match.span()));break
    extra=[]
    for run,group in sorted(groups,key=lambda g:-len(normalise(g[0]['text']))):
        target=normalise(run['text'])
        if len(target)<20 or len(words(run['text']))<3:continue
        at=find(target,whole=True)
        while at is not None:
            end=at+len(target);used[at:end]=b'\1'*(end-at)
            extra.append(dict(page=run['page'],run=run['id'],text=run['text'],
                              output=[positions[at],positions[end-1]+1]))
            at=find(target,whole=True)
    for rec in records:rec.pop('key')
    return dict(version=1,normalization='NFKD casefold alphanumeric; literal isolated punctuation',
                source_tokens=len(records),placed_tokens=sum(r['status']=='placed' for r in records),
                missing_tokens=sum(r['status']=='missing' for r in records),tokens=records,
                extra_run_occurrences=extra)


def legacy_unreported(body, saved, payloads):
    """(page, run) of the earlier ledger's unverified tokens on the delivered body that the earlier list items do
    not quote: the runs the earlier audit recheck told the native trace about (copy_paper.conserve_pdf_copy)."""
    groups=collections.defaultdict(list)
    for token in saved['token_ledger']['tokens']:
        if token['status']!='excluded':groups[token['page'],token['run']].append(token)
    runs=[dict(page=page,id=mid,text=' '.join(t['text'] for t in sorted(tokens,key=lambda t:t['token'])),box=tokens[0].get('box'))
          for (page,mid),tokens in groups.items()]
    missing=[t for t in legacy_token_ledger(body,runs)['tokens'] if t['status']=='missing']
    report=legacy_token_ledger('\n\n'.join(payloads),[dict(page=t['page'],id=str(i),text=t['text'],box=t.get('box'))
                                                       for i,t in enumerate(missing)])
    quoted={int(t['run']) for t in report['tokens'] if t['status']=='placed'}
    return list(dict.fromkeys((t['page'],t['run']) for i,t in enumerate(missing) if i not in quoted))


def name_joiners():
    """The joiners rule 8's author parse consumes between names, read from the boxer itself."""
    with _GEOMETRY_LOCK:
        reader=sys.modules.get('_copy_table_reader') or sys.modules.get('_conserve_geometry')
        if reader is None:
            spec=importlib.util.spec_from_file_location('_conserve_geometry',Path(__file__).resolve().parents[1]/'standalone/element_boxer_sc.py')
            reader=importlib.util.module_from_spec(spec);sys.modules['_conserve_geometry']=reader;spec.loader.exec_module(reader)
    return set(reader.NAME_CONJUNCTIONS)|set(reader.NAME_SEPARATORS)


def normalise(text):
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    return ''.join(c for c in unicodedata.normalize('NFKD', text).casefold() if c.isalnum())


def words(text):
    text=text.translate(dict.fromkeys(map(ord,'\u200b\ufeff\u00ad')))
    text=''.join(c for c in unicodedata.normalize('NFKD', text).casefold() if not unicodedata.combining(c))
    return re.findall(r'[^\W_]+', text)


class CopyIndex:
    """Keep paragraph boundaries while allowing typography and cell wrapping."""
    def __init__(self, text):
        # Adjacent Markdown table rows/list lines are a single local region.
        self.parts = [normalise(p) for p in re.split(r'\n\s*\n', text) if normalise(p)]
        self.whole = ''.join(self.parts)
        self.numbers=set(re.findall(r'\d+',unicodedata.normalize('NFKC',text).translate(dict.fromkeys(map(ord,'\u200b\ufeff\u00ad')))))
        self.pages = {}
        start=0;last='';previous=''
        for marker in re.finditer(r'<!-- end of page (\d+) -->',text):
            chunk=text[start:marker.start()].strip()
            # Consecutive page markers follow a paragraph spanning pages.
            if not normalise(chunk):chunk=last
            else:last=chunk
            self.pages[int(marker[1])] = CopyIndex(previous+'\n\n'+chunk) if chunk else None
            paragraphs=[p for p in re.split(r'\n\s*\n',chunk) if normalise(p)]
            previous=chunk
            start=marker.end()

    def contains(self, text, page=None):
        tokens=words(text)
        if sum(any(ch.isalpha() for ch in token) for token in tokens)>=2 and normalise(text) in self.whole:
            return True
        # Long sentences can legitimately cross several intervening float
        # pages before their end marker. Short cells/labels need local page
        # evidence so a year in the references cannot hide a lost table row.
        if page in self.pages and self.pages[page] is not None and len(tokens)<4:
            return self.pages[page].contains(text)
        target = normalise(text)
        if (re.fullmatch(r'\d+(?:\s+\d+)*',text.strip()) and target not in self.numbers
                and any(token not in self.numbers for token in tokens)):return False
        if not target: return True
        # Joining at a page marker or a paragraph boundary can split a source
        # line; exact contiguous letters still prove conservation.
        if target in self.whole: return True
        tokens = words(text)
        if len(tokens) < 2: return False
        for part in self.parts:
            start = part.find(tokens[0])
            while start >= 0:
                end = start + len(tokens[0])
                for token in tokens[1:]:
                    at = part.find(token, end)
                    if at < 0: break
                    end = at + len(token)
                else: return True
                start = part.find(tokens[0], start+1)
        return False


def duplicate_paragraphs(text):
    body = text.split(UNCERTAINTY)[0]
    # Printed table rows are not prose paragraphs. The explicit gate count
    # bounds its payload even when a real list follows without a blank line.
    lines=body.splitlines();kept=[];remaining=0
    for line in lines:
        gate=re.match(r'\[table structure not recovered: (\d+) printed lines',line)
        if gate:remaining=int(gate[1]);continue
        if remaining and line.startswith('- '):remaining-=1;continue
        kept.append(line)
    body='\n'.join(kept)
    # A list line is also a paragraph, including individual references.
    entries = []
    for piece in re.split(r'\n\s*\n|\n(?=[ >]*[-*] )', body):
        clean = re.sub(r'<!--.*?-->', '', piece, flags=re.S).strip()
        if not clean or clean.startswith(('#', '|', '[table structure')): continue
        key = normalise(clean)
        if not key: continue
        entries.append((clean, key))
    findings = []; seen = set()
    for index,(text,key) in enumerate(entries):
        if key in seen: continue
        hits = [i+1 for i,(_,other) in enumerate(entries) if key in other]
        occurrences = sum(other.count(key) for _,other in entries)
        if occurrences > 1:
            findings.append(dict(paragraph=index+1, text=text, occurrences=occurrences,
                                 in_paragraphs=hits))
            seen.add(key)
    return findings


def placed_tables(body, evidence):
    """Locate actual copy tables by unique complete caption and source frame.

    Floats may be anchored before an intervening image-only page. Their copy
    page markers then differ from the printed page; a matching caption gives
    stronger local evidence than searching unrelated prose for short cells.
    """
    path=Path(evidence)/'copy.tables.json'
    if not path.exists():return []
    parts=re.split(r'\n\s*\n',body);keys=[normalise(p) for p in parts];found=[]
    for table in json.loads(path.read_text()).get('tables',[]):
        key=normalise(table.get('caption',''));frame=(table.get('region_coverage') or {}).get('frame')
        if len(key)<20 or not frame or keys.count(key)!=1:continue
        i=keys.index(key)+1;payload=[]
        while i<len(parts) and parts[i].lstrip().startswith(('|','[table structure not recovered:','- ')):
            payload.append(parts[i]);i+=1
        if payload:found.append((table['page'],frame,CopyIndex('\n\n'.join(payload))))
    return found


def exclusions(page):
    """Use final exporter ownership if present; otherwise explicit boxer IDs."""
    recorded = page.get('copy_conservation')
    if recorded is not None:
        excluded=recorded.get('excluded', [])
        # Recorded furniture is evidence, not an exemption from validation.
        # A wrapped numeric URL tail inside the original URL block has a
        # content witness even when an older exporter called it a folio.
        runs={e['id']:e for e in page.get('elements',[]) if e['kind']=='text'}
        tails=set()
        for item in excluded:
            e=runs.get(item.get('id'))
            if not e or not re.fullmatch(r'\d{1,8}[Xx]?',e['text'].strip()):continue
            em=e.get('run_size_px',16);eb=e['box_px']
            if any(abs(eb[0]-b['box_px'][0])<em and any(
                   re.search(r'https?://\S+[-/._]$',runs[m]['text'].strip()) and
                   0<=eb[1]-runs[m]['box_px'][3]<1.5*em
                   for m in b['members'] if m in runs)
                   for b in page.get('blocks',[]) if e['id'] in b['members']):tails.add(e['id'])
        return [dict(e, angle=runs[e['id']].get('angle', 0)) if e.get('id') in runs else e
                for e in excluded if e.get('id') not in tails]
    es = {e['id']:e for e in page.get('elements',[]) if e['kind']=='text'}
    reasons = {}
    for f in (page.get('main_text') or {}).get('furniture',[]):
        for m in f['members']: reasons[m] = f['why']
    for f in page.get('floats',[]):
        for m in f.get('lettering',[]): reasons.setdefault(m, 'figure lettering')
    for m in page.get('copy_figure_lettering',[]): reasons.setdefault(m, 'figure lettering')
    for e in page.get('copy_omitted',[]):
        if not e.get('after'): reasons[e['run']] = e['why']
    return [dict(id=m, text=es[m]['text'], box=es[m]['box_px'], reason=why, angle=es[m].get('angle', 0))
            for m,why in reasons.items() if m in es]


def baseline_evidence(page):
    """Re-evaluate old ownership using today's exporter, entirely in memory.

    A legacy figure frame can swallow an adjacent table. Let the same caption
    and shaded-row rules used by the copy reclaim it before excluding letters.
    Band-only footer decisions need the same local column-continuation veto;
    a detached reference URL likewise retains its printed baseline peers.
    """
    global _exporter
    if '_exporter' not in globals():
        spec=importlib.util.spec_from_file_location('_conserve_copy',Path(__file__).resolve().parents[1]/'copy_paper.py')
        _exporter=importlib.util.module_from_spec(spec);spec.loader.exec_module(_exporter)
    mt=page.get('main_text') or {}; body=mt.get('body_size_px') or 16
    runs={e['id']:e for e in page.get('elements',[]) if e['kind']=='text'}
    released=set()
    for f in mt.get('furniture',[]):
        for m in f['members']:
            if m not in runs:continue
            e=runs[m];b=e['box_px'];size=e.get('run_size_px',body)
            if f.get('why')=='inside the recurring footer band':
                if any(x['id']!=m and x.get('angle',0)==0 and
                       0<=b[1]-x['box_px'][3]<body and
                       min(b[2],x['box_px'][2])-max(b[0],x['box_px'][0])>body and
                       abs(size-x.get('run_size_px',body))<.1*size for x in runs.values()):released.add(m)
            if f.get('why')=='DOI or URL outside the page text frame' and page['page']>1:
                if any(x['id']!=m and x.get('angle',0)==0 and
                       abs((x['box_px'][1]+x['box_px'][3]-b[1]-b[3])/2)<.4*size and
                       0<=max(b[0]-x['box_px'][2],x['box_px'][0]-b[2])<4*size and
                       len(words(x['text']))>=2 for x in runs.values()):released.add(m)
    if released:
        mt['furniture']=[dict(f,members=[m for m in f['members'] if m not in released]) for f in mt.get('furniture',[])]
        for b in mt.get('blocks',[]):
            if b.get('cls')=='furniture' and any(released.intersection(x['members']) for x in page['blocks'] if x['id']==b['id']):
                b['cls']='other'
    _exporter.recover_table_frame_furniture([page])
    _exporter.read_page(page,body,[])
    return page


def pdf_lines(pdf):
    result = subprocess.run(['pdftotext','-bbox-layout','-enc','UTF-8',str(pdf),'-'],
                            capture_output=True, check=True, timeout=180)
    # Poppler can emit literal PDF control characters into its XHTML.
    # They have no printed word value and are illegal in XML 1.0.
    xml = re.sub('[\x00-\x08\x0b\x0c\x0e-\x1f]', '', result.stdout.decode('utf-8',errors='replace'))
    root = ET.fromstring(xml)
    tag = lambda e:e.tag.rsplit('}',1)[-1]
    for number,page in enumerate((e for e in root.iter() if tag(e)=='page'),1):
        for line in (e for e in page.iter() if tag(e)=='line'):
            ws = [dict(text=''.join(w.itertext()), box=[float(w.get(k)) for k in ('xMin','yMin','xMax','yMax')])
                  for w in line if tag(w)=='word']
            if ws: yield number, float(page.get('width')), float(page.get('height')), ws


def covered(word, excluded, sx, sy):
    """The reason of the excluded run that holds this Poppler word, or None.

    An upright excluded run holds the words its box covers. A rotated or
    oblique one (a sideways or diagonal watermark) holds only its own words:
    its box spans body text it never contained, so a word under it is held
    only when its text is the run's (glyph identity, never region; AI03)."""
    a = word.get('native_box')
    if a is None:
        a=word['box'];a=[a[0]*sx,a[1]*sy,a[2]*sx,a[3]*sy]
    area = max(.01,(a[2]-a[0])*(a[3]-a[1]))
    for e in excluded:
        b = e['box']
        overlap = max(0,min(a[2],b[2])-max(a[0],b[0]))*max(0,min(a[3],b[3])-max(a[1],b[1]))
        if overlap/area > .45 and (not round(e.get('angle', 0)) % 360 or
                                   normalise(word['text']) and normalise(word['text']) in normalise(e['text'])): return e['reason']
        # Poppler includes trailing space advances in some word boxes. The
        # printed word and its leading position still match the native run.
        if (normalise(word['text']) and normalise(word['text']) in normalise(e['text'])
                and max(0,min(a[3],b[3])-max(a[1],b[1]))>.3*(a[3]-a[1])
                and b[0]-2<=a[0]<=b[2]+2):return e['reason']
    return None


def visible_word(word, excluded, sx, sy):
    """Separate a visible word from a proven invisible suffix joined by Poppler.

    Only exact text at the start of a white-rendered omitted run qualifies,
    and its geometric boundary must lie inside the word on the same baseline.
    The visible portion keeps its own box so whole-word coverage cannot hide it.
    """
    a=word.get('native_box') or [v*(sx if i%2==0 else sy) for i,v in enumerate(word['box'])]
    for e in excluded:
        if e['reason']!='white fill and white rendered glyph area':continue
        b=e['box']
        if not (a[0]<b[0]<a[2] and
                min(a[3],b[3])-max(a[1],b[1])>.5*(a[3]-a[1])):continue
        for cut in range(1,len(word['text'])-1):
            suffix=word['text'][cut:]
            if e['text'].startswith(suffix):
                return (dict(word,text=word['text'][:cut],native_box=[a[0],a[1],b[0],a[3]]),
                        dict(text=suffix,reason=e['reason']))
    return word,None


def page_geometry(pdf):
    """Read page frames only, using the same native reader as rule 1."""
    name='_conserve_geometry'
    with _GEOMETRY_LOCK:
        reader=sys.modules.get('_copy_table_reader') or sys.modules.get(name)
        if reader is None:
            spec=importlib.util.spec_from_file_location(name,Path(__file__).resolve().parents[1]/'standalone/element_boxer_sc.py')
            reader=importlib.util.module_from_spec(spec);sys.modules[name]=reader;spec.loader.exec_module(reader)
    doc=reader.SCDoc(str(pdf))
    try:
        return {n:dict(media=list(p.mediabox),rotation=p.rotate%360,width=doc.page_size(n)[0],height=doc.page_size(n)[1])
                for n,p in enumerate(doc.pages,1)}
    finally:doc.fp.close()


def native_box(box, geometry, sx, sy):
    """Match rule 1's Poppler-to-native transform, including shifted/rotated pages."""
    x0,y0,x1,y1=geometry['media'];height=geometry['height'];rotation=geometry['rotation']
    points=[]
    for x,y in ((box[0],box[1]),(box[0],box[3]),(box[2],box[1]),(box[2],box[3])):
        if rotation==90:u,v=x0+y,y0+x
        elif rotation==180:u,v=x1-x,y0+y
        elif rotation==270:u,v=x1-y,y1-x
        else:u,v=x0+x,y1-y
        points.append((u*sx,(height-v)*sy))
    return [min(p[0] for p in points),min(p[1] for p in points),max(p[0] for p in points),max(p[1] for p in points)]


def audit_run_tokens(body, uncertainty, pages, excluded, saved=None, fallback_runs=()):
    """Recheck delivered text, never trust a saved 'placed' status or offset."""
    runs=[]
    if saved and saved.get('token_ledger'):
        groups=collections.defaultdict(list)
        for token in saved['token_ledger']['tokens']:
            if token['status']!='excluded':groups[token['page'],token['run']].append(token)
        for (page,mid),tokens in groups.items():
            tokens=sorted(tokens,key=lambda t:t['token'])
            # Saved output spans are positions to recheck first, never proof.
            runs.append(dict(page=page,id=mid,text=' '.join(t['text'] for t in tokens),box=tokens[0].get('box'),
                             hints=[t.get('output') for t in tokens],byline=any(t['status']=='joined' for t in tokens)))
    else:
        for n,page in pages.items():
            omitted={e.get('id') for e in excluded.get(n,[])}
            for e in page.get('elements',[]):
                if e['kind']=='text' and e['id'] not in omitted:
                    runs.append(dict(page=n,id=e['id'],text=e['text'],box=e['box_px']))
    native=bool(runs)
    if not native:runs=list(fallback_runs)
    ledger=token_ledger(body,runs)
    ledger['source']='exporter runs' if native else 'PDF lines (no saved native runs)'
    # Only quoted source payloads are evidence under uncertainty. Page/run
    # numbers and prose in the diagnostic itself must not satisfy a token.
    payloads=[]
    for line in uncertainty.splitlines():
        for match in re.finditer(r'"(?:[^"\\]|\\.)*"',line):
            try:payloads.append(json.loads(match[0]))
            except ValueError:pass
    missing=[t for t in ledger['tokens'] if t['status']=='missing']
    report=token_ledger('\n\n'.join(payloads),[dict(page=t['page'],id=str(i),text=t['text'],box=t.get('box'))
                                                   for i,t in enumerate(missing)])
    for token in report['tokens']:
        if token['status']=='placed':missing[int(token['run'])].update(status='reported',reason='quoted source token under uncertainty')
    ledger['reported_tokens']=sum(t['status']=='reported' for t in ledger['tokens'])
    ledger['missing_tokens']=sum(t['status']=='missing' for t in ledger['tokens'])
    for n,entries in excluded.items():
        for i,e in enumerate(entries):
            for j,token in enumerate(e['text'].split()):
                ledger['tokens'].append(dict(page=n,run=e.get('id',f'exclusion:{i}'),token=j,
                    text=token,box=e['box'],status='excluded',reason=e['reason'],exclusion=i))
    ledger['excluded_tokens']=sum(t['status']=='excluded' for t in ledger['tokens'])
    ledger['source_tokens']+=ledger['excluded_tokens']
    return ledger


def audit(copy_dir, pdf, evidence_dir=None):
    folder = Path(copy_dir); evidence = Path(evidence_dir or copy_dir)
    text = (folder/'copy.md').read_text()
    body,_,uncertainty = text.partition(UNCERTAINTY)
    placed = CopyIndex(body); reported_index = CopyIndex(uncertainty)
    table_indexes=placed_tables(body,evidence)
    pages = {p['page']:p for f in evidence.glob('page-[0-9]*.json') for p in [json.loads(f.read_text())]}
    # Both compact folders and the scan route carry final ownership here.
    # Its snapshot supersedes earlier native classifications in page JSON.
    sidecar = evidence/'copy.conservation.json'
    saved=json.loads(sidecar.read_text()) if sidecar.exists() else None
    if saved:
        for p in saved.get('pages',[]):
            pages.setdefault(p['page'],{}).update(p)
    excluded = {n:exclusions(p if p.get('copy_conservation') is not None else baseline_evidence(p)) for n,p in pages.items()}
    try:geometry=page_geometry(pdf);geometry_warning=None
    except Exception as exc:
        geometry={};geometry_warning=f'Native page frame unavailable; used page-size scaling: {type(exc).__name__}: {exc}'
    missing=[]; reported=[]; omitted=[]; source_lines=[]; pdf_runs=[]; previous_line=None; count=0; checked=0
    for n,width,height,ws in pdf_lines(pdf):
        count += 1
        page=pages.get(n,{})
        box=page.get('region_box_px',[0,0,width,height]);sx=(box[2]-box[0])/width;sy=(box[3]-box[1])/height
        if n in geometry:
            g=geometry[n];sx=(box[2]-box[0])/g['width'];sy=(box[3]-box[1])/g['height']
            for w in ws:w['native_box']=native_box(w['box'],g,sx,sy)
        keep=[];skip=[]
        for w in ws:
            w,partial=visible_word(w,excluded.get(n,[]),sx,sy)
            if partial:skip.append(partial)
            why=covered(w,excluded.get(n,[]),sx,sy)
            if why:skip.append(dict(text=w['text'],reason=why))
            else:keep.append(w)
        if skip:omitted.append(dict(page=n,words=skip))
        if not keep:
            previous_line=None
            continue
        checked += 1
        line=' '.join(w['text'] for w in keep)
        source_lines.append((n,normalise(line)))
        line_box=[min(w['box'][0] for w in keep),min(w['box'][1] for w in keep),
                  max(w['box'][2] for w in keep),max(w['box'][3] for w in keep)]
        pdf_runs.append(dict(page=n,id=f'pdf:line:{count}',text=line,box=line_box))
        joined_url=None
        if previous_line and line.strip().isdigit():
            pn,pt,pb=previous_line
            url=re.search(r'https?://\S+(?:\s+\d+)*$',pt.translate(dict.fromkeys(map(ord,'\u200b\ufeff\u00ad'))))
            h=line_box[3]-line_box[1]
            if (pn==n and url and abs(pb[0]-line_box[0])<2*h
                    and 0<=line_box[1]-pb[3]<h):joined_url=re.sub(r'\s+','',url[0])+line.strip()
        # Poppler can split a justified reference baseline into several lines,
        # including a URL prefix and its spaced numeric suffix. Preserve the
        # local baseline for checking the following wrapped numeric tail.
        context=line;context_box=line_box
        if previous_line:
            pn,pt,pb=previous_line;h=line_box[3]-line_box[1]
            if (pn==n and abs(pb[1]+pb[3]-line_box[1]-line_box[3])<.8*h
                    and line_box[0]>pb[0] and -h<line_box[0]-pb[2]<4*h):
                context=pt+' '+line
                context_box=[pb[0],min(pb[1],line_box[1]),line_box[2],max(pb[3],line_box[3])]
        previous_line=(n,context,context_box)
        tables=(page.get('copy_conservation') or {}).get('tables',[t['box_px'] for t in page.get('tables',[])])
        in_table=any(any(b[0]<=.5*(a[0]+a[2])<=b[2] and b[1]<=.5*(a[1]+a[3])<=b[3] for b in tables)
                     for w in keep for a in [w.get('native_box') or [w['box'][0]*sx,w['box'][1]*sy,w['box'][2]*sx,w['box'][3]*sy]])
        if (placed.contains(line,page=n if in_table else None)
                or not in_table and joined_url and placed.contains(joined_url)):continue
        if in_table and any(tn==n and index.contains(line) and
                            any(b[0]<=.5*(a[0]+a[2])<=b[2] and b[1]<=.5*(a[1]+a[3])<=b[3]
                                for w in keep for a in [w.get('native_box') or [v*(sx if i%2==0 else sy) for i,v in enumerate(w['box'])]])
                            for tn,b,index in table_indexes):continue
        item=dict(page=n,text=line,box=line_box)
        (reported if reported_index.contains(line) else missing).append(item)
    duplicates=duplicate_paragraphs(text)
    for item in duplicates:
        key=normalise(item['text'])
        item['pages']=sorted({n for n,line in source_lines if line==key or
                             len(line)>=20 and line in key or len(key)>=20 and key in line})
    ledger=audit_run_tokens(body,uncertainty,pages,excluded,saved,pdf_runs)
    return dict(copy=str(folder/'copy.md'),pdf=str(pdf),evidence=str(evidence),
                checker_sha256=CHECKER_CODE_SHA256,
                geometry_warning=geometry_warning,
                evidence_pages=len(pages),printed_lines=count,checked_lines=checked,
                missing_count=len(missing),reported_only_count=len(reported),
                duplicate_count=len(duplicates),missing=missing,reported_only=reported,
                duplicates=duplicates,excluded=omitted,token_ledger=ledger,
                token_missing_count=ledger['missing_tokens'],token_reported_count=ledger['reported_tokens'],
                token_duplicate_count=len(ledger['extra_run_occurrences']))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('copy_dir');parser.add_argument('pdf')
    parser.add_argument('--evidence-dir');parser.add_argument('--json')
    args=parser.parse_args()
    result=audit(args.copy_dir,args.pdf,args.evidence_dir)
    print(f"{Path(args.copy_dir).name}: {result['checked_lines']}/{result['printed_lines']} lines checked; "
          f"{result['missing_count']} missing; {result['reported_only_count']} only under uncertainty; "
          f"{result['duplicate_count']} repeated paragraphs")
    ledger=result['token_ledger']
    print(f"{ledger['source_tokens']} source tokens: {ledger['placed_tokens']} placed, "
          f"{ledger['reported_tokens']} reported, {ledger['excluded_tokens']} excluded with reasons, "
          f"{ledger['missing_tokens']} unreported; {len(ledger['extra_run_occurrences'])} extra run occurrences")
    for token in ledger['tokens']:
        if token['status']=='missing':print(f"missing token page {token['page']} {token['run']}:{token['token']}: {token['text']}")
    for key in ('missing','reported_only'):
        for item in result[key]: print(f"{key} page {item['page']}: {item['text']}")
    for item in result['duplicates']:
        print(f"duplicate paragraph {item['paragraph']} ({item['occurrences']} occurrences; "
              f"source pages {','.join(map(str,item['pages'])) or 'unmatched'}): {item['text']}")
    if args.json:Path(args.json).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')


if __name__=='__main__':main()
