"""Lightweight validation tests for the real Text-RAG corpus builder."""

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REAL_KG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = REAL_KG_DIR.parents[1]
BUILDER_PATH = REAL_KG_DIR / "build_real_text_corpus.py"

REQUIRED_COLUMNS = [
    "case_id",
    "candidate_id",
    "candidate_name",
    "target_signal_id",
    "target_signal_name",
    "edge_type",
    "status",
    "source_dataset",
    "method",
    "region",
    "time_window_start",
    "time_window_end",
    "lag_weeks",
    "score",
    "threshold",
    "evidence_sentence",
    "limitation",
]


class BuildRealTextCorpusTests(unittest.TestCase):
    def make_claim(self, status="present"):
        lag_weeks = "2" if status != "insufficient_data" else ""
        score = "0.940000" if status != "insufficient_data" else ""

        return {
            "case_id": "real_us_flu_wastewater_leading_indicator_001",
            "candidate_id": "real_signal_influenza_a_wastewater_activity",
            "candidate_name": "Influenza A wastewater activity",
            "target_signal_id": (
                "real_signal_us_influenza_hospitalization_rate"
            ),
            "target_signal_name": "U.S. influenza hospitalization rate",
            "edge_type": "LEADING_INDICATOR_FOR",
            "status": status,
            "source_dataset": "CDC surveillance fixture",
            "method": "lagged_pearson_correlation_v1",
            "region": "United States",
            "time_window_start": "2025-W01",
            "time_window_end": "2025-W10",
            "lag_weeks": lag_weeks,
            "score": score,
            "threshold": "0.60",
            "evidence_sentence": (
                "Controlled evidence sentence for validation."
            ),
            "limitation": (
                "Associational evidence only; not causal proof."
            ),
        }

    def write_claims(self, path: Path, claims) -> None:
        with path.open("w", newline="", encoding="utf-8") as claim_file:
            writer = csv.DictWriter(
                claim_file,
                fieldnames=REQUIRED_COLUMNS,
            )
            writer.writeheader()
            writer.writerows(claims)

    def run_builder(self, input_path: Path, output_path: Path):
        return subprocess.run(
            [
                sys.executable,
                str(BUILDER_PATH),
                "--input",
                str(input_path),
                "--output",
                str(output_path),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def build_corpus_for_claim(self, claim):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "claims.csv"
            output_path = temp_path / "corpus.json"
            self.write_claims(input_path, [claim])

            result = self.run_builder(input_path, output_path)
            self.assertEqual(result.returncode, 0, msg=result.stderr)

            with output_path.open("r", encoding="utf-8") as corpus_file:
                return json.load(corpus_file)

    def test_present_claim_produces_complete_deterministic_chunk(self):
        claim = self.make_claim(status="present")
        chunks = self.build_corpus_for_claim(claim)

        self.assertEqual(len(chunks), 1)
        chunk = chunks[0]
        self.assertEqual(chunk["source_type"], "real_evidence_claim")
        self.assertEqual(chunk["status"], "present")
        self.assertEqual(chunk["edge_type"], "LEADING_INDICATOR_FOR")
        self.assertTrue(chunk["chunk_id"].startswith("real_chunk__"))
        self.assertTrue(
            chunk["evidence_claim_id"].startswith("real_claim__")
        )

        for expected_text in [
            claim["candidate_name"],
            claim["target_signal_name"],
            claim["score"],
            claim["threshold"],
            claim["method"],
            claim["source_dataset"],
            claim["limitation"],
        ]:
            self.assertIn(expected_text, chunk["text"])

    def test_missing_claim_text_is_explicitly_not_positive(self):
        chunks = self.build_corpus_for_claim(
            self.make_claim(status="missing")
        )
        text = chunks[0]["text"].lower()

        self.assertIn("the evidence threshold was not met", text)
        self.assertIn("this is not a positive evidence claim", text)

    def test_insufficient_data_text_is_explicitly_not_positive(self):
        chunks = self.build_corpus_for_claim(
            self.make_claim(status="insufficient_data")
        )
        text = chunks[0]["text"].lower()

        self.assertIn(
            "could not be assessed due to insufficient data",
            text,
        )
        self.assertIn("this is not a positive evidence claim", text)

    def test_invalid_status_returns_nonzero_without_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "claims.csv"
            output_path = temp_path / "corpus.json"
            self.write_claims(
                input_path,
                [self.make_claim(status="unsupported")],
            )

            result = self.run_builder(input_path, output_path)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid status", result.stderr)
            self.assertFalse(output_path.exists())

    def test_duplicate_evidence_claim_ids_return_nonzero_without_output(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "claims.csv"
            output_path = temp_path / "corpus.json"
            claim = self.make_claim(status="present")
            self.write_claims(input_path, [claim, dict(claim)])

            result = self.run_builder(input_path, output_path)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Duplicate evidence_claim_id", result.stderr)
            self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()
