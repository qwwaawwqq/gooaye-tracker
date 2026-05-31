# Data Extraction Refactor Plan (se-monolith-1 / fe-perf-inline-data-1)

**Status:** Plan only. Do NOT implement without live verification (Codex:verify). The inline merge rule at index.html:1411 must be preserved exactly.

**Risk:** Behavioral refactor. Extracting data without verification is a silent-failure vector — inline hardcoded values intentionally override fetched data in certain cases (e.g., for offline fallback, manual overrides). Extraction that breaks this merge path will silently render stale or wrong data without console errors.

---

## Current State

- **index.html:1411** (`load_existing_auto()`): Defines the merge rule — inline `const EPISODES = {...}`, `const CALLS = {...}`, `const STOCKS = {...}` are read-only fallbacks that can be **overridden** by fetched `_episodes_auto.json`, `_market_auto.json`, but ONLY if fetch succeeds AND the fetched value is non-empty.
  ```javascript
  for (let ep of Object.values(EPISODES)) {
    if (auto[ep.ep]) Object.assign(ep, auto[ep.ep]);
  }
  ```
  This means:
  - Inline is the authoritative baseline (must always exist for offline mode).
  - Fetch result **augments** inline, never replaces wholesale.
  - Empty/corrupt fetch = silently use inline.
  - If fetch has only 5 episodes but inline has 10, the user sees all 10 (merged).

- **index.html line count:** ~2,232 lines (confirmed in audit).
- **Data volume:** EPISODES 6–660, CALLS hundreds, STOCKS ~50 hardcoded.
- **Inline data currently:**
  - EP650–EP660 have full `title`, `date`, `summary`, `deep`, `calls` (backup fallback).
  - CALLS dict indexed by `[ep][i]` for verdict tracking.
  - STOCKS dict indexed by code; some pre-baked `v:'hit'`/`v:'miss'` (hardcoded verdicts — see cred-2).

---

## Extraction Target

### New Files

1. **`_episodes_seed.json`** (baseline fallback, ~200KB)
   - Keys: episode IDs (string, e.g., `"660"`).
   - Contents: `{ "660": { "ep": 660, "title": "...", "date": "...", "summary": "...", "deep": "...", "calls": [...], "v": "pending" }, ... }`
   - **Scope:** EP650–EP660 (the curated fallback set) extracted as-is from current inline.
   - **Commitment:** Once extracted, this becomes read-only in the repo; never edit by hand. Updates flow via `_episodes_auto.json` (cred-1: unify on auto).

2. **`_calls_seed.json`** (baseline fallback, ~50KB)
   - Keys: call IDs (string, e.g., `"649_0"`).
   - Contents: `{ "649_0": { "ep": 649, "t": "...", "c": "...", "v": "pending" }, ... }`
   - **Scope:** All calls from inline CALLS dict.
   - **Commitment:** Read-only baseline; compute verdicts in `_market_auto.json`, not here.

3. **`_stocks_seed.json`** (baseline fallback, ~10KB)
   - Keys: stock codes (string, e.g., `"2330"`).
   - Contents: `{ "2330": { "code": "2330", "name": "...", "mkt": "tw", "v": "hit" }, ... }`
   - **Scope:** All stocks from inline STOCKS dict.
   - **Commitment:** Read-only baseline; verdicts computed in `_market_auto.json`, not here. **This replaces the regex-scrape in update_market.py** (se-market-coupling-1).
   - **Version marker:** Add `"schema": 1` to root (dp-corr-1: schema validation).

---

## Load Order (in index.html, after DOMContentLoaded)

```javascript
// 1. Inline seed as fallback (EXISTING inline code becomes read-only constant)
const EPISODES_SEED = { /* extracted from current inline */ };
const CALLS_SEED = { /* extracted */ };
const STOCKS_SEED = { /* extracted */ };

// 2. Working copy (mutable, merged)
let EPISODES = { ...EPISODES_SEED };
let CALLS = { ...CALLS_SEED };
let STOCKS = { ...STOCKS_SEED };

// 3. Fetch auto (async)
// 3a. Fetch _episodes_auto.json
const auto_episodes = (await fetch('_episodes_auto.json').then(r => r.json())).episodes || {};
for (let [ep_str, ep_data] of Object.entries(auto_episodes)) {
  if (EPISODES[ep_str]) {
    Object.assign(EPISODES[ep_str], ep_data);  // merge into seed
  } else {
    EPISODES[ep_str] = ep_data;  // new episode
  }
}

// 3b. Similar for _market_auto.json.validation → CALLS
// (merge call verdicts by [ep][i] key)

// 3c. _stocks_seed.json (versioned, not inline)
const auto_stocks = (await fetch('_stocks_seed.json').then(r => r.json()));
if (auto_stocks.schema === 1) {
  Object.assign(STOCKS, auto_stocks);  // trust versioned stocks
}
```

**Key invariant:** After load, EPISODES/CALLS/STOCKS contain the **union** of seed + fetched data, with fetched taking precedence (by key).

---

## Extraction Steps

### Phase A: Extract & Commit Seeds (Refactor Part 1)

1. **Scan index.html for inline data boundaries.**
   - Grep `const EPISODES = {` → find closing `};`
   - Grep `const CALLS = {` → find closing `};`
   - Grep `const STOCKS = {` → find closing `};`
   - Extract exact text (preserve formatting, comments).

2. **Create `_episodes_seed.json`.**
   - Parse extracted EPISODES JS object into JSON.
   - Validate: every entry has `ep`, `date`, `summary`, `deep`, `calls`.
   - Commit to git with a message: `"Extract inline EPISODES EP650-EP660 to _episodes_seed.json (se-monolith-1 phase A)"`.

3. **Create `_calls_seed.json`.**
   - Parse extracted CALLS into flat JSON (handle nested `[ep][i]` indexing).
   - Validate: every entry has `ep`, `t`, `c`, `v`.
   - Commit.

4. **Create `_stocks_seed.json` with schema marker.**
   - Parse extracted STOCKS; add `"schema": 1` at root.
   - Validate: every stock has `code`, `mkt`, `name`; no hardcoded `v:'hit'` (move to cred-2: computed verdicts only).
   - Commit.

5. **Sanity check in live index.html:**
   - Keep the inline JS unchanged for now.
   - Verify that the extracted JSON round-trips to equivalent in-memory structures.
   - Test in browser: all three tabs (Episodes, Calls, Stocks) still render identically.

### Phase B: Update Load Path in index.html (Refactor Part 2)

1. **Add load logic (after DOMContentLoaded).**
   ```javascript
   const seedUrls = ['_episodes_seed.json', '_calls_seed.json', '_stocks_seed.json'];
   const seeds = await Promise.all(seedUrls.map(u => 
     fetch(u).then(r => r.ok ? r.json() : null)
   ));
   // Assign to global EPISODES_SEED, CALLS_SEED, STOCKS_SEED
   ```

2. **Merge with existing auto-load.**
   - Integrate into the existing `load_existing_auto()` call (index.html:1411 area).
   - Test: auto + seed merge produces same result as before.

3. **Comment out inline data (NOT delete yet).**
   - Keep inline EPISODES/CALLS/STOCKS in `<script>` but wrapped in `/* Phase A inline — can be deleted after Phase C verification */`.
   - This keeps git history readable and provides a rollback point.

### Phase C: Verification & Cleanup (Refactor Part 3)

1. **Run `verify` skill on three scenarios:**
   - **Scenario 1 (offline):** Disconnect network, load index.html → should render from seed.
   - **Scenario 2 (seed + auto):** Reconnect, fetch _episodes_auto.json → merged result matches current behavior.
   - **Scenario 3 (corrupted auto):** Corrupt _episodes_auto.json, reload → gracefully falls back to seed, no console errors.

2. **Performance measurement:**
   - Time to first paint with/without extraction (should be minimal; seed files are small).
   - Cache behavior: _episodes_seed.json should cache-bust less often than index.html.

3. **Data audit:**
   - Grep index.html for any remaining hardcoded calls/stocks → should be zero (or only comments).
   - Verify `_stocks_seed.json` no longer has pre-baked `v:'hit'` verdicts (cred-2 fix).

4. **Delete inline after sign-off.**
   - Once Phase C passes, remove the commented-out inline JS from index.html.
   - Commit: `"Remove inline EPISODES/CALLS/STOCKS fallback (se-monolith-1 phase C)"`.

---

## Data Structure Reference

### _episodes_seed.json
```json
{
  "660": {
    "ep": 660,
    "date": "2026-05-15",
    "title": "EP660 | 🏗",
    "dur": "45分",
    "v": "pending",
    "tags": [...],
    "summary": "HTML string with <b>bold</b> etc.",
    "deep": "<h4>Main axis 1</h4>...",
    "stocks": [["TW", "2330"], ...],
    "calls": [
      {"ep": 660, "t": "title", "c": "call text", "a": "action", "v": "pending"}
    ]
  }
}
```

### _calls_seed.json
```json
{
  "660_0": {"ep": 660, "t": "...", "c": "...", "a": "...", "v": "pending"},
  "660_1": {"ep": 660, "t": "...", "c": "...", "a": "...", "v": "pending"}
}
```

### _stocks_seed.json
```json
{
  "schema": 1,
  "2330": {"code": "2330", "name": "台積電", "mkt": "tw"},
  "2454": {"code": "2454", "name": "聯發科", "mkt": "tw"},
  "AMD": {"code": "AMD", "name": "Advanced Micro Devices", "mkt": "us"}
}
```

---

## Rollback Strategy

If Phase B/C verification fails:

1. **Revert last three commits** (Phase A–C).
2. **Keep _episodes_seed.json, _calls_seed.json, _stocks_seed.json** in git (they're data, not code; safe to ship).
3. **Re-enable inline JS** from git history.
4. **Re-diagnose:** Check if failure is in merge logic (load_existing_auto) or seed format. Open an issue, iterate.

---

## Related Fixes (Dependencies)

- **cred-2** (computed verdicts): Remove all hardcoded `v:'hit'` from STOCKS before extraction. Move to `_market_auto.json` verdict field.
- **se-market-coupling-1** (stock universe): After _stocks_seed.json exists, update `update_market.py` to read `_stocks_seed.json` instead of regex-scraping index.html.
- **dp-corr-1** (schema validation): Bump `_stocks_seed.json` schema marker each time format changes; frontend validates it.

---

## Success Criteria

- [ ] _episodes_seed.json, _calls_seed.json, _stocks_seed.json committed to git.
- [ ] Offline scenario: seed renders correctly.
- [ ] Online scenario: seed + auto merge produces identical result to pre-refactor.
- [ ] Corrupt auto scenario: graceful fallback, zero console errors.
- [ ] index.html file size reduced by ~20–30% (removal of inline data).
- [ ] No hardcoded verdicts remain in seed files (cred-2 prerequisite).
- [ ] update_market.py updated to read _stocks_seed.json (se-market-coupling-1).
