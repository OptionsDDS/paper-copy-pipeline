"""Renderer raster, crop geometry, multipage panels and stale-data checks."""
import hashlib
import importlib.util
import json
import pathlib
import struct
import tempfile
import unittest
from unittest.mock import patch

ROOT=pathlib.Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('show_tests',ROOT/'tools/trace_show.py')
s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)

class Show(unittest.TestCase):
    def test_ppm_keeps_first_whitespace_pixel(self):
        raster=b'\n\x00\xff'*6
        w,h,p=s.ppm(b'P6\n# Comment\n3 2\n255\n'+raster)
        self.assertEqual((w,h),(3,2));self.assertEqual(bytes(p),raster)
        with self.assertRaises(ValueError):s.ppm(b'P6\n1 2\n255\nshort')

    def test_png_dimensions_and_rectangle(self):
        pixels=bytearray(b'\xff'*300)
        s.rectangle(pixels,10,10,[2,2,7,7])
        result=s.png_bytes(10,10,pixels)
        self.assertEqual(result[:8],b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('>II',result[16:24]),(10,10))
        self.assertNotEqual(pixels,bytearray(b'\xff'*300))

    def test_render_crop_and_multi_page_order(self):
        calls=[]
        def run(command,**kwargs):
            calls.append(command)
            class Reply:stdout=b'P6\n100 100\n255\n'+b'\xff'*30000
            return Reply()
        with tempfile.TemporaryDirectory() as folder,patch.object(s.subprocess,'run',run):
            output=pathlib.Path(folder)/'regions.png'
            meta=s.render('paper.pdf',[dict(line_id='p2.l001',page=2,box_110dpi=[30,40,50,60]),dict(line_id='p1.l001',page=1,box_110dpi=[10,20,30,40])],output)
            self.assertEqual([m['page'] for m in meta],[2,1])
            self.assertEqual(meta[0]['crop_110dpi'][:2],[12,22])
            self.assertEqual(calls[0][calls[0].index('-r')+1],'110')
            self.assertEqual(struct.unpack('>II',output.read_bytes()[16:24]),(100,216))

    def test_stale_copy_refused(self):
        with tempfile.TemporaryDirectory() as folder:
            path=pathlib.Path(folder);(path/'copy.md').write_text('changed')
            (path/'copy.trace.json').write_text(json.dumps(dict(copy=dict(sha256='wrong'))))
            with self.assertRaisesRegex(ValueError,'copy.md has changed'):s.show(path,'u00001')

if __name__=='__main__':unittest.main()
