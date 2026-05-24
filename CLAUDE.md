# 股癌 Tracker — Project Rules for Claude Code

Live site: https://qwwaawwqq.github.io/gooaye-tracker/ — single-page tracker. Only `index.html` is served.

## CRITICAL: Never speculate episode content from RSS show notes

When a new EP appears in the RSS feed, the show notes typically contain only the title + sponsor copy + one tagline. **Do NOT write a `deep` summary from that material.** This pattern has burned us three times (EP662, EP663, EP664) — each time the speculated content contradicted what the actual whisper transcript said, and had to be reverted.

**Correct flow for a newly-detected episode:**
1. Add a minimal placeholder inline entry: `summary` only, **no `deep` field**, and `tags` should include `"⏳ 待 whisper 轉錄"`.
2. Let the LaunchAgent (`com.gooaye.update-episodes`, runs Wed/Sat 20:00+22:00 TPE / Thu/Sun 09:00 TPE) run `auto_update.py` which does whisper + LLM and writes to `_episodes_auto.json`.
3. The runtime merge at `index.html:1394` (`if (existing && existing.deep) continue;`) means inline-with-`deep` blocks the auto pipeline. Placeholder-without-`deep` lets auto take over.
4. If you need to manually trigger whisper now: `/Users/wangtingwei/opt/anaconda3/bin/python auto_update.py --force-ep <N> --model small` (~25-30 min on Rosetta).

**Never write `deep` content for an EP whose audio you haven't fed to whisper.** Title-emoji-pattern-matching plus "previous-EP narrative continuation" is exactly how the EP662/663/664 speculation went wrong.

## Other key rules

- **`index.html` inline `EPISODES` is authoritative if it has `deep`.** See merge rule at index.html:1394.
- **Don't edit the orphan `*.html` / `*.md` files** at repo root (e.g. `股癌_Ting_wei_Wang_App.html`, `股癌_新集_*.html`). They are not linked from `index.html`.
- **Pipeline is split**: episodes via local LaunchAgent (GH Actions timed out — don't try to fix the workflow). Market data via GitHub Actions `update-market.yml` (daily 17:30 TPE, works reliably).
- **Git remote is SSH** (`git@github.com:qwwaawwqq/gooaye-tracker.git`). HTTPS PAT is broken — `gh api repos/...` returns 404.
- **`git push origin main` from Claude Code is blocked** by the auto-mode classifier even after AskUserQuestion approval. User must literally type `push origin main` in chat to unlock it. (LaunchAgent push works — runs outside Claude Code.)
- **LaunchAgent log**: `.cache_audio/launchd-episodes.log`. Test fire: `launchctl kickstart -p gui/$(id -u)/com.gooaye.update-episodes`.
