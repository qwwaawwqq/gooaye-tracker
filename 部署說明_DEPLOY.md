# 把這個 web app 部署到任何電腦都能訪問

`股癌_Chengwaye風格_App.html` 是一個完全自包含的 HTML 檔——可以丟到任何免費靜態網站平台，立刻拿到一個 URL，從手機 / 公司電腦 / 任何瀏覽器都能開。

---

## 🚀 最簡單：Netlify Drop（無需註冊也能用）

1. 打開 https://app.netlify.com/drop
2. **直接拖曳** `股癌_Chengwaye風格_App.html` 到頁面
3. 立刻拿到一個 URL 像 `https://random-name-12345.netlify.app/股癌_Chengwaye風格_App.html`
4. 想要好看的網址 → 註冊 Netlify 帳號 → Site settings → Change site name → 改成 `tingwei-gooaye` → URL 變 `https://tingwei-gooaye.netlify.app`

**優點：** 0 設定、永久免費、自動 HTTPS
**缺點：** 改名要註冊帳號

---

## 🌟 推薦：Cloudflare Pages（速度最快、永久免費）

1. 註冊 https://dash.cloudflare.com/sign-up
2. 左側選 **Workers & Pages** → **Create application** → **Pages** → **Upload assets**
3. Project name 填 `gooaye-tracker`
4. 把 `股癌_Chengwaye風格_App.html` 拖進去
5. Deploy → 拿到 URL `https://gooaye-tracker.pages.dev`

**優點：** Cloudflare CDN 全球加速，更新只要重新上傳
**缺點：** 需要註冊帳號（免費）

---

## 🔧 進階：GitHub Pages（搭配 Git 版本控制）

```bash
# 在你的工作資料夾
cd "/Users/wangtingwei/Documents/Claude/Projects/股癌"
git init
git add 股癌_Chengwaye風格_App.html
git commit -m "Gooaye tracker initial"

# 在 GitHub 開新 repo (例如 gooaye-tracker)
git remote add origin https://github.com/YOUR_USERNAME/gooaye-tracker.git
git branch -M main
git push -u origin main

# GitHub repo settings → Pages → Source: main branch
# URL 會是 https://YOUR_USERNAME.github.io/gooaye-tracker/股癌_Chengwaye風格_App.html
```

把檔案改名成 `index.html` 的話 URL 更短：`https://YOUR_USERNAME.github.io/gooaye-tracker/`

---

## ⚠️ 部署後需要注意的事

### CORS proxy 仍然會用
這個 web app 透過 4 個 CORS proxy fetch SoundOn RSS（`rss2json` 是首選）。部署到任何 host 都不影響，因為 proxy 是公共服務。

### 後端排程任務還是在你 Mac 上
- 部署的網頁版只負責 **顯示 + 即時偵測**（用 RSS 拉新集）
- Cowork 排程 `gooaye-new-episode-watcher` 還是在你 Mac 上跑（每週三、六 19:09），會在你的 `股癌` 資料夾生成新集摘要 HTML
- 兩者獨立運作，不影響

### localStorage 是「每瀏覽器各自獨立」
- 在公司電腦 mark as read 不會同步到家裡電腦
- 如果想跨裝置同步，需要更進階的後端（不在這個免費方案內）

### 自動更新內容？
這個 HTML 內建的 EP651-EP660 詳細摘要是**靜態的**。要新增新集（例如 EP661 出爐後的深度摘要）：
1. 排程任務會在你 Mac 上產生新的摘要 HTML
2. 把新摘要的 EPISODES/STOCKS/CALLS 資料貼進 `股癌_Chengwaye風格_App.html` 的 `<script>` 區塊
3. 重新 deploy（Netlify / Cloudflare Pages 直接覆蓋上傳即可）

---

## 📂 檔案清單

| 檔案 | 用途 | 部署？ |
|---|---|---|
| `股癌_Chengwaye風格_App.html` | 主推 web app（Chengwaye 風格） | ✅ 部署這個 |
| `股癌_整合追蹤驗證_App.html` | 上一版整合 app | ✅ 也可以部署 |
| `股癌_互動式深度摘要_v2.html` | EP656-660 純摘要 | 可選 |
| `股癌_預測驗證_Backtest.html` | 預測驗證回測 | 可選 |
| `股癌_即時追蹤_WebApp.html` | 第一版 tracker | 可選 |
| `_state.json` | 排程任務本地用，不部署 | ❌ |

---

製作：Claude · Cowork mode · 2026/05/09
