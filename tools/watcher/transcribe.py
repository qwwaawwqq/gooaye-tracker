#!/usr/bin/env python3
"""Download + transcribe new 股癌 episodes with faster-whisper (cloud runner).

usage:  python3 tools/watcher/transcribe.py 703 704        # EP numbers from the RSS feed
Writes transcripts/EP<N>.txt ("[MM:SS] text" per segment, Traditional Chinese).
Run it in the background (setsid nohup ... &) and poll the log: a 50-min episode
takes ~11 min on 2 CPU cores (small / int8 / beam 1 / VAD).

Notes learned 2026-10-04:
- faster-whisper 1.0.3 cannot build PyAV on Python 3.13; the latest release works,
  but its av.open(metadata_errors=...) call breaks with av>=15, so we never pass a
  file path: the wav is loaded here and passed as a float32 numpy array.
- OpenCC s2tw turns 台→臺 and 只→隻; post() undoes both.
"""
import json, os, re, subprocess, sys, time, wave
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
WORK = os.environ.get('WATCHER_WORK', os.path.expanduser('~/watcher_work'))
RSS = 'https://feeds.soundon.fm/podcasts/954689a5-3096-43a4-a80b-7810b219cef3.xml'
HF = 'https://huggingface.co/Systran/faster-whisper-small/resolve/main'
MODEL_BYTES = 483546902
PROMPT = ('以下是繁體中文的股癌 Podcast 逐字稿，主持人謝孟恭（主委）聊台股與美股：'
          '台積電、聯發科、輝達 NVIDIA、博通 Broadcom、AMD、HBM、CoWoS、ASIC、AI 伺服器。')
KEEP_ZHI = '一兩二三四五六七八九十幾這那每哪多某半整些單個好'


def sh(cmd):
    print('$', cmd, flush=True)
    subprocess.run(cmd, shell=True, check=True)


def post(t):
    t = t.replace('臺', '台')
    t = re.sub(r'(?<![%s])隻(?!狼)' % KEEP_ZHI, '只', t)
    return t.replace('\ufffd', '')


def ensure_model(d):
    os.makedirs(d, exist_ok=True)
    for f in ('config.json', 'tokenizer.json', 'vocabulary.txt'):
        if not os.path.exists(f'{d}/{f}'):
            sh(f'curl -sSL --retry 5 -o {d}/{f} {HF}/{f}')
    mb = f'{d}/model.bin'
    if os.path.exists(mb) and os.path.getsize(mb) == MODEL_BYTES:
        return
    n = 8
    part = (MODEL_BYTES + n - 1) // n
    procs = []
    for i in range(n):
        s, e = i * part, min(MODEL_BYTES, (i + 1) * part) - 1
        procs.append(subprocess.Popen(
            f'for t in 1 2 3 4 5 6; do h=$(stat -c%s {d}/p{i} 2>/dev/null || echo 0); '
            f'[ $h -ge {e - s + 1} ] && break; curl -sSL -r $(({s}+h))-{e} {HF}/model.bin >> {d}/p{i}; done',
            shell=True))
    for p in procs:
        p.wait()
    sh(f'cat ' + ' '.join(f'{d}/p{i}' for i in range(n)) + f' > {mb} && rm -f {d}/p*')
    assert os.path.getsize(mb) == MODEL_BYTES, 'model.bin size mismatch'


def enclosures(eps):
    req = urllib.request.Request(RSS, headers={'User-Agent': 'Mozilla/5.0'})
    root = ET.parse(urllib.request.urlopen(req, timeout=60)).getroot()
    out = {}
    for it in root.find('channel').findall('item'):
        m = re.search(r'EP\s*(\d+)', it.findtext('title') or '')
        if m and int(m.group(1)) in eps:
            out[int(m.group(1))] = it.find('enclosure').get('url')
    return out


def load(fn):
    import numpy as np
    with wave.open(fn) as w:
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768.0


def main(eps):
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(f'{ROOT}/transcripts', exist_ok=True)
    ensure_model(f'{WORK}/model')
    urls = enclosures(eps)
    from faster_whisper import WhisperModel
    import opencc
    cc = opencc.OpenCC('s2tw')
    m = WhisperModel(f'{WORK}/model', device='cpu', compute_type='int8', cpu_threads=os.cpu_count() or 2)
    for ep in eps:
        out = f'{ROOT}/transcripts/EP{ep}.txt'
        if os.path.exists(out):
            print('skip', ep, flush=True)
            continue
        mp3, wav = f'{WORK}/EP{ep}.mp3', f'{WORK}/EP{ep}.wav'
        sh(f'curl -sSL --retry 5 -A "Mozilla/5.0" -o {mp3} "{urls[ep]}"')
        sh(f'ffmpeg -loglevel error -y -i {mp3} -ar 16000 -ac 1 -c:a pcm_s16le {wav}')
        t0 = time.time()
        segs, info = m.transcribe(load(wav), language='zh', beam_size=1, vad_filter=True, initial_prompt=PROMPT)
        with open(out + '.part', 'w', encoding='utf-8') as f:
            for s in segs:
                mm, ss = divmod(int(s.start), 60)
                f.write(post(f'[{mm:02d}:{ss:02d}] {cc.convert(s.text.strip())}') + '\n')
                f.flush()
        os.rename(out + '.part', out)
        print(f'EP{ep} done in {time.time() - t0:.0f}s (audio {info.duration:.0f}s)', flush=True)


if __name__ == '__main__':
    main([int(x) for x in sys.argv[1:]])
