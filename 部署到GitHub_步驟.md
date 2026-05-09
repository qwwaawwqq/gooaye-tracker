# GitHub Pages 部署步驟（Private Repo）

✅ 已準備好的檔案（在你的 `股癌` 資料夾裡）：
- `index.html` ← GitHub Pages 入口（Chengwaye 風格 app 的副本）
- `README.md` ← repo 首頁說明
- `.gitignore` ← 排除 `_state.json` 不上傳
- `setup_github.sh` ← 一鍵 setup 腳本

---

## 🎯 完整流程（5 分鐘搞定）

### 步驟 1：在 GitHub 開新 PRIVATE repo

1. 開 https://github.com/new
2. **Repository name**: `gooaye-tracker`（或您喜歡的名字）
3. ⭐ 勾選 **Private**
4. **不要勾** Add a README / .gitignore / license（會跟我們的衝突）
5. 點 **Create repository**
6. **記下您的 GitHub 帳號名稱**（待會要用）

### 步驟 2：在 Terminal 跑一行指令

打開 macOS 的 Terminal（Spotlight 搜尋 "Terminal"），複製貼上：

```bash
cd "/Users/wangtingwei/Documents/Claude/Projects/股癌"
bash setup_github.sh YOUR_GITHUB_USERNAME gooaye-tracker
```

⚠️ **把 `YOUR_GITHUB_USERNAME` 換成您的 GitHub 帳號**（例如 `tingweiwang`）

第一次 push 時 macOS 會跳出視窗要求 GitHub 登入：
- 用瀏覽器登入 GitHub 授權，或
- 用 Personal Access Token（如果帳號有開 2FA）

### 步驟 3：啟用 GitHub Pages

1. 開 `https://github.com/YOUR_USERNAME/gooaye-tracker/settings/pages`
2. **Source**: Deploy from a branch
3. **Branch**: `main` / `(root)`
4. 點 **Save**
5. 等 1-2 分鐘，最上方會顯示 ✅ **Your site is live at https://YOUR_USERNAME.github.io/gooaye-tracker/**

---

## 🎉 完成！

您的私人追蹤站網址：
```
https://YOUR_USERNAME.github.io/gooaye-tracker/
```

存成書籤，從**任何電腦／手機**打開都能用。

---

## 🔄 之後怎麼更新？

每次想推新版本（例如新集出爐後更新摘要）：

```bash
cd "/Users/wangtingwei/Documents/Claude/Projects/股癌"
git add .
git commit -m "更新 EPxxx"
git push
```

GitHub Pages 約 1 分鐘內自動重新部署。

---

## ❓ 常見問題

**Q: GitHub Pages 在 private repo 真的免費嗎？**
A: 是的。2021 後 GitHub Free 帳號就支援 private repo + public Pages。

**Q: 網頁本身會被搜尋引擎找到嗎？**
A: 預設可能會被爬。可在 `index.html` 的 `<head>` 加 `<meta name="robots" content="noindex">` 防止被索引。

**Q: 想讓網頁也需要密碼/登入才能看？**
A: GitHub Pages 不支援。需用 Cloudflare Pages + Cloudflare Access（免費），詳見 `部署說明_DEPLOY.md` 方案 B。

**Q: 第一次 git push 卡住要登入？**
A: 三種方法之一：
1. 用 [GitHub Desktop](https://desktop.github.com/) 自動處理登入
2. 用瀏覽器登入跳出的對話框
3. 建 Personal Access Token：https://github.com/settings/tokens → Generate (classic) → 勾 `repo` → 用 token 當密碼

**Q: setup script 跑完顯示權限錯誤？**
A: 先跑 `chmod +x setup_github.sh` 給執行權限，再跑 `bash setup_github.sh ...`
