#!/usr/bin/env python3
"""Read unmapped (U+FFFD) native glyphs, then check font trust with offline OCR.

Render each affected run at 300 dpi, upright, using the reader's character
boxes and PDF page origin/rotation. Align compact OCR and native text; retain
every native character and space. A replacement needs unchanged anchors, its
own TSV word confidence >= 60, and a matching whole word for letters/digits.
Letters/digits additionally need confidence >= 95 and three known letters in
that word. Short unit prefixes are too easily confused with Latin letters.
Basic arithmetic signs must also agree with the glyph's raster strokes: an
OCR '+' on a printed plus/minus must stay unknown. Dash typography from OCR
is normalized to minus only before a number, after checking a horizontal bar.
Comparisons require the same isolated lower-bar raster check as sign fonts;
a confirmed separate bar upgrades < or >, and ambiguous geometry stays unknown.

Only ocr_text, ocr_conf, ocr_subs and ocr_model are added to successful runs.
Older cached comparisons are rechecked; failed verification removes their
old OCR metadata, including when source geometry cannot be verified.
Unknowns, original text, geometry and character IDs are preserved. Missing
OCR, unsupported geometry, bad alignment or unreadable crops leave U+FFFD.
No glyph-name guesses, lexical corrections, models or downloads are used.
Crop workers run concurrently; their temporary images are deleted. A JSON
report records every attempt and rejection, including unresolved glyphs with
their character IDs, font names, raw codes and offsets. The reading layer's
unmapped glyphs already arrive as U+FFFD; this pass never silently removes one.
After this pass, check_fonts.py verifies suspect font/code claims against
DejaVu glyph rasters, including claimed signs, two-part punctuation set in a
sign face beside a number, and marker-font letters. A
replacement needs confidence/raster-gated OCR or a decisive competing shape
with independent stroke evidence; weaker separated evidence is flagged.
It also screens embedded outlines once per font/code, including valid-looking
URL, DOI and e-mail characters and duplicate letter/digit claims. Confident
shape alternatives can correct these claims; ambiguous mismatches keep the
text and carry page/run/glyph notices into the copy. This additional pass
uses precomputed reference silhouettes and no page rendering or OCR calls.
Solid midline bars claimed as letters also retain their em-relative length for
en/em dash decisions. Thin arrows in symbol fonts use shaft/wing topology with
independent template support; ambiguous symbol-font punctuation is flagged.
Its separately recorded font_subs never alter this pass's U+FFFD decisions.
It also reads private-use codes of Symbol fonts through the Adobe Symbol
encoding with an outline check; this OCR pass never treats them as U+FFFD.

Usage: /usr/bin/python3 -I tools/read_signs.py PAPER_DIR PAPER.pdf
Exit 0 includes safely unresolved glyphs; exit 1 means an OCR/runtime failure.
"""

import argparse
import collections
from concurrent.futures import ThreadPoolExecutor
import csv
import difflib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


ROOT = Path(__file__).resolve().parents[1]
shapes = module('_sign_shapes', ROOT / 'tools/read_shapes.py')
copy = module('_sign_copy', ROOT / 'copy_paper.py')
SIGNS = set('−-–±+=<>≤≥µ×°')   # no %, ~, ≈: tesseract confuses × with % and ~ with -, and a wrong sign is worse than a flagged one (G01 "100×" read as "100%")


def page_transform(doc, page_number, dpi):
    """Boxer pixels -> CropBox-rendered pixels, including nonzero PDF origins."""
    _, height, box = doc.page_size(page_number)
    rotate = doc.pages[page_number - 1].rotate % 360
    if rotate not in (0, 90, 180, 270):
        raise ValueError('unsupported page rotation')
    scale = dpi / 72
    width, depth = box[2] - box[0], box[3] - box[1]
    def transform(b):
        points = []
        for x, y in ((b[0], b[1]), (b[2], b[3]), (b[0], b[3]), (b[2], b[1])):
            u, v = x / scale - box[0], y / scale + box[3] - height
            u, v = {0: (u, v), 90: (depth-v, u),
                    180: (width-u, depth-v), 270: (v, width-u)}[rotate]
            points.append((u*scale, v*scale))
        return [min(x for x,y in points), min(y for x,y in points),
                max(x for x,y in points), max(y for x,y in points)]
    return transform, rotate


def ppm_read(path):
    data = path.read_bytes()
    match = re.match(rb'P6\s+(\d+)\s+(\d+)\s+255(?:\r\n|\s)', data)
    if not match:
        raise ValueError('invalid RGB PPM')
    width, height = map(int, match.groups())
    pixels = data[match.end():]
    if len(pixels) != width*height*3:
        raise ValueError('incomplete RGB PPM')
    return width, height, pixels


def upright(width, height, pixels, angle):
    """Clockwise quarter turns undo text reading bottom-to-top in the PDF."""
    if angle == 0: return width, height, pixels
    if angle == 180:
        return width, height, b''.join(pixels[i:i+3] for i in range(len(pixels)-3, -1, -3))
    if angle == 90:
        order = ((x,y) for x in range(width) for y in range(height-1,-1,-1))
    elif angle == 270:
        order = ((x,y) for x in range(width-1,-1,-1) for y in range(height))
    else:
        raise ValueError('unsupported text angle')
    return height, width, b''.join(pixels[(y*width+x)*3:(y*width+x+1)*3] for x,y in order)


def arithmetic_shape(image, box, crop, dpi, angle):
    """Conservative pixel veto for confused arithmetic signs, never an OCR replacement."""
    width, height, pixels = image
    x,y = crop[:2]; scale = 300/dpi
    left, top = max(0, math.floor(box[0]*scale)-x), max(0, math.floor(box[1]*scale)-y)
    right, bottom = min(width, math.ceil(box[2]*scale)-x), min(height, math.ceil(box[3]*scale)-y)
    if right <= left or bottom <= top: return ''
    data = b''.join(pixels[(v*width+left)*3:(v*width+right)*3] for v in range(top,bottom))
    w,h,data = upright(right-left,bottom-top,data,angle)
    ink = [(i%w,i//w) for i in range(w*h) if min(data[3*i:3*i+3]) < 160]
    if not ink: return ''
    x0,x1 = min(x for x,y in ink),max(x for x,y in ink)
    y0,y1 = min(y for x,y in ink),max(y for x,y in ink)
    w,h = x1-x0+1,y1-y0+1
    rows = collections.Counter(y-y0 for x,y in ink)
    bars = []
    for y in range(h):
        if rows[y] >= .7*w:
            if bars and bars[-1][-1] == y-1: bars[-1].append(y)
            else: bars.append([y])
    if len(bars) == 1 and w >= 2.5*h: return '−'
    if len(bars) == 1 and .5*w <= h <= 2*w and bars[0][0] > .15*h and bars[0][-1] < .85*h:
        return '+'
    if len(bars) == 2:
        gap = range(bars[0][-1]+1,bars[1][0])
        if gap and all(rows[y] <= .12*w for y in gap) and bars[0][0] <= .15*h:
            return '='
        if bars[0][0] > .15*h and bars[1][-1] >= .8*h:
            return '±'
    return ''


def tsv_words(tsv):
    words = []
    for row in csv.DictReader(io.StringIO(tsv), delimiter='\t', quoting=csv.QUOTE_NONE):
        if row.get('level') != '5' or not row.get('text','').strip(): continue
        conf = float(row['conf'])
        if not math.isfinite(conf) or not 0 <= conf <= 100:
            raise ValueError('invalid OCR confidence')
        words.append((row['text'].strip(), conf))
    if not words: raise ValueError('OCR returned no words')
    return words


def align(source, words):
    """Only one-for-one unknowns in anchored matching spans; whitespace stays native."""
    positions = [i for i,ch in enumerate(source) if not ch.isspace()]
    native = ''.join(source[i] for i in positions)
    target, confidences, word_spans = '', [], []
    for word, conf in words:
        word = re.sub(r'\s','',word)
        word_spans.append((len(target),len(target)+len(word)))
        target += word
        confidences.extend([conf]*len(word))
    matcher = difflib.SequenceMatcher(None,native,target,autojunk=False)
    opcodes = matcher.get_opcodes()
    mapping, candidates = {}, []
    for tag,a,b,c,d in opcodes:
        if tag == 'equal' or tag == 'replace' and b-a == d-c:
            mapping.update(zip(range(a,b),range(c,d)))
        if tag == 'replace' and b-a == d-c:
            for i,j in zip(range(a,b),range(c,d)):
                if native[i] != '�': continue
                # Nearby printed characters must anchor the location on both sides.
                if any(0 <= k < len(native) and (k not in mapping or native[k] != target[mapping[k]])
                       for k in range(max(a,i-2),i) if native[k] != '�'):
                    continue
                candidates.append((i,j))
    result=[]
    for i,j in candidates:
        ch=target[j]; conf=confidences[j]
        if conf < 60: continue
        # Reject an OCR edit to either immediate known neighbour. Edge glyphs need
        # an anchor on the available side; wholly unknown words are never filled.
        neighbors = [k for k in (i-1,i+1) if 0<=k<len(native) and native[k]!='�']
        if not neighbors or any(k not in mapping or native[k]!=target[mapping[k]] for k in neighbors): continue
        if ch in '—–-−' and i+1<len(native) and native[i+1].isdigit(): ch='−'
        if ch=='μ': ch='µ'
        if ch not in SIGNS:
            if not ch.isalnum() or conf < 95: continue
            left,right = next((a,b) for a,b in word_spans if a<=j<b)
            offset = i-j
            a,b = left+offset,right+offset
            if not 0<=a<=i<b<=len(native): continue
            known = [k for k in range(a,b) if native[k]!='�']
            if sum(native[k].isalpha() for k in known)<3: continue
            if any(mapping.get(k)!=k-offset or native[k]!=target[k-offset] for k in known): continue
            # Require native whitespace/punctuation boundaries too; a matched
            # substring of an OCR word is insufficient evidence for a letter.
            if a and native[a-1].isalnum() and not source[positions[a-1]+1:positions[a]].isspace(): continue
            if b<len(native) and native[b].isalnum() and not source[positions[b-1]+1:positions[b]].isspace(): continue
        result.append(dict(offset=positions[i], before='�', after=ch, confidence=conf, ocr_char=target[j]))
    return result


def collect(folder, pdf):
    pages, records = {}, []
    for path in sorted(folder.glob('page-[0-9]*.json')):
        raw=path.read_bytes(); page=json.loads(raw)
        affected=[(i,e) for i,e in enumerate(page['elements']) if e.get('kind')=='text' and '�' in e['text']]
        if not affected: continue
        pages[str(path)]=(raw,page)
        # A temporary view prevents reader caches entering saved JSON.
        view=dict(page,_table_pdf=str(pdf))
        chars=copy.table_characters(view)
        doc=sys.modules['_copy_table_reader'].sc_doc(str(pdf))
        dpi=page.get('params',{}).get('dpi',150)
        transform,rotate=page_transform(doc,page['page'],dpi)
        for index,e in affected:
            record=dict(file=str(path),index=index,id=e['id'],page=page['page'],pdf=str(pdf),
                        source=e['text'],boxer_dpi=dpi,status='pending')
            records.append(record)
            ids=e.get('char_ids',[])
            cs=[(i,chars[i]) for i in ids if chars[i]['text'].strip()] if ids and min(ids)>=0 and max(ids)<len(chars) else []
            if re.sub(r'\s','',e['text'])!=''.join(re.sub(r'\s','',c['text']) for i,c in cs):
                record.update(status='unresolved',reason='character IDs do not match native text');continue
            angle=(round(e['angle'])-rotate)%360
            if angle not in (0,90,180,270):
                record.update(status='unresolved',reason='unsupported text angle');continue
            expanded=[(i,c) for i,c in cs for ch in c['text'] if not ch.isspace()]
            glyphs={}
            for offset,(i,c) in zip((i for i,ch in enumerate(e['text']) if not ch.isspace()),expanded):
                if e['text'][offset]=='�':
                    ox,oy=c['origin']
                    glyphs[offset]=dict(char_id=i,font=c['font'],source_code=c.get('source_code'),
                                       box_px=transform([c[k] for k in ('x0','y0','x1','y1')]),
                                       em=c['size']*300/dpi,origin_px=transform([ox,oy,ox,oy]))
            record.update(crop_xywh=shapes.crop_rectangle(transform(e['box_px']),dpi),angle=angle,glyphs=glyphs)
            if e.get('ocr_subs') and (e.get('ocr_model') == 'tesseract-bars-v2' or
                                     not any(s.get('after') in '<>≤≥' for s in e['ocr_subs'])):
                record.update(status='existing',ocr_text=e.get('ocr_text'),ocr_subs=e['ocr_subs'])
    return pages,records


def recognize(task, scratch, binary, data, libs):
    result=dict(file=task['file'],index=task['index'],status='unresolved')
    started=time.perf_counter()
    with tempfile.TemporaryDirectory(dir=scratch,prefix='run-') as temp:
        path=Path(temp)/'crop.ppm'
        try:
            x,y,w,h=task['crop_xywh']
            subprocess.run(['pdftoppm','-cropbox','-f',str(task['page']),'-l',str(task['page']),
                            '-singlefile','-r','300','-x',str(x),'-y',str(y),'-W',str(w),'-H',str(h),
                            task['pdf'],str(path.with_suffix(''))],check=True,capture_output=True,timeout=15)
            original=ppm_read(path)
            width,height,pixels=upright(*original,task['angle'])
            path.write_bytes(f'P6\n{width} {height}\n255\n'.encode()+pixels)
            env=dict(os.environ,OMP_THREAD_LIMIT='1')
            env['LD_LIBRARY_PATH']=str(libs)+(os.pathsep+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
            reply=subprocess.run([str(binary),str(path),'stdout','--tessdata-dir',str(data),'-l','eng',
                                  '--psm','7','-c','tessedit_create_tsv=1'],check=True,capture_output=True,
                                 text=True,env=env,timeout=15)
            words=tsv_words(reply.stdout)
            result['reading']=' '.join(word for word,conf in words)
            subs=[]; rejected=[]
            for sub in align(task['source'],words):
                glyph=task['glyphs'][sub['offset']]
                if sub['after'] in '−-–+=±':
                    shape=arithmetic_shape(original,glyph['box_px'],task['crop_xywh'],task['boxer_dpi'],task['angle'])
                    if shape != ('−' if sub['after'] in '−-–' else sub['after']):
                        rejected.append(dict(sub,reason='glyph strokes disagree with OCR',shape=shape));continue
                if sub['after'] in '<>≤≥':
                    fonts = module('_sign_bar_checks', ROOT / 'tools/check_fonts.py')
                    box = fonts.local_box(task,glyph['box_px'],original)
                    upright_image = upright(*original,task['angle'])
                    crop,isolated = fonts.isolate_glyph(upright_image,box,[],300)
                    baseline = fonts.local_box(task,glyph['origin_px'],original)[1]-crop[1]
                    candidates = fonts.raster_symbols(isolated,glyph['em'],baseline)
                    after,reason = fonts.comparison_decision(dict(text=sub['after'],confidence=sub['confidence'],status='read'),candidates)
                    if after is None:
                        rejected.append(dict(sub,reason=reason,raster_symbols=candidates));continue
                    sub = dict(sub,after=after,raster_symbols=candidates)
                subs.append(dict(sub,char_id=glyph['char_id']))
            result['rejected']=rejected
            if subs:
                text=list(task['source'])
                for sub in subs: text[sub['offset']]=sub['after']
                result.update(status='read',ocr_text=''.join(text),ocr_conf=min(s['confidence'] for s in subs),
                              ocr_subs=subs,ocr_model='tesseract-bars-v2')
            else: result['reason']='no safe aligned replacement'
        except ValueError as exc:
            result['reason']=str(exc)
        except (OSError,subprocess.SubprocessError) as exc:
            result.update(status='error',reason=f'{type(exc).__name__}: {exc}')
    result['seconds']=time.perf_counter()-started
    return result


def apply_results(pages,records,results):
    by_key={(r['file'],r['index']):r for r in records};changed=set()
    for result in results:
        record=by_key[result['file'],result['index']]
        record.update(result)
        page=pages[result['file']][1]
        element=page['elements'][result['index']]
        previous={key:element[key] for key in ('ocr_text','ocr_conf','ocr_subs','ocr_model') if key in element}
        # Revalidation may withdraw an older, barless comparator reading.
        for key in ('ocr_text','ocr_conf','ocr_subs','ocr_model'): element.pop(key,None)
        if result['status']=='read':
            element.update({k:result[k] for k in ('ocr_text','ocr_conf','ocr_subs','ocr_model')})
        current={key:element[key] for key in ('ocr_text','ocr_conf','ocr_subs','ocr_model') if key in element}
        if current != previous: changed.add(result['file'])
    for filename in changed:
        if Path(filename).read_bytes()!=pages[filename][0]:raise ValueError('page changed during sign OCR: '+filename)
    for filename in sorted(changed):
        path=Path(filename)
        with tempfile.NamedTemporaryFile('w',dir=path.parent,prefix='.signs-',delete=False) as stream:
            temp=Path(stream.name)
            try:
                json.dump(pages[filename][1],stream,ensure_ascii=False,indent=2);stream.write('\n')
            except BaseException:
                temp.unlink(missing_ok=True);raise
        try:
            temp.chmod(path.stat().st_mode & 0o777);temp.replace(path)
        finally:temp.unlink(missing_ok=True)
    return len(changed)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder',type=Path);parser.add_argument('pdf',type=Path)
    parser.add_argument('--report',type=Path)
    parser.add_argument('--workers',type=int,default=4,choices=range(1,9))
    parser.add_argument('--tesseract',type=Path,default=shapes.TESSERACT)
    parser.add_argument('--tessdata',type=Path,default=shapes.TESSDATA)
    parser.add_argument('--tesseract-libs',type=Path,default=shapes.TESS_LIBS)
    args=parser.parse_args(argv);started=time.perf_counter()
    try:
        pages,records=collect(args.folder.resolve(),args.pdf.resolve())
        pending=[r for r in records if r['status']=='pending']
        with tempfile.TemporaryDirectory(dir=args.folder,prefix='.read-signs-') as scratch:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                results=list(pool.map(lambda r:recognize(r,scratch,args.tesseract,args.tessdata,args.tesseract_libs),pending))
        # A cached comparison also loses its authority when source IDs or
        # geometry cannot be verified, even before an OCR task can be formed.
        results.extend(r for r in records if r['status']=='unresolved')
        changed=apply_results(pages,records,results)
        report=dict(seconds=time.perf_counter()-started,runs=len(records),changed_pages=changed,
                    statuses=dict(collections.Counter(r['status'] for r in records)),
                    substitutions=sum(len(r.get('ocr_subs',[])) for r in records),elements=records)
        (args.report or args.folder/'signs-ocr.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k!='elements'}))
        font_status = module('_sign_font_checker', ROOT / 'tools/check_fonts.py').check(
            args.folder, args.pdf, args.workers, args.tesseract, args.tessdata, args.tesseract_libs)
        return int(any(r['status']=='error' for r in records) or font_status)
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(f'read_signs: {type(exc).__name__}: {exc}',file=sys.stderr);return 1


if __name__=='__main__':
    raise SystemExit(main())
