#!/usr/bin/env python3
"""
ps-search-1: Generate _search_index.json with episode, call, and stock entries
for lightweight full-text substring/token search. Fetched on-demand by index.html
via vanilla JS, no external library.
"""
import json
from pathlib import Path
from html import unescape as html_unescape

OUTPUT_DIR = Path(__file__).parent
BASE_URL = "https://qwwaawwqq.github.io/gooaye-tracker"

def strip_html(s):
    """Remove HTML tags and decode entities."""
    s = s or ''
    s = s.replace('<b>', '').replace('</b>', '')
    s = s.replace('<br>', ' ').replace('</br>', ' ')
    return html_unescape(s).strip()

def tokenize(s):
    """Split into tokens for search matching (Chinese characters + words)."""
    tokens = []
    word = ''
    for c in s:
        if '一' <= c <= '鿿':  # CJK Unified Ideographs
            if word:
                tokens.append(word)
                word = ''
            tokens.append(c)
        elif c.isalnum():
            word += c
        else:
            if word:
                tokens.append(word)
                word = ''
    if word:
        tokens.append(word)
    return tokens

def gen_search_index():
    """Build _search_index.json from episodes_auto, market_auto, and 660-ep history."""
    index = []
    
    # Load auto data
    try:
        with open(OUTPUT_DIR / '_episodes_auto.json') as f:
            episodes_auto = json.load(f)
    except:
        episodes_auto = {}
    
    try:
        with open(OUTPUT_DIR / '_market_auto.json') as f:
            market_auto = json.load(f)
    except:
        market_auto = {}
    
    try:
        with open(OUTPUT_DIR / '股癌_全集歷史_660集.json') as f:
            history_660 = json.load(f)
    except:
        history_660 = {}
    
    # Index recent episodes from _episodes_auto.json
    for ep_key, ep_data in episodes_auto.get('episodes', {}).items():
        ep_num = ep_data.get('ep')
        if not ep_num:
            continue
        
        title = ep_data.get('title', f'EP{ep_num}')
        title_clean = strip_html(title)
        summary = strip_html(ep_data.get('summary', ''))
        date = ep_data.get('date', '')
        
        # Episode entry
        text = f"{title_clean} {summary} {date}"
        index.append({
            'type': 'ep',
            'id': f"ep{ep_num}",
            'title': title_clean,
            'text': text[:300],  # Limit to 300 chars
            'url': f"{BASE_URL}/ep/{ep_num}.html",
            'tokens': tokenize(title_clean + ' ' + summary)
        })
        
        # Index calls in this episode
        for call_idx, call in enumerate(ep_data.get('calls', [])):
            call_topic = strip_html(call.get('t', ''))
            call_content = strip_html(call.get('c', ''))
            call_verdict = call.get('v', 'pending')
            
            call_text = f"{call_topic} {call_content} {call_verdict}"
            index.append({
                'type': 'call',
                'id': f"ep{ep_num}_call{call_idx}",
                'title': f"EP{ep_num}: {call_topic}",
                'text': call_text[:250],
                'url': f"{BASE_URL}/ep/{ep_num}.html",
                'tokens': tokenize(call_topic + ' ' + call_content)
            })
    
    # Index all episodes from 660-ep history (for historical search)
    for ep in history_660.get('episodes', []):
        ep_num = ep.get('ep')
        if not ep_num:
            continue
        
        title = ep.get('title', f'EP{ep_num}')
        title_clean = strip_html(title)
        desc = strip_html(ep.get('description_preview', ''))
        date = ep.get('date', '')
        
        text = f"{title_clean} {desc} {date}"
        index.append({
            'type': 'ep_history',
            'id': f"ep{ep_num}_hist",
            'title': title_clean,
            'text': text[:200],
            'url': f"{BASE_URL}/ep/{ep_num}.html",
            'tokens': tokenize(title_clean + ' ' + desc)
        })
    
    # Index stocks from validation table
    for row in market_auto.get('validation', {}).get('rows', []):
        code = row.get('code')
        name = row.get('name')
        mkt = row.get('mkt', 'tw')
        verdict = row.get('verdict')
        
        if not code or not name:
            continue
        
        text = f"{code} {name} {verdict}"
        index.append({
            'type': 'stock',
            'id': f"stock{code}",
            'title': f"{code} {name}",
            'text': text,
            'url': f"{BASE_URL}/stock/{mkt.lower()}-{code}.html",
            'tokens': tokenize(code + ' ' + name)
        })
    
    # Write index
    with open(OUTPUT_DIR / '_search_index.json', 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    
    print(f"✓ Generated _search_index.json with {len(index)} entries")
    return len(index)

if __name__ == '__main__':
    print("[gen_search_index.py] Building search index...")
    count = gen_search_index()
    print(f"[gen_search_index.py] ✓ Done. Indexed {count} searchable entries.")
