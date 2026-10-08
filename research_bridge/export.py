"""Export transcript-backed observations without touching the website or watcher.

No network, broker, transcription or language-model dependencies are used here.
See docs/RESEARCH_BRIDGE.md for the input and availability contracts.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit


SCHEMA = "research-event-v1"
SOURCE_REPO = "gooaye-tracker"
TIME_FIELDS = ("published_at", "transcribed_at", "extracted_at")
SOURCE_FIELDS = TIME_FIELDS + (
    "available_at", "source_url", "transcript_path", "transcript_sha256",
)


class EvidenceError(ValueError):
    """A record lacks sufficient explicit evidence for research export."""


def canonical_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def content_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def parse_time(value: object, name: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value
    ):
        raise EvidenceError(f"{name}: timezone-aware RFC3339 timestamp required")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as exc:
        raise EvidenceError(f"{name}: invalid timestamp") from exc


def utc(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _times(record: dict) -> tuple[dict, datetime]:
    times = {key: parse_time(record.get(key), key) for key in TIME_FIELDS}
    if times["extracted_at"] < times["transcribed_at"]:
        raise EvidenceError("extracted_at precedes transcribed_at")
    if record.get("available_at") is not None:
        times["available_at"] = parse_time(record["available_at"], "available_at")
    available = max(times.values())
    return {key: utc(value) for key, value in times.items()} | {"available_at": utc(available)}, available


def _ticker(record: dict) -> tuple[str, str]:
    ticker = record.get("ticker")
    market = record.get("market")
    if isinstance(ticker, dict):
        declared = ticker.get("mkt", ticker.get("market"))
        if market is not None and declared != market:
            raise EvidenceError("conflicting ticker market")
        market, ticker = declared, ticker.get("code", ticker.get("ticker"))
    elif isinstance(ticker, str) and "/" in ticker:
        declared, ticker = ticker.split("/", 1)
        if market is not None and declared != market:
            raise EvidenceError("conflicting ticker market")
        market = declared
    if record.get("ticker_resolved") is False:
        raise EvidenceError("ticker explicitly unresolved")
    pattern = {"TW": r"\d{4,6}[A-Z]?", "US": r"[A-Z]{1,6}(?:[.\-][A-Z]{1,2})?"}.get(market)
    if not pattern or not isinstance(ticker, str) or not re.fullmatch(pattern, ticker):
        raise EvidenceError("explicit resolved TW/US market and ticker required")
    return market, ticker


def _episode_id(value: object) -> str:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return f"EP{value}"
    if isinstance(value, str) and re.fullmatch(r"EP[1-9]\d*", value):
        return value
    raise EvidenceError("explicit episode_id (EP<number>) or positive ep required")


def _event(record: dict, episode_id: str, commit: str, root: Path, cutoff: datetime) -> dict:
    times, available = _times(record)
    if available > cutoff:
        raise EvidenceError("not_available_at_cutoff")
    market, ticker = _ticker(record)
    stance = record.get("stance")
    if stance not in ("bullish", "bearish", "neutral"):
        raise EvidenceError("explicit stance must be bullish, bearish or neutral")
    horizon = record.get("horizon")
    if not isinstance(horizon, dict) or set(horizon) != {"value", "unit"} or (
        type(horizon["value"]) is not int or horizon["value"] <= 0
        or horizon["unit"] not in ("trading_days", "calendar_days")
    ):
        raise EvidenceError("explicit positive horizon value and supported unit required")
    source_url = record.get("source_url")
    if not isinstance(source_url, str):
        raise EvidenceError("source_url required")
    url = urlsplit(source_url)
    if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
        raise EvidenceError("source_url must be an HTTP(S) source without credentials")
    relative = record.get("transcript_path")
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise EvidenceError("transcript_path must be relative to transcript root")
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise EvidenceError("transcript_path escapes transcript root") from exc
    expected_sha = record.get("transcript_sha256")
    if not isinstance(expected_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", expected_sha):
        raise EvidenceError("explicit transcript_sha256 required")
    try:
        raw = path.read_bytes()
        transcript = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise EvidenceError("transcript unavailable or not UTF-8") from exc
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise EvidenceError("transcript_sha256 mismatch")
    quote = record.get("quote")
    if not isinstance(quote, str) or not quote.strip() or quote not in transcript:
        raise EvidenceError("exact source quote absent from transcript")
    start = transcript.index(quote)
    provenance = {"source_url": source_url, "quote": quote,
                  "transcript_path": path.relative_to(root).as_posix(),
                  "transcript_sha256": expected_sha, "quote_start": start,
                  "quote_end": start + len(quote)}
    identity = {"source_repo": SOURCE_REPO, "episode_id": episode_id,
                "market": market, "ticker": ticker, "stance": stance,
                "horizon": horizon, "quote": quote, "transcript_sha256": expected_sha}
    return {"schema_version": 1, "event_id": content_hash(identity),
            "source_repo": SOURCE_REPO, "source_commit": commit,
            "episode_id": episode_id, "market": market, "ticker": ticker,
            "stance": stance, "horizon": horizon, **times,
            "provenance": provenance, "research_only": True}


def build_export(document: dict, *, source_commit: str, cutoff: str,
                 transcript_root: str | Path, evidence: dict | None = None) -> dict:
    """Validate explicit calls; quarantine incomplete records and conflicting copies.

    A watcher content JSON with no calls requires a hash-bound evidence sidecar.
    Only fields expressly supplied by the curator are used; prose is never parsed
    into predictions. The caller retains responsibility for timestamp evidence.
    """
    if not re.fullmatch(r"[0-9a-fA-F]{40}", source_commit or ""):
        raise EvidenceError("source_commit must be a full 40-character Git commit SHA")
    source_commit = source_commit.lower()
    cutoff_time = parse_time(cutoff, "cutoff")
    root = Path(transcript_root).resolve()
    if not isinstance(document, dict):
        raise EvidenceError("input must be a JSON object")
    if evidence is not None:
        if not isinstance(evidence, dict) or evidence.get("content_sha256") != content_hash(document):
            raise EvidenceError("sidecar content_sha256 must match canonical input JSON")
        if "episodes" in document:
            raise EvidenceError("sidecar supported only for a single curated episode")
        metadata = evidence.get("episode", {})
        if not isinstance(metadata, dict):
            raise EvidenceError("sidecar episode must be an object")
        merged = dict(document)
        for key, value in metadata.items():
            if key not in SOURCE_FIELDS + ("episode_id",):
                raise EvidenceError(f"unsupported sidecar episode field: {key}")
            if key in merged and merged[key] != value:
                raise EvidenceError(f"sidecar conflicts with input field: {key}")
            merged[key] = value
        if "calls" in evidence:
            if "calls" in merged and merged["calls"] != evidence["calls"]:
                raise EvidenceError("sidecar conflicts with input calls")
            merged["calls"] = evidence["calls"]
        episodes = [merged]
    else:
        episodes = document.get("episodes", [document])
    if not isinstance(episodes, list):
        raise EvidenceError("episodes must be a list")
    candidates: dict[str, list[tuple[dict, dict]]] = {}
    quarantine = []
    duplicates = 0

    def reject(record: object, reason: str, episode: str | None = None) -> None:
        quarantine.append({"record_sha256": content_hash(record),
                           "episode_id": episode, "reason": reason})

    for episode in episodes:
        try:
            if not isinstance(episode, dict):
                raise EvidenceError("episode must be an object")
            ep_id = _episode_id(episode.get("episode_id", episode.get("ep")))
            if "episode_id" in episode and "ep" in episode and _episode_id(episode["ep"]) != ep_id:
                raise EvidenceError("conflicting episode identifiers")
        except EvidenceError as exc:
            reject(episode, str(exc))
            continue
        calls = episode.get("calls")
        if not isinstance(calls, list) or not calls:
            reject(episode, "no_explicit_research_calls", ep_id)
            continue
        shared = {key: episode[key] for key in SOURCE_FIELDS if key in episode}
        if "source_url" not in shared and "link" in episode:
            shared["source_url"] = episode["link"]
        for call in calls:
            try:
                if not isinstance(call, dict):
                    raise EvidenceError("call must be an object")
                # Per-call timing may be later (e.g. a revised extraction). Never
                # reduce shared availability with a record-specific override.
                record = {**shared, **call}
                for key in TIME_FIELDS + ("available_at",):
                    if key in shared and key in call:
                        record[key] = utc(max(parse_time(shared[key], key), parse_time(call[key], key)))
                event = _event(record, ep_id, source_commit, root, cutoff_time)
                candidates.setdefault(event["event_id"], []).append((event, record))
            except (EvidenceError, TypeError, ValueError) as exc:
                reject(call, str(exc), ep_id)
    events = {}
    for event_id, copies in candidates.items():
        if len({content_hash(event) for event, _ in copies}) == 1:
            events[event_id] = copies[0][0]
            duplicates += len(copies) - 1
        else:
            # Quarantine every copy, independent of input ordering. Conflicting
            # evidence must be resolved by a curator, never by first/last wins.
            for event, record in copies:
                reject(record, "conflicting_duplicate_event", event["episode_id"])
    ordered = sorted(events.values(), key=lambda item: (item["available_at"], item["event_id"]))
    quarantine.sort(key=lambda item: (item["record_sha256"], item["reason"]))
    manifest = {"input_sha256": content_hash(document),
                "evidence_sha256": content_hash(evidence) if evidence is not None else None,
                "events_sha256": content_hash(ordered), "quarantine_sha256": content_hash(quarantine),
                "event_count": len(ordered), "quarantine_count": len(quarantine),
                "duplicates_dropped": duplicates, "cutoff": utc(cutoff_time)}
    return {"schema_version": SCHEMA, "source_repo": SOURCE_REPO,
            "source_commit": source_commit, "research_only": True,
            "events": ordered, "quarantine": quarantine, "manifest": manifest}


def calculate_outcome(event: dict, *, entry_at: str, exit_at: str,
                      entry_price: float, exit_price: float,
                      benchmark_id: str, benchmark_entry_at: str, benchmark_exit_at: str,
                      benchmark_entry_price: float, benchmark_exit_price: float,
                      round_trip_cost_bps: float) -> dict:
    """Compute simple cost-adjusted, direction-aware returns for an explicit window.

    No prices are fetched and no hit verdict is imported. This is an observation,
    not a broker fill model or proof that the specified horizon was respected.
    """
    _, available = _times(event)
    entry, end = parse_time(entry_at, "entry_at"), parse_time(exit_at, "exit_at")
    if entry < available or end <= entry:
        raise EvidenceError("entry must be at/after availability and exit after entry")
    if (parse_time(benchmark_entry_at, "benchmark_entry_at") != entry
            or parse_time(benchmark_exit_at, "benchmark_exit_at") != end):
        raise EvidenceError("benchmark and asset windows must match exactly")
    if not isinstance(benchmark_id, str) or not benchmark_id.strip():
        raise EvidenceError("explicit benchmark_id required")
    prices = (entry_price, exit_price, benchmark_entry_price, benchmark_exit_price)
    if any(type(p) not in (int, float) or not math.isfinite(p) or p <= 0 for p in prices):
        raise EvidenceError("prices must be finite positive numbers")
    if (type(round_trip_cost_bps) not in (int, float) or not math.isfinite(round_trip_cost_bps)
            or round_trip_cost_bps < 0):
        raise EvidenceError("round_trip_cost_bps must be explicit, finite and nonnegative")
    stance = event.get("stance")
    if stance not in ("bullish", "bearish", "neutral"):
        raise EvidenceError("unsupported stance")
    asset_return = exit_price / entry_price - 1
    benchmark_return = benchmark_exit_price / benchmark_entry_price - 1
    direction = {"bullish": 1, "bearish": -1, "neutral": 0}[stance]
    net = direction * asset_return - round_trip_cost_bps / 10000 if direction else None
    excess = net - direction * benchmark_return if direction else None
    return {"event_id": event["event_id"], "research_only": True,
            "entry_at": utc(entry), "exit_at": utc(end), "benchmark_id": benchmark_id,
            "entry_price": entry_price, "exit_price": exit_price,
            "benchmark_entry_price": benchmark_entry_price, "benchmark_exit_price": benchmark_exit_price,
            "round_trip_cost_bps": round_trip_cost_bps,
            "asset_return": asset_return, "benchmark_return": benchmark_return,
            "net_directional_return": net, "net_directional_excess_return": excess,
            "outcome": ("unscored" if excess is None else "outperformed" if excess > 0
                        else "underperformed" if excess < 0 else "matched")}


def atomic_write(path: str | Path, value: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json(value) + b"\n"
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cutoff", required=True, help="Timezone-aware as-of timestamp")
    parser.add_argument("--evidence", type=Path, help="Optional hash-bound watcher metadata/calls")
    parser.add_argument("--transcript-root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    try:
        protected = [args.input.resolve()] + ([args.evidence.resolve()] if args.evidence else [])
        if args.output.resolve() in protected or args.output.suffix != ".json":
            raise EvidenceError("output must be a separate .json artifact")
        document = json.loads(args.input.read_text(encoding="utf-8"))
        evidence = json.loads(args.evidence.read_text(encoding="utf-8")) if args.evidence else None

        def declared_transcripts(value: object):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "transcript_path" and isinstance(child, str):
                        yield (args.transcript_root / child).resolve()
                    else:
                        yield from declared_transcripts(child)
            elif isinstance(value, list):
                for child in value:
                    yield from declared_transcripts(child)

        if args.output.resolve() in set(declared_transcripts([document, evidence])):
            raise EvidenceError("output must not overwrite source transcript")
        result = build_export(document, source_commit=args.source_commit, cutoff=args.cutoff,
                              transcript_root=args.transcript_root, evidence=evidence)
        atomic_write(args.output, result)
    except (OSError, ValueError, TypeError) as exc:
        parser.exit(1, f"research export failed: {exc}\n")
    print(f"Exported {len(result['events'])} events; quarantined {len(result['quarantine'])} records.")
    return 2 if result["quarantine"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
