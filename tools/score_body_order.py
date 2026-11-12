#!/usr/bin/env python3
"""Measure rule-9 and current-copy box order against an explicit truth manifest.

Usage: /usr/bin/python3 -I tools/score_body_order.py MANIFEST.json OUTPUT.json
Manifest entries: paper, pages (directory or pages.json.gz), order (body-order.json),
truth (audited copy.md), current (current copy.md), cohort (truth or failing).

Alignment is independent of either proposed order: Unicode/alphanumeric exact
whole-box matches, otherwise unique line/line-fragment anchors. Repeated short
headings and absent text stay unresolved. A line can tolerate a corrected glyph
using two unique 24-character fragments, but no fuzzy match or inferred reading
order supplies truth. Nonmonotonic line anchors expose an indivisible source
box whose contents have been rearranged by the copy program. Such boxes are
flagged, not counted as correct. A paper is fully right only if every box is
aligned, internally monotonic, and the complete box permutation matches.
Overlapping spans from distinct boxes cannot establish an atomic box order;
both alignments stay unresolved, even if their individual anchors are unique.
Edges compare exact adjacency among aligned boxes; unresolved endpoints are
flagged/unscored. Continuation flags are counted independently of order errors.
No PDF or baseline is written. This is a box-order score, not a text/ownership
or paragraph-break score, and audited copies do not constitute independent
truth for their own order. Failing-copy disagreements are diagnostic only.
"""
import argparse
import collections
import gzip
import importlib.util
import json
from pathlib import Path
import re
import statistics
import unicodedata


def normalise(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',s).lower() if c.isalnum())


def visible(s):
    s=s.split('## Places the program is not sure of')[0]
    return re.sub(r'<!--.*?-->','',s,flags=re.S)


def occurrences(text,needle,limit=50):
    if not needle:return []
    at=0; found=[]
    while len(found)<limit:
        at=text.find(needle,at)
        if at<0:break
        found.append(at);at+=len(needle)
    return found


def heading_offsets(markdown):
    """Complete isolated text blocks anchor short headings across formatting.

    The copier may preserve a heading as a plain paragraph while the repaired
    truth uses Markdown hashes. Blank lines on both sides distinguish that
    whole text block from an incidental phrase inside prose. Markdown table
    rows cannot supply these anchors; source-row uniqueness is checked later.
    """
    offsets=collections.defaultdict(list);pos=0;lines=visible(markdown).splitlines()
    for i,line in enumerate(lines):
        key=normalise(line)
        isolated=(not i or not lines[i-1].strip()) and (i+1==len(lines) or not lines[i+1].strip())
        if key and (re.match(r'^#{2,6}\s',line) or isolated and '|' not in line):offsets[key].append(pos)
        pos+=len(key)
    return offsets


def align(rows,text,headings=None):
    """Return conservative text offsets and full alignment evidence."""
    keys=[normalise(r['text']) for r in rows]
    whole=''.join(keys); hits=occurrences(text,whole)
    if headings and len(headings.get(whole,[]))==1:
        at=headings[whole][0]
        return dict(status='aligned',start=at,end=at+len(whole),method='standalone text block',coverage=1)
    # A unique short fragment (e.g. "and were") can belong to a different
    # paragraph after the real source fragment was repaired or omitted. Use
    # the same 24-character minimum as fragment anchors; explicit headings
    # above remain usable. Never manufacture truth from that accidental hit.
    if len(hits)==1 and len(whole)>=24:
        return dict(status='aligned',start=hits[0],end=hits[0]+len(whole),method='whole',coverage=1)
    anchors=[]
    for i,key in enumerate(keys):
        if len(key)<24:continue
        hits=occurrences(text,key)
        if len(hits)==1:
            anchors.append(dict(row=i,start=hits[0],end=hits[0]+len(key),coverage=1));continue
        if len(key)<48:continue
        parts=[]
        for offset in range(0,len(key)-23,24):
            fragment=key[offset:offset+24];where=occurrences(text,fragment)
            if len(where)==1: parts.append((offset,where[0]))
        if len(parts)>=2:
            positions=[p-o for o,p in parts]
            if max(positions)-min(positions) <= max(12,.1*len(key)):
                pos=int(statistics.median(positions))
                anchors.append(dict(row=i,start=pos,end=pos+len(key),coverage=min(1,len(parts)*24/len(key))))
    covered=sum(len(keys[a['row']])*a['coverage'] for a in anchors)
    coverage=covered/max(1,len(whole))
    if not anchors or coverage<.65:
        return dict(status='unresolved',reason='no unique match or insufficient anchored text',coverage=coverage,anchors=anchors)
    backwards=any(a['start']>=b['start'] for a,b in zip(anchors,anchors[1:]))
    start=min(a['start'] for a in anchors);end=max(a['end'] for a in anchors)
    if backwards:
        return dict(status='interleaved',reason='source box line order differs inside the copy',start=start,end=end,coverage=coverage,anchors=anchors)
    return dict(status='aligned',start=start,end=end,method='line anchors',coverage=coverage,anchors=anchors)


def load_pages(path):
    p=Path(path)
    if p.suffix=='.gz':
        with gzip.open(p,'rt') as f:return json.load(f)
    return [json.loads(f.read_text()) for f in sorted(p.glob('page-*.json'))]


def score(entry,boxer):
    pages=load_pages(entry['pages']); ledger=json.loads(Path(entry['order']).read_text())
    truth_md=Path(entry['truth']).read_text();current_md=Path(entry['current']).read_text()
    truth=normalise(visible(truth_md));current=normalise(visible(current_md))
    truth_heads=heading_offsets(truth_md);current_heads=heading_offsets(current_md)
    nodes={};texts={};alignments={};current_alignments={};source_rows={}
    row_counts=collections.Counter()
    for p in pages:
        for b in p.get('main_text',{}).get('blocks',[]):
            if b.get('cls')!='main':continue
            key=f"{p['page']}:{b['id']}"; rows=boxer.body_order_rows(p,b)
            nodes[key]=dict(page=p['page'],id=b['id'],box_px=b['box_px'])
            texts[key]=' '.join(r['text'] for r in rows)
            source_rows[key]=rows
            row_counts.update(normalise(r['text']) for r in rows)
    for key,rows in source_rows.items():
        # A table's "References" header must not borrow the document's sole
        # Markdown reference-section anchor. A heading anchor must also be
        # unique among the source rows, including rows inside larger boxes.
        heading_ok=len(rows)!=1 or row_counts[normalise(rows[0]['text'])]==1
        alignments[key]=align(rows,truth,truth_heads if heading_ok else None)
        current_alignments[key]=align(rows,current,current_heads if heading_ok else None)
    for matches in (alignments,current_alignments):
        claims=collections.defaultdict(list)
        for key,a in matches.items():
            if a['status']=='aligned':claims[(a['start'],a['end'])].append(key)
        for claim in claims.values():
            if len(claim)>1:
                for key in claim:
                    matches[key]=dict(matches[key],status='unresolved',reason='multiple source boxes claim the same copy span',competing_boxes=claim)
        # A copy can insert a note/table inside another source box's text.
        # Sorting only the starts would invent a whole-box order for those
        # interleaved spans. Keep every conflict, including nested spans,
        # unresolved; a shared boundary alone is not an overlap.
        spans=sorted((a['start'],a['end'],k) for k,a in matches.items() if a['status']=='aligned')
        overlaps=collections.defaultdict(set)
        for i,(start,end,key) in enumerate(spans):
            for other_start,other_end,other_key in spans[i+1:]:
                if other_start>=end:break
                if start<other_end:
                    overlaps[key].add(other_key);overlaps[other_key].add(key)
        for key,others in overlaps.items():
            matches[key]=dict(matches[key],status='unresolved',reason='distinct source box spans overlap in the copy',competing_boxes=sorted(others))
    known={k for k,a in alignments.items() if a['status']=='aligned'}
    expected=sorted(known,key=lambda k:(alignments[k]['start'],alignments[k]['end'],k))
    rank={k:i for i,k in enumerate(expected)}
    predicted=[f"{b['page']}:{b['id']}" for b in ledger['blocks']]
    copied=sorted((k for k in known if current_alignments[k]['status']=='aligned'),
                  key=lambda k:(current_alignments[k]['start'],current_alignments[k]['end'],k))
    def edges(sequence,missing_positions=()):
        counts=collections.Counter();wrong=[]
        for a,b in zip(sequence,sequence[1:]):
            if a not in rank or b not in rank:counts['unscored']+=1;continue
            if rank[b]==rank[a]+1:counts['right']+=1;continue
            # The current copy's sequence excludes boxes whose position is
            # unresolved. A forward gap containing only such boxes is unknown,
            # not evidence that the surviving boxes were reordered.
            if rank[b]>rank[a]+1 and all(k in missing_positions for k in expected[rank[a]+1:rank[b]]):
                counts['unscored']+=1;continue
            counts['wrong']+=1
            actual=expected[rank[a]+1] if rank[a]+1<len(expected) else None
            wrong.append(dict(source=nodes[a],target=nodes[b],expected_next=nodes.get(actual),
                              source_words=' '.join(texts[a].split()[-8:]),target_words=' '.join(texts[b].split()[:8]),
                              expected_words=' '.join(texts[actual].split()[:8]) if actual else None,
                              reversed=rank[b]<rank[a]))
        return dict(counts),wrong
    rc,rw=edges(predicted);cc,cw=edges(copied,known-set(copied))
    # Unaligned current boxes have no defensible position. Keep their edge
    # budget unscored instead of silently reporting a shorter, perfect stream.
    cc['unscored']=cc.get('unscored',0)+max(0,len(nodes)-1-sum(cc.values()))
    all_known=bool(nodes) and len(known)==len(nodes) and not ledger['unplaced']
    return dict(paper=entry['paper'],cohort=entry['cohort'],truth=entry['truth'],current=entry['current'],
        boxes=len(nodes),aligned=len(known),unresolved=[dict(nodes[k],alignment=a) for k,a in alignments.items() if a['status']!='aligned'],
        rule9=dict(fully_right=all_known and predicted==expected,aligned_order_right=bool(known) and [k for k in predicted if k in known]==expected,
                   edges=rc,wrong=rw,flagged=sum(e['flagged'] for e in ledger['edges']),
                   order_flagged=sum(e['order_flagged'] for e in ledger['edges']),unplaced=ledger['unplaced']),
        current_copy=dict(fully_right=all_known and copied==expected,aligned_order_right=bool(known) and copied==expected,edges=cc,wrong=cw),
        alignments=alignments,current_alignments=current_alignments)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('manifest');ap.add_argument('output');args=ap.parse_args()
    spec=importlib.util.spec_from_file_location('boxer',Path(__file__).resolve().parents[1]/'standalone/element_boxer_sc.py')
    boxer=importlib.util.module_from_spec(spec);spec.loader.exec_module(boxer)
    entries=json.loads(Path(args.manifest).read_text());results=[score(e,boxer) for e in entries]
    totals={}
    for cohort in sorted({r['cohort'] for r in results}):
        rs=[r for r in results if r['cohort']==cohort];agg=dict(papers=len(rs),boxes=sum(r['boxes'] for r in rs),aligned=sum(r['aligned'] for r in rs))
        for kind in ('rule9','current_copy'):
            counts=collections.Counter()
            for r in rs:counts.update(r[kind]['edges'])
            agg[kind]=dict(fully_right=sum(r[kind]['fully_right'] for r in rs),aligned_order_right=sum(r[kind]['aligned_order_right'] for r in rs),edges=dict(counts))
        agg['flagged_edges']=sum(r['rule9']['flagged'] for r in rs)
        agg['order_flagged_edges']=sum(r['rule9']['order_flagged'] for r in rs)
        totals[cohort]=agg
    Path(args.output).write_text(json.dumps(dict(totals=totals,papers=results),indent=1))
    print(json.dumps(totals,indent=2))


if __name__=='__main__':main()
