"""Check stage, step 2 (GPU): the page-reading model answers the narrow questions.

Run with the vLLM environment's Python (not the program's standard-library Python):
  VLLM_PY -I worker.py SPECS.json ANSWERS.json
SPECS.json = {"model": PATH, "papers": [spec, ...]} as written by prep.prepare(); the model
is loaded once for the whole batch. Every answer is scored from token log-probabilities
(constrained choices), never from the model's own words, and nothing the model says is
copied into the copy. Questions and prompts are those of the local-checker trial's best
design (Qwen3.6-27B-FP8, "B+ with (ii) veto", 2026-10-25):
  (ii) block class per numbered block on a set-of-marks page image (8 letters);
  (i)  reading order of the blocks (ii) reads as running text (P(body)+P(heading) >= 0.5),
       "yes/no" then "Order: ..." (regex-constrained), every token's top alternatives kept
       so the ops builder can score the first departure from the copy's order;
  (iii) sentence continuation yes/no for each join candidate (both boxes drawn);
  (iv) heading yes/no for each heading candidate, then main/sub when P(yes) >= 0.5.
GPU memory: a fixed KV cache (KV_GIB, default 8) and GPU_UTIL (default 0.46 of the card)
keep the process near 45 GB; a watchdog stops this worker's own processes (never any
other) if they pass CHECK_GPU_LIMIT_MIB (default 49000).
"""
import base64
import io
import json
import math
import os
import signal
import subprocess
import sys
import threading
import time

DPI = 120
CATS = [('A', 'body text paragraph (running text of the article, including abstract and reference list entries)', True),
        ('B', 'section heading', True),
        ('C', 'figure or table caption', False),
        ('D', 'footnote, affiliation, correspondence or funding note', False),
        ('E', 'running head, page number or journal masthead', False),
        ('F', 'lettering inside a figure or chart (labels, axis values, legend)', False),
        ('G', 'table text (cells, column heads)', False),
        ('H', 'front matter (title, author names, article dates, keywords, copyright line)', False)]
LETTERS = [c for c, _, _ in CATS]
RUNNING = {c for c, _, r in CATS if r}

B_CLASS = """The image shows printed page {page} of a scientific paper. Coloured boxes with number tags mark the page regions that a machine-made copy of the paper took its paragraphs from. Look at the region with tag {num}. Its copied text begins and ends:
"{snip}"
What kind of printed text is block {num}?
""" + "\n".join(f"{c}. {d}" for c, d, _ in CATS) + "\nAnswer with the letter only."

B_ORDER = """The image shows printed page {page} of a scientific paper. Coloured boxes with number tags mark the regions of the body text and headings, numbered in the order a machine-made copy currently places them:
{listing}
Read the printed page the way a person reads it (column by column, top to bottom; a block that continues from one column into the next stays in sequence). Is the copy's numbering already the correct reading order of these blocks? Answer "yes" or "no" on the first line. Then, on the second line after "Order:", give all the block numbers in the correct reading order, separated by commas."""

Q_JOIN = """The image(s) show printed page(s) of a scientific paper. Box 1 and box 2 mark two pieces of text that a machine-made copy keeps as two separate paragraphs:
1: "...{a}"
2: "{b}..."
On the printed page, does the text of box 2 continue the same sentence as box 1 (the sentence runs on directly from the end of box 1 to the start of box 2, perhaps across a column or page break)? Answer yes or no."""

Q_HEAD = """The image shows printed page {page} of a scientific paper. A machine-made copy has this line as ordinary text:
"{line}"
On the printed page, is this line a section or subsection heading (a title printed on its own line in heading type, above the text it introduces)? Answer yes or no."""

Q_LEVEL = """The image shows printed page {page} of a scientific paper. The line "{line}" is a heading on this page. Is it a main section heading (such as Introduction, Materials and Methods, Results, Discussion, References) or a subsection heading inside a section? Answer main or sub."""

ORDER_REGEX = r'(yes|no)\nOrder: [0-9]{1,2}(, [0-9]{1,2}){0,60}'
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'


# ------------------------------------------------------------------ GPU memory watchdog (own processes only)
def _descendants(pid):
    out = {pid}
    try:
        txt = subprocess.run(['ps', '-e', '-o', 'pid=,ppid='], capture_output=True, text=True).stdout
    except Exception:
        return out
    kids = {}
    for ln in txt.splitlines():
        a, b = ln.split()
        kids.setdefault(int(b), []).append(int(a))
    stack = [pid]
    while stack:
        x = stack.pop()
        for k in kids.get(x, []):
            if k not in out:
                out.add(k)
                stack.append(k)
    return out


class GpuMonitor:
    def __init__(self, interval=0.5, limit_mib=49000):
        self.limit_mib = limit_mib
        self.peak_own_mib = 0
        self.peak_total_mib = 0
        self.interval = interval
        self._stop = False
        self.t = threading.Thread(target=self.run, daemon=True)

    def start(self):
        self.t.start()
        return self

    def run(self):
        me = os.getpid()
        while not self._stop:
            try:
                pids = _descendants(me)
                apps = subprocess.run(['nvidia-smi', '--query-compute-apps=pid,used_memory', '--format=csv,noheader,nounits'],
                                      capture_output=True, text=True).stdout
                own = sum(int(m) for p, m in (l.split(',') for l in apps.strip().splitlines() if l.strip()) if int(p) in pids)
                tot = int(subprocess.run(['nvidia-smi', '--query-gpu=memory.used', '--format=csv,noheader,nounits'],
                                         capture_output=True, text=True).stdout.strip().splitlines()[0])
                self.peak_own_mib = max(self.peak_own_mib, own)
                self.peak_total_mib = max(self.peak_total_mib, tot)
                if own > self.limit_mib:
                    print(f'GPU MEMORY CAP: own processes use {own} MiB > {self.limit_mib}; stopping', flush=True)
                    for q in pids - {me}:
                        try:
                            os.kill(q, signal.SIGKILL)
                        except Exception:
                            pass
                    os._exit(97)
            except Exception:
                pass
            time.sleep(self.interval)

    def stop(self):
        self._stop = True


# ------------------------------------------------------------------ images
def draw_som(img_path, out_path, blocks, scale=DPI / 72.0):
    """Outline each block's rectangles and tag it with its number (the trial's set-of-marks drawing)."""
    from PIL import Image, ImageDraw, ImageFont
    im = Image.open(img_path).convert('RGB')
    dr = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype(FONT, 18)
    except Exception:
        font = ImageFont.load_default()
    colors = [(220, 20, 60), (0, 90, 200), (0, 150, 60), (200, 100, 0), (140, 0, 170)]
    for num, rects in blocks:
        c = colors[num % len(colors)]
        for r in rects:
            x0, y0, x1, y1 = [v * scale for v in r]
            dr.rectangle([x0 - 2, y0 - 2, x1 + 2, y1 + 2], outline=c, width=2)
        x0, y0 = rects[0][0] * scale, rects[0][1] * scale
        lab = str(num)
        tw = 11 * len(lab) + 6
        lx, ly = max(0, x0 - tw - 2), max(0, y0 - 4)
        dr.rectangle([lx, ly, lx + tw, ly + 22], fill=c)
        dr.text((lx + 3, ly + 1), lab, fill=(255, 255, 255), font=font)
    im.save(out_path)


def img_part(path):
    b = base64.b64encode(open(path, 'rb').read()).decode()
    return {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + b}}


# ------------------------------------------------------------------ model
def load_llm(model_path, max_model_len=20480, images=2):
    os.environ.setdefault('HF_HUB_OFFLINE', '1')
    os.environ.setdefault('TRANSFORMERS_OFFLINE', '1')
    os.environ.setdefault('VLLM_USE_FLASHINFER_SAMPLER', '0')
    import dataclasses
    from vllm import LLM
    from vllm.engine.arg_utils import EngineArgs
    names = {f.name for f in dataclasses.fields(EngineArgs)}
    kw = {'enable_flashinfer_autotune': False} if 'enable_flashinfer_autotune' in names else {}
    util = float(os.environ.get('GPU_UTIL', '0.46'))
    mmkw = {'size': {'longest_edge': 1800000, 'shortest_edge': 65536}}
    kvb = os.environ.get('KV_GIB', '8')
    if kvb and float(kvb) > 0:  # fixed KV cache: skips start-up memory profiling that another GPU job can disturb
        kw['kv_cache_memory_bytes'] = int(float(kvb) * (1 << 30))
    return LLM(model=model_path, max_model_len=max_model_len, gpu_memory_utilization=util,
               limit_mm_per_prompt={'image': images, 'video': 0}, seed=0, enable_prefix_caching=True,
               mm_processor_kwargs=mmkw, max_num_seqs=int(os.environ.get('MAX_SEQS', '48')),
               max_num_batched_tokens=int(os.environ.get('MAX_BATCHED', '8192')), **kw)


def chat_kwargs(model_path):
    if 'qwen3.6' in model_path.lower() or 'qwen3_5' in model_path.lower():
        return {'chat_template_kwargs': {'enable_thinking': False}}
    return {}


def first_token_probs(out, choices, tok):
    """Normalised probabilities of the given choice strings at the first generated position."""
    lp = out.outputs[0].logprobs
    if not lp:
        return None
    d = lp[0]
    acc = {c: -1e9 for c in choices}
    for tid, l in d.items():
        s = (l.decoded_token if l.decoded_token is not None else tok.decode([tid])).strip()
        for c in choices:
            if s == c or s.lower() == c.lower():
                acc[c] = max(acc[c], l.logprob) if acc[c] > -1e9 else l.logprob
    m = max(acc.values())
    if m <= -1e9:
        return None
    z = sum(math.exp(v - m) for v in acc.values() if v > -1e9)
    return {c: (math.exp(v - m) / z if v > -1e9 else 0.0) for c, v in acc.items()}


def q(s):
    return s.replace('"', "'")


def run(specs, out_path):
    from vllm import SamplingParams
    from vllm.sampling_params import StructuredOutputsParams
    mon = GpuMonitor(limit_mib=int(os.environ.get('CHECK_GPU_LIMIT_MIB', '49000'))).start()
    model = specs['model']
    t0 = time.time()
    llm = load_llm(model)
    load_s = time.time() - t0
    tok = llm.get_tokenizer()
    ck = chat_kwargs(model)
    papers = specs['papers']
    answers = {i: {'pages': {}, 'joins': [], 'heads': []} for i in range(len(papers))}
    timing = {}

    def chat(reqs, sp):
        return llm.chat(reqs, sp, use_tqdm=False, **ck) if reqs else []

    # ---- (ii) class of every block
    t1 = time.time()
    reqs, keys = [], []
    for i, sp_ in enumerate(papers):
        work = sp_['work']
        os.makedirs(os.path.join(work, 'som'), exist_ok=True)
        for pg in sp_['pages']:
            bl = sp_['blocks'].get(str(pg['page']))
            if not bl:
                continue
            img = os.path.join(work, 'som', 'p%02d-all.png' % pg['page'])
            draw_som(pg['image'], img, [(b['num'], b['rects_pt']) for b in bl])
            ip = img_part(img)
            for b in bl:
                qq = B_CLASS.format(page=pg['page'], num=b['num'], snip=q(b['snippet']))
                reqs.append([{'role': 'user', 'content': [ip, {'type': 'text', 'text': qq}]}])
                keys.append((i, pg['page'], b['num']))
    outs = chat(reqs, SamplingParams(temperature=0.0, max_tokens=1, logprobs=20,
                                     structured_outputs=StructuredOutputsParams(choice=LETTERS)))
    cls = {}
    for k, o in zip(keys, outs):
        cls[k] = {'answer': o.outputs[0].text.strip(), 'probs': first_token_probs(o, LETTERS, tok)}
    t_ii = time.time() - t1
    # ---- (i) order of the running blocks
    t1 = time.time()
    reqs, keys, maps = [], [], {}
    for i, sp_ in enumerate(papers):
        for pg in sp_['pages']:
            bl = sp_['blocks'].get(str(pg['page']))
            if not bl:
                continue
            run_bl = []
            for b in bl:
                c = cls[(i, pg['page'], b['num'])]
                pr = c['probs'] or {}
                p_run = sum(v for kk, v in pr.items() if kk in RUNNING) if pr else (1.0 if c['answer'] in RUNNING else 0.0)
                if p_run >= 0.5:
                    run_bl.append(b)
            if len(run_bl) < 2:
                continue
            rb = [dict(b, num=j + 1) for j, b in enumerate(run_bl)]
            img = os.path.join(sp_['work'], 'som', 'p%02d-run.png' % pg['page'])
            draw_som(pg['image'], img, [(b['num'], b['rects_pt']) for b in rb])
            listing = "\n".join(f"{b['num']}: \"{b['order_snippet']}\"".replace('\n', ' ') for b in rb)
            reqs.append([{'role': 'user', 'content': [img_part(img), {'type': 'text', 'text': B_ORDER.format(page=pg['page'], listing=listing)}]}])
            keys.append((i, pg['page']))
            maps[(i, pg['page'])] = [{'num': b['num'], 'para': b['para'], 'orig_num': ob['num']} for b, ob in zip(rb, run_bl)]
    outs = chat(reqs, SamplingParams(temperature=0.0, max_tokens=400, logprobs=20,
                                     structured_outputs=StructuredOutputsParams(regex=ORDER_REGEX)))
    order = {}
    for k, o in zip(keys, outs):
        steps = []
        for tid, lpd in zip(o.outputs[0].token_ids, o.outputs[0].logprobs or []):
            alts = {}
            for t2, l in lpd.items():
                if l.logprob > -30:
                    alts[l.decoded_token if l.decoded_token is not None else tok.decode([t2])] = round(l.logprob, 4)
            steps.append({'tok': tok.decode([tid]), 'alts': alts})
        order[k] = {'answer': o.outputs[0].text, 'probs': first_token_probs(o, ['yes', 'no'], tok), 'steps': steps,
                    'cum_logprob': o.outputs[0].cumulative_logprob}
    t_i = time.time() - t1
    for i, sp_ in enumerate(papers):
        for pg in sp_['pages']:
            bl = sp_['blocks'].get(str(pg['page']))
            if not bl:
                continue
            answers[i]['pages'][str(pg['page'])] = {
                'page': pg['page'],
                'blocks': [{'num': b['num'], 'para': b['para'], 'multi': b.get('multi', False), 'snippet': b['snippet'],
                            'class': cls[(i, pg['page'], b['num'])]} for b in bl],
                'order': order.get((i, pg['page'])), 'order_blocks': maps.get((i, pg['page']))}
    yn = SamplingParams(temperature=0.0, max_tokens=1, logprobs=20, structured_outputs=StructuredOutputsParams(choice=['yes', 'no']))
    # ---- (iii) joins
    t1 = time.time()
    reqs, keys = [], []
    for i, sp_ in enumerate(papers):
        pages = {pg['page']: pg for pg in sp_['pages']}
        for c in sp_['joins']:
            if c['pa'] == c['pb']:
                f = os.path.join(sp_['work'], 'som', f"j{c['a']}.png")
                draw_som(pages[c['pa']]['image'], f, [(1, c['rects_a']), (2, c['rects_b'])])
                imgs = [f]
            else:
                f1 = os.path.join(sp_['work'], 'som', f"j{c['a']}a.png")
                f2 = os.path.join(sp_['work'], 'som', f"j{c['a']}b.png")
                draw_som(pages[c['pa']]['image'], f1, [(1, c['rects_a'])])
                draw_som(pages[c['pb']]['image'], f2, [(2, c['rects_b'])])
                imgs = [f1, f2]
            qq = Q_JOIN.format(a=q(c['tail_a']), b=q(c['head_b']))
            reqs.append([{'role': 'user', 'content': [img_part(x) for x in imgs] + [{'type': 'text', 'text': qq}]}])
            keys.append((i, c))
    outs = chat(reqs, yn)
    for (i, c), o in zip(keys, outs):
        answers[i]['joins'].append({k: c[k] for k in ('a', 'b', 'pa', 'pb')} | {'probs': first_token_probs(o, ['yes', 'no'], tok)})
    t_join = time.time() - t1
    # ---- (iv) headings and their level
    t1 = time.time()
    reqs, keys = [], []
    for i, sp_ in enumerate(papers):
        pages = {pg['page']: pg for pg in sp_['pages']}
        for c in sp_['heads']:
            qq = Q_HEAD.format(page=c['page'], line=q(c['core']))
            reqs.append([{'role': 'user', 'content': [img_part(pages[c['page']]['image']), {'type': 'text', 'text': qq}]}])
            keys.append((i, c))
    outs = chat(reqs, yn)
    heads = [(i, dict(c, probs=first_token_probs(o, ['yes', 'no'], tok))) for (i, c), o in zip(keys, outs)]
    lv_reqs, lv_idx = [], []
    for j, (i, h) in enumerate(heads):
        if h['probs'] and h['probs']['yes'] >= 0.5:
            pages = {pg['page']: pg for pg in papers[i]['pages']}
            qq = Q_LEVEL.format(page=h['page'], line=q(h['core']))
            lv_reqs.append([{'role': 'user', 'content': [img_part(pages[h['page']]['image']), {'type': 'text', 'text': qq}]}])
            lv_idx.append(j)
    outs = chat(lv_reqs, SamplingParams(temperature=0.0, max_tokens=1, logprobs=20,
                                        structured_outputs=StructuredOutputsParams(choice=['main', 'sub'])))
    for j, o in zip(lv_idx, outs):
        heads[j][1]['level'] = first_token_probs(o, ['main', 'sub'], tok)
    for i, h in heads:
        answers[i]['heads'].append(h)
    t_head = time.time() - t1
    wall = time.time() - t0 - load_s
    n_req = {'class': len(cls), 'order': len(order), 'join': sum(len(a['joins']) for a in answers.values()),
             'head': len(heads), 'level': len(lv_reqs)}
    meta = {'model': model, 'load_seconds': round(load_s, 1), 'question_seconds': round(wall, 1),
            'seconds': {'class': round(t_ii, 1), 'order': round(t_i, 1), 'join': round(t_join, 1), 'head': round(t_head, 1)},
            'requests': n_req, 'papers': len(papers),
            'peak_gpu_mib_own_processes': mon.peak_own_mib, 'peak_gpu_mib_total_device': mon.peak_total_mib,
            'gpu_memory_utilization': float(os.environ.get('GPU_UTIL', '0.46')), 'kv_gib': os.environ.get('KV_GIB', '8')}
    out = {'meta': meta, 'papers': [dict(answers[i], paper_dir=papers[i]['paper_dir']) for i in range(len(papers))]}
    tmp = out_path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
    os.replace(tmp, out_path)
    mon.stop()
    print('WORKER DONE', json.dumps(meta), flush=True)


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit('usage: worker.py SPECS.json ANSWERS.json')
    run(json.load(open(sys.argv[1], encoding='utf-8')), sys.argv[2])
