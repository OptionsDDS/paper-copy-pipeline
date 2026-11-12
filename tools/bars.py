"""Stage bars between a base run and a new run, per paper: rule 8 status, main-text lines, tables, floats,
pdftotext-vocabulary tokens lost from main text, unknown-token share. Usage: bars.py BASE NEW PDFMAP.json"""
import sys, os, re, json, glob, collections, subprocess
A, B, pdfs = sys.argv[1], sys.argv[2], json.load(open(sys.argv[3]))
tot = collections.Counter(); notes = []
for n, pdf in sorted(pdfs.items()):
    ref = set(w.lower() for w in re.findall(r"[A-Za-z]{3,}", subprocess.run(["pdftotext", pdf, "-"], capture_output=True, text=True).stdout))
    def stats(d):
        t = open(f"{d}/{n}/main-text.txt", encoding="utf-8").read()
        toks = [w.lower() for w in re.findall(r"[A-Za-z]{3,}", t)]
        known = collections.Counter(w for w in toks if w in ref)
        lines = sum(1 for l in t.split("\n") if l.strip() and not l.startswith("#"))
        pages = [json.load(open(f)) for f in sorted(glob.glob(f"{d}/{n}/page-[0-9]*.json"))]
        try: st = json.load(open(f"{d}/{n}/authors.json"))["checks"].get("status")
        except Exception: st = None
        return dict(known=known, unk=sum(1 for w in toks if w not in ref), toks=len(toks), lines=lines,
                    tables=sum(len(p["tables"]) for p in pages), floats=sum(len(p["floats"]) for p in pages), r8=st)
    a, b = stats(A), stats(B)
    lost = sum((a["known"] - b["known"]).values()); gained = sum((b["known"] - a["known"]).values())
    tot["lost"] += lost; tot["gained"] += gained; tot["unk_a"] += a["unk"]; tot["unk_b"] += b["unk"]; tot["toks_a"] += a["toks"]; tot["toks_b"] += b["toks"]
    tot["tables_a"] += a["tables"]; tot["tables_b"] += b["tables"]; tot["floats_a"] += a["floats"]; tot["floats_b"] += b["floats"]
    if a["r8"] != b["r8"]:
        v = a["r8"] == "verified"; tot["r8_lost" if v else ("r8_gained" if b["r8"] == "verified" else "r8_other")] += 1
        notes.append(f"{n}: rule 8 {a['r8']} -> {b['r8']}")
    if b["lines"] < 0.95 * a["lines"]: tot["lines_down_5pct"] += 1; notes.append(f"{n}: main-text lines {a['lines']} -> {b['lines']}")
    if a["lines"] != b["lines"]: tot["lines_changed"] += 1
    if lost: notes.append(f"{n}: vocabulary tokens lost {lost} (gained {gained})")
    if a["tables"] != b["tables"] or a["floats"] != b["floats"]: notes.append(f"{n}: tables {a['tables']}->{b['tables']} floats {a['floats']}->{b['floats']}")
print(f"papers {len(pdfs)}; vocabulary tokens lost {tot['lost']} gained {tot['gained']}; unknown tokens {tot['unk_a']}/{tot['toks_a']} -> {tot['unk_b']}/{tot['toks_b']}")
print(f"tables {tot['tables_a']} -> {tot['tables_b']}; floats {tot['floats_a']} -> {tot['floats_b']}; rule 8 verified lost {tot['r8_lost']} gained {tot['r8_gained']} other {tot['r8_other']}; main-text lines down >5% {tot['lines_down_5pct']}; papers with line count changed {tot['lines_changed']}")
for x in notes: print("  " + x)
