# 三層整合 Setup Guide
## Cowork + Hermes + OpenClaw → gooaye-tracker

✅ **前提：** 您已安裝好 Hermes Agent 和 OpenClaw（您剛才確認的）

本指南：把這個資料夾的 skills/tasks 「**載入**」到您的 Hermes 和 OpenClaw，並串好整個 pipeline。

---

## 📋 Step-by-Step 整合步驟

### Step 1：把 OpenClaw skills 載入

```bash
# OpenClaw 把 skills 從 markdown 自動匯入
cd "/Users/wangtingwei/Documents/Claude/Projects/股癌/integrations/openclaw_skills"

# 對每個 skill：
openclaw skill add gooaye_check.md
openclaw skill add gooaye_alert.md
openclaw skill add gooaye_search.md

# 驗證
openclaw skill list
```

### Step 2：設定 OpenClaw 的 Telegram 整合

```bash
openclaw integration add telegram
# 跟著 prompt：
# 1. 開 @BotFather on Telegram
# 2. /newbot → 取得 Bot Token
# 3. 貼 token 給 openclaw
# 4. 您的 Telegram username 給 openclaw（限定誰可以用）
```

### Step 3：測試 OpenClaw Telegram

打開 Telegram → 找您的 bot → 傳：

```
股癌最新
```

應該回傳 EP660 摘要。

### Step 4：啟用 OpenClaw 排程

```bash
openclaw schedule add gooaye_alert \
  --cron "30 19 * * 3,6" \
  --description "Wed/Sat 19:30 detect new gooaye episode"

openclaw schedule add gooaye_alert \
  --cron "0 9 * * *" \
  --description "Daily 9:00 briefing" \
  --variant daily_briefing
```

---

### Step 5：把 Hermes tasks 載入

```bash
cd "/Users/wangtingwei/Documents/Claude/Projects/股癌/integrations/hermes_tasks"

# 一次性：embed 660 集到 vector DB
hermes run embed_660_episodes.py

# 排程：每日 16:30 驗證 watchlist
hermes schedule add validate_calls_daily.py "0 16:30 * * 1-5"

# 觸發式：新集出爐時跑多 LLM 投票
hermes hook on:cowork-new-episode multi_llm_vote.py
```

### Step 6：串接 Cowork → Hermes

在 Cowork 排程的 SKILL.md 加上 webhook 通知：

```bash
# 編輯 ~/Documents/Claude/Scheduled/gooaye-new-episode-watcher/SKILL.md
# 在 Step 8 (auto-push) 之後加 Step 8.5：

### 8.5. Trigger Hermes for deep validation
After git push succeeds, notify Hermes:
\`\`\`
curl -X POST http://localhost:HERMES_PORT/webhook/cowork-new-episode \
  -H "Content-Type: application/json" \
  -d '{"new_eps": [...new episode numbers...]}'
\`\`\`
```

---

## 🎯 完成後的 pipeline

```
┌──────────────────────────────────────────────────┐
│  週三 / 週六 19:09                                │
│  → Cowork 排程偵測新集                             │
│  → 抓 vocus → 寫 deep summary                     │
│  → git push → GitHub Pages 自動部署                │
│  → Webhook 通知 Hermes                             │
└──────────────────┬───────────────────────────────┘
                   ↓
┌──────────────────────────────────────────────────┐
│  Hermes 收到 webhook                              │
│  → 跑 multi_llm_vote.py（3 LLM 投票）              │
│  → 驗證所有 watchlist                             │
│  → 結果寫回 web app + git push                    │
│  → 通知 OpenClaw                                   │
└──────────────────┬───────────────────────────────┘
                   ↓
┌──────────────────────────────────────────────────┐
│  OpenClaw 收到 Hermes 通知                        │
│  → push Telegram：「EP661 完成深度驗證 + 新增 N 檔強推」 │
│  → 您手機立即收到                                  │
└──────────────────────────────────────────────────┘
```

---

## 💰 月費總覽

| 項目 | 月費 |
|---|---|
| Cowork（已有）| $0 |
| OpenClaw（在 Mac/RPi 上）| $0 |
| Hermes（如本機跑）| $0 |
| Hermes（如雲端 VPS）| $5 |
| OpenAI Embedding（一次性 + 增量） | ~$1 |
| Claude API（深度摘要 / multi-LLM 投票） | ~$10 |
| **總計** | **$11-16/月** |

---

## 🚦 各層職責一覽

| 任務 | Cowork | Hermes | OpenClaw |
|---|---|---|---|
| 偵測新集 RSS | ✅ 主要 | 備援 | 備援 |
| 寫深度摘要 | ✅ 主要 | - | - |
| Git push | ✅ 主要 | - | - |
| 660 集向量搜尋 | - | ✅ 主要 | 委派給 Hermes |
| 多 LLM 投票驗證 | - | ✅ 主要 | - |
| 每日股價驗證 | - | ✅ 主要 | - |
| Telegram / iMessage 推播 | - | - | ✅ 主要 |
| 早安日報 | - | - | ✅ 主要 |
| 即時查詢「股癌最新」 | - | - | ✅ 主要 |
| 過熱訊號緊急 push | - | 監控 | ✅ 推播 |

---

## 🧪 驗證整合是否成功

### Test 1：OpenClaw 即時查詢
打開 Telegram，傳：「股癌最新」
**預期：** 30 秒內回傳 EP660 摘要

### Test 2：Hermes 語意搜尋
在 Telegram 傳：「找股癌講過 NVIDIA 估值」
**預期：** OpenClaw 委派 Hermes → 回傳 Top 5 相關集數

### Test 3：自動推播
等 5/13（週三）19:30，**預期：** 您手機收到「🎙 EP661 已偵測」

### Test 4：每日驗證
明天 16:30（台股收盤後），**預期：** 收到 daily validation 推播

---

## 🐛 Troubleshooting

| 問題 | 解法 |
|---|---|
| OpenClaw Telegram 不回應 | `openclaw logs` 看錯誤 |
| Hermes 找不到 vector DB | 確認 embed_660 跑過 |
| Cowork webhook 無法 reach Hermes | 用 ngrok 或 Cloudflare Tunnel 暴露 Hermes |
| git push 卡住 | 跑 `rm -f .git/index.lock` |
| 推播太多 | 在 OpenClaw 設 throttle / quiet hours |

---

## 📚 進階：擴充其他 podcast

複製此架構到其他內容源（如「老謝看世界」、「M 平方」）：

1. 在 `_state.json` 加新 channel：
```json
{
  "channels": [
    {"name": "gooaye", "rss": "...", "last_seen_ep": 660},
    {"name": "lao-xie", "rss": "...", "last_seen_ep": 0}
  ]
}
```

2. Cowork 排程改成 loop 處理所有 channels
3. Hermes 為每個 channel 建獨立 collection
4. OpenClaw 加 prefix 路由：「股癌最新」 / 「老謝最新」

---

由 Claude · Cowork mode 整理 · 2026/05/09
