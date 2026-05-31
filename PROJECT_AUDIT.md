# 股癌 Tracker — Systematic Project Audit & Improvement Roadmap

_Generated 2026-05-31 by a 14-agent audit workflow: 6 parallel expert inspections (software-eng, frontend/UX, call-tracking credibility, data-pipeline reliability, product/growth, security), each adversarially fact-checked by an independent verifier. **57 confirmed findings** (2 dropped as wrong/duplicate), every one grounded in a real `file:line` citation. The workflow's auto-synthesis step hit an API error, so this roadmap was rebuilt from the recovered, verified findings (`/tmp/audit_real.json`). Note: the audit corrected several stale facts in CLAUDE.md/the brief — **index.html is 2,232 lines (not 16,753)**, auto_update.py is 811 lines, and the merge rule is at **index.html:1411** (not :1394)._

---

## Executive summary

For a solo, non-full-time maintainer this project is in **good engineering health** — the episode pipeline has genuine resilience (backoff retries, rebase-before-push, max_tokens truncation retry, contiguous-success state advancement, graceful frontend degradation). But the audit surfaced one theme that outranks everything else:

- **Biggest problem — the credibility layer contradicts itself.** There are **three disconnected, inconsistent representations of 股癌's calls** (`cred-1`), the displayed track record is a **hand-curated stock list with pre-baked `v:'hit'` verdicts that were typed, not computed** (`cred-2`), and the **hero headline says 命中率 73% while the page's own live data says 33.3%** (`cred-3`). On an accountability site, that's existential — the headline number is ~2.2× what the table below it computes.
- **Biggest risk — silent failure + a security gap in rendering.** A failed run still tells nobody (`se-obs-1`), and the frontend builds `innerHTML` from raw pipeline/LLM/**RSS** strings with **no escaping helper anywhere** (`fe-xss-noescape-1`) — a real third-party injection path.
- **Biggest opportunity — the data you already own is invisible.** No Open Graph/share cards (`ps-share-1`/`fe-seo-og-1`), no per-episode/per-stock SEO (`ps-discover-1`), and a **660-episode graded history** sitting unused (`ps-perstock-1`). The moat exists; it's just buried.

The good news: the highest-impact fixes are mostly **S/M effort**. Spend an afternoon on honesty + safety quick wins, then make "one true, honest scorecard" your single focus this month.

---

## Quick wins — high impact, S/M effort (do first)

| ID | Dim | Fix | Eff |
|---|---|---|---|
| **cred-3** | CRED | Drive hero KPI cards (命中率, 命中/失準, total, 截至 date) from `_market_auto.json` — or delete the hardcoded 73%/17-2/23. **The single most credibility-damaging element.** | S |
| **ps-stale-1** | PROD | Same root cause: `updateHeaderDates()` (index.html:1501) rewrites dates but **not** the KPI numbers → they freeze while calls keep accruing. | S |
| **fe-seo-og-1 / ps-share-1** | FE/PROD | Add OG + Twitter Card + canonical to `<head>` (currently zero); generate per-call preview images ("股癌 EP664 喊 X — 至今 +12% ✅"). Highest virality-to-effort ratio in the project. | S/M |
| **fe-xss-noescape-1** | FE | Add one `escapeHtml()` and apply to all interpolated name/code/title/**RSS-title** fields (deep/summary stay HTML). Closes an injection vector. | M |
| **se-err-main-1** | ENG | `main()` + `load_state`/`load_existing_auto` have no try/except → one corrupt `_state.json` aborts every run. Guard loaders, write JSON atomically (`temp + os.replace`), wrap the per-episode loop. | M |
| **se-noci-tests-1** | ENG | `test_advance.py` is git-tracked but **run by no CI**. Convert to pytest; add a CI job that runs it + schema-validates the two JSON outputs. | M |
| **ps-legal-1** | PROD | Persistent 非投資建議 banner on every view + attribution/link-back + correction/takedown contact; reconcile README's "私人追蹤站" wording with public hosting. | S |
| **cred-9** | CRED | LLM buy/sell action cards (加碼/減碼) render with no adjacent disclaimer (the page one is ~700 lines away). Put a caveat inside each card. | S |
| **se-reqs-whisper-1** | ENG | `requirements.txt` still names abandoned `openai-whisper` and omits `faster-whisper`/`pandas`. Split into market vs whisper manifests, pinned. | S |
| **se-env-brittle-1** | ENG | Add a `faster_whisper` import preflight **before** the multi-MB download so a broken venv fails fast with a clear message. | S |

---

## Strategic bets — high impact, larger effort (this month / next)

| ID | Dim | Fix | Eff |
|---|---|---|---|
| **cred-1** | CRED | **Unify on one authoritative call store.** Pick the transcript-extracted `_episodes_auto.json` calls (+ ticker), grade THAT, render it everywhere. Delete the hand-curated `STOCKS` dict and the third hardcoded WATCHLIST. | L |
| **cred-7** | CRED | Extend the auto call schema with resolved ticker + episode date + spoken target + transcript quote, so thematic calls become **gradable** instead of permanently "pending." | M |
| **cred-2** | CRED | Never hand-author `v:'hit'`; derive every verdict from computed data or visibly tag manual vs computed. | M |
| **cred-4 / cred-5** | CRED | Make `miss` reachable (today 0 misses — a −8% call scores "partial") and make grading **time-aware** (a +6%/16d and a +143%/46d both score plain "hit"; benchmark vs TAIEX over the same window). | M |
| **ps-data-1 / ps-discover-1** | PROD | Promote a live "Track Record" hero (overall + rolling 30/90-day accuracy) and emit static `/ep/<N>.html` + `/stock/<ticker>.html` pages → hundreds of indexable long-tail pages from data you already have. | M |
| **ps-perstock-1** | PROD | Per-stock pages aggregating every mention + outcome across all 660 episodes (the unused `股癌_全集歷史_660集.json`). The defensible moat + high-intent search. | M |
| **se-market-coupling-1** | ENG | `update_market.py` regex-scrapes `const STOCKS` out of index.html (SystemExit if reformatted). Move the stock universe to a versioned `_stocks.json` read by both. | M |
| **fe-perf-inline-data-1 / se-monolith-1** | FE/ENG | Move inline EPISODES/CALLS/STOCKS seed into versioned JSON via the merge path that already exists → leaner shell, cacheable data, smaller automated-push diffs. | L |

---

## By dimension

### ENG — Software engineering & pipeline architecture
**Keep:** `urlopen_retry` backoff · `push_if_ahead` rebase · max_tokens-truncation retry · `compute_next_last_seen` (unit-tested) · cache-hit on audio/transcript · `.gitignore` correct, `.env` 0600.
- `[high/M]` **se-err-main-1** unguarded loaders + no per-episode try/except (one corrupt `_state.json` aborts the whole run) · **se-noci-tests-1** the tracked `test_advance.py` is run by no CI.
- `[medium]` se-reqs-whisper-1 wrong deps · se-env-brittle-1 no whisper preflight · se-obs-1 weak observability/no failure alert · se-market-coupling-1 HTML regex-scrape.
- `[low]` se-monolith-1 content/code entangled in index.html · se-doc-drift-1 stale CLAUDE.md line numbers.
- _Two inspector findings were DROPPED by the verifier as fabricated:_ `se-dup-pipeline-1` (a second `integrations/watch_and_notify.py` RSS pipeline) and `se-dup-key-1` (a duplicate `"notified"` key in `_watchlist_state.json`) — neither file/key exists on disk. The verifier flagged this "phantom-evidence" pattern across the audit; treat any uncited integrations/ claim with suspicion.
- _Missed (verifier):_ no dependency vuln scanning (Dependabot/pip-audit); no shared LLM cost cap + prompt-injection risk from transcript text; **no check that GitHub Pages actually deployed** after a push; `__pycache__/` present in repo root.

### CRED — Investment-call tracking & credibility
**Keep:** unusually honest disclaimers (index.html:998, :1187-1192 names whisper false-positives + survivorship bias) · point-in-time entry pricing · direction-aware `verdict_from` · data-driven validation table with staleness indicator.
- `[critical]` **cred-1** three disconnected call datasets · **cred-2** hand-authored `v:'hit'` verdicts.
- `[high]` **cred-3** hero 73% vs live 33.3% · **cred-4** `miss` near-unreachable (0 misses) · **cred-5** time-blind verdicts · **cred-7** thematic calls have no ticker → stuck pending forever.
- `[medium]` cred-6 brittle free-text stance matched against two different keyword lists · cred-8 stale/contradictory watchlist artifacts · cred-9 AI action cards lack adjacent disclaimer.
- `[low]` cred-10 hand-typed perf strings ('+6.6%') can mask stale numbers.
- _Missed (5):_ incl. no benchmark vs index (is the hit-rate beating buy-and-hold?), and no audit trail when a call is retracted/edited.

### FE — Frontend design, UX, performance & accessibility
**Keep:** coherent dark fintech system · real `<button>` tabs bound in `bindTabs` · zero-build single-file deploy fits GH Pages · every fetch try/catch + `res.ok` guarded · prominent risk disclaimer.
- `[high]` **fe-seo-og-1** no OG/Twitter/canonical · **fe-xss-noescape-1** no HTML escaping on `innerHTML` (RSS = injection path) · fe-a11y-tabs-aria-1 zero `role=`/`aria-` in the whole file.
- `[medium]` fe-perf-inline-data-1 slow-changing data hard-inlined · fe-resp-breakpoint-1 sparse responsive breakpoints (verifier: there are **two** @media queries, not one — finding stands but smaller) · fe-dataviz-1 limited trend viz (verifier: a `.sparkbar` bar-chart primitive **does** exist — extend it rather than add from scratch).
- `[low]` fe-a11y-motion-1 infinite pulse, no `prefers-reduced-motion` · fe-a11y-color-1 red/green-only gain/loss · fe-perf-fonts-1 3 render-blocking font families · fe-ux-loading-1 no skeletons → layout shift.
- _Missed (4):_ incl. no favicon/PWA manifest, full-DOM rebuild each load, hardcoded colors vs CSS vars.

### PIPE — Data pipeline reliability, observability & correctness
**Keep:** `push_if_ahead` rebases before push & retries previously-failed pushes (auto_update.py:69-105) · `compute_next_last_seen` contiguous-success advancement (:690-705) · `urlopen_retry` backoff on RSS+audio (:136-152) · Claude truncation detect+retry (:356-385) · LLM output re-validated before persist.
- `[high/M]` **dp-obs-1** No failure alerting anywhere — every failure is a silent `print()` to a local log (git/whisper/Claude failures at auto_update.py:79,97,102,292,366; update_market.py:284). **FIX:** one `notify()` helper on terminal-failure paths (macOS osascript + committed `_pipeline_health.json` with status/last_error/last_success). This is the EP666 failure mode.
- `[high/S]` **dp-obs-2** `main()` returns 0 even on a degraded run (only placeholders/audio-only produced) — the "stuck" list is printed but never affects exit code (auto_update.py:785-807), so launchd can't tell clean from broken. **FIX:** return distinct non-zero (e.g. 2) when any candidate ep isn't `audio+llm`; notify on it.
- `[high/M]` **dp-rel-1** Missed LaunchAgent runs (laptop asleep/offline) are never detected or caught up — `last_check` is written (:675) but never read for staleness. **FIX:** have the reliable cloud Action read `_state.json` + RSS max-EP and fail/annotate if episodes are >N days behind.
- `[medium/M]` **dp-corr-1** No schema validation between writers and the frontend reader; the `schema:1` marker (load_existing_auto:682) is never checked or bumped; `_market_auto.json` has no version. **FIX:** `validate_entry()`/`validate_market()` before write; bump+check schema; frontend `console.warn` on mismatch.
- `[medium/S]` **dp-corr-2** Non-atomic JSON writes (`Path.write_text` at auto_update.py:676,687; update_market.py:340) can truncate on a mid-write crash; unguarded `json.loads` then crash-loops the next run. **FIX:** temp-file + `os.replace()` for all three writers; guard the loaders.
- `[medium/S]` **dp-corr-4** Market staleness badge measures cron liveness, not trading-data freshness — a weekend Action runs fine so `updated_at` is fresh while prices are Friday's close (index.html:1596-1600). **FIX:** surface `end_date` (already computed, update_market.py:119), badge off trading-day age, label "prices as of <date>".
- `[medium/M]` **dp-corr-3** `<OVERSTATED>` Stance grading uses hardcoded substring lists that **differ** between `verdict_from` and `rank_top_and_misses` (update_market.py); auto-added stances silently misclassify. Verifier: confirmed and *worse* than stated (vocab diverges 12 vs 8 entries), one cited line off. **FIX:** one shared stance→direction map; log unmatched stances.
- `[medium/S]` **dp-rel-2** Inconsistent version-control policy for state files — `_watchlist_state.json` untracked while `_state.json` is committed; untracked state is lost on clean checkout. **FIX:** decide commit-vs-ignore per file; document `git checkout <sha> -- _episodes_auto.json` recovery.
- `[low/S]` **dp-rel-3** `<OVERSTATED>` `update_market.py git_commit_push` does a bare push, no rebase (:282). Verifier: real, but `update-market.yml`'s own step already runs `git pull --rebase`, so the live risk is small. **FIX:** mirror `push_if_ahead` in the script anyway.
- `[low/S]` **dp-rel-4** Audio cache pruned to 8 keeps both `.mp3` and `.txt`, forcing expensive re-transcription during catch-up (auto_update.py:661-671). **FIX:** `prune_mp3(keep=8)` + `prune_txt(keep=100)` — transcripts are tiny and costly to regenerate.
- `[low/S]` **dp-corr-5** RSS parser silently drops any item whose title isn't `EP<num>` (auto_update.py:161-163,735) — a publisher title-format change would silently stop ingestion. **FIX:** warn when an item has audio but no parseable EP; fold into the degraded-run signal.
- _Missed (verifier):_ `watchlist_grader.py` is **never invoked by any automation** (so `_watchlist_state.json` is orphaned); the committed `index.html` is ~1,470 lines (frontend citations assumed a larger file); frontend fetch failures are fully silent (no `console.error`); `download_audio` returns a cached mp3 on `exists() && size>0` with no integrity check (truncated-download trap); `transcribe()` hardcodes `--model small`, ignoring overrides.

### PROD — Product strategy, differentiation & growth
**Keep:** the graded HIT/PARTIAL/MISS scorecard is a genuine moat a passive listener can't reproduce · feature-complete 8-pane UI · RSS auto-detect + browser-notification plumbing already shipped · strong editorial-integrity discipline.
- `[high]` ps-share-1 no share cards · ps-discover-1 SPA forfeits SEO · ps-stale-1 frozen headline KPI · ps-data-1 track record buried not the hero · ps-legal-1 thin compliance framing · ps-perstock-1 no per-stock history.
- `[medium]` ps-retain-1 retention is browser-only — **no alert when a PENDING call RESOLVES** (the strongest re-engagement event) · ps-search-1 per-tab substring search, no global full-text over the 660-ep archive · ps-positioning-1 repo identity fragmented across orphan HTML/MD variants.
- `[low]` ps-monetize-1 no sustainability angle despite a scarce longitudinal dataset.
- _Missed:_ the 660-episode dataset is committed but unused by the live site; no analytics to know what users do.

### SEC — Security & secrets hygiene
**Keep:** **no real secret committed anywhere** (full-history `-S 'sk-ant-api'` + `git grep` clean) · `.env` gitignored **and** mode 0600 · key consumed only server-side (`os.environ.get`, auto_update.py:406,584) · CI injects via encrypted `secrets.ANTHROPIC_API_KEY` · degrades safely when key absent.
- `[medium/M]` **sec-2** Python deps are unpinned floating lower bounds (`anthropic>=0.40`, `openai-whisper>=20231117`, `yfinance>=0.2.40`); both Actions `pip install` fresh each run into a job holding the API key. **FIX:** pin exact versions + `requirements.lock` via `pip-compile --generate-hashes`, install `--require-hashes`; enable Dependabot (pip).
- `[medium/M]` **sec-6** No automated secret-scanning / push-protection anywhere, while the pipeline auto-commits machine-generated JSON unattended (auto_update.py:69-105). **FIX:** add gitleaks/trufflehog step to both workflows (fail before push); enable GitHub Secret Scanning + Push Protection; optional local pre-commit hook.
- `[medium/S]` **sec-3** GitHub Actions pinned only to mutable major tags (`actions/checkout@v4`, `setup-python@v5`, `cache@v4`) in a job with the API key + `contents:write`. **FIX:** pin to full commit SHAs (version in trailing comment); Dependabot github-actions ecosystem.
- `[medium/S]` **sec-4** Episode workflow interpolates untrusted `${{ github.event.inputs.* }}` directly into a `run:` block whose env exposes the key (update-episodes.yml:65-73) — a documented shell-injection sink. **FIX:** pass inputs via `env:` and reference quoted `"$MODEL"`/`"$FORCE_EP"`. (Risk limited to actors who can dispatch.)
- `[low/S]` **sec-5** `.env.example` placeholder uses the real provider prefix `sk-ant-...`, weakening scanner signal. **FIX:** use an unmistakable non-key placeholder (`REPLACE_ME`).
- `[low/S]` **sec-1** `<OVERSTATED>` `load_dotenv` does no validation / no `.env` mode check (auto_update.py:48-61). Verifier: code accurate, but the stated exposure risk doesn't hold — `.env` is already 0600 on this machine. **FIX:** still worth a one-line mode-warning.
- `[low/S]` **sec-7** `<OVERSTATED>` SSH push relies on an undocumented local key; CI uses default `GITHUB_TOKEN`. Verifier: unverifiable from repo contents (key lives in `~/.ssh`). **FIX:** document the identity; prefer a per-repo deploy key.
- `[low/S]` **sec-8** `<OVERSTATED>` LaunchAgent log may contain API error strings. Verifier: accurate but already gitignored (`*.log`) and truncated to 200 chars. **FIX:** log rotation/size cap; keep mode 600.
- _Missed (verifier):_ an inspector "strength" about integration helper scripts was itself inaccurate; `RUN_ME_ONCE.sh`/`FINAL_SETUP.sh` and root `setup_github.sh`/`install_cron.sh` were **not scanned** for hardcoded secrets / curl-pipe-to-bash; `actions/cache` is readable by any workflow run on any branch; **`load_dotenv` can set ANY env var from `.env`** (e.g. `PATH`, `WHISPER_PYTHON`) — combined with the venv launcher that's a local-tamper vector worth constraining to known keys.

---

## Sequenced plan

**Phase 1 — this week (honesty + safety, ~1 afternoon):**
`cred-3`+`ps-stale-1` (kill the false 73% headline) · `fe-seo-og-1`+`ps-share-1` (share cards) · `fe-xss-noescape-1` (escaping) · `se-err-main-1` (guarded/atomic state) · `ps-legal-1`+`cred-9` (disclaimers) · `se-reqs-whisper-1`+`se-env-brittle-1` (deps/preflight) · commit+CI `test_advance.py` (`se-noci-tests-1`).

**Phase 2 — this month (one true, honest scorecard):**
`cred-1` unify call stores → `cred-7` gradable transcript calls → `cred-2`/`cred-4`/`cred-5` honest, time-aware, miss-reachable grading → `ps-data-1` make it the hero. Plus `se-obs-1`/PIPE failure-alert + health surface; `se-market-coupling-1` `_stocks.json`.

**Phase 3 — later (growth from the moat):**
`ps-perstock-1` per-stock pages + `ps-discover-1` static SEO pages + `ps-search-1` full-text over 660 episodes; `ps-retain-1` resolved-call feed/alerts; `fe-perf-inline-data-1`/`se-monolith-1` extract data from index.html; benchmark-vs-TAIEX.

---

## Explicitly out of scope / risky (do NOT do)

- **Don't speculate episode content** from RSS show notes — the CLAUDE.md anti-speculation rule stands (burned us on EP662/663/664). All call/grading work must trace to the real transcript.
- **Don't edit the orphan `股癌_*.html`/`*.md` files** — archive them (helps `ps-positioning-1`), don't modify; they're not linked from index.html.
- **Keep the push gate** — `git push origin main` from Claude Code requires you to type the literal phrase; the scheduled LaunchAgent pushes outside it. Don't engineer around it.
- **Don't revive the GitHub Actions episode pipeline** (`update-episodes.yml`) — it timed out 5/5; episodes are LaunchAgent-only by design.
- **Don't over-engineer** — the full `se-monolith-1` SPA refactor and i18n are real but low-urgency; resist until the scorecard (Phase 2) is done.
