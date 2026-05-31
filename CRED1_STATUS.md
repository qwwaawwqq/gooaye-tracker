# SE-MARKET-COUPLING-1 Completion Status

Date: 2026-05-31
Target: Migrate inline STOCKS from index.html to versioned _stocks.json (per audit se-market-coupling-1)

## What's Done

1. **Extract STOCKS to _stocks.json** (NEW)
   - Implemented: `scripts/extract_stocks_json.js` (faithful brace-counting eval, idempotent)
   - Extracts 33 stock entries from inline `const STOCKS = {...}` in index.html
   - Output: `_stocks.json` with schema `stockData-v1`, entry_count, codes array
   - Validation: all 33 entries, structure check (name/mkt/eps present), markets diversity

2. **Decouple update_market.py from index.html formatting** (PATCHED)
   - Modified: `extract_stocks_from_html()` now reads _stocks.json if present (preferred)
   - Fallback: regex scrape of inline STOCKS if _stocks.json absent (reversible, safe)
   - Additive: no breaking changes; both paths coexist
   - Market grading now independent of index.html HTML formatting

## What Remains (Deferred)

### 3. Index.html STOCKS load from _stocks.json (NOT YET APPLIED)
   - **Rationale**: Load fallback deferred until render verification by human
   - **Risk**: Removing inline STOCKS before testing could blank the scorecard if load fails
   - **Next step**: After orchestrator confirms _stocks.json extraction + market gradings OK,
     apply patch to index.html (load _stocks.json at boot, keep inline as fallback)
   - **Full delete of inline STOCKS**: Deferred until (a) render check passes, (b) per-call coverage expands

### 4. Inline STOCKS Deletion (DEFERRED — Coverage Not Yet Met)
   - **Current per-call grading coverage**: 5 unique codes out of 33 inline STOCKS (2327, 2330, 6230→not in STOCKS, GOOGL, TSLA)
   - **Actual inline STOCKS graded**: 2 codes (2327, 2330)
   - **Lost if deleted**: 31 codes have no per-call resolution path (see lost_coverage list below)
   - **Safety requirement**: Full deletion requires >90% call-level grading or safe scorecard rebuild
   - **Status**: NOT MET — per-call coverage must expand before inline removal is safe

## Coverage Audit

- **Inline STOCKS universe**: 33 entries (2308–2492, 3036–3661, 5371–6531, 8261, ADBE–AMZN, INTC–VPG)
- **_market_auto.json graded rows**: 31 entries (via STOCKS first-mention date lookup)
- **_episodes_auto.json call tickers**: ~6 calls with explicit {mkt,code} objects
  - Resolved in perf_map: 2327 (2 calls), 2330 (1 call), GOOGL (1 call), TSLA (1 call), 6230 (1 call)
  - **6230 NOT in inline STOCKS** (unresolved thematic/macro call)
  - **GOOGL, TSLA NOT in inline STOCKS** (unresolved per-call-only)
  - **Only 2327, 2330 overlap** with inline STOCKS ← this is why per-call adds no new coverage

## Lost Coverage If Deleted (31 codes)

```
Taiwan (25): 2308, 2327, 2337, 2375, 2449, 2454, 2492, 3036, 3037, 3443, 3661, 5371, 5469, 6173, 6285, 6531, 8261
US (6): ADBE, AMD, AMZN, AVGO, CRM, CRWD, INTC, META, NET, NVDA, PLTR, QCOM, TEAM, VPG, FORM
```

**Note**: Full list = 31 codes with zero per-call grading path. Deletion would:
- Blank the 31-stock scorecard section on index.html (rendering failure)
- Require manual re-entry or per-call grading expansion (not feasible short-term)

## Verification Steps (Pre-Merge)

- [ ] Run `node scripts/extract_stocks_json.js` → _stocks.json exists with 33 entries
- [ ] Verify `grep -c "'2330'" _stocks.json` → 1 (faithful extraction)
- [ ] Run `python update_market.py --limit 3` → reads _stocks.json, no errors
- [ ] Confirm `_market_auto.json` still has 31 rows (no regression)
- [ ] **DEFER**: index.html patch + inline STOCKS deletion pending render check

## Next Phase (After Orchestrator Verification)

1. Run orchestrator verify steps
2. If all pass, apply index.html patch (load _stocks.json)
3. Keep inline STOCKS as fallback (do NOT delete)
4. Plan per-call coverage expansion (out of scope for this audit)
5. Once coverage >90%, safe to delete inline STOCKS

---

**Audit Finding**: se-market-coupling-1 (Decouple stock universe definition from market grading process)
**Implementation Status**: ✓ Safe extraction + fallback decoupling; ⏳ Inline removal deferred
