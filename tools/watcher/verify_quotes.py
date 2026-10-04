#!/usr/bin/env python3
"""Score 「」 quotes against an episode transcript (difflib matching-block coverage).

usage:
  python3 tools/watcher/verify_quotes.py content/EP703.json        # quotes in the content JSON
  python3 tools/watcher/verify_quotes.py --text FILE 703 704       # every 「」 in FILE vs those transcripts
>=0.9 clean · 0.4-0.9 spot-check (multi-fragment / corrected) · <0.4 investigate.
The content JSON's "fixes" list ([wrong, right] whisper corrections) is applied to the
transcript before scoring, so corrected spellings inside quotes still match.
Your own framing must never sit inside 「」; external (non-host) quotes use 『』.
"""
import json, os, re, sys, difflib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PUNCT = re.compile(r'[\s，。、；：？！「」『』（）()〔〕【】《》…⋯—\-－,.;:?!\'"“”‘’/／~～・·＝=+＋%％*★☆]')


def norm(s):
    s = re.sub(r'\[\d\d:\d\d\]', '', s)
    s = re.sub(r'<[^>]+>', '', s)
    return PUNCT.sub('', s).lower()


def frag_score(frag, T):
    q = norm(frag)
    if not q or q in T:
        return 1.0
    hits = {}
    for i in range(max(1, len(q) - 2)):
        sh, start = q[i:i + 3], 0
        while (j := T.find(sh, start)) >= 0:
            k = (j - i) // 20
            hits[k] = hits.get(k, 0) + 1
            start = j + 1
    if not hits:
        return 0.0
    best = max(hits, key=hits.get) * 20
    win = T[max(0, best - 40):best + len(q) + 60]
    sm = difflib.SequenceMatcher(None, q, win, autojunk=False)
    return sum(b.size for b in sm.get_matching_blocks()) / len(q)


def score(q, transcript, fixes):
    t = transcript
    for w, r in fixes:
        t = t.replace(w, r)
    T = norm(t)
    frags = [f for f in re.split(r'⋯⋯|……', q) if norm(f)]
    return min([frag_score(f, T) for f in frags] or [1.0])


def quotes_in(text):
    return re.findall(r'「([^「」]{2,})」', text)


def content_quotes(e):
    qs = []
    for s in e['sections']:
        qs.append(s['lead'])
        for _, txt in s['bullets']:
            qs += quotes_in(txt)
    return qs + quotes_in(e['position'])


def report(rows):
    bad = [(round(s, 2), q) for s, q in rows if s < 0.9]
    print(f'{len(rows)} quotes · clean {sum(s >= 0.9 for s, _ in rows)} · '
          f'spot {sum(0.4 <= s < 0.9 for s, _ in rows)} · investigate {sum(s < 0.4 for s, _ in rows)}')
    for s, q in bad:
        print(f'  {s:.2f}  {q[:90]}')
    return not any(s < 0.4 for s, _ in rows)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--text':
        text, eps = open(a[1], encoding='utf-8').read(), a[2:]
        Ts = {n: open(f'{ROOT}/transcripts/EP{n}.txt', encoding='utf-8').read() for n in eps}
        rows = [(max(score(q, Ts[n], []) for n in eps), q) for q in sorted(set(quotes_in(re.sub(r'<[^>]+>', '', text))))]
    else:
        e = json.load(open(a[0], encoding='utf-8'))
        T = open(f"{ROOT}/transcripts/EP{e['ep']}.txt", encoding='utf-8').read()
        rows = [(score(q, T, e['fixes']), q) for q in content_quotes(e)]
    sys.exit(0 if report(rows) else 1)
