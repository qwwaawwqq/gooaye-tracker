#!/usr/bin/env bash
# install_cron.sh — register auto_update.py on local crontab.
# Default schedule (Asia/Taipei): Wed/Sat 20:00 and 22:00 + Thu/Sun 09:00 sweep.
# Run with: bash install_cron.sh           # prints planned change + asks before installing
#           bash install_cron.sh --apply   # write directly

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY=$(command -v python3)
SCRIPT="$PROJECT_DIR/auto_update.py"
LOG="$PROJECT_DIR/.cache_audio/cron.log"
TAG="# gooaye-auto-update"

if [ ! -f "$SCRIPT" ]; then
  echo "[error] missing $SCRIPT" >&2
  exit 1
fi
mkdir -p "$(dirname "$LOG")"

# Crontab lines. Run with --model small for speed; bump to medium for accuracy.
read -r -d '' NEW_LINES <<EOF || true
0 20 * * 3,6 cd "$PROJECT_DIR" && "$PY" auto_update.py --model small --push >> "$LOG" 2>&1  $TAG
0 22 * * 3,6 cd "$PROJECT_DIR" && "$PY" auto_update.py --model small --push >> "$LOG" 2>&1  $TAG
0  9 * * 4,0 cd "$PROJECT_DIR" && "$PY" auto_update.py --model small --push >> "$LOG" 2>&1  $TAG
EOF

CURRENT=$(crontab -l 2>/dev/null || true)
FILTERED=$(printf "%s\n" "$CURRENT" | grep -v "$TAG" || true)
NEW=$(printf "%s\n%s\n" "$FILTERED" "$NEW_LINES")

echo "==== planned crontab ===="
printf "%s\n" "$NEW"
echo "========================="

if [ "${1:-}" = "--apply" ]; then
  printf "%s\n" "$NEW" | crontab -
  echo "[ok] installed. View with: crontab -l | grep gooaye"
  echo "[log] $LOG"
else
  echo
  echo "Not installed. Re-run with --apply to write:"
  echo "  bash $0 --apply"
fi
