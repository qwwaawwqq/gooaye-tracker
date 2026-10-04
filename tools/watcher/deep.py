#!/usr/bin/env python3
"""Build the `deep` abstract (HTML shown in the episode detail pane) for an episode.

- deep_from_content(e): from a watcher content JSON (new episodes; render.py uses this)
- deep_from_md(md):     from an existing 股癌_全集深度摘要_AUTO_UPDATE.md section (backfill)
`deep` is inserted with innerHTML inside a JS template literal, so text is HTML-escaped
and backticks / ${ are neutralised. The detail pane styles h4 (yellow) and b (amber);
everything else here carries inline styles.
"""
import html, re

QUOTE = 'style="color:#fde047;margin:6px 0"'
NOTE = 'style="color:#8ea3c0;font-size:11px;margin-top:10px;line-height:1.6"'
TABLE = 'style="width:100%;border-collapse:collapse;font-size:12px;margin:6px 0"'
CELL = 'style="border-bottom:1px solid #1f2d47;padding:4px 6px;text-align:left;vertical-align:top"'
BQ = 'style="border-left:3px solid #fde047;padding:4px 10px;margin:8px 0;color:#e6edf3"'


def tl_safe(s):
    """Make a string safe inside a JS template literal."""
    return s.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')


def esc(s):
    return html.escape(s, quote=False)


def deep_from_content(e):
    out = [f'<h4>📌 本集定位</h4><p>{esc(e["position"])}</p>']
    for s in e['sections']:
        out.append(f'<h4>{esc(s["h"])}</h4>')
        out.append(f'<p {QUOTE}><b>「{esc(s["lead"])}」</b></p>')
        out.append('<ul>' + ''.join(f'<li><b>{esc(l)}</b>：{esc(t)}</li>' for l, t in s['bullets']) + '</ul>')
    out.append(f'<h4>📎 市場背景（外部查證，非主委原話）</h4><p>{esc(e["market"])}</p>')
    n = sum(1 for w, _ in e['fixes'] if w != '臺')
    out.append(f'<p {NOTE}>深度摘要由 Claude 依 whisper 逐字稿（transcripts/EP{e["ep"]}.txt）整理；「」內為主委原話，'
               f'已逐句比對逐字稿，並修正 {n} 處明顯的 whisper 誤字（對照表見 股癌_全集深度摘要_AUTO_UPDATE.md）。'
               f'〔音譯〕待確認：{esc("；".join(e["unresolved"]))}。過熱訊號：{esc(e["overheat"])}。</p>')
    return ''.join(out)


def deep_from_md(md, ep):
    import markdown
    lines = md.strip('\n').split('\n')
    if lines and lines[0].startswith('## '):
        lines = lines[1:]
    keep = []
    for l in lines:
        s = l.strip()
        if re.match(r'^\*\*(日期|長度|贊助)：', s):
            continue  # shown in the detail header already
        if s == '---':
            continue
        # escape stray < (e.g. "<2 年") but keep blockquote markers at line start
        lead = re.match(r'^(\s*(?:>\s*)*)', l).group(1)
        body = l[len(lead):].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        keep.append(lead + body)
    h = markdown.markdown('\n'.join(keep), extensions=['tables', 'sane_lists'])
    h = re.sub(r'<(/?)h[23]>', r'<\1h4>', h)
    h = h.replace('<blockquote>', f'<div {BQ}>').replace('</blockquote>', '</div>')
    h = h.replace('<table>', f'<table {TABLE}>')
    h = re.sub(r'<(td|th)( align="[a-z]+")?>', lambda m: f'<{m.group(1)} {CELL}>', h)
    h = h.replace('<strong>', '<b>').replace('</strong>', '</b>').replace('<em>', '<i>').replace('</em>', '</i>')
    h = re.sub(r'\n+', '', h)
    h += (f'<p {NOTE}>深度摘要由 Claude 依 whisper 逐字稿整理（原載 股癌_全集深度摘要_AUTO_UPDATE.md 的 EP{ep} 一節）；'
          '「」內為主委原話，〔音譯〕為待確認的轉錄字詞。</p>')
    return h
