"""Reference lists checked against the PDF itself: a numbered list must run 1, 2, 3 ... in reading
order; an author-year list (APA, Harvard and the like) must be alphabetical by first author's surname.
usage: python3 -I layout/check_references.py RUN_ROOT"""
import json, os, re, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rules as RL   # noqa: E402


PARTICLES = {'van', 'von', 'de', 'der', 'den', 'da', 'di', 'du', 'le', 'la', 'del', 'della', 'ter', 'ten'}
FOLD = str.maketrans({'ø': 'o', 'Ø': 'o', 'æ': 'ae', 'Æ': 'ae', 'ß': 'ss', 'đ': 'd', 'ł': 'l', 'Ł': 'l'})


def surname_keys(entry):
    """Two sort keys for an entry: its first word, and its first word that is not a name particle
    ("van Charante" files under v or under c, by convention). Letters are folded (Ø as O)."""
    t = RL.REFHEAD.sub('', entry, count=1).strip().translate(FOLD)
    t = unicodedata.normalize('NFKD', t)
    t = ''.join(c for c in t if not unicodedata.combining(c) and c not in '´¨`˜ˆ')     # "Arau´jo" -> "Araujo"
    words = [re.sub(r'[^a-z]', '', w.lower()) for w in t.split()]
    words = [w for w in words if w]
    if not words: return '', ''
    rest = [w for w in words if w not in PARTICLES]
    return words[0], (rest[0] if rest else words[0])


def lines_of_unit(u):
    lines = []
    for text, box, _ in sorted(u['words'], key=lambda w: ((w[1][1] + w[1][3]) / 2, w[1][0])):
        cy = (box[1] + box[3]) / 2
        if lines and abs(cy - lines[-1][0]) < 0.45 * (box[3] - box[1] + 1): lines[-1][1].append((box[0], text))
        else: lines.append([cy, [(box[0], text)]])
    return [(min(x for x, _ in l[1]), ' '.join(t for _, t in sorted(l[1]))) for l in lines]


for name in sorted(os.listdir(sys.argv[1])):
    f = os.path.join(sys.argv[1], name, 'layout.json'); r = os.path.join(sys.argv[1], name, 'report.json')
    if not os.path.exists(f): continue
    style = json.load(open(r)).get('references', {}).get('style')
    units = [u for u in json.load(open(f))['units'] if u['kind'] == 'references']
    if not units: continue
    if style == 'numbered':
        nums = [int(m.group(1)) for u in units for line in u['text'].split('\n') for m in [re.match(r'^\[?(\d{1,3})[\].)]?\s+\S', line)] if m]
        seq = []
        for n in nums:
            if n == (seq[-1] + 1 if seq else 1): seq.append(n)
        out = [n for n in nums if seq and n <= seq[-1] and n not in seq]
        print(f'{name}: numbered: entries in sequence 1..{seq[-1] if seq else 0}; numbers out of place {len(out)} {out[:6]}')
    else:
        ents = []
        for u in units:
            e = RL.entries(lines_of_unit(u))
            # a block that opens with the end of an entry from the block before: that piece is not an entry
            if e and not RL.style_of(e[0], need_year=False) and ents: e = e[1:]
            ents += e
        keys = [surname_keys(e) for e in ents]
        # a step backwards under both conventions (with and without the particle) is out of order
        back = [(keys[i - 1][0], keys[i][0]) for i in range(1, len(keys)) if keys[i][0] < keys[i - 1][0] and keys[i][1] < keys[i - 1][1] and keys[i][0] < keys[i - 1][1] and keys[i][1] < keys[i - 1][0]]
        print(f'{name}: {style}: {len(ents)} entries; alphabetical steps backwards {len(back)} {back[:4]}')
