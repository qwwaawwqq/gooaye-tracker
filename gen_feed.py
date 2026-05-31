#!/usr/bin/env python3
"""
gen_feed.py — Emit RSS 2.0 + JSON feeds for retention (ps-retain-1).

Two event types:
  1. Episode published: new entries from _episodes_auto.json
  2. Call resolved: verdict moved off 'pending' in _market_auto.json.validation

Idempotent: guid based on ep + verdict snapshot; same input always same output.
Stdlib only; outputs feed.xml (RSS) and feed.json (JSON) in project root.

Usage: python gen_feed.py [--no-rss] [--no-json] [--keep 50]
  --no-rss    skip RSS output
  --no-json   skip JSON output
  --keep N    emit only last N events (default: 50)
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from hashlib import md5
import argparse


def load_json(path):
    """Load JSON safely; return {} on missing/corrupt file."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        with open(p) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"warn: failed to load {path}: {e}", file=sys.stderr)
        return {}


def parse_iso8601(date_str):
    """Parse ISO8601 date or datetime; return RFC2822 string for RSS."""
    if not date_str:
        return None
    try:
        # Try full ISO8601 datetime
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            # Date only; assume UTC midnight
            dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        # RFC2822: "Thu, 30 May 2026 10:16:09 +0000"
        return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
    except Exception as e:
        print(f"warn: failed to parse date {date_str}: {e}", file=sys.stderr)
        return None


def strip_html(html):
    """Strip HTML tags; collapse whitespace."""
    import re
    text = re.sub(r"<[^>]+>", "", html or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def guid_from_event(ep, code=None, old_verdict=None, new_verdict=None):
    """Deterministic guid: ep + verdict delta fingerprint."""
    parts = [str(ep)]
    if code:
        parts.append(code)
    if old_verdict or new_verdict:
        parts.append(f"{old_verdict}->{new_verdict}")
    msg = "|".join(parts).encode()
    return md5(msg).hexdigest()


def gen_episode_events(episodes_dict):
    """Yield (pubDate_iso, ep_num, title, link, guid, desc) for each episode."""
    for ep_str in sorted(episodes_dict.keys(), key=lambda x: int(x), reverse=True):
        ep_data = episodes_dict[ep_str]
        ep_num = int(ep_str)
        title = ep_data.get("title", f"EP{ep_num}")
        date_str = ep_data.get("date")  # YYYY-MM-DD
        summary = ep_data.get("summary", "")
        
        if not date_str:
            continue
        
        pubDate_rfc = parse_iso8601(date_str)
        if not pubDate_rfc:
            continue
        
        # Remove HTML, truncate summary
        summary_plain = strip_html(summary)[:200]
        
        # Link: https://qwwaawwqq.github.io/gooaye-tracker/#ep{ep_num}
        link = f"https://qwwaawwqq.github.io/gooaye-tracker/#ep{ep_num}"
        
        guid = guid_from_event(ep_num)
        
        yield {
            "type": "episode_published",
            "pubDate": pubDate_rfc,
            "ep": ep_num,
            "title": title,
            "link": link,
            "guid": guid,
            "description": summary_plain,
            "raw_date": date_str,
        }


def gen_resolved_events(validation_list, old_verdicts=None):
    """
    Yield events for calls that moved off 'pending'.
    
    old_verdicts: dict {code: old_verdict} to detect changes.
                  If None, emit all non-pending as "resolved" (initialization).
    """
    if old_verdicts is None:
        old_verdicts = {}
    
    for val in validation_list:
        code = val.get("code")
        name = val.get("name")
        verdict = val.get("verdict", "pending")
        first_ep = val.get("first_ep")
        stance = val.get("stance", "—")
        start_date = val.get("start_date")
        change_pct = val.get("change_pct")
        days_elapsed = val.get("days_elapsed")
        
        if not code or verdict == "pending":
            continue
        
        old_v = old_verdicts.get(code, "unknown")
        
        # Only emit if verdict changed away from pending, or on first run
        if old_v == "pending" or old_v == "unknown" or old_v != verdict:
            emoji = "✅" if verdict == "hit" else ("⚠️" if verdict == "partial" else "❌")
            pct_str = f"+{change_pct:.1f}%" if change_pct > 0 else f"{change_pct:.1f}%"
            title = f"EP{first_ep} {code} {name} → {verdict} {emoji} ({pct_str})"
            
            # Estimate pubDate as episode date or update_at if not available
            pubDate_rfc = parse_iso8601(start_date) or datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
            
            link = f"https://qwwaawwqq.github.io/gooaye-tracker/#call-{code}"
            guid = guid_from_event(first_ep, code, old_v, verdict)
            
            desc = f"<b>{stance}</b> · {pct_str} over {days_elapsed}d · 自 EP{first_ep}"
            
            yield {
                "type": "call_resolved",
                "pubDate": pubDate_rfc,
                "ep": first_ep,
                "code": code,
                "name": name,
                "verdict": verdict,
                "title": title,
                "link": link,
                "guid": guid,
                "description": desc,
                "change_pct": change_pct,
                "stance": stance,
                "raw_date": start_date,
            }


def merge_events(ep_events, resolved_events):
    """Merge and sort by pubDate (newest first)."""
    all_events = list(ep_events) + list(resolved_events)
    # Sort by raw_date descending, then by type (resolved before episode for same day)
    all_events.sort(
        key=lambda e: (e.get("raw_date", "0000-00-00"), e["type"] == "episode_published"),
        reverse=True
    )
    return all_events


def render_rss(events, keep=50):
    """Render RSS 2.0 XML from events."""
    events = events[:keep]
    
    rss = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "<channel>",
        "<title>股癌 — 追蹤清單 + 解題</title>",
        "<link>https://qwwaawwqq.github.io/gooaye-tracker/</link>",
        "<atom:link href=\"https://qwwaawwqq.github.io/gooaye-tracker/feed.xml\" rel=\"self\" type=\"application/rss+xml\"/>",
        "<description>投資 call 追蹤驗證 + 解題清單</description>",
        "<language>zh-tw</language>",
        "<lastBuildDate>" + datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000") + "</lastBuildDate>",
    ]
    
    for e in events:
        rss.append("<item>")
        rss.append(f"<title>{escape_xml(e['title'])}</title>")
        rss.append(f"<link>{escape_xml(e['link'])}</link>")
        rss.append(f"<guid isPermaLink=\"false\">{escape_xml(e['guid'])}</guid>")
        rss.append(f"<pubDate>{e['pubDate']}</pubDate>")
        rss.append(f"<description>{escape_xml(e['description'])}</description>")
        if e["type"] == "call_resolved":
            rss.append(f"<category>{escape_xml(e['verdict'])}</category>")
        rss.append("</item>")
    
    rss.extend(["</channel>", "</rss>"])
    return "\n".join(rss)


def escape_xml(s):
    """Escape XML special chars."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")


def render_json(events, keep=50):
    """Render JSON feed from events."""
    events = events[:keep]
    return {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "股癌 — 追蹤清單 + 解題",
        "home_page_url": "https://qwwaawwqq.github.io/gooaye-tracker/",
        "feed_url": "https://qwwaawwqq.github.io/gooaye-tracker/feed.json",
        "description": "投資 call 追蹤驗證 + 解題清單",
        "language": "zh-tw",
        "items": events,
    }


def main():
    parser = argparse.ArgumentParser(description="Generate RSS + JSON feeds from 股癌 data.")
    parser.add_argument("--no-rss", action="store_true", help="Skip RSS output")
    parser.add_argument("--no-json", action="store_true", help="Skip JSON output")
    parser.add_argument("--keep", type=int, default=50, help="Keep last N events (default: 50)")
    args = parser.parse_args()
    
    proj_root = Path(__file__).parent
    episodes_path = proj_root / "_episodes_auto.json"
    market_path = proj_root / "_market_auto.json"
    
    # Load data
    episodes = load_json(episodes_path).get("episodes", {})
    market = load_json(market_path)
    # validation is an object {total, counts, hit_rate_pct, avg_return_pct, rows};
    # the per-call records live in .rows.
    validation = (market.get("validation") or {}).get("rows", [])
    
    # Generate events
    ep_events = list(gen_episode_events(episodes))
    resolved_events = list(gen_resolved_events(validation))
    all_events = merge_events(ep_events, resolved_events)
    
    # Output
    if not args.no_rss:
        rss_content = render_rss(all_events, keep=args.keep)
        rss_path = proj_root / "feed.xml"
        rss_path.write_text(rss_content, encoding="utf-8")
        print(f"wrote {len(all_events[:args.keep])} events to {rss_path}")
    
    if not args.no_json:
        json_data = render_json(all_events, keep=args.keep)
        json_path = proj_root / "feed.json"
        json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"wrote {len(all_events[:args.keep])} events to {json_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
