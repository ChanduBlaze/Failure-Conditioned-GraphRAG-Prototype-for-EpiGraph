"""Tests for empirical influenza lag scanning and EvidenceClaims."""

import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from scripts.real_kg.build_empirical_influenza_evidence_claims import (
    CANDIDATE_IDS,
    CASE_ID,
    CLAIM_COLUMNS,
    LAG_SCAN_COLUMNS,
    TARGET_SIGNAL_ID,
    build_empirical_outputs,
    compute_lag_scan,
    pearson_correlation,
    select_best_lag,
    write_csv,
)


TARGET_NAME = "U.S. influenza hospitalization rate from FluSurv-NET"
CANDIDATE_NAMES = {
    "real_signal_influenza_a_wastewater_concentration": (
        "Influenza A wastewater concentration"
    ),
    "real_signal_outpatient_ili_activity": "Outpatient ILI activity",
    "real_signal_influenza_test_positivity": (
        "Influenza test positivity"
    ),
}

INPUT_COLUMNS = [
    "case_id",
    "signal_id",
    "signal_name",
    "signal_role",
    "source_dataset",
    "region",
    "week",
    "normalized_value",
]


def week_label(index):
    monday = date(2024, 9, 30) + timedelta(weeks=index)
    iso_year, iso_week, _weekday = monday.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def normalized_rows(candidate_values, target_values):
    rows = []
    for index, value in enumerate(target_values):
        rows.append(
            {
                "case_id": CASE_ID,
                "signal_id": TARGET_SIGNAL_ID,
                "signal_name": TARGET_NAME,
                "signal_role": "target",
                "source_dataset": (
                    "Delphi Epidata FluSurv / CDC FluSurv-NET"
                ),
                "region": "United States / FluSurv-NET catchment",
                "week": week_label(index),
                "normalized_value": str(value),
            }
        )
    # Deliberately reverse source order to verify deterministic candidate order.
    for candidate_id in reversed(CANDIDATE_IDS):
        values = candidate_values[candidate_id]
        for index, value in enumerate(values):
            rows.append(
                {
                    "case_id": CASE_ID,
                    "signal_id": candidate_id,
                    "signal_name": CANDIDATE_NAMES[candidate_id],
                    "signal_role": "candidate",
                    "source_dataset": f"source for {candidate_id}",
                    "region": "United States",
                    "week": week_label(index),
                    "normalized_value": str(value),
                }
            )
    return rows


def all_candidates(values):
    return {candidate_id: list(values) for candidate_id in CANDIDATE_IDS}


class BuildEmpiricalInfluenzaEvidenceClaimsTests(unittest.TestCase):
    def test_pearson_correlation_is_computed_directly(self):
        self.assertAlmostEqual(
            pearson_correlation([1, 2, 3, 4], [2, 4, 6, 8]),
            1.0,
        )
        self.assertAlmostEqual(
            pearson_correlation([1, 2, 3, 4], [8, 6, 4, 2]),
            -1.0,
        )

    def test_lag_one_can_beat_lag_zero(self):
        candidate_sequence = [
            0.10,
            0.72,
            0.21,
            0.85,
            0.34,
            0.93,
            0.04,
            0.61,
            0.42,
            0.53,
            0.99,
            0.16,
            0.81,
            0.28,
        ]
        target_sequence = [0.47, *candidate_sequence[:-1]]
        start = date(2024, 9, 30)
        candidate = {
            start + timedelta(weeks=index): value
            for index, value in enumerate(candidate_sequence)
        }
        target = {
            start + timedelta(weeks=index): value
            for index, value in enumerate(target_sequence)
        }

        scan = compute_lag_scan(candidate, target, 8, 4)
        best = select_best_lag(scan)

        self.assertIsNotNone(best)
        self.assertEqual(best["lag_weeks"], 1)
        self.assertAlmostEqual(best["pearson_correlation"], 1.0)
        self.assertGreater(
            best["pearson_correlation"],
            scan[0]["pearson_correlation"],
        )

    def test_present_status_when_best_correlation_meets_threshold(self):
        candidate = [
            0.10,
            0.72,
            0.21,
            0.85,
            0.34,
            0.93,
            0.04,
            0.61,
            0.42,
            0.53,
            0.99,
            0.16,
            0.81,
            0.28,
        ]
        target = [0.47, *candidate[:-1]]

        claims, _scan = build_empirical_outputs(
            normalized_rows(all_candidates(candidate), target)
        )

        self.assertTrue(all(claim["status"] == "present" for claim in claims))
        self.assertTrue(all(claim["lag_weeks"] == 1 for claim in claims))
        self.assertTrue(
            all(float(claim["score"]) >= 0.60 for claim in claims)
        )
        self.assertIn("empirical LEADING_INDICATOR_FOR", claims[0][
            "evidence_sentence"
        ])

    def test_missing_status_when_best_correlation_is_below_threshold(self):
        candidate = [index / 19 for index in range(20)]
        target = [float(index % 2) for index in range(20)]

        claims, _scan = build_empirical_outputs(
            normalized_rows(all_candidates(candidate), target)
        )

        self.assertTrue(all(claim["status"] == "missing" for claim in claims))
        self.assertTrue(
            all(float(claim["score"]) < 0.60 for claim in claims)
        )
        self.assertIn(
            "does not meet empirical LEADING_INDICATOR_FOR",
            claims[0]["evidence_sentence"],
        )

    def test_insufficient_status_below_minimum_paired_weeks(self):
        candidate = [0.1, 0.7, 0.2, 0.8, 0.3, 0.9]
        target = [0.0, 0.1, 0.7, 0.2, 0.8, 0.3]

        claims, _scan = build_empirical_outputs(
            normalized_rows(all_candidates(candidate), target),
            minimum_paired_weeks=8,
        )

        self.assertTrue(
            all(claim["status"] == "insufficient" for claim in claims)
        )
        self.assertTrue(all(claim["lag_weeks"] == "" for claim in claims))
        self.assertTrue(all(claim["score"] == "" for claim in claims))
        self.assertIn(
            "insufficient overlapping data",
            claims[0]["evidence_sentence"],
        )

    def test_lag_scan_contains_every_lag_for_every_candidate(self):
        values = [index / 11 for index in range(12)]
        _claims, scan = build_empirical_outputs(
            normalized_rows(all_candidates(values), values)
        )

        self.assertEqual(len(scan), 15)
        for candidate_id in CANDIDATE_IDS:
            candidate_lags = [
                row["lag_weeks"]
                for row in scan
                if row["candidate_id"] == candidate_id
            ]
            self.assertEqual(candidate_lags, [0, 1, 2, 3, 4])

    def test_evidence_claim_csv_has_required_columns(self):
        values = [index / 11 for index in range(12)]
        claims, scan = build_empirical_outputs(
            normalized_rows(all_candidates(values), values)
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            claims_path = temp_path / "claims.csv"
            scan_path = temp_path / "scan.csv"
            write_csv(claims_path, claims, CLAIM_COLUMNS)
            write_csv(scan_path, scan, LAG_SCAN_COLUMNS)
            with claims_path.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as input_file:
                claims_reader = csv.DictReader(input_file)
                written_claims = list(claims_reader)
            with scan_path.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as input_file:
                scan_reader = csv.DictReader(input_file)
                written_scan = list(scan_reader)

        self.assertEqual(claims_reader.fieldnames, CLAIM_COLUMNS)
        self.assertEqual(scan_reader.fieldnames, LAG_SCAN_COLUMNS)
        self.assertEqual(len(written_claims), 3)
        self.assertEqual(len(written_scan), 15)

    def test_candidate_order_is_deterministic(self):
        values = [index / 11 for index in range(12)]
        claims, scan = build_empirical_outputs(
            normalized_rows(all_candidates(values), values)
        )

        self.assertEqual(
            [claim["candidate_id"] for claim in claims],
            CANDIDATE_IDS,
        )
        self.assertEqual(
            [
                scan[index]["candidate_id"]
                for index in range(0, len(scan), 5)
            ],
            CANDIDATE_IDS,
        )


if __name__ == "__main__":
    unittest.main()
