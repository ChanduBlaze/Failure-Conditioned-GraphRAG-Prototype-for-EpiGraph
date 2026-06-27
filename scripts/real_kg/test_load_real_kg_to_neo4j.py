"""Dry-run validation tests for the additive real-data Neo4j loader."""

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


LOADER_PATH = Path(__file__).resolve().with_name("load_real_kg_to_neo4j.py")

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


def make_claim(status="present", edge_type="LEADING_INDICATOR_FOR"):
    return {
        "case_id": "real_case_001",
        "candidate_id": "real_candidate_signal",
        "candidate_name": "Candidate signal",
        "target_signal_id": "real_target_signal",
        "target_signal_name": "Target signal",
        "edge_type": edge_type,
        "status": status,
        "source_dataset": "Test dataset",
        "method": "test_method_v1",
        "region": "Test region",
        "time_window_start": "2025-W01",
        "time_window_end": "2025-W10",
        "lag_weeks": "2" if status != "insufficient_data" else "",
        "score": "0.90" if status != "insufficient_data" else "",
        "threshold": "0.60",
        "evidence_sentence": "Test evidence for an association.",
        "limitation": "Associational evidence only; not causal proof.",
    }


class LoadRealKgDryRunTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.csv_path = Path(self.temporary_directory.name) / "claims.csv"

    def write_claims(self, rows, columns=None):
        """Write claim rows, using every required loader column by default."""
        fieldnames = REQUIRED_COLUMNS if columns is None else columns
        with self.csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {column: row.get(column, "") for column in fieldnames}
                )

    def run_dry_run(self):
        return subprocess.run(
            [
                sys.executable,
                str(LOADER_PATH),
                "--input",
                str(self.csv_path),
                "--dry-run",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_valid_present_claim(self):
        self.write_claims([make_claim("present")])

        result = self.run_dry_run()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Dry run", result.stdout)
        self.assertIn("Rows read: 1", result.stdout)
        self.assertIn("Present typed edges created: 1", result.stdout)
        self.assertIn('"typed_leading_indicator_edge": true', result.stdout)
        self.assertIn(
            "neo4j_loader.py is destructive",
            result.stdout,
        )

    def test_missing_claim_has_no_typed_edge(self):
        self.write_claims([make_claim("missing")])

        result = self.run_dry_run()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Rows read: 1", result.stdout)
        self.assertIn("Present typed edges created: 0", result.stdout)
        self.assertIn(
            "Missing/insufficient claims loaded without typed edges: 1",
            result.stdout,
        )
        self.assertIn('"typed_leading_indicator_edge": false', result.stdout)

    def test_insufficient_data_claim_has_no_typed_edge(self):
        self.write_claims([make_claim("insufficient_data")])

        result = self.run_dry_run()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Present typed edges created: 0", result.stdout)
        self.assertIn('"typed_leading_indicator_edge": false', result.stdout)

    def test_invalid_status(self):
        self.write_claims([make_claim("unknown")])

        result = self.run_dry_run()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid status", result.stderr)

    def test_invalid_edge_type(self):
        self.write_claims([make_claim(edge_type="CAUSES")])

        result = self.run_dry_run()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("v1 supports only", result.stderr)

    def test_duplicate_evidence_claim_rows(self):
        claim = make_claim()
        self.write_claims([claim, claim])

        result = self.run_dry_run()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate evidence_claim_id", result.stderr)

    def test_missing_required_column(self):
        missing_column = "limitation"
        columns = [
            column for column in REQUIRED_COLUMNS if column != missing_column
        ]
        self.write_claims([make_claim()], columns=columns)

        result = self.run_dry_run()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(missing_column, result.stderr)


if __name__ == "__main__":
    unittest.main()
