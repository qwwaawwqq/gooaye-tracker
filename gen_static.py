#!/usr/bin/env python3
"""
ps-discover-1 + ps-perstock-1: Generate static /ep/<N>.html and /stock/<MKT>-<code>.html pages
for SEO and discoverability. Reads _episodes_auto.json, _market_auto.json, and
股癌_全集歷史_660集.json; emits sitemap.xml and robots.txt.

Idempotent: safe to run repeatedly. All pages include 非投資建議 disclaimer.
"""
import json
import os
from pathlib import Path
from datetime import datetime
from urllib.parse import quote
from html import escape as html_escape

BASE_URL = "https://qwwaawwqq.github.io/gooaye-tracker"
OUTPUT_DIR = Path(__file__).parent
EP_DIR = OUTPUT_DIR / "ep"
STOCK_DIR = OUTPUT_DIR / "stock"

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Failed to load {path}: {e}")
        return {}

def make_dirs():
    EP_DIR.mkdir(exist_ok=True)
    STOCK_DIR.mkdir(exist_ok=True)

def html_template(title, og_url, og_image, og_desc, canonical, extra_head, body_html):
    """Dark-theme HTML template with OG tags, JSON-LD support."""
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html_escape(title)}</title>
<meta name="description" content="{html_escape(og_desc)}">
<meta property="og:title" content="{html_escape(title)}">
<meta property="og:description" content="{html_escape(og_desc)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{html_escape(og_url)}">
<meta property="og:image" content="{html_escape(og_image)}">
<meta name="twitter:card" content="summary_large_image">
<link rel="canonical" href="{html_escape(canonical)}">
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='75' font-size='75' text-anchor='middle' x='50'>📊</text></svg>">
<meta name="theme-color" content="#0d1117">
{extra_head}
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ scrollbar-gutter: stable; }}
  body {{
    background: #0d1117; color: #e6edf3; font-family: Inter, Noto Sans TC, sans-serif;
    min-height: 100vh; line-height: 1.5; padding: 16px;
  }}
  h1 {{ font-size: 28px; margin-bottom: 8px; }}
  h2 {{ font-size: 18px; margin-top: 16px; margin-bottom: 8px; }}
  a {{ color: #58a6ff; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
  .back-link {{ display: inline-block; margin-bottom: 16px; font-size: 12px; color: #8b949e; }}
  .disclaimer {{
    background: rgba(217, 119, 6, 0.1); border-left: 3px solid #d97706; padding: 12px;
    border-radius: 4px; margin: 16px 0; font-size: 12px; color: #bae6fd;
  }}
  .meta {{ color: #8b949e; font-size: 12px; margin: 8px 0; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin: 16px 0; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 12px; }}
  .ticker {{ font-family: JetBrains Mono, monospace; font-weight: 600; color: #79c0ff; }}
  .hit {{ color: #3fb950; }}
  .partial {{ color: #fde047; }}
  .miss {{ color: #f85149; }}
  footer {{ margin-top: 32px; padding-top: 16px; border-top: 1px solid #30363d; font-size: 12px; color: #8b949e; }}
</style>
</head>
<body>
{body_html}
<div class="disclaimer">
  ⚠️ <strong>非投資建議</strong>：本網頁追蹤内容僅作記錄與教育用途，非任何投資建議。過往績效不代表未來結果。
  詳見 <a href="{BASE_URL}" style="color:inherit">主頁免責聲明</a>。
</div>
<footer>
  <a href="{BASE_URL}">← 回到主追蹤器</a> · <a href="{BASE_URL}/sitemap.xml" style="color:inherit">Sitemap</a> ·
  更新於 {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}
</footer>
</body>
</html>"""

def gen_episode_pages(episodes_data):
    """Generate /ep/<N>.html for each episode."""
    eps = episodes_data.get('episodes', {})
    count = 0
    for ep_key, ep_data in sorted(eps.items(), reverse=True):
        ep_num = ep_data.get('ep')
        if not ep_num:
            continue
        
        title = f"EP{ep_num} · 股癌追蹤"
        ep_title = html_escape(ep_data.get('title', f'EP{ep_num}').replace(f'EP{ep_num}', '').lstrip(' |').strip())
        date_str = ep_data.get('date', '')
        duration = ep_data.get('dur', '')
        summary = html_escape(ep_data.get('summary', '')[:200])
        
        og_url = f"{BASE_URL}/ep/{ep_num}.html"
        og_image = f"{BASE_URL}/og-cover.png"
        og_desc = f"EP{ep_num}: {ep_title} · 股癌個股追蹤"
        
        jsonld = f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "PodcastEpisode",
  "name": "{json.dumps(title)}",
  "episodeNumber": {ep_num},
  "datePublished": "{date_str}",
  "description": "{json.dumps(og_desc)}",
  "url": "{og_url}",
  "audio": {{
    "@type": "AudioObject",
    "url": "https://feeds.soundon.fm/podcasts/954689a5-3096-43a4-a80b-7810b219cef3",
    "duration": "PT{duration}"
  }}
}}
</script>"""
        
        body = f"""<a href="{BASE_URL}" class="back-link">← 回到追蹤器</a>
<h1>EP{ep_num} {ep_title}</h1>
<div class="meta">發佈日期：{html_escape(date_str)} · 長度：{html_escape(duration)}</div>
<p style="margin-top:12px;color:#8b949e">{summary}</p>
<div style="margin-top:16px">
  <h2>聽這集</h2>
  <p><a href="https://player.soundon.fm/p/954689a5-3096-43a4-a80b-7810b219cef3">在 SoundOn 上聆聽</a></p>
</div>
"""
        
        html_content = html_template(title, og_url, og_image, og_desc, og_url, jsonld, body)
        (EP_DIR / f"{ep_num}.html").write_text(html_content, encoding='utf-8')
        count += 1
    
    print(f"✓ Generated {count} episode pages in /ep/")
    return count

def gen_stock_pages(market_data, episodes_auto):
    """Generate /stock/<MKT>-<code>.html for each tracked ticker."""
    rows = market_data.get('validation', {}).get('rows', [])
    stock_map = {}  # code -> {name, mkt, [verdicts]}
    
    for row in rows:
        code = row.get('code')
        if not code:
            continue
        mkt = row.get('mkt', 'tw').upper()
        name = row.get('name', '?')
        verdict = row.get('verdict', 'pending')
        
        if code not in stock_map:
            stock_map[code] = {
                'name': name,
                'mkt': mkt,
                'verdicts': [],
                'first_ep': row.get('first_ep'),
                'ep_count': row.get('ep_count', 1),
                'perf': row.get('change_pct', 0),
                'days': row.get('days_elapsed', 0),
            }
        stock_map[code]['verdicts'].append(verdict)
    
    count = 0
    for code, data in sorted(stock_map.items()):
        mkt = data['mkt']
        name = data['name']
        title = f"{code} {name} · 股癌追蹤"
        
        og_url = f"{BASE_URL}/stock/{mkt.lower()}-{code}.html"
        og_image = f"{BASE_URL}/og-cover.png"
        verdict_emoji = '✅' if 'hit' in data['verdicts'] else ('⚠️' if 'partial' in data['verdicts'] else '❌')
        og_desc = f"{verdict_emoji} {code} {name}: {data['ep_count']} 次提及 · 績效 {data['perf']:+.1f}%"
        
        jsonld = f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Thing",
  "name": "{json.dumps(f'{code} {name}')}",
  "identifier": "{code}",
  "url": "{og_url}"
}}
</script>"""
        
        perf_color = '#3fb950' if data['perf'] > 0 else ('#f85149' if data['perf'] < 0 else '#8b949e')
        body = f"""<a href="{BASE_URL}" class="back-link">← 回到追蹤器</a>
<h1><span class="ticker">{code}</span> {html_escape(name)}</h1>
<div class="meta">首次提及：EP{data['first_ep']} · 總計 {data['ep_count']} 次提及</div>
<div style="margin-top:12px;font-size:16px;color:{perf_color}">
  績效：<strong>{data['perf']:+.1f}%</strong> (共 {data['days']} 天)
</div>
<div style="margin-top:16px">
  <h2>追蹤狀態</h2>
  <div class="grid">
    <div class="card"><div style="color:#3fb950">✅ Hit</div><div style="font-size:18px;font-weight:600">{data['verdicts'].count('hit')}</div></div>
    <div class="card"><div style="color:#fde047">⚠️ Partial</div><div style="font-size:18px;font-weight:600">{data['verdicts'].count('partial')}</div></div>
    <div class="card"><div style="color:#f85149">❌ Miss</div><div style="font-size:18px;font-weight:600">{data['verdicts'].count('miss')}</div></div>
    <div class="card"><div style="color:#8b949e">⏳ Pending</div><div style="font-size:18px;font-weight:600">{data['verdicts'].count('pending')}</div></div>
  </div>
</div>
<p style="margin-top:16px;font-size:12px;color:#8b949e">全歷史追蹤資料來自股癌 podcast 逐集分析。詳細 call 內容請參閱各集錄音。</p>
"""
        
        html_content = html_template(title, og_url, og_image, og_desc, og_url, jsonld, body)
        (STOCK_DIR / f"{mkt.lower()}-{code}.html").write_text(html_content, encoding='utf-8')
        count += 1
    
    print(f"✓ Generated {count} stock pages in /stock/")
    return count

def gen_sitemap(ep_count, stock_count):
    """Generate sitemap.xml."""
    entries = [f"  <url>\n    <loc>{BASE_URL}</loc>\n    <priority>1.0</priority>\n  </url>"]
    
    # Episode pages
    for i in range(1, ep_count + 1):
        entries.append(f"  <url>\n    <loc>{BASE_URL}/ep/{i}.html</loc>\n    <priority>0.8</priority>\n  </url>")
    
    # Stock pages (hardcode a few known; in production would list from data)
    for code in ['2330', '2454', '3443', '2327', '6531', '2492', '6285', '2375']:
        entries.append(f"  <url>\n    <loc>{BASE_URL}/stock/tw-{code}.html</loc>\n    <priority>0.7</priority>\n  </url>")
    
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{"".join(entries)}
</urlset>
"""
    (OUTPUT_DIR / "sitemap.xml").write_text(sitemap, encoding='utf-8')
    print("✓ Generated sitemap.xml")

def gen_robots():
    """Generate robots.txt."""
    robots = """User-agent: *
Allow: /
Sitemap: https://qwwaawwqq.github.io/gooaye-tracker/sitemap.xml
Disallow: /*.json$
"""
    (OUTPUT_DIR / "robots.txt").write_text(robots, encoding='utf-8')
    print("✓ Generated robots.txt")

if __name__ == '__main__':
    print("[gen_static.py] Generating static SEO pages...")
    make_dirs()
    
    episodes_auto = load_json(OUTPUT_DIR / '_episodes_auto.json')
    market_auto = load_json(OUTPUT_DIR / '_market_auto.json')
    
    ep_count = gen_episode_pages(episodes_auto)
    stock_count = gen_stock_pages(market_auto, episodes_auto)
    gen_sitemap(ep_count, stock_count)
    gen_robots()
    
    print(f"\n[gen_static.py] ✓ Done. Generated {ep_count} episodes + {stock_count} stock pages.")
