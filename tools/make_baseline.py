"""Baseline record from a run folder holding the 15 baseline papers. Usage: make_baseline.py RUN_DIR WHAT_JSON_STRING PROGRAM_JSON_STRING"""
import json, glob, os, sys, hashlib
run = sys.argv[1]
ORDER = ["slots", "medicina", "montero", "jcpe-1198", "jcpe-13198", "S01", "S02", "S03", "S04", "S05", "P1", "P2", "P3", "P4", "P5"]
papers = {}
for n in ORDER:
    d = os.path.join(run, n)
    pages = [json.load(open(f)) for f in sorted(glob.glob(d + "/page-[0-9]*.json"))]
    try: a = json.load(open(d + "/authors.json"))
    except Exception: a = None
    files = sorted([os.path.basename(f) for f in glob.glob(d + "/page-[0-9]*.json")] + [f for f in ("main-text.txt", "main-text.json", "authors.json") if os.path.exists(os.path.join(d, f))])
    papers[n] = {"pages": len(pages), "tables": sum(len(p["tables"]) for p in pages), "floats": sum(len(p["floats"]) for p in pages),
                 "main_text_lines": sum(b["lines"] for p in pages for b in p["main_text"]["blocks"] if b["cls"] == "main"),
                 "furniture_lines": sum(b["lines"] for p in pages for b in p["main_text"]["blocks"] if b["cls"] == "furniture"),
                 "rule8_status": a["checks"].get("status") if a else None, "rule8_authors": len(a.get("authors", [])) if a else None,
                 "rule8_affiliations": (len(a["affiliations"]) if a.get("affiliations") else None) if a else None,
                 "files": {f: hashlib.sha256(open(os.path.join(d, f), "rb").read()).hexdigest() for f in files}}
print(json.dumps({"what": sys.argv[2], "program": json.loads(sys.argv[3]), "papers": papers}, indent=1, ensure_ascii=False))
