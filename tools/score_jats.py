"""Score element boxer outputs against publisher JATS XML (truth), by code.
For each article: body+abstract words (multiset) -> recall of truth words in main-text.txt and precision of
main-text words against truth; word-pair (bigram) recall as a joint measure of word integrity and order;
figure and table captions: truth count vs floats found with a matching label number; authors: truth surnames
found in authors.json names. Usage: score_jats.py OUTDIR TRUTHDIR [ids...]"""
import sys, os, re, json, glob, collections
import xml.etree.ElementTree as ET
OUT, TRUTH = sys.argv[1], sys.argv[2]
W = re.compile(r"[A-Za-z0-9]+")
def words(t): return [w.lower() for w in W.findall(t)]
def text_of(e, skip=("fig", "table-wrap", "disp-formula", "supplementary-material")):
    out = []
    def walk(x):
        if x.tag in skip: 
            if x.tail: out.append(x.tail)
            return
        if x.text: out.append(x.text)
        for c in x: walk(c)
        if x.tail: out.append(x.tail)
    walk(e); return " ".join(out)
def truth(xmlp):
    r = ET.parse(xmlp).getroot()
    body = r.find(".//body"); abst = r.findall(".//abstract")
    btxt = (text_of(body) if body is not None else "") + " " + " ".join(text_of(a) for a in abst)
    figs = [f for f in r.iter("fig")]; tabs = [t for t in r.iter("table-wrap")]
    def lab(e):
        l = e.find("label"); return (l.text or "").strip() if l is not None and l.text else ""
    sur = [s.text.strip() for c in r.iter("contrib") if c.get("contrib-type") == "author" for s in c.iter("surname") if s.text]
    return {"words": words(btxt), "fig_labels": [lab(f) for f in figs], "tab_labels": [lab(t) for t in tabs], "surnames": sur}
def num(s):
    m = re.search(r"(\d+)", s or ""); return m.group(1) if m else None
rows = []; agg = collections.Counter()
ids = sys.argv[3:] or sorted(os.listdir(OUT))
for a in ids:
    d = os.path.join(OUT, a); xs = glob.glob(os.path.join(TRUTH, a, "*.xml"))
    if not xs or not os.path.exists(os.path.join(d, "main-text.txt")): continue
    T = truth(xs[0]); tw = collections.Counter(T["words"])
    mt = open(os.path.join(d, "main-text.txt"), encoding="utf-8").read()
    mt = "\n".join(l for l in mt.split("\n") if not l.startswith("#") and not l.startswith("## page"))
    mt = re.sub(r"^\[\d+\] ", "", mt, flags=re.M)
    ow = words(mt); oc = collections.Counter(ow)
    hit = sum(min(oc[w], tw[w]) for w in tw)
    rec = hit / max(1, sum(tw.values())); prec = hit / max(1, sum(oc.values()))
    tb = collections.Counter(zip(T["words"], T["words"][1:])); ob = collections.Counter(zip(ow, ow[1:]))
    brec = sum(min(ob[b], tb[b]) for b in tb) / max(1, sum(tb.values()))
    floats = []; tables = 0
    for f in sorted(glob.glob(os.path.join(d, "page-[0-9][0-9]*.json"))):
        p = json.load(open(f)); floats += [x["caption"] for x in p.get("floats", [])]; tables += len(p.get("tables", []))
    fnums = {(("table" if re.sub(r"\s+", "", c).lower().startswith("tab") else "fig"), num(c)) for c in floats}
    fig_found = sum(1 for l in T["fig_labels"] if ("fig", num(l)) in fnums); tab_found = sum(1 for l in T["tab_labels"] if ("table", num(l)) in fnums)
    au = json.load(open(os.path.join(d, "authors.json"))) if os.path.exists(os.path.join(d, "authors.json")) else {}
    names = " ".join(x.get("name", "") for x in au.get("authors", [])).lower()
    au_found = sum(1 for s in T["surnames"] if s.lower() in names)
    row = {"id": a, "recall": rec, "precision": prec, "bigram_recall": brec, "figs": (fig_found, len(T["fig_labels"])), "tables": (tab_found, len(T["tab_labels"])), "authors": (au_found, len(T["surnames"]))}
    rows.append(row)
    for k in ("figs", "tables", "authors"): agg[k + "_found"] += row[k][0]; agg[k + "_truth"] += row[k][1]
n = len(rows)
def mean(k): return sum(r[k] for r in rows) / max(1, n)
print(f"articles {n}: word recall {mean('recall'):.3f}, precision {mean('precision'):.3f}, bigram recall {mean('bigram_recall'):.3f}; figures {agg['figs_found']}/{agg['figs_truth']}, tables {agg['tables_found']}/{agg['tables_truth']}, authors {agg['authors_found']}/{agg['authors_truth']}")
json.dump(rows, open(os.path.join(OUT, "TRUTH-SCORE.json"), "w"), indent=1)
worst = sorted(rows, key=lambda r: r["bigram_recall"])[:8]
print("lowest bigram recall:", [(r["id"], round(r["bigram_recall"], 2), round(r["recall"], 2), round(r["precision"], 2)) for r in worst])
