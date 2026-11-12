#!/usr/bin/env python3
"""Show a trace unit's outlined PDF regions or a line's exact copy spans.

/usr/bin/python3 -I tools/trace_show.py COPY_DIR UNIT_OR_LINE [--out file.png]

A unit writes a PNG (by default COPY_DIR/trace-UNIT.png) and prints the copy
span and source IDs. A line prints every destination span, its furniture reason
or its unresolved text; --out also renders that line. Multiple pages become
separate panels in one PNG, ordered by the unit's first use of each page.
Uses only the standard library and pdftoppm. Existing trace/copy/PDF hashes are
checked before showing anything; stale provenance is an error.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import subprocess
import sys
import zlib


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def ppm(data):
    """Read Poppler's binary RGB PPM, including legal header comments."""
    at=0;tokens=[]
    while len(tokens)<4:
        while at<len(data) and data[at] in b' \t\r\n':at+=1
        if at<len(data) and data[at]==35:
            at=data.index(b'\n',at)+1;continue
        end=at
        while end<len(data) and data[end] not in b' \t\r\n':end+=1
        if end==at:raise ValueError('truncated PPM header')
        tokens.append(data[at:end]);at=end
    if tokens[0]!=b'P6' or tokens[3]!=b'255':raise ValueError('expected 8-bit RGB PPM')
    if data[at:at+2]==b'\r\n':at+=2
    else:at+=1
    width,height=map(int,tokens[1:3]);pixels=bytearray(data[at:])
    if width<=0 or height<=0 or len(pixels)!=width*height*3:raise ValueError('invalid PPM raster length')
    return width,height,pixels


def png_bytes(width,height,pixels):
    def chunk(kind,value):return struct.pack('>I',len(value))+kind+value+struct.pack('>I',zlib.crc32(kind+value)&0xffffffff)
    raw=b''.join(b'\0'+pixels[y*width*3:(y+1)*width*3] for y in range(height))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw,6))+chunk(b'IEND',b'')


def rectangle(pixels,width,height,box,color=(215,30,40)):
    left,top,right,bottom=[round(v) for v in box]
    left=max(0,left-1);top=max(0,top-1);right=min(width-1,right+1);bottom=min(height-1,bottom+1)
    for y in range(top,bottom+1):
        for x in (range(left,right+1) if y in (top,bottom) else (left,right)):
            at=3*(y*width+x);pixels[at:at+3]=bytes(color)


def render(pdf, sources, output):
    groups={}
    for source in sources:
        groups.setdefault(source['page'],{})[source.get('line_id',source.get('id'))]=source['box_110dpi']
    if not groups:raise ValueError('no matched source lines to render')
    panels=[];metadata=[]
    for page,records in groups.items():
        boxes=list(records.values());left=max(0,math.floor(min(b[0] for b in boxes))-18);top=max(0,math.floor(min(b[1] for b in boxes))-18)
        right=math.ceil(max(b[2] for b in boxes))+18;bottom=math.ceil(max(b[3] for b in boxes))+18
        command=['pdftoppm','-r','110','-f',str(page),'-l',str(page),'-singlefile','-x',str(left),'-y',str(top),'-W',str(right-left),'-H',str(bottom-top),str(pdf)]
        result=subprocess.run(command,check=True,capture_output=True,timeout=120)
        width,height,pixels=ppm(result.stdout)
        for box in boxes:rectangle(pixels,width,height,[box[0]-left,box[1]-top,box[2]-left,box[3]-top])
        panels.append((width,height,pixels));metadata.append(dict(page=page,crop_110dpi=[left,top,left+width,top+height],lines=list(records)))
    width=max(p[0] for p in panels);height=sum(p[1] for p in panels)+16*(len(panels)-1)
    canvas=bytearray(b'\xff')*(width*height*3);y=0
    for w,h,pixels in panels:
        for row in range(h):
            start=((y+row)*width)*3;canvas[start:start+w*3]=pixels[row*w*3:(row+1)*w*3]
        y+=h+16
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(png_bytes(width,height,canvas))
    return metadata


def show(folder, identifier, output=None, pdf=None):
    folder=Path(folder);data=json.loads((folder/'copy.trace.json').read_text());copy_path=folder/'copy.md'
    if sha(copy_path)!=data['copy']['sha256']:raise ValueError('copy.md has changed; rerun trace.py')
    pdf=Path(pdf or data['pdf']['path'])
    if sha(pdf)!=data['pdf']['sha256']:raise ValueError('PDF has changed; rerun trace.py')
    text=copy_path.read_text(encoding='utf-8')
    unit=next((u for u in data['units'] if u['id']==identifier),None)
    line=next((l for l in data['lines'] if l['id']==identifier or l.get('export_id')==identifier),None)
    if unit:
        report=dict(id=identifier,kind=unit['kind'],status=unit['status'],copy_span=unit['span'],text=text[slice(*unit['span'])],
                    sources=[s['line_id'] for s in unit['sources']],unmatched=unit['unmatched'])
        sources=unit['sources']
        output=output or (folder/f'trace-{identifier}.png' if sources else None)
    elif line:
        report=dict(id=line['id'],export_id=line.get('export_id'),status=line['status'],text=line['text'],destinations=[dict(unit_id=d['unit_id'],span=d['copy_span'],text=text[slice(*d['copy_span'])]) for d in line['units']],
                    furniture_reason=line.get('furniture_reason'),unmatched=line['unmatched'])
        sources=[line]
    else:raise ValueError(f'unknown unit or line: {identifier}')
    if output:
        if not sources:raise ValueError('unit has no source witness; inspect its unmatched explanation')
        report['panels']=render(pdf,sources,output);report['image']=str(output)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('copy_dir');parser.add_argument('unit_or_line')
    parser.add_argument('--out');parser.add_argument('--pdf',help='relocated PDF with the identical hash')
    args=parser.parse_args()
    try:print(json.dumps(show(args.copy_dir,args.unit_or_line,args.out,args.pdf),ensure_ascii=True,indent=2))
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as exc:parser.exit(2,f'trace_show: {exc}\n')


if __name__=='__main__':main()
