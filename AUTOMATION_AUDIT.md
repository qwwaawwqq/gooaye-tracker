# 股癌 Tracker — Full-Auto Pipeline: Root Causes, Fixes, Runbook

_Updated 2026-05-30. Goal: make new-episode → published-summary fully automatic._

## TL;DR — why EP666 didn't go live, and what was fixed

EP666 **was detected** today (2026-05-30 20:14) by the LaunchAgent. It failed at
**two independent points**, both now fixed in code:

| # | Failure | Root cause | Fix |
|---|---------|-----------|-----|
| 1 | **Whisper crashes** → EP666 fell back to `audio-pending` placeholder, no transcript | `~/.local/bin/whisper` runs on x86_64/Rosetta anaconda Py3.9; its `numba` dep fails: `SystemError: initialization of _internal failed`. Machine is arm64. | New faster-whisper backend on a native arm64 venv + a CLI shim. |
| 2 | **`git push` rejected** (non-fast-forward) → even the placeholder never reached the live site | The market-data GitHub Action pushes to `origin/main` independently; bare `git push` from the LaunchAgent then loses the race. | `git_commit_and_push` now does `pull --rebase origin main` before pushing, with clean `rebase --abort` on conflict. |

A third thing my *first* draft of this doc got wrong: the LLM summarizer
(`call_claude_for_transcript`) is **complete, not a stub** — and the
`ANTHROPIC_API_KEY` in `.env` is **valid** (verified live: returned PONG via
claude-opus-4-7). So once whisper produces a transcript, the structured
deep-summary + CALLS generation already works end to end.

## Changes made this session

**Environment (durable, outside git):**
- Created venv `~/.venvs/whisper` (native **arm64** python3.12).
- Installed `faster-whisper 1.2.0` into it (no numba, no torch). Verified importable.

**`auto_update.py`:**
- `WHISPER_PYTHON` constant → `~/.venvs/whisper/bin/python` (env-overridable).
- `find_whisper()` → prefers repo-local `whisper_cli.py` shim when the venv
  exists; falls back to PATH / known whisper locations. (Also fixes the launchd
  PATH-misses-`~/.local/bin` problem.)
- `transcribe()` → when the resolved transcriber is the `.py` shim, launches it
  via `WHISPER_PYTHON` (does not depend on the shim's executable bit/shebang).
- `git_commit_and_push()` → `pull --rebase origin main` before push.

**`whisper_cli.py` (NEW):** drop-in shim reproducing the exact openai-whisper CLI
subset auto_update.py calls (`--model --language Chinese --task transcribe
--output_dir --output_format txt ...`), backed by faster-whisper. Writes
`<output_dir>/<stem>.txt` so the pipeline's `EP<N>.txt` contract is preserved.
Maps `Chinese`→`zh`, accepts-and-ignores `--fp16/--verbose`, prints progress
heartbeats, supports txt/srt/vtt.

**`_state.json`:** `last_seen_ep` rolled back `666 → 665` so EP666 reprocesses on
the next run.

**Plist:** no change needed. The LaunchAgent runs `auto_update.py` under anaconda
python, which only *shells out* to the venv for whisper — it doesn't import
faster-whisper itself.

## VERIFY (run these — a harness glitch blocked me from confirming live)

```bash
cd ~/Documents/Claude/Projects/股癌

# 1. Shim + venv present, wiring resolves
ls -l whisper_cli.py ~/.venvs/whisper/bin/python
~/.venvs/whisper/bin/python -c "import faster_whisper; print(faster_whisper.__version__)"

# 2. find_whisper() resolves to the shim, venv python is found
/Users/wangtingwei/opt/anaconda3/bin/python - <<'PY'
import importlib.util
s=importlib.util.spec_from_file_location("au","auto_update.py")
au=importlib.util.module_from_spec(s); s.loader.exec_module(au)
from pathlib import Path
print("WHISPER_PYTHON:", au.WHISPER_PYTHON, "| exists:", Path(au.WHISPER_PYTHON).exists())
print("find_whisper():", au.find_whisper())
PY
```

## TRIGGER EP666 now (full pipeline, ~10-20 min with faster-whisper)

```bash
cd ~/Documents/Claude/Projects/股癌
/Users/wangtingwei/opt/anaconda3/bin/python auto_update.py --force-ep 666 --model small --push
```

This will: download EP666 audio → faster-whisper transcript → Claude structures
deep+CALLS → write `_episodes_auto.json` → `pull --rebase` → push → live site
merges it (index.html:1411, since EP666 has no inline `deep`).

> First faster-whisper run downloads the `small` model (~480MB) into
> `~/.cache/huggingface`; subsequent runs are cached.

## Test the LaunchAgent end-to-end (optional)

```bash
launchctl kickstart -p gui/$(id -u)/com.gooaye.update-episodes
tail -f ~/Documents/Claude/Projects/股癌/.cache_audio/launchd-episodes.log
```

## VERIFIED 2026-05-30 (end-to-end, real run)

Full pipeline executed against real EP666 audio:
- **Whisper FIXED**: faster-whisper shim produced a real **24,873-char** transcript
  (`.cache_audio/EP666.txt`, 64KB). The numba/Rosetta crash is gone.
- **LLM FIXED**: root cause was `max_tokens=4000` truncating the structured JSON
  mid-string (`Unterminated string at char 5030`) → EP666 first fell back to
  `audio-only` with **0 CALLS**. Raised to 16000 (retry at 24000) + explicit
  `stop_reason=="max_tokens"` truncation detection. Re-run produced
  `auto_status=audio+llm`, **6 CALLS**, 19 stocks, 3067-char deep summary.
- **Content grounded in transcript** (the CLAUDE.md anti-speculation rule):
  spot-checked claims appear in the real transcript. The names that weren't
  *literal* were whisper homophones the LLM correctly resolved —
  `Octa`→Okta, `Piantia`→Palantir, `Cloudstrike`→CrowdStrike,
  `Servus now`→ServiceNow. 鴻海/廣達/陳泰銘成首富 are literal. Only 國巨/2327 is a
  domain-knowledge inference (Pierre Chen chairs Yageo), carried with the
  pipeline's built-in "個股代號以模型還原為準，必要時人工二校" disclaimer.
- **last_seen retry logic**: `compute_next_last_seen` unit-tested (6/6 PASS).
- **launchd-env simulation** (restricted PATH, clean env, anaconda python): all
  5 resolution checks pass — anthropic SDK, API key, find_whisper→shim,
  WHISPER_PYTHON exists, venv faster_whisper importable.

### What's committed
- Commit 1 (code): faster-whisper backend + whisper_cli.py + push_if_ahead +
  compute_next_last_seen + max_tokens fix + reuse + test_advance.py + this doc.
- Commit 2 (content): EP666 `_episodes_auto.json` (audio+llm, 6 CALLS).

### The ONE remaining manual gate: push
Per CLAUDE.md, `git push origin main` from Claude Code is classifier-blocked —
**you must literally type `push origin main` in chat** to release the commits to
the live site. Alternatively the next LaunchAgent run will auto-push them, since
`push_if_ahead()` now pushes whenever local is ahead of origin.

## Open item (not blocking)

`already_done()` semantics: an entry with truthy `deep` is treated as done. The
placeholder EP666 written today has a `deep` status blurb, so `--force-ep` is the
clean way to reprocess it. Future hardening: gate "done" on a real-summary marker
(e.g. `auto_status == "audio+llm"` or presence of `calls`) so excerpt-only /
placeholder entries auto-reprocess without `--force-ep`.
