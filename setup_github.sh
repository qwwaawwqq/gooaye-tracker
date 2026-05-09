#!/bin/bash
# GitHub Pages setup for Gooaye Tracker
# 用法：先在 GitHub 建好 PRIVATE repo (例：gooaye-tracker)，再在 Terminal cd 到此資料夾跑：
#   bash setup_github.sh YOUR_GITHUB_USERNAME gooaye-tracker

set -e

USERNAME="${1:-}"
REPO="${2:-gooaye-tracker}"

if [ -z "$USERNAME" ]; then
  echo "❌ 用法: bash setup_github.sh YOUR_GITHUB_USERNAME [repo_name]"
  echo "   範例: bash setup_github.sh tingweiwang gooaye-tracker"
  exit 1
fi

echo "📦 部署 Gooaye Tracker 到 GitHub Pages"
echo "   GitHub user : $USERNAME"
echo "   Repo name   : $REPO (請確認已在 https://github.com/new 建好 PRIVATE repo)"
echo ""

# 1. 清掉沙盒留下的損壞 .git
if [ -d ".git" ]; then
  echo "🧹 清除舊的 .git ..."
  rm -rf .git
fi

# 2. Init
echo "📂 初始化 git repo ..."
git init -b main
git config user.email "eltonwang1@gmail.com"
git config user.name "Ting Wei Wang"

# 3. Stage + commit
echo "📝 加入檔案..."
git add .
echo "💾 第一次 commit ..."
git commit -m "Gooaye tracker initial · EP651-EP660 + validation backtest"

# 4. Add remote
echo "🔗 連結到 GitHub remote ..."
git remote add origin "https://github.com/$USERNAME/$REPO.git"

# 5. Push
echo "🚀 推送到 GitHub (可能會要求登入) ..."
git push -u origin main

echo ""
echo "✅ 推送完成！"
echo ""
echo "👉 接下來去 GitHub 啟用 Pages："
echo "   1. 開 https://github.com/$USERNAME/$REPO/settings/pages"
echo "   2. Source: Deploy from a branch"
echo "   3. Branch: main / (root) → Save"
echo "   4. 等 1-2 分鐘"
echo ""
echo "🌐 你的網址會是："
echo "   https://$USERNAME.github.io/$REPO/"
echo ""
echo "📌 之後要更新內容，只要 cd 到此資料夾跑："
echo "   git add . && git commit -m '更新' && git push"
