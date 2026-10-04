# 股癌 Tracker — Project Rules for Claude Code

Live site: https://qwwaawwqq.github.io/gooaye-tracker/ — single-page tracker. Only `index.html` is served.

## CRITICAL: Never speculate episode content from RSS show notes

When a new EP appears in the RSS feed, the show notes typically contain only the title + sponsor copy + one tagline. **Do NOT write a `deep` summary from that material.** This pattern has burned us three times (EP662, EP663, EP664) — each time the speculated content contradicted what the actual whisper transcript said, and had to be reverted.

**Correct flow for a newly-detected episode (since 2026-10-04):**
1. The cloud scheduled task "Gooaye watcher (cloud)" (Wed/Sat 18:56 TPE) transcribes the audio itself with `tools/watcher/transcribe.py` → `transcripts/EP<N>.txt`, then curates per `tools/watcher/README.md`: content JSON → `verify_quotes.py` → `render.py` → watchlist edits → dated report → commit + push to `main` (GitHub Pages deploys).
2. Inline entries carry a curated `summary`/`tags`/`stocks` **and a `deep` abstract (深度摘要)**, all built by `render.py` from the content JSON that Claude writes from the whisper transcript in that same session — Claude is the LLM here, on the user's subscription, so no `ANTHROPIC_API_KEY` is needed. Because the entry has `deep`, the runtime merge in `loadAutoEpisodes()` (`if (existing && existing.deep) continue;`) keeps it authoritative over `_episodes_auto.json` — never add entries there (an auto entry replaces any inline entry that lacks `deep`). Tags lead with real topics (the 集數 table's 主軸 column shows the first three); the `📝 whisper 已轉錄…` status tag goes last and `⏳ 待 LLM 深度摘要` is no longer used. (Navigate by the function name, not the line number — it drifts.)
3. If the audio can't be transcribed, add at most a placeholder (`summary` only, tags include `"⏳ 待 whisper 轉錄"`) and report the failure.
4. Legacy (Mac, dead since 2026-08-30): LaunchAgent `com.gooaye.update-episodes` running `auto_update.py` (`/Users/wangtingwei/opt/anaconda3/bin/python auto_update.py --force-ep <N> --model small`).

**Never write `deep` content for an EP whose audio you haven't fed to whisper.** Title-emoji-pattern-matching plus "previous-EP narrative continuation" is exactly how the EP662/663/664 speculation went wrong.

## Other key rules

- **`index.html` inline `EPISODES` is authoritative if it has `deep`.** See merge rule in `loadAutoEpisodes()`; navigate by function name — absolute line numbers drift as the file changes.
- **`_episodes_auto.json` is legacy** (old Mac pipeline, EP661–692). Every inline entry from EP669 on now has `deep` (EP669–687 curated 2026-10-04 from their whisper transcripts in `transcripts/`), so auto entries only show for EP662–668 (their old audio+LLM abstracts). Leave the file alone.
- **Don't edit the orphan `*.html` / `*.md` files** at repo root (e.g. `股癌_Ting_wei_Wang_App.html`, `股癌_新集_*.html`). They are not linked from `index.html`.
- **Pipeline is split**: episodes via the cloud scheduled task (GitHub `main` is the source of truth; the Mac copy at `~/Documents/Claude/Projects/股癌` is only a mirror — `git pull` there before editing). The GH Actions `update-episodes.yml` job is skipped by design — don't try to fix it. Market data via GitHub Actions `update-market.yml` (daily 17:30 TPE; its commit-before-rebase bug that stalled `_market_auto.json` since 2026-05-30 was fixed 2026-10-04).
- **GitHub Pages needs the repo public** (free plan): while it was private (2026-08-23 → 10-04) Pages silently stopped building.
- **Mac clone (legacy)**: remote is SSH (`git@github.com:qwwaawwqq/gooaye-tracker.git`); `git push origin main` from Claude Code on the Mac is blocked by the auto-mode classifier — the user must literally type `push origin main` in chat. LaunchAgent log: `.cache_audio/launchd-episodes.log`.
