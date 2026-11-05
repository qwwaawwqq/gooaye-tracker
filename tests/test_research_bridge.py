"""All transcript/price examples here are synthetic, not podcast claims."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from research_bridge.export import (
    EvidenceError, atomic_write, build_export, calculate_outcome, content_hash, main,
)


class ResearchBridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.transcript = "SYNTHETIC TEST ONLY. Example company may benefit over ten days."
        (self.root / "transcript.txt").write_text(self.transcript, encoding="utf-8")
        self.commit = "a" * 40
        self.document = {
            "episode_id": "EP1", "source_url": "https://example.org/synthetic/EP1",
            "published_at": "2026-10-01T18:00:00+08:00",
            "transcribed_at": "2026-10-01T19:00:00+08:00",
            "extracted_at": "2026-10-01T20:00:00+08:00",
            "transcript_path": "transcript.txt",
            "transcript_sha256": hashlib.sha256(self.transcript.encode()).hexdigest(),
            "calls": [{"ticker": "TW/2330", "stance": "bullish",
                       "horizon": {"value": 10, "unit": "trading_days"},
                       "quote": "Example company may benefit over ten days.", "v": "hit"}],
        }

    def export(self, document=None, **kwargs):
        return build_export(document or self.document, source_commit=self.commit,
                            cutoff=kwargs.pop("cutoff", "2026-10-02T00:00:00Z"),
                            transcript_root=self.root, **kwargs)

    def event(self):
        return self.export()["events"][0]

    def prices(self):
        return dict(entry_at="2026-10-02T01:00:00Z", exit_at="2026-10-12T01:00:00Z",
                    entry_price=100, exit_price=110, benchmark_id="synthetic-index",
                    benchmark_entry_at="2026-10-02T01:00:00Z",
                    benchmark_exit_at="2026-10-12T01:00:00Z",
                    benchmark_entry_price=1000, benchmark_exit_price=1050,
                    round_trip_cost_bps=20)

    def test_exact_provenance_and_availability(self):
        result = self.export()
        event = result["events"][0]
        self.assertEqual(event["available_at"], "2026-10-01T12:00:00Z")
        self.assertEqual(event["source_commit"], self.commit)
        self.assertEqual(event["market"], "TW")
        self.assertTrue(event["research_only"])
        self.assertNotIn("v", event)
        provenance = event["provenance"]
        self.assertEqual(self.transcript[provenance["quote_start"]:provenance["quote_end"]], provenance["quote"])
        self.assertEqual(result["manifest"]["events_sha256"], content_hash(result["events"]))
        self.assertEqual(result["manifest"]["quarantine_sha256"], content_hash([]))

    def test_latest_time_controls_all_uses_and_cutoff(self):
        self.document["available_at"] = "2026-10-03T02:00:00Z"
        self.document["calls"][0]["available_at"] = "2026-10-01T01:00:00Z"
        result = self.export()
        self.assertFalse(result["events"])
        self.assertEqual(result["quarantine"][0]["reason"], "not_available_at_cutoff")
        result = self.export(cutoff="2026-10-03T02:00:00Z")
        self.assertEqual(result["events"][0]["available_at"], "2026-10-03T02:00:00Z")

    def test_publication_date_cannot_substitute_for_ingestion_times(self):
        for key, value in (("transcribed_at", None), ("extracted_at", "2026-10-01"),
                           ("published_at", "2026-10-01T18:00:00")):
            with self.subTest(key=key):
                doc = copy.deepcopy(self.document)
                doc[key] = value
                result = self.export(doc)
                self.assertEqual(result["events"], [])
                self.assertIn(key, result["quarantine"][0]["reason"])

    def test_extraction_before_transcription_is_invalid(self):
        self.document["extracted_at"] = "2026-10-01T10:00:00Z"
        self.assertIn("precedes", self.export()["quarantine"][0]["reason"])

    def test_unresolved_ticker_horizon_stance_and_no_inference(self):
        for key, value in (("ticker", None), ("ticker", "台積電"), ("ticker", "??"),
                           ("market", "US"), ("ticker_resolved", False),
                           ("stance", "看好"), ("horizon", None),
                           ("horizon", {"value": True, "unit": "trading_days"})):
            with self.subTest(key=key, value=value):
                doc = copy.deepcopy(self.document)
                doc["calls"][0][key] = value
                doc["stocks"] = [["TW", "2330"]]
                self.assertFalse(self.export(doc)["events"])

    def test_quote_must_match_raw_transcript_and_hash(self):
        self.document["calls"][0]["quote"] = "Imagined quote."
        self.assertIn("quote absent", self.export()["quarantine"][0]["reason"])
        self.document["calls"][0]["quote"] = "Example company may benefit over ten days."
        (self.root / "transcript.txt").write_text(self.transcript + " Modified.")
        self.assertIn("sha256 mismatch", self.export()["quarantine"][0]["reason"])

    def test_transcript_root_escape_is_quarantined(self):
        self.document["transcript_path"] = "../other/transcript.txt"
        self.assertIn("escapes", self.export()["quarantine"][0]["reason"])

    def test_identical_events_deduplicate_and_keep_identity_across_commits(self):
        original_id = self.event()["event_id"]
        self.document["calls"] *= 2
        result = self.export()
        self.assertEqual(len(result["events"]), 1)
        self.assertEqual(result["manifest"]["duplicates_dropped"], 1)
        self.commit = "b" * 40
        self.assertEqual(self.event()["event_id"], original_id)
        self.assertEqual(self.export(), self.export())

    def test_conflicting_duplicates_are_not_arbitrarily_selected(self):
        first = copy.deepcopy(self.document)
        second = copy.deepcopy(first)
        second["extracted_at"] = "2026-10-01T21:00:00+08:00"
        result = self.export({"episodes": [first, second]})
        self.assertEqual(result["events"], [])
        self.assertIn("conflicting_duplicate", result["quarantine"][0]["reason"])
        other_order = self.export({"episodes": [second, first]})
        self.assertEqual(result["quarantine"], other_order["quarantine"])

    def test_watcher_requires_explicit_sidecar_and_never_reads_stocks_as_calls(self):
        content = {"ep": 1, "link": self.document["source_url"], "date": "2026-10-01",
                   "pub": "18:00", "stocks": [["TW", "2330"]],
                   "sections": [{"h": "Synthetic fixture", "lead": self.transcript}]}
        self.assertEqual(self.export(content)["quarantine"][0]["reason"], "no_explicit_research_calls")
        metadata = {k: v for k, v in self.document.items() if k != "calls"}
        evidence = {"content_sha256": content_hash(content), "episode": metadata,
                    "calls": self.document["calls"]}
        self.assertEqual(len(self.export(content, evidence=evidence)["events"]), 1)
        content["date"] = "2026-10-02"
        with self.assertRaisesRegex(EvidenceError, "content_sha256"):
            self.export(content, evidence=evidence)

    def test_sidecar_conflicts_and_short_commit_rejected(self):
        evidence = {"content_sha256": content_hash(self.document),
                    "episode": {"published_at": "2026-01-01T00:00:00Z"}}
        with self.assertRaisesRegex(EvidenceError, "conflicts"):
            self.export(evidence=evidence)
        self.commit = "abcdef0"
        with self.assertRaisesRegex(EvidenceError, "40-character"):
            self.export()

    def test_outcome_is_computed_against_benchmark_after_costs(self):
        result = calculate_outcome(self.event(), **self.prices())
        self.assertAlmostEqual(result["asset_return"], .10)
        self.assertAlmostEqual(result["benchmark_return"], .05)
        self.assertAlmostEqual(result["net_directional_return"], .098)
        self.assertAlmostEqual(result["net_directional_excess_return"], .048)
        self.assertEqual(result["outcome"], "outperformed")
        prices = self.prices() | {"exit_price": 90}
        self.assertEqual(calculate_outcome(self.event(), **prices)["outcome"], "underperformed")

    def test_outcome_rejects_pre_availability_entry_even_if_available_at_tampered(self):
        event = self.event() | {"available_at": "2026-10-01T00:00:00Z"}
        prices = self.prices() | {"entry_at": "2026-10-01T11:00:00Z",
                                 "benchmark_entry_at": "2026-10-01T11:00:00Z"}
        with self.assertRaisesRegex(EvidenceError, "availability"):
            calculate_outcome(event, **prices)

    def test_outcome_rejects_misaligned_benchmark_and_invalid_prices(self):
        for changes in ({"benchmark_exit_at": "2026-10-13T01:00:00Z"},
                        {"entry_price": 0}, {"exit_price": float("nan")},
                        {"round_trip_cost_bps": -1}, {"benchmark_id": ""}):
            with self.subTest(changes=changes), self.assertRaises(EvidenceError):
                calculate_outcome(self.event(), **(self.prices() | changes))

    def test_neutral_is_unscored_and_bearish_return_is_directional(self):
        neutral = calculate_outcome(self.event() | {"stance": "neutral"}, **self.prices())
        self.assertIsNone(neutral["net_directional_return"])
        self.assertEqual(neutral["outcome"], "unscored")
        bearish = calculate_outcome(self.event() | {"stance": "bearish"}, **self.prices())
        self.assertAlmostEqual(bearish["net_directional_return"], -.102)

    def test_atomic_replacement_failure_preserves_previous_artifact(self):
        path = self.root / "export.json"
        path.write_text("previous")
        with patch("research_bridge.export.os.replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                atomic_write(path, self.export())
        self.assertEqual(path.read_text(), "previous")
        self.assertFalse(list(self.root.glob(".export.json.*")))

    def test_cli_never_overwrites_a_quarantined_transcript(self):
        input_path, transcript_path = self.root / "input.json", self.root / "transcript.json"
        transcript_path.write_text("source to preserve")
        self.document["transcript_path"] = "transcript.json"
        # Intentionally wrong hash would quarantine the call. Source protection
        # must cover declarations, not only successfully exported provenance.
        input_path.write_text(json.dumps(self.document))
        with self.assertRaises(SystemExit) as error:
            main(["--input", str(input_path), "--output", str(transcript_path),
                  "--source-commit", self.commit, "--cutoff", "2026-10-02T00:00:00Z",
                  "--transcript-root", str(self.root)])
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(transcript_path.read_text(), "source to preserve")

    def test_cli_success_quarantine_status_and_input_protection(self):
        input_path, output_path = self.root / "input.json", self.root / "result.json"
        input_path.write_text(json.dumps(self.document))
        args = ["--input", str(input_path), "--output", str(output_path),
                "--source-commit", self.commit, "--cutoff", "2026-10-02T00:00:00Z",
                "--transcript-root", str(self.root)]
        self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(output_path.read_text()), self.export())
        self.document["calls"][0].pop("ticker")
        input_path.write_text(json.dumps(self.document))
        self.assertEqual(main(args), 2)
        args[3] = str(input_path)
        with self.assertRaises(SystemExit) as error:
            main(args)
        self.assertEqual(error.exception.code, 1)
        self.assertEqual(json.loads(input_path.read_text()), self.document)


if __name__ == "__main__":
    unittest.main()
