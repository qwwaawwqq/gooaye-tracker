# 股癌 new-episode watcher — cloud tools

Used by the scheduled task (runs Wed/Sat ~18:56 Asia/Taipei in a cloud session, no Mac needed).
GitHub `main` is the source of truth; the Mac copy is only a mirror (`git pull` there).

1. **Detect** — newest curated EP = highest key of `const EPISODES = {` in `index.html`; new = RSS items above it.
2. **Transcribe** — `setsid nohup python3 tools/watcher/transcribe.py <EP...> > ~/watcher_work/tx.log 2>&1 &`
   then poll the log (~11 min per 50-min episode on 2 cores). Output: `transcripts/EP<N>.txt`.
   Needs `pip install --break-system-packages faster-whisper opencc-python-reimplemented` and ffmpeg.
3. **Curate** — read the whole transcript, write `tools/watcher/content/EP<N>.json` (schema = `content/EP702.json`).
   Quotes 「」 are the host's words only (copy from the transcript, list whisper corrections in `fixes`);
   external quotes use 『』; uncertain names get 〔音譯〕 and go in `unresolved`; zero-stock episodes keep `stocks: []`.
4. **Verify** — `python3 tools/watcher/verify_quotes.py tools/watcher/content/EP<N>.json` (exit 1 if any quote < 0.4),
   and `--text <file> <EPs>` for watchlist/report text you wrote by hand.
5. **Render** — `python3 tools/watcher/render.py tools/watcher/content/EP<N>.json ... --report-cards cards.html`
   (inline EPISODES entries without `deep`, AUTO_UPDATE.md sections + meta, report cards).
6. **Watchlist** — edit `<section class="pane" id="watchlist">` surgically: 🟢/🟡 rows have 6 `<td>`, 🟠/🔴 4, ⚪ 3;
   band move = new row in the target band + badge on the old row; finish with a per-table column count and tag-balance check.
7. **Report** — `股癌_新集_YYYY-MM-DD.html`, copy `<head>` from the newest existing report, insert the cards.
8. **Commit + push** — `git fetch origin main && git rebase origin/main && git push origin HEAD:main`.
   Do not commit `gen_all.sh` timestamp churn (ep/, stock/, feeds); the market workflow regenerates those daily.

Never edit the orphan/archive HTML files listed in CLAUDE.md, and never add entries to `_episodes_auto.json`
(an auto entry overrides the curated inline entry at runtime).
