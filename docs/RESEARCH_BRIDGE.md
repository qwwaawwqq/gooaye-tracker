# Read-only research bridge

This optional, standard-library-only exporter turns explicit transcript-backed
calls into point-in-time research observations. It does not fetch prices, download
audio, use a paid API, place orders, or change the website, watcher, watchlist,
legacy episode data, or market updater. Exported observations are research inputs;
they are not trading instructions or validated strategy returns.

The current authoritative watcher produces curated JSON under
`tools/watcher/content/` and renders inline entries with `deep`. Its `stocks` list
contains mentions, not predictions. Its `date`/`pub` fields do not establish when a
transcript or research extraction became available. The bridge deliberately does
not infer calls, directions, horizons, exchange mappings, or ingestion times from
these fields. An old episode curated today cannot enter yesterday's backtest.

## Command and exit status

Run from the repository root, using the immutable commit of the source evidence:

```sh
python3 -m research_bridge.export \
  --input tools/watcher/content/EP702.json \
  --evidence /path/to/EP702.research-evidence.json \
  --transcript-root . \
  --source-commit FULL_40_CHARACTER_SOURCE_COMMIT \
  --cutoff 2026-10-08T23:00:00+08:00 \
  --output /path/to/research/events.json
```

Use the actual timestamps and commit; the command's values are placeholders. No
sidecar or real calls are created by this change. With the existing watcher JSON
alone, the command writes a quarantine entry `no_explicit_research_calls` and exits
2. Missing historical metadata must be recovered from trustworthy records or left
unavailable; do not backdate it to publication or use filesystem modification time.

Exit 0 means all supplied records were accepted, 2 means an artifact was written
with quarantined records, and 1 means input/operational failure. An empty explicit
`episodes` list produces a zero-event artifact, not evidence of a successful
research experiment. Artifact replacement is atomic. Existing source input,
sidecar, and declared transcript paths cannot be overwritten by the CLI.

## Input contract

The API accepts one episode object or `{"episodes": [episode, ...]}`. Each episode
contains `episode_id` (`EP<number>`) or positive integer `ep`, source metadata, and
explicit `calls`. Every field below is mandatory except `available_at`:

| Field | Meaning |
|---|---|
| `published_at` | Actual public release time, with seconds and timezone |
| `transcribed_at` | Time this transcript became available |
| `extracted_at` | Time the curated research interpretation became available |
| `available_at` | Optional additional release/ingestion delay; cannot reduce availability |
| `source_url` | Episode evidence URL; watcher `link` is supported |
| `transcript_path` | UTF-8 transcript path relative to `--transcript-root` |
| `transcript_sha256` | SHA256 of the exact raw transcript bytes |
| `calls[].ticker` | Explicit `TW/2330`, `US/NVDA`, or `{mkt, code}`; alternatively bare code plus `market` |
| `calls[].stance` | Explicit `bullish`, `bearish`, or `neutral` |
| `calls[].horizon` | `{value: positive integer, unit: trading_days or calendar_days}` |
| `calls[].quote` | Exact, nonempty substring of the raw transcript |

Episode metadata is inherited by calls. A per-call timestamp cannot reduce an
episode timestamp. The effective availability is the latest of publication,
transcription, extraction, and any extra availability delay. Extraction preceding
transcription is invalid. Dates without times/timezones are quarantined. Records
with availability after `--cutoff` are quarantined rather than emitted. All output
times use UTC. Availability equal to the cutoff is accepted.

The ticker parser checks explicit TW/US notation; it does not query an instrument
registry or establish that a ticker is currently listed. Curators are responsible
for identity resolution. Set `ticker_resolved: false` for unresolved entities;
those records are quarantined. Names, `stocks` arrays, thematic phrases, and
free-text stance labels are never converted into tickers/directions. Existing
`v: hit` or other legacy verdicts are ignored. Raw quotes with spelling corrections
must still be supplied as the original transcript span; this bridge does not apply
watcher `fixes`, fuzzy matching, punctuation removal, or ellipsis expansion.

## Using current watcher content without modifying it

A sidecar can add the missing evidence and curated calls to one unchanged watcher
content JSON. It has this shape (types shown, not actual episode data):

```json
{
  "content_sha256": "SHA256_OF_CANONICAL_CONTENT_JSON",
  "episode": {
    "published_at": "RFC3339_WITH_TIMEZONE",
    "transcribed_at": "RFC3339_WITH_TIMEZONE",
    "extracted_at": "RFC3339_WITH_TIMEZONE",
    "transcript_path": "transcripts/EP702.txt",
    "transcript_sha256": "SHA256_OF_RAW_TRANSCRIPT_BYTES"
  },
  "calls": [
    {
      "market": "EXPLICIT_MARKET",
      "ticker": "EXPLICIT_TICKER",
      "stance": "EXPLICIT_DIRECTION",
      "horizon": {"value": 10, "unit": "trading_days"},
      "quote": "EXACT_RAW_TRANSCRIPT_SPAN"
    }
  ]
}
```

The horizon above illustrates the data type only; select the actual stated or
prespecified research horizon and document that choice in the curation record.
Canonical JSON uses UTF-8, sorted keys, compact separators, and unescaped Unicode.
Use `content_hash(json.loads(content_path.read_text()))` from
`research_bridge.export` to calculate `content_sha256`. A content change invalidates
the sidecar. Existing source fields/calls cannot be silently overwritten by a
sidecar. Source transcript SHA and quote are verified against local bytes before
any event is accepted. Paths outside the declared transcript root are rejected.

## Output and integration API

```python
from research_bridge.export import build_export, calculate_outcome, atomic_write

artifact = build_export(
    curated_document,
    evidence=optional_sidecar,
    source_commit=source_commit,
    cutoff=as_of_timestamp,
    transcript_root=repository_root,
)
atomic_write(output_path, artifact)
```

The envelope contains `schema_version: research-event-v1`, `source_repo:
gooaye-tracker`, `source_commit`, `research_only: true`, `events`, `quarantine`, and
`manifest`. Each event carries version 1, source identity, `event_id`, `episode_id`,
market/ticker, stance/horizon, the four timestamps, and `provenance` with the source
URL, raw quote, transcript SHA/path, and zero-based Unicode character offsets
(`quote_start` inclusive, `quote_end` exclusive). If a quote repeats, the first
exact occurrence is recorded; no audio timecode is claimed.

Event identity is a SHA256 of source repository, episode, explicit instrument,
stance, horizon, raw quote and transcript SHA. It remains stable across unrelated
commits/reexports. A changed interpretation or transcript produces a new identity.
Identical events deduplicate. Copies with the same identity but conflicting
timestamps/provenance all go to quarantine; a curator must resolve the conflict.
No input order silently chooses a winner. Event/quarantine arrays are sorted.

The manifest includes SHA256 hashes of canonical input, optional evidence, emitted
events and quarantine, counts, duplicates dropped, and cutoff. Quarantine includes
the record hash, episode ID when available, and reason; it does not repeat the raw
transcript. No current wall-clock generation timestamp is inserted, so repeated
exports of identical evidence and parameters produce identical bytes.

The source commit is an asserted provenance identifier supplied by the caller. The
exporter validates SHA format; it does not access GitHub or prove that local
evidence belongs to that commit. Consumers must separately verify artifact hashes,
source checkout provenance and their own cutoff before use. Public bridge code has
no imports or source content from private repositories. Keep private results and
credentials outside this repository.

## Computed outcomes, separate from source observations

`calculate_outcome(event, *, entry_at, exit_at, entry_price, exit_price,
benchmark_id, benchmark_entry_at, benchmark_exit_at, benchmark_entry_price,
benchmark_exit_price, round_trip_cost_bps)` requires all prices, both aligned
windows and explicit all-in modeled costs. Entry must be at/after the latest event
availability and exit must follow entry. Benchmark timestamps must match the asset
window exactly. Missing, nonfinite or nonpositive prices are rejected.

The output reports simple price return, benchmark return, direction-adjusted return
after costs, and direction-adjusted excess return after costs. `bullish` uses +1;
`bearish` uses -1. A neutral observation is `unscored`. The computed labels are
`outperformed`, `underperformed`, or `matched`; no manual HIT value is imported.

This function does not fetch prices, model futures rolls/margin/fills, adjust
corporate actions, infer a trading calendar, or certify that the supplied exit
matches the event horizon. These checks belong to the consumer's market dataset
and evaluation protocol. It does not promote an observation into a live strategy.

## Validation and operational scope

```sh
python3 -m unittest discover -s tests -p 'test_research_bridge.py' -v
```

Tests use clearly synthetic transcripts/prices and cover availability leakage,
quarantine, exact provenance, sidecar binding, duplicate conflicts, cost/benchmark
arithmetic, invalid windows and atomic-write interruption. The optional CI workflow
only runs these offline tests. It has no schedule, secrets, content-write permission,
model calls or data commits. Continuous collection remains the existing watcher;
this change provides the validated export boundary for a separate research worker.
