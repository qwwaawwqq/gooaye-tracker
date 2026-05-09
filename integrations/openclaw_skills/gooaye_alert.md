# OpenClaw Skill: gooaye_alert

## Purpose
Proactive push notification when 股癌 publishes new episode OR when overheating signals trigger.

## Schedule (using OpenClaw's natural language cron)

```
Every Wednesday and Saturday at 19:30, run gooaye_alert
Every weekday at 9:00, send daily briefing
```

## Implementation

### A. New Episode Detection (Wed/Sat 19:30)
```python
# OpenClaw skill body
import requests, json

# Fetch RSS via rss2json (most reliable)
rss = "https://feeds.soundon.fm/podcasts/954689a5-3096-43a4-a80b-7810b219cef3.xml"
resp = requests.get(f"https://api.rss2json.com/v1/api.json?rss_url={rss}&count=3").json()
latest = resp['items'][0]
ep_match = re.search(r'EP(\d+)', latest['title'])
ep_num = int(ep_match.group(1)) if ep_match else None

# Read state
state = json.load(open(os.path.expanduser('~/Documents/Claude/Projects/股癌/_state.json')))
last_seen = state['last_seen_ep']

if ep_num > last_seen:
    # New episode!
    send_telegram(f"""
    🎙 *股癌新集出爐 EP{ep_num}*
    📅 {latest['pubDate']}
    📋 {latest['title']}
    
    🔗 https://qwwaawwqq.github.io/gooaye-tracker/
    
    ⏳ 深度摘要 1-2 天後 vocus 整理上線後自動更新
    """)
```

### B. Daily Briefing (每天早上 9:00)
```python
# Pull current watchlist from web app
# Send digest to Telegram
send_telegram(f"""
☀️ *早安 · 股癌追蹤站日報 {today}*

🟢 *強推持倉*
- 創意 3443 +36%
- 國巨 2327 漲停
- 信昌電 6173 漲停

⚠️ *風險警示*
- 聯發科 2454 處置股期間（5/7-5/20）

🚨 *過熱訊號狀態：3/4 已亮燈*
- ✅ 券商晴天收傘
- ✅ 估值上緣
- ✅ 大資金不解套
- ⏳ 大盤長黑 K（未觸發）

💡 *今日建議*：保持 30% 現金，停損紀律
""")
```

### C. Overheating Alert (大盤跌破關鍵點時)
```python
# Hourly during market hours
twse_index = scrape_yahoo_finance("^TWII")
yesterday_close = ...

if (twse_index - yesterday_close) / yesterday_close < -0.025:
    send_telegram_urgent(f"""
    🚨 *大盤過熱訊號觸發！*
    
    加權指數：{twse_index} ({pct}%)
    
    根據 EP659 退場條件：
    👉 大盤長黑 K 出現
    
    *建議行動：*
    1. 檢查您的槓桿水位
    2. 個股設停損 -5%
    3. 整體部位 -8%
    
    詳細紅線清單：https://qwwaawwqq.github.io/gooaye-tracker/#watchlist
    """)
```

## Skill metadata
- name: gooaye_alert
- type: scheduled
- channels: telegram, imessage
- priority: high
