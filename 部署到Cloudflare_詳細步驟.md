# Cloudflare Pages 部署詳細步驟（搭配 Private GitHub Repo）

✅ **前提**：您已經把檔案 push 到 `https://github.com/qwwaawwqq/gooaye-tracker`（Private）

---

## 步驟 1：註冊 Cloudflare（已有帳號可跳過）

1. 開 **https://dash.cloudflare.com/sign-up**
2. 輸入 email + 密碼
3. 收信驗證 email
4. 登入後會看到 dashboard

> 💡 完全免費，不需要信用卡

---

## 步驟 2：建立 Pages 專案

### 2-1 找到 Pages

登入 dashboard 後：

- **左側選單** 找到 **Workers & Pages**（圖示像個齒輪 + 星星）
- 點進去 → 右上角 **Create application** 按鈕

### 2-2 選 Pages 分頁

進入 Create application 頁面後，**頂端會有兩個分頁**：

```
[ Workers ]    [ Pages ]   ← 點這個
```

點 **Pages** 分頁 → 點 **Connect to Git**（不要點 Direct Upload）

### 2-3 授權 GitHub

如果第一次用，會看到 **Connect GitHub** 按鈕：

- 點 **Connect GitHub** → 跳到 GitHub 授權頁
- GitHub 會問「Install Cloudflare on your account」：
  - 選 ⭐ **Only select repositories**（不要選 All）
  - 下拉選單 → 勾 ✅ **`gooaye-tracker`**
  - 點 **Install & Authorize**

### 2-4 回到 Cloudflare 選 repo

授權完會跳回 Cloudflare：

- 列表會顯示 `qwwaawwqq/gooaye-tracker`
- 點 repo 名稱 → 出現 **Begin setup** 按鈕（在右下角）
- 點 **Begin setup**

---

## 步驟 3：部署設定

進入 setup 頁面，填這些：

```
Project name:           gooaye-tracker
Production branch:      main
─────────────────────────────────────
Build settings
─────────────────────────────────────
Framework preset:       None
Build command:          （留空，整行什麼都不填）
Build output directory: （留空，預設根目錄）
─────────────────────────────────────
Environment variables: （不用設）
```

⚠️ **重要**：因為這是純 HTML 網站，**Build command 一定要留空**。如果它預設填了東西進去，把它清空。

點底部綠色 **Save and Deploy** 按鈕

---

## 步驟 4：等部署

點 Save and Deploy 後會跳到 deployment 頁面：

```
Building...
├─ Initializing build environment
├─ Cloning git repository
├─ Building application
└─ Deploying to Cloudflare's global network
```

整個過程約 **30-60 秒**。完成後會顯示綠色 ✅ 與網址。

---

## 步驟 5：拿到網址 🎉

部署完成後您會看到：

> **Your project is live at:**
> 🌐 **https://gooaye-tracker.pages.dev**

點網址測試 → 應該會看到您的「Gooaye 股癌 · Ting Wei Wang 私人追蹤站」首頁。

存成書籤！

---

## ✅ 部署完成後的檢查清單

打開 `https://gooaye-tracker.pages.dev`，確認：

- [ ] 頁面正常顯示，深色主題
- [ ] 上方狀態列顯示 「**RSS 已載入 ✓ (via rss2json)**」
- [ ] 點「個股總表」分頁 → 看到 20 檔股票
- [ ] 點「逐項驗證」分頁 → 看到 23 項 call
- [ ] 點「各集概況」分頁 → 看到 EP651-EP660
- [ ] 重新整理 → RSS 自動拉新集

---

## 🔄 之後怎麼更新內容？

**自動部署**：每次 `git push` 到 main 分支，Cloudflare 會自動偵測 → 重新部署 → 約 30 秒生效。

```bash
cd "/Users/wangtingwei/Documents/Claude/Projects/股癌"
# 改檔案後...
git add .
git commit -m "更新 EPxxx"
git push
# Cloudflare 約 30 秒後自動部署完成
```

可在 Cloudflare dashboard → Workers & Pages → gooaye-tracker → Deployments 看到所有部署紀錄。

---

## 🛡️ 進階：加 Cloudflare Access 鎖網頁（網頁也需要登入）

部署完成後想讓網頁本身也需要登入才能看：

### 設定 Zero Trust

1. Cloudflare dashboard 左下角 → **Zero Trust**
2. 第一次會要您設一個「team domain」(像 `tingwei`) → Free plan
3. 選免費方案 (Free, ≤50 users)
4. 完成設定

### 加 Application

1. Zero Trust dashboard → **Access** → **Applications**
2. 點 **Add an application** → **Self-hosted**
3. 填寫：
   - Application name: `Gooaye Tracker`
   - Session Duration: `24 hours`
   - Application domain: `gooaye-tracker.pages.dev`
4. 下一步 → **Identity providers**：
   - 預設有 **One-time PIN**（用 email 收驗證碼，最簡單）
   - 也可加 Google OAuth
5. 下一步 → **Add policy**：
   - Policy name: `Only me`
   - Action: **Allow**
   - Configure rules → Include → **Emails** → `eltonwang1@gmail.com`
6. 下一步 → 預設值即可
7. **Save application**

完成後任何人開 `https://gooaye-tracker.pages.dev` 都會被擋下，要求輸入 email。輸入您的 email 後會收到 6 位數 PIN，輸入後即可進入。

**有效期 24 小時**，下次重開瀏覽器才需重新驗證。

---

## ❓ 常見問題

**Q1：Build failed 怎麼辦？**
A: 99% 是因為填了 Build command。回 setup → Settings → Build & deployments → 把 Build command 清空 → Retry deployment。

**Q2：網頁開出來空白？**
A: 檢查根目錄有沒有 `index.html`（您的 repo 有 ✅）。如果沒有，Cloudflare 不知道要顯示什麼。

**Q3：RSS 載入失敗？**
A: 跟部署無關，是 CORS proxy 暫時不穩。app 內建 4 個 proxy fallback，刷新幾次就好。

**Q4：想要自己的網域（像 `gooaye.tingwei.com`）？**
A: Cloudflare Pages 設定頁 → Custom domains → 加自訂網域（要您擁有該 domain）。

**Q5：Cloudflare 要錢嗎？**
A: Pages 完全免費（每月 500 次部署、無流量限制）。Access 也免費（≤50 users）。

---

製作：Claude · Cowork mode · 2026/05/09
