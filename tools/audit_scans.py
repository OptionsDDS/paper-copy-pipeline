"""Survey PDF-native scan evidence, including near misses, without writing source files.

Usage: /usr/bin/python3 -I tools/audit_scans.py OUTPUT.json PDFMAP.json [...]
Map namespaces avoid confusing papers with the same short identifier.
"""
import importlib.util
import json
from pathlib import Path
import sys


def main(output, maps):
    root=Path(__file__).resolve().parents[1]
    spec=importlib.util.spec_from_file_location('scan_audit_reader',root/'standalone/element_boxer_sc.py')
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    results=[]
    for mapping in maps:
        for name,pdf in sorted(json.loads(Path(mapping).read_text()).items()):
            doc=reader.sc_doc(pdf);pages=[]
            for number,page in enumerate(doc.pages,1):
                sink=reader.SCSink()
                interp=reader.SCInterpreter(doc.rsrc,reader.PDFDevice(doc.rsrc),sink,doc,0)
                interp.sc_start={'bbox_local':doc.page_size(number)[2]}
                interp.render_contents(page.resources,page.contents,ctm=reader.MATRIX_IDENTITY)
                pages.append(dict(page=number,**reader.sc_scan_evidence(doc,number,sink,full=True)))
            item=dict(set=Path(mapping).stem,id=name,pdf=pdf,pages=pages,
                ocr_document=sum(p['ocr_layer'] for p in pages)>len(pages)/2)
            results.append(item)
            doc.fp.close();reader.SC_DOCS.clear()
            if any(p['candidate'] for p in pages):
                print(Path(mapping).stem,name,'OCR' if item['ocr_document'] else 'near',flush=True)
    Path(output).write_text(json.dumps(dict(papers=results),ensure_ascii=False,indent=2)+'\n')
    print(f'{len(results)} papers; {sum(r["ocr_document"] for r in results)} OCR documents',flush=True)


if __name__=='__main__':main(sys.argv[1],sys.argv[2:])
