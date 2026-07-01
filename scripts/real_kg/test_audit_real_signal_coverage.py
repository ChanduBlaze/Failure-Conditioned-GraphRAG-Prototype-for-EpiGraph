"""Tests for real normalized-signal coverage and overlap auditing."""

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.real_kg.audit_real_signal_coverage import (
    COVERAGE_COLUMNS,
    OVERLAP_COLUMNS,
    REQUIRED_INPUT_COLUMNS,
    audit_rows,
    read_signal_rows,
    write_csv,
)


CASE_ID = "real_case"
TARGET_ID = "target_signal"


def signal_row(
    signal_id,
    role,
    week,
    normalized_value="0.5",
    name=None,
):
    return {
        "case_id": CASE_ID,
        "signal_id": signal_id,
        "signal_name": name or signal_id,
        "signal_role": role,
        "source_name": f"source_{signal_id}",
        "region": "United States",
        "week": week,
        "normalized_value": normalized_value,
    }


def weeks(year, count):
    return [f"{year}-W{week:02d}" for week in range(1, count + 1)]


def target_rows(year=2025, count=12):
    return [
        signal_row(TARGET_ID, "target", week)
        for week in weeks(year, count)
    ]


def candidate_rows(signal_id, year=2025, count=12):
    return [
        signal_row(signal_id, "candidate", week)
        for week in weeks(year, count)
    ]


def round_trip_input(rows):
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "normalized.csv"
        with path.open("w", newline="", encoding="utf-8") as output_file:
            writer = csv.DictWriter(
                output_file,
                fieldnames=REQUIRED_INPUT_COLUMNS,
            )
            writer.writeheader()
            writer.writerows(rows)
        return read_signal_rows(path)


class RealSignalCoverageAuditTests(unittest.TestCase):
    def test_coverage_computes_first_last_and_counts(self):
        rows = [
            signal_row(TARGET_ID, "target", "2025-W01", "0.1"),
            signal_row(TARGET_ID, "target", "2025-W02", ""),
            signal_row(TARGET_ID, "target", "2025-W03", "0.3"),
            signal_row(TARGET_ID, "target", "2025-W03", "0.4"),
            *candidate_rows("candidate_a"),
        ]

        coverage, _overlap = audit_rows(
            round_trip_input(rows),
            minimum_required_shared_weeks=8,
            max_lag_weeks=4,
        )
        target = next(
            row for row in coverage if row["signal_id"] == TARGET_ID
        )

        self.assertEqual(target["week_count"], 3)
        self.assertEqual(target["first_week"], "2025-W01")
        self.assertEqual(target["last_week"], "2025-W03")
        self.assertEqual(target["nonmissing_count"], 2)
        self.assertIn("duplicate weekly row", target["notes"])

    def test_candidate_with_enough_overlap_is_eligible(self):
        rows = [
            *target_rows(),
            *candidate_rows("candidate_a"),
        ]

        _coverage, overlap = audit_rows(
            round_trip_input(rows),
            minimum_required_shared_weeks=8,
            max_lag_weeks=4,
        )

        self.assertEqual(overlap[0]["shared_week_count"], 12)
        self.assertTrue(overlap[0]["lagged_correlation_possible"])

    def test_candidate_with_too_little_overlap_is_blocked(self):
        rows = [
            *target_rows(count=12),
            *candidate_rows("candidate_a", count=10),
        ]

        _coverage, overlap = audit_rows(
            round_trip_input(rows),
            minimum_required_shared_weeks=8,
            max_lag_weeks=4,
        )

        self.assertEqual(overlap[0]["shared_week_count"], 10)
        self.assertFalse(overlap[0]["lagged_correlation_possible"])
        self.assertIn("conservative requirement of 12", overlap[0]["notes"])

    def test_candidate_with_no_overlap_is_blocked(self):
        rows = [
            *target_rows(year=2025),
            *candidate_rows("candidate_a", year=2024),
        ]

        _coverage, overlap = audit_rows(
            round_trip_input(rows),
            minimum_required_shared_weeks=8,
            max_lag_weeks=4,
        )

        self.assertEqual(overlap[0]["shared_week_count"], 0)
        self.assertFalse(overlap[0]["lagged_correlation_possible"])
        self.assertIn("no shared weeks", overlap[0]["notes"])

    def test_multiple_candidates_are_audited(self):
        rows = [
            *target_rows(),
            *candidate_rows("candidate_a"),
            *candidate_rows("candidate_b", count=9),
            *candidate_rows("candidate_c", year=2024),
        ]

        coverage, overlap = audit_rows(
            round_trip_input(rows),
            minimum_required_shared_weeks=8,
            max_lag_weeks=4,
        )

        self.assertEqual(len(coverage), 4)
        self.assertEqual(len(overlap), 3)
        self.assertEqual(
            [row["candidate_signal_id"] for row in overlap],
            ["candidate_a", "candidate_b", "candidate_c"],
        )
        self.assertEqual(
            sum(row["lagged_correlation_possible"] for row in overlap),
            1,
        )

    def test_missing_target_raises_clear_error(self):
        rows = candidate_rows("candidate_a")

        with self.assertRaisesRegex(ValueError, "No target signal"):
            audit_rows(
                round_trip_input(rows),
                minimum_required_shared_weeks=8,
                max_lag_weeks=4,
            )

    def test_output_csvs_have_required_columns(self):
        rows = [
            *target_rows(),
            *candidate_rows("candidate_a"),
        ]
        coverage, overlap = audit_rows(
            round_trip_input(rows),
            minimum_required_shared_weeks=8,
            max_lag_weeks=4,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            coverage_path = temp_path / "coverage.csv"
            overlap_path = temp_path / "overlap.csv"
            write_csv(coverage_path, COVERAGE_COLUMNS, coverage)
            write_csv(overlap_path, OVERLAP_COLUMNS, overlap)

            with coverage_path.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as coverage_file:
                coverage_reader = csv.DictReader(coverage_file)
                coverage_rows = list(coverage_reader)
            with overlap_path.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as overlap_file:
                overlap_reader = csv.DictReader(overlap_file)
                overlap_rows = list(overlap_reader)

        self.assertEqual(coverage_reader.fieldnames, COVERAGE_COLUMNS)
        self.assertEqual(overlap_reader.fieldnames, OVERLAP_COLUMNS)
        self.assertEqual(len(coverage_rows), 2)
        self.assertEqual(len(overlap_rows), 1)


if __name__ == "__main__":
    unittest.main()
