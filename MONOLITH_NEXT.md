# Monolith Swap (se-monolith-1) — Remaining Manual Steps

**Status**: Extraction verified ✓ | Seed faithful ✓ | **AWAITING RENDER VERIFICATION**

This document describes the exact steps to complete the monolith extraction once a human renders the page and confirms no visual breakage.

---

## Why Not Auto-Applied Yet

The `extract_episodes_seed.js` script produces a **seed JSON** (`_episodes_seed.json`) by faithfully evaluating the inline `const EPISODES = {...}` from `index.html`. This seed is **verified byte-exact** by `scripts/verify_seed_faithful.js`.

However, swapping the runtime source (inline → async fetch) risks:
1. **Render race**: Page loads before seed JSON arrives → blank content
2. **Function call order**: `loadAutoEpisodes()` depends on `updateHeaderDates`, `rebuildHighlightCards`, `refreshEpisodeListFromDict` already being bound
3. **Browser-only verification**: Only a real browser can see if header dates update, episode cards render, highlight animations work

**Solution**: This document is NOT auto-applied. A human must:
1. Take the verified seed output
2. Render the page in a browser with the proposed changes
3. Confirm all UI elements load and function correctly
4. Then commit

---

## The Swap Itself (Manual Steps)

### Step 1: Verify Seed is Faithful

```bash
# This MUST pass before proceeding
node scripts/verify_seed_faithful.js index.html _episodes_seed.json
# Exit 0 = safe to proceed
```

If this fails, **stop and debug the extractor** — do NOT patch index.html.

### Step 2: Update index.html — Replace Inline with Async Loader

**Find** (line ~1369):
```javascript
const EPISODES = {
  665:{date:'2026-05-27',...
  ...
};
```

**Replace with**:
```javascript
// EPISODES is now loaded asynchronously from _episodes_seed.json
// Default to empty object during page render; actual data loads below.
let EPISODES = {};

// Async loader: fetch and merge seed data
(async function loadEpisodesFromSeed(){
  try {
    const res = await fetch('_episodes_seed.json?ts=' + Date.now(), { cache: 'no-store' });
    if (!res.ok) {
      console.warn('[seed-loader] failed to fetch seed:', res.statusText);
      return;
    }
    const seedData = await res.json();
    if (seedData && seedData.episodes && typeof seedData.episodes === 'object') {
      // Copy seed episodes into the live EPISODES dict
      Object.assign(EPISODES, seedData.episodes);
      console.log(`[seed-loader] loaded ${Object.keys(seedData.episodes).length} episodes from seed`);
      // Re-invoke the render pipeline (same as auto-merge does)
      try { updateHeaderDates(); } catch(_) {}
      try { rebuildHighlightCards(); } catch(_) {}
      try { refreshEpisodeListFromDict(); } catch(_) {}
    }
  } catch(e) {
    console.warn('[seed-loader] error:', e.message);
  }
})();
```

### Step 3: Keep the Auto-Merge Pipeline (No Change)

The existing `loadAutoEpisodes()` function (currently ~1435–1533) **remains unchanged**.
Its merge logic already handles:
- Filling missing episodes from `_episodes_auto.json`
- Not overwriting inline entries that already have `deep` content
- Re-invoking `updateHeaderDates()`, `rebuildHighlightCards()`, `refreshEpisodeListFromDict()`

This means the pipeline becomes:
1. **Seed loader** executes (async) → fills EPISODES from `_episodes_seed.json`
2. **Auto-merge** executes (async) → fills gaps from `_episodes_auto.json`, re-renders

Both are async, so page may show in stages:
- T0: Page loads, EPISODES = {} → header says "loading…"
- T1: Seed arrives (~50ms) → header updates, cards render
- T2: Auto data arrives (~1–2s) → any new episodes/calls/stocks added

This is **acceptable** and actually mirrors the current state (page also waits for `_episodes_auto.json`).

### Step 4: Render Check in Browser

1. Open `index.html` in a browser (local or on deployed site)
2. Inspect:
   - [ ] Header shows correct EP range ("EP651–EP665")
   - [ ] Latest date shows correctly (should be 2026-05-27 for EP665)
   - [ ] Episode cards load and render without layout shifts
   - [ ] Highlight card animations work
   - [ ] Call cards show the 16 stock calls + 4 market calls
   - [ ] Stocks pane loads without errors
   - [ ] No red/orange console errors (warnings are OK)

3. If all pass → proceed to Step 5
4. If any UI break:
   - Revert the swap
   - Debug the race condition
   - Adjust the loader or function call order
   - Re-test

### Step 5: Commit & Push

Once render-verified:

```bash
# Stage the modified index.html
git add index.html

# Commit with clear message
git commit -m "Extract EPISODES monolith: move inline literal to async seed loader

- Inline 'const EPISODES = {...}' replaced with async loader from _episodes_seed.json
- Seed extraction verified faithful via scripts/verify_seed_faithful.js (15 ep, byte-exact)
- Auto-merge pipeline remains unchanged; load order: seed → auto → render
- Render tested in browser; all UI elements load & function correctly
- Reduces inline HTML by ~16KB; enables faster episode updates without full deploy

Co-Authored-By: Claude Code <noreply@anthropic.com>"

# Push to origin (manual trigger required)
git push origin main
```

---

## Guard: Preventing Accidental Inline Restore

If someone later re-adds a massive inline EPISODES literal:

1. **verify_seed_faithful.js will fail** — seed and inline will diverge
2. **File size bloat** — index.html will re-grow to ~44KB inline
3. **Review**: Look for commits that add `const EPISODES = {` with >100 lines of data

Add a pre-commit hook (optional, if desired) to reject >50KB index.html:
```bash
# .git/hooks/pre-commit
FILE_SIZE=$(stat -f%z index.html 2>/dev/null || stat -c%s index.html)
if [ "$FILE_SIZE" -gt 51200 ]; then
  echo "Error: index.html exceeds 50KB — check for inline EPISODES restore"
  exit 1
fi
```

---

## Risk Summary

**Low Risk** (already extracted & verified):
- Seed is byte-exact to inline → no data loss
- Auto-merge pipeline unchanged → no new logic failure modes
- Async load is standard web pattern → no browser compat issues

**Render-Specific Risk** (needs human check):
- Race condition: EPISODES {} before seed arrives → header briefly empty
- Function binding: `updateHeaderDates()` called before defined → silent fail
- Network: `_episodes_seed.json` 404 → falls back to empty EPISODES, auto-merge fills gaps

**Mitigation**: Render test in browser (Step 4) catches all of these before push.

---

## Reference: Seed Verification Output

When `verify_seed_faithful.js` runs, a clean pass looks like:

```
[VERIFY] Starting faithful comparison...

HTML: index.html
Seed: _episodes_seed.json

✓ Extracted inline EPISODES (15 episodes)
✓ Loaded seed JSON (15 episodes)

✓ VERIFICATION PASSED: seed is faithful to inline EPISODES
  - All 15 episodes present
  - All fields match (byte-exact including HTML deep content)
  - Safe to proceed with monolith swap
```

If mismatches found, script exits 1 with per-episode diffs (e.g., `EP662: deep: length(12000 vs 11950)`).

---

## Appendix: Why This Design

- **No blocking on `_episodes_seed.json`**: Page renders immediately with `EPISODES = {}`, then updates when seed arrives
- **Auto-merge gap-fills**: Whisper transcriptions from LaunchAgent still merge seamlessly
- **Decoupled from RSS**: RSS feed updates `_episodes_auto.json`, not inline HTML
- **Easier future updates**: Episode data changes only touch the seed file, not the monolithic HTML

This design was chosen to keep the page **lean, async, and audit-friendly** without sacrificing user experience.