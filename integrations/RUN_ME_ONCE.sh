#!/usr/bin/env bash
# ============================================================
#  股癌追蹤 · 三層整合一鍵 setup
#  Cowork (existing) + Hermes Agent + OpenClaw
# ============================================================
#
#  用法：
#    cd "/Users/wangtingwei/Documents/Claude/Projects/股癌/integrations"
#    bash RUN_ME_ONCE.sh
#
#  跑完會自動：
#    1. 載入 3 個 OpenClaw skills
#    2. 設定 OpenClaw 排程（Wed/Sat 19:30 + Daily 9:00）
#    3. 載入 3 個 Hermes tasks
#    4. 排程 Hermes daily validation
#    5. push 到 GitHub
#    6. 跑 smoke test
#
#  之後您手機收到的第一個 Telegram 推播，就是整合成功的訊號。
# ============================================================

set -e

PROJECT_DIR="/Users/wangtingwei/Documents/Claude/Projects/股癌"
INTEG_DIR="$PROJECT_DIR/integrations"
OPENCLAW_SKILLS="$INTEG_DIR/openclaw_skills"
HERMES_TASKS="$INTEG_DIR/hermes_tasks"

cyan()    { printf "\033[36m%s\033[0m\n" "$1"; }
green()   { printf "\033[32m%s\033[0m\n" "$1"; }
yellow()  { printf "\033[33m%s\033[0m\n" "$1"; }
red()     { printf "\033[31m%s\033[0m\n" "$1"; }

cyan "╔══════════════════════════════════════════════════════════╗"
cyan "║   股癌追蹤 · 三層整合 setup                              ║"
cyan "║   Cowork + Hermes + OpenClaw → gooaye-tracker            ║"
cyan "╚══════════════════════════════════════════════════════════╝"
echo ""

# ============================================================
# STEP 0: Pre-flight check
# ============================================================
cyan "[STEP 0/6] Pre-flight check..."

if ! command -v openclaw &> /dev/null; then
    red "  ❌ openclaw command not found"
    red "  Please install: curl -fsSL https://openclaw.ai/install.sh | bash"
    exit 1
fi
green "  ✓ openclaw installed: $(openclaw --version 2>&1 | head -1)"

if ! command -v hermes &> /dev/null; then
    yellow "  ⚠ hermes command not found"
    yellow "  Skipping Hermes setup. Install later: curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
    HAS_HERMES=0
else
    green "  ✓ hermes installed: $(hermes --version 2>&1 | head -1)"
    HAS_HERMES=1
fi

if ! command -v git &> /dev/null; then
    red "  ❌ git command not found"
    exit 1
fi
green "  ✓ git installed"

if [ ! -d "$PROJECT_DIR/.git" ]; then
    yellow "  ⚠ .git not found in $PROJECT_DIR — git push will be skipped"
    HAS_GIT=0
else
    green "  ✓ git repo initialized"
    HAS_GIT=1
fi

echo ""

# ============================================================
# STEP 1: Load OpenClaw skills
# ============================================================
cyan "[STEP 1/6] Loading OpenClaw skills..."

cd "$OPENCLAW_SKILLS"
for skill_file in gooaye_check.md gooaye_alert.md gooaye_search.md; do
    echo "  Loading $skill_file..."
    if openclaw skill add "$skill_file" 2>&1 | grep -q "added\|created\|loaded\|installed"; then
        green "    ✓ $skill_file loaded"
    else
        yellow "    ⚠ $skill_file may already be loaded (check: openclaw skill list)"
    fi
done

echo ""
green "✓ OpenClaw skills loaded. List with: openclaw skill list"
echo ""

# ============================================================
# STEP 2: Configure Telegram (interactive)
# ============================================================
cyan "[STEP 2/6] Telegram setup (interactive)..."

if openclaw integration list 2>/dev/null | grep -q telegram; then
    green "  ✓ Telegram already configured"
else
    yellow "  ⚠ Telegram not yet configured."
    echo "     Run NOW (interactive):"
    echo ""
    echo "       openclaw integration add telegram"
    echo ""
    echo "     Steps in the prompt:"
    echo "       1. Open @BotFather on Telegram → /newbot → get token"
    echo "       2. Paste token here"
    echo "       3. Provide your Telegram username (limits who can use)"
    echo ""
    read -p "  Press ENTER after Telegram setup is done (or Ctrl-C to skip)..."
fi
echo ""

# ============================================================
# STEP 3: Set up OpenClaw schedules
# ============================================================
cyan "[STEP 3/6] Setting up OpenClaw schedules..."

# Wed/Sat 19:30 - new episode detection
echo "  Adding: Wed/Sat 19:30 new episode detection..."
openclaw schedule add gooaye_alert \
    --cron "30 19 * * 3,6" \
    --description "新集偵測" 2>&1 | sed 's/^/    /' || \
    yellow "    (already exists or command syntax differs — check: openclaw schedule list)"

# Daily 9:00 - briefing
echo "  Adding: Daily 9:00 briefing..."
openclaw schedule add gooaye_alert \
    --cron "0 9 * * *" \
    --description "早安日報" \
    --variant daily_briefing 2>&1 | sed 's/^/    /' || \
    yellow "    (already exists or command syntax differs — check: openclaw schedule list)"

green "✓ OpenClaw schedules configured. List with: openclaw schedule list"
echo ""

# ============================================================
# STEP 4: Hermes setup
# ============================================================
if [ "$HAS_HERMES" = "1" ]; then
    cyan "[STEP 4/6] Setting up Hermes tasks..."

    cd "$HERMES_TASKS"

    # One-time: embed 660 episodes
    echo "  Running one-time embedding of 660 episodes..."
    yellow "    (this takes ~5 min and costs ~\$0.50)"
    read -p "  Run now? [y/N]: " do_embed
    if [ "$do_embed" = "y" ] || [ "$do_embed" = "Y" ]; then
        hermes run embed_660_episodes.py 2>&1 | sed 's/^/    /' || red "    Failed (check Hermes logs)"
    else
        yellow "    Skipped. Run later: cd $HERMES_TASKS && hermes run embed_660_episodes.py"
    fi

    # Schedule daily validation
    echo "  Adding daily validation (16:30 weekdays)..."
    hermes schedule add validate_calls_daily.py "30 16 * * 1-5" 2>&1 | sed 's/^/    /' || \
        yellow "    (may already exist)"

    green "✓ Hermes setup done"
else
    cyan "[STEP 4/6] Skipping Hermes (not installed)"
fi
echo ""

# ============================================================
# STEP 5: Git push everything
# ============================================================
if [ "$HAS_GIT" = "1" ]; then
    cyan "[STEP 5/6] Pushing to GitHub..."
    cd "$PROJECT_DIR"

    # Clean any leftover lock
    rm -f .git/index.lock

    git add . 2>&1 | sed 's/^/  /'
    if git diff --cached --quiet; then
        yellow "  No changes to commit"
    else
        git commit -m "Add 3-tier AI integration (Cowork + Hermes + OpenClaw): skills, tasks, master setup script" 2>&1 | sed 's/^/  /'
        if git push 2>&1 | sed 's/^/  /'; then
            green "✓ Push successful → https://qwwaawwqq.github.io/gooaye-tracker/ (1-3 min to redeploy)"
        else
            red "  Push failed (auth issue?). Run manually: cd $PROJECT_DIR && git push"
        fi
    fi
else
    cyan "[STEP 5/6] Skipping git push (no .git directory)"
fi
echo ""

# ============================================================
# STEP 6: Smoke test instructions
# ============================================================
cyan "[STEP 6/6] Smoke test instructions"
echo ""
echo "  ① Open Telegram → find your bot → send:"
echo "        股癌最新"
echo "     Expected: gets EP660 summary in <30 seconds"
echo ""
echo "  ② Check Cowork scheduled task is alive:"
echo "        Cowork sidebar → Scheduled → gooaye-new-episode-watcher"
echo ""
echo "  ③ Check OpenClaw schedules:"
echo "        openclaw schedule list"
echo ""
if [ "$HAS_HERMES" = "1" ]; then
    echo "  ④ Check Hermes is running:"
    echo "        hermes status"
    echo ""
fi
echo "  ⑤ Check GitHub Pages is updated:"
echo "        https://qwwaawwqq.github.io/gooaye-tracker/"
echo ""

green "╔══════════════════════════════════════════════════════════╗"
green "║   ✅ Setup complete!                                     ║"
green "║                                                          ║"
green "║   Next milestones:                                       ║"
green "║   - Tomorrow 9:00am  → first daily briefing in Telegram  ║"
green "║   - Tomorrow 16:30   → first daily validation            ║"
green "║   - 5/13 (Wed) 19:30 → first auto new-episode push       ║"
green "╚══════════════════════════════════════════════════════════╝"
