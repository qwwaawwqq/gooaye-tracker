#!/usr/bin/env python3
"""
Hermes Task: validate_calls_daily
Purpose: Daily 16:30 (after TWSE close) - validate watchlist calls vs actual prices.
Schedule via Hermes: hermes schedule "0 16:30 * * 1-5" validate_calls_daily.py
"""

import json
import requests
from datetime import datetime
from pathlib import Path

WATCHLIST_FILE = Path.home() / "Documents/Claude/Projects/股癌/_watchlist_state.json"

# Stocks currently on watchlist (mirror web app)
WATCHLIST = {
    "3443": {"name": "創意", "stance": "強推", "call_price": 4000, "call_date": "2026-04-25", "call_ep": 656},
    "3661": {"name": "世芯-KY", "stance": "強推", "call_price": 3800, "call_date": "2026-04-25", "call_ep": 656},
    "2327": {"name": "國巨", "stance": "啟動", "call_price": None, "call_date": "2026-05-06", "call_ep": 659},
    "6173": {"name": "信昌電", "stance": "啟動", "call_price": None, "call_date": "2026-05-06", "call_ep": 659},
    "2337": {"name": "旺宏", "stance": "看好", "call_price": None, "call_date": "2026-04-29", "call_ep": 657},
    "2454": {"name": "聯發科", "stance": "預期打滿", "call_price": 3500, "call_date": "2026-05-06", "call_ep": 659},
    "2330": {"name": "台積電", "stance": "持有", "call_price": 2200, "call_date": "2026-04-25", "call_ep": 656},
}

def fetch_tw_stock_price(ticker):
    """Fetch TW stock close price from Yahoo Finance."""
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}.TW"
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    if resp.status_code == 200:
        data = resp.json()
        return data['chart']['result'][0]['meta']['regularMarketPrice']
    return None

def calc_verdict(call_price, current, days_held):
    """Apply 100-episode backtest verdict rules."""
    if call_price is None:
        return "PENDING"
    pct = (current - call_price) / call_price * 100
    if pct >= 5 and days_held <= 3:
        return "🟢 STRONG HIT"
    elif pct >= 0 and days_held <= 10:
        return "🟢 HIT"
    elif pct < 0 and days_held > 7:
        return "🟡 PARTIAL"
    elif pct < -10:
        return "🔴 MISS"
    else:
        return "⏳ PENDING"

def main():
    today = datetime.now().strftime('%Y-%m-%d')
    results = {"date": today, "stocks": {}}

    for ticker, info in WATCHLIST.items():
        print(f"📊 Validating {ticker} {info['name']}...")
        current = fetch_tw_stock_price(ticker)
        if current is None:
            print(f"  ⚠ Failed to fetch")
            continue

        call_date = datetime.fromisoformat(info['call_date'])
        days_held = (datetime.now() - call_date).days

        verdict = calc_verdict(info.get('call_price'), current, days_held)
        pct = ((current - info['call_price']) / info['call_price'] * 100) if info.get('call_price') else None

        results['stocks'][ticker] = {
            'name': info['name'],
            'call_ep': info['call_ep'],
            'call_price': info.get('call_price'),
            'current': current,
            'pct_change': round(pct, 2) if pct else None,
            'days_held': days_held,
            'verdict': verdict,
        }
        print(f"  {ticker} {info['name']}: ${current} ({pct:+.2f}%) → {verdict}")

    # Save state
    with open(WATCHLIST_FILE, 'w') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # Send Telegram update if any new STRONG HIT or MISS
    new_alerts = [s for s in results['stocks'].values()
                  if 'STRONG' in s['verdict'] or 'MISS' in s['verdict']]
    if new_alerts:
        send_telegram_summary(new_alerts)

    print(f"\n✓ Validation done, saved to {WATCHLIST_FILE}")

def send_telegram_summary(alerts):
    """Send via Hermes' Telegram integration."""
    msg = f"📊 *股癌追蹤 daily validation*\n\n"
    for s in alerts:
        msg += f"{s['verdict']} {s['name']} ({s['pct_change']:+.2f}%)\n"
    # hermes.telegram.send(msg)
    print(f"\n📨 Telegram alert:\n{msg}")

if __name__ == "__main__":
    main()
