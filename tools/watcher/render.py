#!/usr/bin/env python3
"""Render curated episode content (JSON) into the site files.

usage:  python3 tools/watcher/render.py content/EP703.json [content/EP704.json ...] [--report-cards OUT.html]
- index.html: inserts each episode at the top of `const EPISODES = {` (newest first), with its `deep`
  abstract (detail pane HTML) built by deep.py from the same content JSON
- 股癌_全集深度摘要_AUTO_UPDATE.md: inserts sections right after the marker line, updates AUTO_UPDATE_META
- --report-cards: writes the per-episode <div class="card"> blocks for the dated report
Content schema: see tools/watcher/content/EP702.json (keys: ep, date, wd, pub, emoji, tagline,
dur_sec, sponsor, mentions, stocks [[mkt, code]], overheat, fixes [[wrong, right]], unresolved,
tags, position, sections [{h, lead, bullets [[label, text]]}], market, link).
summary text is rendered through escapeHtml() on the site, and deep.py HTML-escapes every field:
never put HTML in content fields. Status tags: '⏳ 待 LLM 深度摘要' is dropped and '📝 …' tags go last,
so the site's 主軸 column (first three tags) shows real topics.
"""
import html, json, os, re, sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deep import deep_from_content, tl_safe  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
MD = f'{ROOT}/股癌_全集深度摘要_AUTO_UPDATE.md'
MARKER = '===== AUTO_INSERT_POINT_BELOW =====\n'


def tstats(n):
    s = open(f'{ROOT}/transcripts/EP{n}.txt', encoding='utf-8').read()
    return len(s.encode('utf-8')), s.count('\n')


def js(s):
    return s.replace('\\', '\\\\').replace("'", "\\'").replace('\n', ' ')


def dur_txt(sec):
    return f'{sec // 60} 分 {sec % 60:02d} 秒（{sec:,} 秒）'


def summary(e):
    b, l = tstats(e['ep'])
    parts = [f"主軸（依 whisper 逐字稿 transcripts/EP{e['ep']}.txt，{b:,} bytes／{l:,} 段；"
             f"雲端 faster-whisper small int8 單次轉錄）：" + e['position']]
    for s in e['sections']:
        parts.append(f"{s['h']}：主委原話：「{s['lead']}」")
        parts += [f'{lab}：{txt}' for lab, txt in s['bullets']]
    parts.append(f"外部查證（非主委原話）：{e['market']}")
    out = '　'.join(parts)
    assert '<' not in out and '>' not in out, 'summary must be plain text (escapeHtml on the site)'
    return out


def clean_tags(tags):
    """Drop the pending-abstract status tag; move the whisper status tag(s) to the end."""
    status = [t for t in tags if t.startswith('📝')]
    return [t for t in tags if not t.startswith(('⏳ 待 LLM', '📝'))] + status


def inline_entry(e):
    tags = ','.join(f"'{js(t)}'" for t in clean_tags(e['tags']))
    stocks = ','.join(f"['{m}','{c}']" for m, c in e['stocks'])
    return (f"  {e['ep']}:{{date:'{e['date']}',title:'EP{e['ep']} | {e['emoji']}',dur:'{round(e['dur_sec'] / 60)}分',"
            f"v:'pending',sponsor:'{js(e['sponsor'])}',\n    tags:[{tags}],\n    summary:'{js(summary(e))}',\n"
            f"    stocks:[{stocks}],\n    deep:`{tl_safe(deep_from_content(e))}`}},\n")


def md_section(e):
    b, l = tstats(e['ep'])
    fixes = '、'.join(f'{w}→{r}' for w, r in e['fixes'] if w != '臺')
    L = [f"## EP{e['ep']} ｜ {e['emoji']}「{e['tagline']}」", '',
         f"**日期：** {e['date']}（{e['wd']}）{e['pub']} TPE　**長度：** {dur_txt(e['dur_sec'])}",
         f"**贊助：** {e['sponsor']}",
         f"**資料來源：** whisper 逐字稿（`transcripts/EP{e['ep']}.txt`，{b:,} bytes／{l:,} 段；雲端排程 faster-whisper small int8 單次轉錄）",
         f"**個股點名：** {e['mentions']}　**過熱訊號：** {e['overheat']}", '',
         f"> ⚠️ **引述處理原則**：本節引述已逐一以 difflib 比對 `transcripts/EP{e['ep']}.txt`（全數 ≥0.9）。為可讀性，"
         f"引號內已修正 whisper 明顯誤字（{fixes}；另 OpenCC 的「臺」統一為「台」），並在跨行處補標點；**語序與語意未改動**。"
         f"仍有疑義者標記〔音譯〕：{'；'.join(e['unresolved'])}。", '',
         f"> 📌 **本集定位**：{e['position']}", '', '---', '']
    for s in e['sections']:
        L += [f"### {s['h']}", '', f"> 「{s['lead']}」", '']
        L += [f'- **{lab}**：{txt}' for lab, txt in s['bullets']]
        L.append('')
    L += [f"> 📎 **市場背景（外部查證，非主委原話）**：{e['market']}", '', '---', '', '']
    return '\n'.join(L)


def tag_cls(t):
    if t.startswith(('📝', '★')):
        return 'tag done'
    if t.startswith('⏳'):
        return 'tag pending'
    if re.search(r'META|AMD|Amazon|Google|NVIDIA|Broadcom|Tesla|OpenAI|美股', t):
        return 'tag us'
    if re.search(r'台股|台達|台積|聯發科|MTK', t):
        return 'tag tw'
    return 'tag'


def report_card(e):
    h = lambda x: html.escape(x, quote=False)
    b, l = tstats(e['ep'])
    out = [f'<div class="card" id="ep{e["ep"]}">', f"  <h2>{e['emoji']} EP{e['ep']}｜「{h(e['tagline'])}」</h2>",
           f"  <div class=\"meta\">{e['date']}（{e['wd']}）{e['pub']} TPE · {h(dur_txt(e['dur_sec']))} · 贊助：{h(e['sponsor'])} · "
           f"<a href=\"{e['link']}\" target=\"_blank\">SoundOn</a> · 逐字稿 {b:,} bytes／{l:,} 段</div>", '  <div>']
    out += [f'    <span class="{tag_cls(t)}">{h(t)}</span>' for t in clean_tags(e['tags'])]
    out += ['  </div>', f"  <div class=\"note good\"><b>本集定位</b>　{h(e['position'])}</div>"]
    for s in e['sections']:
        out += [f"  <h3 class=\"sec\">{h(s['h'])}</h3>", f"  <div class=\"quote\">「{h(s['lead'])}」</div>", '  <ul>']
        out += [f'    <li><b>{h(lab)}</b>：{h(txt)}</li>' for lab, txt in s['bullets']]
        out.append('  </ul>')
    out += [f"  <div class=\"note\"><b>市場背景（外部查證，非主委原話）</b>　{h(e['market'])}</div>",
            f"  <div class=\"meta\" style=\"margin-top:10px\">〔音譯〕待確認：{h('；'.join(e['unresolved']))}</div>", '</div>', '']
    return '\n'.join(out)


def main(paths, cards_out=None):
    eps = sorted((json.load(open(p, encoding='utf-8')) for p in paths), key=lambda e: -e['ep'])
    ip = f'{ROOT}/index.html'
    s = open(ip, encoding='utf-8').read()
    anchor = 'const EPISODES = {\n'
    assert s.count(anchor) == 1
    for e in eps:
        assert f"\n  {e['ep']}:{{date:" not in s, f"EP{e['ep']} already inline"
    s = s.replace(anchor, anchor + ''.join(inline_entry(e) for e in eps), 1)
    open(ip, 'w', encoding='utf-8').write(s)
    m = open(MD, encoding='utf-8').read()
    assert m.count('===== AUTO_INSERT_POINT_BELOW =====') == 1
    m = m.replace(MARKER, MARKER + ''.join(md_section(e) for e in eps), 1)
    newest = max(e['ep'] for e in eps)
    now = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%dT%H:%M:%S+08:00')
    m = re.sub(r'last_seen_ep: \d+', f'last_seen_ep: {newest}', m, count=1)
    m = re.sub(r'newest_ep_in_file: \d+', f'newest_ep_in_file: {newest}', m, count=1)
    m = re.sub(r'last_check: \S+', f'last_check: {now}', m, count=1)
    m = re.sub(r'total_episodes_covered: (\d+)', lambda x: f'total_episodes_covered: {int(x.group(1)) + len(eps)}', m, count=1)
    m = re.sub(r'(\*\*涵蓋範圍：\*\* EP651 至 EP)\d+', rf'\g<1>{newest}', m, count=1)
    open(MD, 'w', encoding='utf-8').write(m)
    if cards_out:
        open(cards_out, 'w', encoding='utf-8').write(''.join(report_card(e) for e in eps))
    print('rendered', [e['ep'] for e in eps])


if __name__ == '__main__':
    a = sys.argv[1:]
    out = None
    if '--report-cards' in a:
        i = a.index('--report-cards')
        out = a[i + 1]
        a = a[:i] + a[i + 2:]
    main(a, out)
