# OpenClaw Skill: gooaye_check

## Purpose
Quick query of latest 股癌 podcast info from Telegram/iMessage/WhatsApp.

## Trigger phrases
- "股癌最新"
- "gooaye latest"
- "股癌 EP" + number
- "今天股癌"

## Implementation

When user says "股癌最新" or similar:

1. Fetch the live web app:
   ```bash
   curl -s "https://qwwaawwqq.github.io/gooaye-tracker/" | head -c 50000
   ```

2. Or fetch the JSON state directly:
   ```bash
   curl -s "https://raw.githubusercontent.com/qwwaawwqq/gooaye-tracker/main/_state.json"
   ```

3. Extract the latest episode info and respond:
   ```
   🎙 股癌最新：EP{ep}
   📅 {date}
   🏷 {tags}
   📊 命中率：{hit_rate}%
   🔗 完整內容：https://qwwaawwqq.github.io/gooaye-tracker/
   ```

## Example interactions

User: "股癌最新"
Claw: 🎙 EP660 (5/9) 「這樣下去會不會壞掉」
       過熱階段警示，4 大訊號齊發
       👉 https://qwwaawwqq.github.io/gooaye-tracker/

User: "推薦個股"
Claw: 🟢 強推 5 檔：
       創意 (3443) +36% / 國巨 (2327) 漲停 / 信昌電 (6173) 漲停
       世芯-KY (3661) +5% / 旺宏 (2337) 漲價兌現
       詳見 web app

User: "EP659 講啥"
Claw: 🦤 做壞掉了 (51 分)
       ① 被動元件第三波（國巨/信昌電）
       ② AMD CPU >50% 市佔
       ③ ASIC 全動（GUC/世芯-KY）
       ④ 過熱訊號累積
       金句：「我不想要在派對結束之前就走出去」

## Skill metadata
- name: gooaye_check
- author: claude-cowork-integration
- triggers: 股癌, gooaye, 推薦個股, EP{number}
- timeout: 10s
