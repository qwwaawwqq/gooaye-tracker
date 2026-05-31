#!/bin/bash
# gen_all.sh: Run all static generators (gen_static.py + gen_search_index.py)
# Called by pipeline/LaunchAgent to regenerate SEO pages and search index

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[gen_all.sh] Starting static generator pipeline..."

cd "$SCRIPT_DIR"

echo "[1/2] gen_static.py (episode + stock pages)..."
python3 gen_static.py

echo "[2/2] gen_search_index.py (search index)..."
python3 gen_search_index.py

echo ""
echo "[gen_all.sh] ✓ All generators completed."
echo "  Generated: /ep/*.html, /stock/*.html, sitemap.xml, robots.txt, _search_index.json"
echo "  Next step: Add search JS to index.html settings pane + commit changes"
