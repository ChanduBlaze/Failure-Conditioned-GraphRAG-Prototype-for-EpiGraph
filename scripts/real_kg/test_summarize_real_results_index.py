"""Tests for the final fixture and empirical real-results index."""

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.real_kg.summarize_real_results_index import (
    FIXTURE_NOTES,
    OUTPUT_COLUMNS,
    build_index,
    read_summary,
    write_index,
)


FIXTURE_COLUMNS = [
    "method",
    "case_count",
    "candidate_accuracy",
    "status_accuracy",
]
EMPIRICAL_COLUMNS = [
    "method",
    "case_count",
    "status_accuracy",
    "score_accuracy",
    "notes",
]


def write_rows(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def fixture_rows():
    return [
        {
            "method": "llm_only",
            "case_count": "4",
            "candidate_accuracy": "0.75",
            "status_accuracy": "0.5",
        },
        {
            "method": "graphrag_context",
            "case_count": "4",
            "candidate_accuracy": "1.0",
            "status_accuracy": "1.0",
        },
    ]


def empirical_rows():
    return [
        {
            "method": "empirical_text_rag",
            "case_count": "3",
            "status_accuracy": "1.0",
            "score_accuracy": "0.8",
            "notes": "Preserved empirical note.",
        }
    ]


class SummarizeRealResultsIndexTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        fixture_path = temp_path / "fixture.csv"
        empirical_path = temp_path / "empirical.csv"
        write_rows(
            fixture_path,
            FIXTURE_COLUMNS,
            fixture_rows(),
        )
        write_rows(
            empirical_path,
            EMPIRICAL_COLUMNS,
            empirical_rows(),
        )
        self.index_rows = build_index(
            read_summary(fixture_path, "Fixture summary"),
            read_summary(empirical_path, "Empirical summary"),
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_writes_fixture_rows_before_empirical_rows(self):
        rows = self.index_rows

        self.assertEqual(
            [row["result_family"] for row in rows],
            [
                "fixture_real_kg",
                "fixture_real_kg",
                "empirical_influenza",
            ],
        )
        self.assertEqual(
            [row["method"] for row in rows],
            ["llm_only", "graphrag_context", "empirical_text_rag"],
        )
        self.assertEqual(rows[0]["notes"], FIXTURE_NOTES)

    def test_preserves_fixture_candidate_accuracy(self):
        rows = self.index_rows

        self.assertEqual(rows[0]["candidate_accuracy"], "0.75")
        self.assertEqual(rows[1]["candidate_accuracy"], "1.0")

    def test_leaves_missing_columns_blank(self):
        rows = self.index_rows

        self.assertEqual(rows[0]["score_accuracy"], "")
        self.assertEqual(rows[0]["threshold_accuracy"], "")
        self.assertEqual(rows[0]["paired_week_count_accuracy"], "")
        self.assertEqual(rows[-1]["candidate_accuracy"], "")
        self.assertEqual(rows[-1]["threshold_claims"], "")

    def test_preserves_empirical_notes(self):
        rows = self.index_rows

        self.assertEqual(rows[-1]["notes"], "Preserved empirical note.")

    def test_output_has_required_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "index.csv"
            write_index(
                output_path,
                self.index_rows,
            )

            with output_path.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as input_file:
                reader = csv.DictReader(input_file)
                rows = list(reader)

        self.assertEqual(reader.fieldnames, OUTPUT_COLUMNS)
        self.assertEqual(len(rows), 3)

    def test_missing_fixture_input_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing_fixture.csv"

            with self.assertRaisesRegex(
                FileNotFoundError,
                "Fixture summary input not found",
            ):
                read_summary(missing, "Fixture summary")

    def test_missing_empirical_input_raises_clear_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing_empirical.csv"

            with self.assertRaisesRegex(
                FileNotFoundError,
                "Empirical summary input not found",
            ):
                read_summary(missing, "Empirical summary")


if __name__ == "__main__":
    unittest.main()
