"""Small standard-library RGB renderer. PDF rendering is exclusively pdftoppm.

Bundles store one compressed RGB PNG per page, never one image per question.
Outlines and crops are generated in memory for each request. This PNG reader
accepts only our own filter-0, 8-bit RGB, non-interlaced files (fail closed).
"""
import math
from pathlib import Path
import re
import struct
import subprocess
import zlib


def encode(width, height, pixels):
    if len(pixels) != width * height * 3:
        raise ValueError('RGB length mismatch')
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    stride = width * 3
    raw = b''.join(b'\0' + pixels[y * stride:(y + 1) * stride] for y in range(height))
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw, 6)) + chunk(b'IEND', b''))


def decode(data):
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a checker PNG')
    at, compressed, dimensions = 8, bytearray(), None
    while at + 12 <= len(data):
        size = struct.unpack('>I', data[at:at + 4])[0]
        kind, body = data[at + 4:at + 8], data[at + 8:at + 8 + size]
        if len(body) != size or data[at + 8 + size:at + 12 + size] != struct.pack('>I', zlib.crc32(kind + body)):
            raise ValueError('corrupt PNG chunk')
        if kind == b'IHDR':
            w, h, depth, color, comp, filt, interlace = struct.unpack('>IIBBBBB', body)
            if (depth, color, comp, filt, interlace) != (8, 2, 0, 0, 0) or not 0 < w * h <= 40_000_000:
                raise ValueError('unsupported PNG format or dimensions')
            dimensions = w, h
        elif kind == b'IDAT':
            compressed.extend(body)
        elif kind == b'IEND':
            break
        at += size + 12
    if dimensions is None:
        raise ValueError('PNG dimensions missing')
    w, h = dimensions
    raw = zlib.decompress(compressed)
    stride = 3 * w + 1
    if len(raw) != stride * h or any(raw[y * stride] != 0 for y in range(h)):
        raise ValueError('PNG must use checker filter-0 encoding')
    return w, h, bytearray(b''.join(raw[y * stride + 1:(y + 1) * stride] for y in range(h)))


def render(pdf, page, dpi=110):
    data = subprocess.run(['pdftoppm', '-r', str(dpi), '-f', str(page), '-l', str(page),
                           '-singlefile', str(pdf)], check=True, capture_output=True, timeout=180).stdout
    # Consume exactly the delimiter after maxval; the first pixel can be whitespace.
    m = re.match(rb'P6\s+(\d+)\s+(\d+)\s+255(?:\r\n|\s)', data)
    if not m:
        raise ValueError('pdftoppm did not return 8-bit RGB PPM')
    w, h = int(m[1]), int(m[2])
    pixels = data[m.end():]
    if len(pixels) != w * h * 3:
        raise ValueError('truncated PPM')
    return w, h, bytearray(pixels)


FONT = {
    'A': ['010','101','111','101','101'], 'B': ['110','101','110','101','110'],
    'F': ['111','100','110','100','100'], 'C': ['111','100','100','100','111'],
    '0': ['111','101','101','101','111'], '1': ['010','110','010','010','111'],
    '2': ['110','001','010','100','111'], '3': ['110','001','010','001','110'],
    '4': ['101','101','111','001','001'], '5': ['111','100','110','001','110'],
    '6': ['011','100','111','101','111'], '7': ['111','001','010','010','010'],
    '8': ['111','101','111','101','111'], '9': ['111','101','111','001','110'],
}


def outlined(image, marks):
    w, h, source = image
    pixels = bytearray(source)
    def rect(x0, y0, x1, y1, color):
        row = bytes(color) * max(0, min(w, x1) - max(0, x0))
        for y in range(max(0, y0), min(h, y1)):
            start = 3 * (y * w + max(0, x0))
            pixels[start:start + len(row)] = row
    for mark in marks:
        x0, y0, x1, y1 = [round(x) for x in mark['box']]
        color = mark.get('color', [220, 20, 30])
        rect(x0, y0, x1, y0 + 2, color); rect(x0, y1 - 2, x1, y1, color)
        rect(x0, y0, x0 + 2, y1, color); rect(x1 - 2, y0, x1, y1, color)
        label = mark.get('label', '')
        lx, ly = max(0, min(w - len(label) * 8 - 2, x0)), max(0, y0 - 12)
        if label:
            rect(lx, ly, lx + len(label) * 8, ly + 11, [255, 255, 255])
        for i, ch in enumerate(label):
            for y, row in enumerate(FONT[ch]):
                for x, bit in enumerate(row):
                    if bit == '1':
                        rect(lx + i * 8 + x * 2, ly + y * 2, lx + i * 8 + x * 2 + 2, ly + y * 2 + 2, color)
    return w, h, pixels


def crop(image, box):
    w, h, pixels = image
    x0, y0 = max(0, math.floor(box[0])), max(0, math.floor(box[1]))
    x1, y1 = min(w, math.ceil(box[2])), min(h, math.ceil(box[3]))
    if x0 >= x1 or y0 >= y1:
        raise ValueError('empty image crop')
    return x1 - x0, y1 - y0, b''.join(pixels[3 * (y * w + x0):3 * (y * w + x1)] for y in range(y0, y1))


def view_bytes(path, view):
    image = outlined(decode(Path(path).read_bytes()), view.get('marks', []))
    if view.get('crop'):
        image = crop(image, view['crop'])
    return encode(*image)
