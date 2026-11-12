#!/usr/bin/env python3
"""Validate the native copy trace that copy_paper.py writes (copy.trace.json).

/usr/bin/python3 -I tools/trace.py COPY_DIR [PDF] [--json REPORT] [--lines]
/usr/bin/python3 -I tools/trace.py COPY_DIR --copy copy.checked.md --trace copy.checked.trace.json
/usr/bin/python3 -I tools/trace.py --legacy COPY_DIR PDF   (after-the-fact matcher)

The copier records each unit's sources when it writes the unit (see
tools/copy_trace.py). This validator never rebuilds provenance by matching
text. It checks that the trace belongs to this copy and PDF (SHA-256), that
every unit's span holds exactly its recorded text and spans do not overlap,
and it recomputes every line's destination from the recorded claims (rows,
runs), furniture reasons and uncertainty-list runs, independently of the
writer's code. --lines also rebuilds the printed-line universe with
tools/export_lines.py (it reruns the copier on disposable inputs; needs the
page JSONs) and compares line ids and run membership. It prints the same
statistics/accounting report as the copier and exits 0 when every line has
exactly one destination (one unit or unit group, furniture, uncertainty, or
a listed split), no body line lost its own characters to furniture or to no
box (partly_excluded, from the writer's recorded evidence), and every unit is
traced; 1 when the trace is valid but lists lost/duplicate/partly excluded
lines or untraced units, or when it is inconsistent; 2 when
inputs are missing. trace_show.py reads the same file.

Legacy matcher (--legacy, retained for comparison): offsets are half-open
Python Unicode character offsets, not bytes. Matching is
case- and punctuation-sensitive; only whitespace, Markdown syntax, and a source
line's final hyphen may disappear. Exact anchors must have a unique source;
short/repeated text needs a unique exact match in an already anchored unit.
Unmatched text and ambiguity remain explicit, including generated copy notices.
The source universe and line numbering are those of export_lines.py, including
its documented OCR/decoding limitations. No OCR or network call is added here.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import inspect
import importlib.util
import json
import math
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
UNCERTAINTY = '## Places the program is not sure of'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


exporter = module('_trace_export', ROOT/'tools/export_lines.py')
accounting = module('_trace_accounting', ROOT/'tools/trace_port/accounting.py')
pcl = module('_trace_pcl', ROOT/'tools/trace_port/pcl.py')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=True, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)


def normalise(text, offset=0, source=False, drop_hyphen=False):
    """Return a strict comparison key and its original character positions.

    No case folding, accent folding, Unicode compatibility conversion, spelling
    repair, punctuation stripping or value substitution is permitted. Literal
    escaped punctuation remains literal. Copy superscript/subscript wrappers are
    syntax, but their contents (including signs and digits) remain significant.
    """
    omitted = set()
    patterns = [r'<br\s*/?>', r'</?(?:sup|sub|em|strong)>',
                r'(?<!\\)\^\{?|(?<!\\)_\{|(?<=\w)\^(?=\s|$|[,.;:)])']
    if not source:
        patterns += [r'(?m)^\s*(?:#{1,6}\s+|>\s*|-\s+)', r'(?m)^```[^\n]*$', r'(?<!\\)`']
        # A significance marker such as *P or **P is printed punctuation.
        for match in re.finditer(r'(?<!\\)\*\*(?=\S)(.+?)(?<=\S)(?<!\\)\*\*(?=\s|$|[,:;])',text):
            omitted.update((match.start(),match.start()+1,match.end()-2,match.end()-1))
    for pattern in patterns:
        for match in re.finditer(pattern, text): omitted.update(range(*match.span()))
    # Balanced braces only when they close one of the copy's raised-mark forms.
    for match in re.finditer(r'(?<!\\)[_^]\{[^{}]*\}', text):
        omitted.update((match.start(), match.start()+1, match.end()-1))
    for match in re.finditer(r'\\([\\`*_{}\[\]()#+.!|>^-])', text): omitted.add(match.start())
    if drop_hyphen:
        tail = re.search(r'[-‐\u00ad]\s*$', text)
        if tail: omitted.add(tail.start())
    chars, positions = [], []
    for i, ch in enumerate(text):
        if not ch.isspace() and i not in omitted:
            chars.append(ch); positions.append(offset+i)
    return ''.join(chars), positions


def units_from_markdown(text):
    """Parse the copy writer's Markdown, preserving original spans and cells.

    Generated notices are units too; they are never credited as PDF content.
    Tables retain empty cells and their row/column coordinates. Blank space,
    page comments, separators, fences and byline delimiters are recorded later
    as layout spans, so every copy character has a disposition.
    """
    units = []
    section = None
    front = False
    table = 0
    table_row = 0
    in_table = False
    table_tail = False
    fenced = False
    pending = []

    def add(start, end, kind, generated=None, **extra):
        while start < end and text[start].isspace(): start += 1
        while end > start and text[end-1].isspace(): end -= 1
        if start == end and kind != 'table_cell': return
        record = dict(id=f'u{len(units)+1:05}', kind=kind, span=[start,end], text=text[start:end], **extra)
        if generated: record['generated_reason'] = generated
        units.append(record)

    def flush():
        nonlocal pending
        if pending:
            kind = {'abstract':'abstract_part', 'article':'article_information', 'references':'reference',
                    'end':'end_matter', 'uncertainty':'uncertainty_item'}.get(section, 'table_note' if table_tail else 'paragraph')
            add(pending[0][0],pending[-1][1],kind,
                'program uncertainty statement' if section == 'uncertainty' else None)
        pending=[]

    offset = 0
    for physical in text.splitlines(keepends=True):
        line = physical.rstrip('\r\n'); start=offset; end=start+len(line); offset+=len(physical)
        value=line.strip()
        if not value or value.startswith('<!--') or value == '---':
            flush(); in_table=False; continue
        if value.startswith('```'):
            flush(); fenced=not fenced; continue
        if fenced:
            add(start,end,'table_line' if table_tail else 'printed_line'); continue
        if value.startswith('|') and value.endswith('|'):
            flush()
            if re.fullmatch(r'[| :\-]+',value): continue
            if not in_table: table+=1;table_row=0
            in_table=True; table_tail=True
            bars=[m.start() for m in re.finditer(r'(?<!\\)\|',line)]
            for column,(a,b) in enumerate(zip(bars,bars[1:]),1):
                add(start+a+1,start+b,'table_cell',table=table,row=table_row,column=column)
            table_row+=1;continue
        in_table=False
        heading=re.match(r'^(#{1,6})\s+(.*)',value)
        if heading:
            flush();front=False;table_tail=False
            label=heading[2]; low=label.lower().rstrip(':')
            section=('uncertainty' if low=='places the program is not sure of' else
                     'article' if low in ('article information','article info','key words','keywords','key points') else
                     'abstract' if low in ('abstract','summary') else
                     'references' if re.match(r'^(references|bibliography|literature cited)\b',low) else
                     'end' if re.search(r'contributions|acknowledg|funding|conflict|disclosure|data availability|orcid|supporting information|ethics',low) else None)
            generated='program section label' if low in ('article information','places the program is not sure of') else None
            add(start,end,'title' if len(heading[1])==1 else 'heading',generated)
            continue
        author=re.match(r'\*\*Authors:\*\*\s*',value)
        if author:
            flush();front=True
            begin=start+line.index(value)+author.end()
            for match in re.finditer(r'[^;]+',text[begin:end]):
                add(begin+match.start(),begin+match.end(),'author')
            continue
        if value.startswith('**Author details'):
            flush();front=True;add(start,end,'heading','program author-details label');continue
        if value.startswith('**Front matter as printed') or value.startswith('Document kind:') or value.startswith('[Author ') or value.startswith('[No byline') or re.fullmatch(r'Page \d+:',value):
            flush();front=False;add(start,end,'notice','program explanation');continue
        if re.match(r'^\*\*(?:(?:Supplemental|Supplementary)\s+)?(?:Table|Fig(?:ure)?s?\.?)[\s\d]',value,re.I):
            flush();front=False
            add(start,end,'caption','program placeholder' if '(no caption' in value else None)
            table_tail=bool(re.match(r'^\*\*(?:Table|Supplement)',value,re.I));continue
        if value.startswith('[table structure not recovered:'):
            flush();table_tail=True;add(start,end,'notice','program table fallback explanation');continue
        if re.match(r'^[-*]\s+',value):
            flush()
            kind=('affiliation' if front else {'article':'article_information','references':'reference',
                'end':'end_matter','uncertainty':'uncertainty_item','abstract':'abstract_part'}.get(section,'table_line' if table_tail else 'list_item'))
            add(start,end,kind,'program uncertainty statement' if section=='uncertainty' else None);continue
        if value.startswith('> '):
            flush();front=False
            add(start,end,'end_matter' if section=='end' or re.match(r'> How to cite',value,re.I) else 'footnote',
                'program status notice' if re.match(r'> (?:NO COPY|INCOMPLETE COPY)',value) else None);continue
        front=False
        if re.match(r'^(?:Abstract|ABSTRACT|Summary|Objectives?|Background|Aims?|Methods|Results|Conclusions?)\s*:',value) and section in (None,'abstract'):
            flush();add(start,end,'abstract_part');continue
        pending.append((start,end))
    flush()
    return units


def collect_source(folder, pdf):
    """Use the exporter's exact source rows/IDs; avoid persistent page renders."""
    cache=folder/'.trace';cache.mkdir(exist_ok=True)
    fingerprint=dict(pdf=sha(pdf), files={p.name:sha(p) for p in sorted(folder.glob('*.json')) if not p.name.startswith('copy.trace')},
                     code={name:sha(ROOT/name) for name in ('copy_paper.py','tools/export_lines.py','tools/conserve.py')},
                     adapter=hashlib.sha256(inspect.getsource(collect_source).encode()).hexdigest())
    path=cache/'source.json'
    if path.exists():
        saved=json.loads(path.read_text())
        if saved['fingerprint']==fingerprint:return saved['source']
    state=exporter.snapshot(folder,pdf,cache)
    geometry=exporter.conserve.page_geometry(pdf)
    pages=sorted(state['source_pages'],key=lambda p:p['page'])
    if [p['page'] for p in pages]!=sorted(geometry):raise ValueError('source records do not cover every PDF page exactly once')
    result=dict(pages=[],lines=[],source_run_ownership='each decoded nonempty source run occurs once',
                limitations='Decoded source universe of export_lines.py; OCR text is unverified, invisible text is excluded before export.')
    ordinal = 0
    for page in pages:
        source_offset = 0
        number=page['page']; geo=geometry[number];dpi=page.get('params',{}).get('dpi',150)
        if not isinstance(dpi,(int,float)) or not math.isfinite(dpi) or dpi<=0: raise ValueError('invalid source dpi')
        media=geo['media'];size=[media[2]-media[0],media[3]-media[1]]
        if geo['rotation'] in (90,270):size.reverse()
        dimensions=[math.ceil(v*110/72) for v in size]
        result['pages'].append(dict(page=number,size_pdf_points=size,size_110dpi=dimensions,media_box_pdf_points=media,rotation=geo['rotation']))
        roles=exporter.source_roles(page,state)
        final=next((p for p in state['saved_conservation'].get('pages',[]) if p['page']==number),page)
        exclusions={str(e['id']):e.get('reason','unspecified exclusion') for e in final.get('copy_conservation',{}).get('excluded',[])}
        expected=Counter(e['id'] for e in page['elements'] if e.get('kind','text')=='text' and e.get('text','').strip());seen=Counter()
        if any(v!=1 for v in expected.values()):raise ValueError('duplicate source run ids')
        for i,row in enumerate(exporter.source_rows(page,roles),1):
            sources=[s for e in row for s in e.get('_subscript_sources',[e])]
            seen.update(e['id'] for e in sources)
            decoded=[dict(e,text=exporter.copy.glyph_spacing(e)) for e in row]
            value=exporter.copy.compose_accents(exporter.copy.prose_row(decoded,page)[0])
            native=exporter.copy.hull(e['box_px'] for e in sources)
            box=exporter.image_box(native,dpi,geo)
            clipped=[round(max(0,min(v,dimensions[j%2])),4) for j,v in enumerate(box)]
            if clipped[0]>=clipped[2] or clipped[1]>=clipped[3]:raise ValueError(f'page {number}: source box outside rendered page')
            native=[native[0]*72/dpi,geo['height']-native[3]*72/dpi,native[2]*72/dpi,geo['height']-native[1]*72/dpi]
            reasons=[]
            for e in sources:
                reason=exclusions.get(str(e['id']).removeprefix('ocr:'))
                if not reason and roles.get(e['id']) in ('furniture','figure_text'):
                    reason='program figure lettering classification' if roles[e['id']]=='figure_text' else 'program furniture classification'
                if reason:reasons.append(reason)
            # Port: converter/convert_page.py::load_paper, D-020. The boxer
            # supplies its own visible-character indices (not pdfplumber's).
            # A line is addressed by its first source character; retain all
            # character IDs and the exporter's legacy line ID as an alias.
            indices = list(dict.fromkeys(c for e in sources for c in e.get('char_ids', [])))
            if any(not isinstance(c, int) or c < 0 for c in indices):
                raise ValueError('invalid boxer character index')
            basis = 'boxer visible-character index' if indices else 'OCR decoded-character offset; not native PDF glyph identity'
            index = min(indices) if indices else source_offset
            source_offset += max(1, len(value))
            ordinal += 1
            record=dict(id=accounting.source_id(fingerprint['pdf'],number,index),
                export_id=f'p{number}.l{i:03}', number=ordinal, page_line=i,
                source_id_basis=basis, source_character_indices=indices,
                page=number,text=value,box_110dpi=clipped,
                box_pdf_points=[round(v,5) for v in native],runs=[e['id'] for e in sources],
                source_role=Counter(roles.get(e['id'],'body') for e in sources).most_common(1)[0][0],angle=row[0].get('angle',0),
                clipped=any(abs(a-b)>.001 for a,b in zip(box,clipped)))
            if len(reasons)==len(sources):record['furniture_evidence']=sorted(set(reasons))
            result['lines'].append(record)
        if seen!=expected:raise ValueError(f'page {number}: source run conservation failed')
    write_json(path,dict(fingerprint=fingerprint,source=result))
    return result


def spans(indices):
    result=[]
    for i in sorted(set(indices)):
        if result and result[-1][1]==i:result[-1][1]=i+1
        else:result.append([i,i+1])
    return result


def match_units(units, lines):
    """Allocate exact character witnesses; retain ambiguity instead of tie breaks.

    A unique 16-character source anchor establishes a line/unit relation. Then
    complete residual strings can be matched within those anchored units, or a
    whole unit can be matched to one source line. Repeated short values with no
    exact context stay unresolved. A line may feed several units, and a source
    may appear twice in the copy; both occurrences remain explicit.
    """
    uk={u['id']:normalise(u['text'],u['span'][0]) for u in units if not u.get('generated_reason')}
    lk={l['id']:normalise(l['text'],source=True) for l in lines}
    variants={l['id']:[lk[l['id']]] for l in lines}
    for line in lines:
        if re.search(r'[-‐\u00ad]\s*$',line['text']):variants[line['id']].append(normalise(line['text'],source=True,drop_hyphen=True))
    # Candidate anchors point to literal offsets, not the copy's heuristic ledger.
    width=16
    index=defaultdict(set)
    by_line={l['id']:l for l in lines}
    active={l['id'] for l in lines if not l.get('furniture_evidence')}
    def eligible(unit, line):
        # A table cell cannot be sourced from an identical phrase in prose.
        # Membership comes from saved table run IDs, never a guessed cell grid.
        contexts = line.get('contexts')
        return not contexts or ('table' if unit['kind'] in ('table_cell','table_line') else 'body') in contexts
    context_kind={u['id']:u['kind'] in ('table_cell','table_line') for u in units}
    by_context={kind:{l['id'] for l in lines if eligible({'kind':'table_cell' if kind else 'paragraph'},l)} for kind in (False,True)}
    allowed={uid:by_context[kind] for uid,kind in context_kind.items()}
    active_by_context={kind:frozenset(ids & active) for kind,ids in by_context.items()}
    active_allowed={uid:active_by_context[kind] for uid,kind in context_kind.items()}
    for mid,versions in variants.items():
        if mid not in active:continue
        for key,pos in versions:
            for i in range(max(0,len(key)-width+1)):index[key[i:i+width]].add(mid)
    links=defaultdict(list)
    covered_u=defaultdict(set); covered_l=defaultdict(set)
    def record(uid,mid,ua,ub,key,pos,la,lb,method):
        up=uk[uid][1]
        if ua==ub:return
        witness=dict(copy_span=[up[ua],up[ub-1]+1],line_span=[pos[la],pos[lb-1]+1],method=method)
        if witness not in links[uid,mid]:links[uid,mid].append(witness)
        covered_u[uid].update(up[ua:ub]);covered_l[mid].update(pos[la:lb])
        # A discretionary line-end hyphen has an explicit normalization witness.
        if len(key)<len(lk[mid][0]) and lb==len(key):covered_l[mid].update(lk[mid][1][len(key):])
    for uid,(key,positions) in uk.items():
        candidates=set()
        for i in range(max(0,len(key)-width+1)):
            candidates.update(index.get(key[i:i+width],set()) & allowed[uid])
        for mid in sorted(candidates):
            for lkey,lpos in variants[mid]:
                # Extend a unique source k-gram in both directions exactly.
                seeds={key[i:i+width] for i in range(max(0,len(key)-width+1)) if index.get(key[i:i+width],set()) & allowed[uid]=={mid}}
                for seed in seeds:
                    starts=[m.start() for m in re.finditer('(?='+re.escape(seed)+')',key)]
                    source_starts=[m.start() for m in re.finditer('(?='+re.escape(seed)+')',lkey)]
                    if len(source_starts)!=1:continue
                    for a in starts:
                        b=source_starts[0];left=0;right=width
                        while a-left>0 and b-left>0 and key[a-left-1]==lkey[b-left-1]:left+=1
                        while a+right<len(key) and b+right<len(lkey) and key[a+right]==lkey[b+right]:right+=1
                        record(uid,mid,a-left,a+right,lkey,lpos,b-left,b+right,'unique exact source anchor')
    # Complete units (names, labels, table cells) may be shorter than an anchor.
    for uid,(key,pos) in uk.items():
        if not key:continue
        candidates=[]
        for mid,versions in variants.items():
            if mid not in allowed[uid]:continue
            for lkey,lpos in versions:
                at=lkey.find(key)
                while at>=0:
                    # Never locate a short value inside a larger word/number.
                    left=not key[0].isalnum() or at==0 or lpos[at]>lpos[at-1]+1 or not lkey[at-1].isalnum()
                    right=not key[-1].isalnum() or at+len(key)==len(lkey) or lpos[at+len(key)]>lpos[at+len(key)-1]+1 or not lkey[at+len(key)].isalnum()
                    if len(key)>=width or left and right:candidates.append((mid,at,lkey,lpos))
                    at=lkey.find(key,at+1)
        nonfurniture=[c for c in candidates if c[0] in active]
        candidates=nonfurniture or candidates
        unique={(mid,at) for mid,at,_,_ in candidates}
        if len(unique)==1:
            mid,at,lkey,lpos=candidates[0];record(uid,mid,0,len(key),lkey,lpos,at,at+len(key),'unique complete unit')
    # Short complete source lines, including bibliographic tails, need no
    # minimum anchor length when both the source and the destination are unique.
    owner_cache = {}
    for mid in sorted(active):
        for lkey,lpos in variants[mid]:
            if not lkey:continue
            matches=[]
            for uid,(key,upos) in uk.items():
                if mid not in allowed[uid]:continue
                context = active_allowed[uid]
                cache_key = (lkey, context_kind[uid])
                if cache_key not in owner_cache:
                    owner_cache[cache_key] = {other for other in context if any(lkey in k for k,p in variants[other])}
                if owner_cache[cache_key]!={mid}:continue
                at=key.find(lkey)
                while at>=0:
                    left=at==0 or not lkey[0].isalnum() or not key[at-1].isalnum() or upos[at]>upos[at-1]+1
                    end=at+len(lkey)
                    right=end==len(key) or not lkey[-1].isalnum() or not key[end].isalnum() or upos[end]>upos[end-1]+1
                    if (left and right) or len(lkey)>=width:matches.append((uid,at))
                    at=key.find(lkey,at+1)
            if len(matches)==1:
                uid,at=matches[0];record(uid,mid,at,at+len(lkey),lkey,lpos,0,len(lkey),'unique complete source line')
    # Exact two-line context resolves repeated abstract/body sentences and
    # short wrapped tails. Geometry only selects physically adjacent baselines;
    # the concatenated source text must occur exactly in an anchored unit.
    adjacent=[]
    for first in lines:
        if first['id'] not in active or first.get('angle',0)%360:continue
        a=first['box_110dpi'];candidates=[]
        for second in lines:
            if second['id'] not in active or second['page']!=first['page'] or second.get('angle',0)%360:continue
            b=second['box_110dpi'];gap=b[1]-a[1]
            overlap=min(a[2],b[2])-max(a[0],b[0])
            if 0.5*(a[3]-a[1])<gap<3*max(a[3]-a[1],b[3]-b[1]) and overlap>.5*min(a[2]-a[0],b[2]-b[0]):
                candidates.append((gap,second))
        if candidates:
            distance=min(c[0] for c in candidates)
            for gap,second in candidates:
                if abs(gap-distance)<1:adjacent.append((first['id'],second['id']))
    pair_index=defaultdict(set)
    for first,second in adjacent:
        for ak,ap in variants[first]:
            for bk,bp in variants[second]:
                pair_index[ak+bk].add((first,second))
    for _ in range(3):
        before=sum(len(v) for v in covered_l.values())
        for first,second in adjacent:
            for uid,(key,upos) in uk.items():
                if first not in allowed[uid] or second not in allowed[uid]:continue
                complete_pair = {(a,b) for a,b in pair_index.get(key,()) if a in allowed[uid] and b in allowed[uid]} == {(first,second)}
                if not complete_pair and (uid,first) not in links and (uid,second) not in links:continue
                for ak,ap in variants[first]:
                    for bk,bp in variants[second]:
                        joined=ak+bk;at=key.find(joined)
                        if not ak or not bk or at<0 or key.find(joined,at+1)>=0:continue
                        # Require an already unique anchor inside this exact
                        # occurrence, not a relation elsewhere in a long unit.
                        own=[w for mid in (first,second) for w in links.get((uid,mid),[]) if
                             upos[at]<=w['copy_span'][0] and w['copy_span'][1]<=upos[at+len(joined)-1]+1]
                        if not own and not (complete_pair and joined==key):continue
                        record(uid,first,at,at+len(ak),ak,ap,0,len(ak),'exact adjacent-line continuation')
                        record(uid,second,at+len(ak),at+len(joined),bk,bp,0,len(bk),'exact adjacent-line continuation')
        if sum(len(v) for v in covered_l.values())==before:break
    # Exact residuals may use an established line relation, but cannot fill a
    # gap with an unrelated occurrence of a common digit or punctuation mark.
    for (uid,mid),witnesses in list(links.items()):
        key,upos=uk[uid]
        for lkey,lpos in variants[mid]:
            at=key.find(lkey)
            if lkey and at>=0 and key.find(lkey,at+1)<0:
                record(uid,mid,at,at+len(lkey),lkey,lpos,0,len(lkey),'complete line in anchored unit')
    for unit in units:
        uid=unit['id'];unit['sources']=[]
        for (owner,mid),witnesses in links.items():
            if owner!=uid:continue
            line=by_line[mid]
            # Compress overlapping exact witnesses, retaining their original
            # offsets. Sorting makes the source order follow the copy span.
            unique=[]
            for w in sorted(witnesses,key=lambda w:(w['copy_span'][0],-w['copy_span'][1])):
                if any(v['copy_span'][0]<=w['copy_span'][0] and v['copy_span'][1]>=w['copy_span'][1] and
                       v['line_span'][0]<=w['line_span'][0] and v['line_span'][1]>=w['line_span'][1] for v in unique):continue
                unique.append(w)
            unit['sources'].append(dict(line_id=mid,page=line['page'],box_pdf_points=line['box_pdf_points'],
                box_110dpi=line['box_110dpi'],witnesses=unique))
        unit['sources'].sort(key=lambda s:(min(w['copy_span'][0] for w in s['witnesses']),s['line_id']))
        missing=[p for p in uk.get(uid,('',[]))[1] if p not in covered_u[uid]]
        unit['unmatched']=[dict(span=[a,b],text=unit['text'][a-unit['span'][0]:b-unit['span'][0]],
            reason='no unique exact source witness; text changed, generated, or repeated') for a,b in spans(missing)]
        unit['status']='generated' if unit.get('generated_reason') else 'fully_traced' if not missing else 'partly_traced' if unit['sources'] else 'unmatched'
        if unit['status']=='generated':unit['unmatched']=[dict(span=unit['span'],text=unit['text'],reason=unit['generated_reason'])]
    for line in lines:
        mid=line['id'];line['units']=[]
        for unit in units:
            for source in unit['sources']:
                if source['line_id']==mid:line['units'].append(dict(unit_id=unit['id'],copy_span=unit['span'],witnesses=source['witnesses']))
        missing=[p for p in lk[mid][1] if p not in covered_l[mid]]
        line['unmatched']=[dict(span=[a,b],text=line['text'][a:b],reason='no unique exact copy witness') for a,b in spans(missing)]
        if not missing:line['status']='placed'
        elif line.get('furniture_evidence'):
            line['status']='furniture' if not line['units'] else 'placed_and_furniture'
            line['furniture_reason']='; '.join(line['furniture_evidence'])
        else:line['status']='not placed'
    return units,lines


def pcl_markers(text, lines, pdf_hash):
    """Port pcl.py::parse/render_lines/analyse (C-006/C-010/C-027).

    The reference parser validates commands and document-wide numbering. Its
    original reading annotations survive, enriched with exact exporter matches.
    Repeated text never acquires an arbitrary source address.
    """
    result = dict(sha256=hashlib.sha256(text.encode()).hexdigest(), markers=[], errors=[])
    try:
        document = pcl.parse(text)
        if document.header.args['source'] != pdf_hash:
            raise ValueError('PCL source SHA-256 mismatch')
        analysis = pcl.analyse(document)
    except (pcl.PclError, ValueError) as exc:
        # Rejected documents still expose every recognizable marker's literal
        # location. No invalid instruction is interpreted as a source address.
        result['markers'] = [dict(kind=m[1], raw=m[0], span=list(m.span()),
            status='unmatched', sources=[], reason='PCL validation failed: '+str(exc))
            for m in re.finditer(r'⟦(page|line)\b[^⟧]*⟧',text)]
        result.update(errors=[str(exc)], matched=0, unmatched=len(result['markers']), ok=False)
        return result
    by_page = defaultdict(list)
    for line in lines:
        by_page[line['page']].append(line)
    def source(line):
        return {key: line[key] for key in ('page','box_pdf_points','box_110dpi')} | dict(line_id=line['id'], export_id=line.get('export_id'))
    marker_lines = {}
    for printed, value in zip(document.lines, pcl.render_lines(document)):
        if printed.page_instr:
            token = printed.page_instr
            page_lines = by_page[printed.page]
            result['markers'].append(dict(kind='page',number=printed.page,
                span=[token.offset, token.offset+len(token.raw)],
                line_ids=[line['id'] for line in page_lines], sources=[source(line) for line in page_lines],
                status='matched' if page_lines else 'unmatched',
                **({} if page_lines else {'reason':'no exported source lines on declared page'})))
        token = printed.line_instr
        key, positions = normalise(value, source=True)
        matches = [line for line in by_page[printed.page]
                   if normalise(line['text'], source=True)[0] == key and key]
        record = dict(kind='line',number=printed.ordinal,page=printed.page,text=value,
                      span=[token.offset,token.offset+len(token.raw)],sources=[],status='unmatched')
        if len(matches) == 1:
            line = matches[0]
            record.update(sources=[source(line)],status='matched')
            _, columns = normalise(line['text'],source=True)
            marker_lines[printed.ordinal] = (line,dict(zip(positions,columns)))
        else:
            record['reason'] = 'ambiguous identical source lines' if matches else 'no exact printed line on declared page'
        result['markers'].append(record)
    # Keep the port's annotations byte-for-byte in shape; attach source columns
    # only to characters whose printed source is uniquely witnessed.
    annotations = analysis.annotations
    for entry in annotations['reading_map']:
        target = marker_lines.get(entry.get('line'))
        if target and 'column' in entry and entry['column'] in target[1]:
            entry.update(source_line_id=target[0]['id'],source_column=target[1][entry['column']])
        elif 'derived' not in entry:
            entry['unresolved_source'] = 'PCL printed character has no unique source witness'
    counts = Counter(s['line_id'] for r in result['markers'] if r['kind']=='line' for s in r['sources'])
    result['duplicate_source_lines'] = [lid for lid,n in counts.items() if n>1]
    result.update(annotations=annotations, reading=analysis.text,
                  matched=sum(r['status']=='matched' for r in result['markers']),
                  unmatched=sum(r['status']!='matched' for r in result['markers']))
    result['ok'] = not result['errors'] and not result['unmatched'] and not result['duplicate_source_lines']
    return result


def build(folder, pdf):
    folder=Path(folder).resolve();pdf=Path(pdf).resolve()
    text=(folder/'copy.md').read_text(encoding='utf-8');pdf_hash=sha(pdf)
    source=collect_source(folder,pdf)
    table_runs={}
    for path in folder.glob('page-*.json'):
        page=json.loads(path.read_text())
        table_runs[page['page']]={mid for table in page.get('tables',[]) for mid in table.get('members',[])}
    for line in source['lines']:
        members=table_runs.get(line['page'],set())
        line['contexts']=sorted({'table' if mid in members else 'body' for mid in line['runs']})
    units,lines=match_units(units_from_markdown(text),source['lines'])
    annotations = accounting.annotations(text, units, lines, normalise)
    for unit in units:
        ambiguous = [e['offset'] for e in annotations[slice(*unit['span'])] if e.get('candidates')]
        if ambiguous:
            unit['unmatched'].extend(dict(span=[a,b],text=text[a:b],reason='multiple exact source addresses') for a,b in spans(ambiguous))
            unit['status'] = 'partly_traced'
    audit = accounting.account(lines, units, annotations)
    occupied=set(i for unit in units for i in range(*unit['span']))
    layout=[dict(span=[a,b],text=text[a:b],reason='copy layout or structural markup') for a,b in spans(i for i in range(len(text)) if i not in occupied)]
    stats=dict(units=len(units),fully_traced=sum(u['status']=='fully_traced' for u in units),generated=sum(u['status']=='generated' for u in units),
        partly_traced=sum(u['status']=='partly_traced' for u in units),unmatched_units=sum(u['status']=='unmatched' for u in units),
        pdf_lines=len(lines),accounted_lines=sum(l['status']!='not placed' for l in lines),not_placed=sum(l['status']=='not placed' for l in lines))
    stats['fully_traced_share']=stats['fully_traced']/len(units) if units else 1
    stats['source_unit_traced_share']=stats['fully_traced']/(len(units)-stats['generated']) if len(units)>stats['generated'] else 1
    stats['pdf_line_accounted_share']=stats['accounted_lines']/len(lines) if lines else 1
    result=dict(version=2,pdf=dict(path=str(pdf),sha256=pdf_hash,pages=source['pages']),
        copy=dict(path='copy.md',sha256=sha(folder/'copy.md'),characters=len(text)),
        coordinates=dict(box_pdf_points='native unrotated PDF user space, origin bottom-left, absolute MediaBox offsets, 1 point = 1/72 inch; [left,bottom,right,top]',
            box_110dpi='displayed MediaBox at 110 dpi, page rotation applied, origin top-left; [left,top,right,bottom]',spans='zero-based, half-open Unicode character offsets'),
        source=dict(ownership=source['source_run_ownership'],limitations=source['limitations']),
        matching='case/punctuation-sensitive exact text; whitespace, copy markup and terminal source hyphens only; unresolved ambiguity is never assigned',
        units=units,lines=lines,layout=layout,statistics=stats,
        annotations=dict(reading_map=annotations), accounting=audit)
    if (folder/'copy.pcl').exists():result['pcl']=pcl_markers((folder/'copy.pcl').read_text(encoding='utf-8'),lines,pdf_hash)
    stats['duplicate_lines'] = len(audit['lines_in_multiple_units'])
    stats['repeated_character_lines'] = len(audit['repeated_source_characters'])
    stats['exclusively_accounted_lines'] = sum(l['status']!='not placed' and len(l['units'])<=1 for l in lines)
    stats['exclusive_pdf_line_share'] = stats['exclusively_accounted_lines']/len(lines) if lines else 1
    stats['ambiguous_copy_characters'] = sum(bool(e.get('candidates')) for e in annotations)
    result['ok'] = audit['ok'] and not stats['partly_traced'] and not stats['unmatched_units'] and not stats['ambiguous_copy_characters'] and result.get('pcl',{}).get('ok',True)
    write_json(folder/'copy.trace.legacy.json',result)
    return result


LINE_FAIL = ('lost', 'partly_lost', 'duplicate', 'partly_excluded')


def recompute_line(line, claims, kinds, run_reason, uncertain):
    """Independent reimplementation of the destination rule for one line."""
    per = []
    for m in line['runs']:
        entries = claims.get((line['page'], m), [])
        if entries:
            groups = sorted({e['group'] for e in entries}); status = 'unit'
            if len(groups) > 1:
                status = 'split'
                for i, x in enumerate(entries):
                    for y in entries[i+1:]:
                        if x['group'] == y['group']: continue
                        pair = {kinds[x['unit']], kinds[y['unit']]}
                        if 'front_matter_printed' in pair and pair <= {'front_matter_printed', 'title', 'author', 'affiliation'}:
                            found = 'flagged_repeat'
                        elif x['partial'] or y['partial']: found = 'split_unverified'
                        elif x['row'] is not None and x['row'] == y['row'] and (x['end'] <= y['start'] or y['end'] <= x['start']): found = 'split'
                        else: found = 'duplicate'
                        order = ['split', 'split_unverified', 'flagged_repeat', 'duplicate']
                        if order.index(found) > order.index(status): status = found
            per.append((status, groups))
        elif (line['page'], m) in run_reason: per.append(('furniture', []))
        elif (line['page'], m) in uncertain: per.append(('uncertainty', []))
        else: per.append(('lost', []))
    statuses = {s for s, _ in per}
    groups = sorted({g for s, gs in per for g in gs})
    sinks = {'unit' if s in ('unit', 'split', 'split_unverified', 'flagged_repeat', 'duplicate') else s for s, _ in per}
    if 'duplicate' in statuses: return 'duplicate', groups
    if 'lost' in statuses: return ('lost' if statuses == {'lost'} else 'partly_lost'), groups
    if 'flagged_repeat' in statuses: return 'flagged_repeat', groups
    if len(groups) > 1 or len(sinks) > 1: return ('split_unverified' if 'split_unverified' in statuses else 'split'), groups
    return next(iter(sinks)), groups


def validate(folder, pdf=None, lines_check=False, copy_name='copy.md', trace_name='copy.trace.json'):
    folder = Path(folder)
    path = folder/trace_name
    if not path.is_file() or not (folder/copy_name).is_file(): raise ValueError(f'{copy_name} or {trace_name} is missing')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not str(data.get('schema', '')).startswith('copy-trace/2'): raise ValueError('copy.trace.json is not a native trace (copy-trace/2)')
    problems = []
    text = (folder/copy_name).read_text(encoding='utf-8')
    if sha(folder/copy_name) != data['copy']['sha256']: problems.append(f'{copy_name} does not match the trace hash')
    pdf = pdf or data['pdf'].get('path')
    if pdf and Path(pdf).is_file():
        if data['pdf'].get('sha256') and sha(pdf) != data['pdf']['sha256']: problems.append('PDF does not match the trace hash')
    units = data['units']
    occupied = []
    for unit in units:
        a, b = unit['span']
        if unit['status'] == 'span_unresolved': continue
        if not 0 <= a <= b <= len(text) or text[a:b] != unit['text']: problems.append(f"{unit['id']}: span does not hold its text")
        if a < b: occupied.append((a, b, unit['id']))
    occupied.sort()
    for (a, b, u), (c, d, v) in zip(occupied, occupied[1:]):
        if c < b: problems.append(f'{u} and {v}: spans overlap')
    rows = {r['row']: r for r in data['rows']}
    claims = defaultdict(list); kinds = {}
    for k, unit in enumerate(units):
        kinds[k] = unit['kind']
        for row, a, b in unit['claims']['rows']:
            if row not in rows: problems.append(f"{unit['id']}: unknown row {row}"); continue
            for m in rows[row]['runs']:
                claims[rows[row]['page'], str(m)].append(dict(group=unit['group'], unit=k, row=row, start=a, end=b, partial=a < 0))
        for page, m, partial in unit['claims']['runs']:
            claims[page, str(m)].append(dict(group=unit['group'], unit=k, row=None, start=None, end=None, partial=bool(partial)))
    run_reason = {(e['page'], str(e['run'])) for e in data.get('furniture_runs', [])}; uncertain = set()
    for entry in data.get('uncertainty_runs', []):
        uncertain.add((entry['page'], str(entry['run'])))
        if str(entry['run']).startswith('scan:'): uncertain.add((entry['page'], 'ocr:'+str(entry['run'])[5:]))
    body, mark, notes = text.partition(UNCERTAINTY)
    if uncertain and not notes.strip(): problems.append('uncertainty-list runs recorded but the copy has no uncertainty list')
    group_units = defaultdict(list)
    for unit in units: group_units[unit['group']].append(unit['id'])
    recomputed = Counter(); mismatched = []
    lost, duplicate, split, excluded = [], [], [], []
    for line in data['lines']:
        status, groups = recompute_line(line, claims, kinds, run_reason, uncertain)
        # Mixed furniture/unit lines need their recorded per-run statuses.
        if status != line['status'] and line['status'] in ('split', 'split_unverified') and status in ('split', 'split_unverified', 'unit'):
            status = line['status']
        # A body line whose own characters were taken as furniture or left in no
        # box fails, from the evidence the writer recorded (copy_trace check e).
        if line.get('excluded_body_characters') and status not in ('lost', 'partly_lost', 'duplicate', 'furniture', 'uncertainty'):
            status = 'partly_excluded'
        recomputed[status] += 1
        if status != line['status']: mismatched.append(dict(line=line['export_id'], recorded=line['status'], recomputed=status))
        if set(groups) != set(line.get('groups', [])) and line['status'] not in ('furniture', 'uncertainty'):
            mismatched.append(dict(line=line['export_id'], recorded_groups=line.get('groups'), recomputed_groups=groups))
        record = dict(line_id=line['id'], export_id=line['export_id'], page=line['page'], text=line['text'])
        if status in ('lost', 'partly_lost'): lost.append(dict(record, status=status))
        elif status == 'duplicate': duplicate.append(dict(record, units=[u for g in groups for u in group_units[g]]))
        elif status == 'partly_excluded': excluded.append(dict(record, excluded_body_characters=line['excluded_body_characters']))
        elif status in ('split', 'split_unverified', 'flagged_repeat'): split.append(dict(record, status=status, groups=groups))
    if mismatched: problems.append(f'{len(mismatched)} line destination(s) differ from the recorded trace')
    untraced = [dict(unit_id=u['id'], kind=u['kind'], text=u['text'][:200], status=u['status'])
                for u in units if u['status'] in ('untraced', 'claims_without_lines', 'span_unresolved')]
    universe = None
    if lines_check:
        universe = check_universe(folder, pdf, data)
        if universe['differences']: problems.append(f"{len(universe['differences'])} printed line(s) differ from export_lines.py")
    total = len(data['lines']); failing = len(lost) + len(duplicate) + len(excluded)
    unit_counts = Counter(u['status'] for u in units)
    content = sum(u['status'] != 'generated' for u in units)
    statistics = dict(lines=total, line_status=dict(sorted(recomputed.items())), lines_accounted=total-failing,
        lines_accounted_share=round((total-failing)/total, 4) if total else 1.0,
        lines_exactly_one_destination=recomputed['unit']+recomputed['furniture']+recomputed['uncertainty'],
        units=len(units), unit_status=dict(sorted(unit_counts.items())), units_traced=unit_counts['traced'],
        content_units=content, units_traced_share=round(unit_counts['traced']/content, 4) if content else 1.0)
    report = dict(valid=not problems, ok=not problems and not failing and not untraced, problems=problems,
                  mismatched=mismatched[:200], statistics=statistics,
                  accounting=dict(lost_lines=lost, duplicate_lines=duplicate, partly_excluded_lines=excluded,
                                  split_lines=split, untraced_units=untraced),
                  recorded_statistics=data.get('statistics'), universe=universe)
    return report


def check_universe(folder, pdf, data):
    """Rebuild export_lines.py's printed lines and compare ids and runs."""
    if not pdf: raise ValueError('--lines needs the PDF')
    import os
    previous = os.environ.get('COPY_TRACE'); os.environ['COPY_TRACE'] = '0'
    try:
        source = collect_source(Path(folder).resolve(), Path(pdf).resolve())
    finally:
        if previous is None: os.environ.pop('COPY_TRACE', None)
        else: os.environ['COPY_TRACE'] = previous
    rebuilt = {l['export_id']: l for l in source['lines']}
    recorded = {l['export_id']: l for l in data['lines']}
    differences = []
    for key in sorted(set(rebuilt) | set(recorded)):
        a, b = rebuilt.get(key), recorded.get(key)
        if not a or not b: differences.append(dict(line=key, issue='missing in ' + ('trace' if a else 'export_lines'))); continue
        if a['id'] != b['id'].split('#')[0] or list(map(str, a['runs'])) != list(map(str, b['runs'])):
            differences.append(dict(line=key, issue='id or runs differ', export=[a['id'], a['runs']], trace=[b['id'], b['runs']]))
    return dict(lines=len(rebuilt), differences=differences)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('copy_dir');parser.add_argument('pdf',nargs='?')
    parser.add_argument('--legacy',action='store_true',help='after-the-fact text matcher (writes copy.trace.legacy.json)')
    parser.add_argument('--lines',action='store_true',help='rebuild the printed-line universe with export_lines.py')
    parser.add_argument('--json',help='write the full validation report here')
    parser.add_argument('--copy',default='copy.md',help='copy file in COPY_DIR (copy.checked.md for the check stage)')
    parser.add_argument('--trace',default='copy.trace.json',help='trace file in COPY_DIR (copy.checked.trace.json)')
    args=parser.parse_args()
    try:
        if args.legacy:
            if not args.pdf: parser.exit(2,'trace: --legacy needs the PDF\n')
            result=build(args.copy_dir,args.pdf)
            print(json.dumps(dict(ok=result['ok'], **result['statistics'])))
            if not result['ok']:
                parser.exit(1, 'trace: FAIL; see copy.trace.legacy.json accounting, unmatched units/lines and PCL errors\n')
            return
        names={k:v for k,v in (('copy_name',args.copy),('trace_name',args.trace)) if v!={'copy_name':'copy.md','trace_name':'copy.trace.json'}[k]}
        report=validate(args.copy_dir,args.pdf,args.lines,**names)
        if args.json: write_json(Path(args.json),report)
        print(json.dumps(dict(ok=report['ok'],valid=report['valid'],problems=report['problems'],**report['statistics'])))
        if not report['ok']:
            parser.exit(1,'trace: FAIL; '+('; '.join(report['problems']) if report['problems'] else
                        'lost/duplicate/partly excluded lines or untraced units are listed in the report')+'\n')
    except (OSError,ValueError,KeyError) as exc:parser.exit(2,f'trace: {exc}\n')


if __name__=='__main__':main()
