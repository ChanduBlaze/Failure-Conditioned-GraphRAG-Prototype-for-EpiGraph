"""Tests for empirical influenza lag scanning and EvidenceClaims."""

import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from scripts.real_kg.build_empirical_influenza_evidence_claims import (
    CANDIDATE_IDS,
    CASE_ID,
    CLAIM_COLUMNS,
    LAG_SCAN_COLUMNS,
    NEGATIVE_CONTROL_ID,
    NEGATIVE_CONTROL_LIMITATION,
    TARGET_SIGNAL_ID,
    build_empirical_outputs,
    build_negative_control_signal,
    collect_signals,
    compute_lag_scan,
    parse_args,
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

SMOOTH_SEQUENCE = [
    0.02,
    0.05,
    0.10,
    0.18,
    0.30,
    0.48,
    0.68,
    0.88,
    1.00,
    0.91,
    0.74,
    0.55,
    0.37,
    0.23,
    0.13,
    0.07,
]

LOW_AUTOCORRELATION_SEQUENCE = [
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
    0.65,
    0.02,
    0.44,
    0.76,
    0.19,
    0.57,
]

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
        self.assertIn(
            "best positive lag = 1 weeks",
            claims[0]["evidence_sentence"],
        )
        self.assertIn(
            "Lag 0 was retained only as a concurrent-association diagnostic.",
            claims[0]["limitation"],
        )

    def test_lag_zero_is_excluded_when_it_has_highest_correlation(self):
        start = date(2024, 9, 30)
        values = {
            start + timedelta(weeks=index): value
            for index, value in enumerate(SMOOTH_SEQUENCE)
        }

        scan = compute_lag_scan(values, values, 8, 4)
        best = select_best_lag(scan)

        self.assertAlmostEqual(scan[0]["pearson_correlation"], 1.0)
        self.assertTrue(scan[0]["eligible"])
        self.assertEqual(best["lag_weeks"], 1)
        self.assertLess(
            best["pearson_correlation"],
            scan[0]["pearson_correlation"],
        )
        self.assertIn(
            "excluded from LEADING_INDICATOR_FOR best-lag selection",
            scan[0]["notes"],
        )

    def test_positive_lag_one_selected_when_lag_zero_is_higher(self):
        claims, scan = build_empirical_outputs(
            normalized_rows(
                all_candidates(SMOOTH_SEQUENCE),
                SMOOTH_SEQUENCE,
            )
        )

        self.assertTrue(all(claim["lag_weeks"] == 1 for claim in claims))
        self.assertTrue(all(claim["status"] == "present" for claim in claims))
        lag_zero = [
            row for row in scan if row["lag_weeks"] == 0
        ]
        lag_one = [
            row for row in scan if row["lag_weeks"] == 1
        ]
        self.assertTrue(
            all(
                float(zero["pearson_correlation"])
                > float(one["pearson_correlation"])
                for zero, one in zip(lag_zero, lag_one)
            )
        )
        self.assertTrue(
            all(
                row["notes"]
                == "Eligible for leading-indicator best-lag selection."
                for row in lag_one
            )
        )

    def test_missing_status_when_best_correlation_is_below_threshold(self):
        claims, _scan = build_empirical_outputs(
            normalized_rows(
                all_candidates(LOW_AUTOCORRELATION_SEQUENCE),
                LOW_AUTOCORRELATION_SEQUENCE,
            )
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
        candidate = [0.1, 0.7, 0.2, 0.8, 0.3, 0.9, 0.4, 0.6]
        target = list(candidate)

        claims, scan = build_empirical_outputs(
            normalized_rows(all_candidates(candidate), target),
            minimum_paired_weeks=8,
        )

        lag_zero = [row for row in scan if row["lag_weeks"] == 0]
        self.assertTrue(all(row["eligible"] for row in lag_zero))
        self.assertTrue(
            all(claim["status"] == "insufficient" for claim in claims)
        )
        self.assertTrue(all(claim["lag_weeks"] == "" for claim in claims))
        self.assertTrue(all(claim["score"] == "" for claim in claims))
        self.assertTrue(
            all(claim["paired_week_count"] == 7 for claim in claims)
        )
        self.assertIn(
            "insufficient overlapping data",
            claims[0]["evidence_sentence"],
        )

    def test_cli_accepts_minimum_lead_weeks(self):
        with patch(
            "sys.argv",
            [
                "build_empirical_influenza_evidence_claims.py",
                "--minimum-lead-weeks",
                "2",
            ],
        ):
            args = parse_args()

        self.assertEqual(args.minimum_lead_weeks, 2)

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
        lag_zero_rows = [
            row for row in scan if row["lag_weeks"] == 0
        ]
        self.assertEqual(len(lag_zero_rows), 3)
        self.assertTrue(
            all(
                "minimum_lead_weeks = 1" in row["notes"]
                for row in lag_zero_rows
            )
        )

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

    def test_default_does_not_include_negative_control(self):
        claims, scan = build_empirical_outputs(
            normalized_rows(
                all_candidates(SMOOTH_SEQUENCE),
                SMOOTH_SEQUENCE,
            )
        )

        self.assertEqual(len(claims), 3)
        self.assertNotIn(
            NEGATIVE_CONTROL_ID,
            {claim["candidate_id"] for claim in claims},
        )
        self.assertNotIn(
            NEGATIVE_CONTROL_ID,
            {row["candidate_id"] for row in scan},
        )

    def test_include_negative_control_adds_one_claim(self):
        claims, _scan = build_empirical_outputs(
            normalized_rows(
                all_candidates(SMOOTH_SEQUENCE),
                SMOOTH_SEQUENCE,
            ),
            include_negative_control=True,
        )

        self.assertEqual(len(claims), 4)
        self.assertEqual(claims[-1]["candidate_id"], NEGATIVE_CONTROL_ID)
        self.assertEqual(
            sum(
                claim["candidate_id"] == NEGATIVE_CONTROL_ID
                for claim in claims
            ),
            1,
        )

    def test_negative_control_uses_same_lagged_pearson_rule(self):
        rows = normalized_rows(
            all_candidates(SMOOTH_SEQUENCE),
            SMOOTH_SEQUENCE,
        )
        signals = collect_signals(rows)
        target = signals[TARGET_SIGNAL_ID]
        control = build_negative_control_signal(target)
        expected_scan = compute_lag_scan(
            control["values"],
            target["values"],
            8,
            4,
            1,
        )
        expected_best = select_best_lag(expected_scan, 1)

        claims, _scan = build_empirical_outputs(
            rows,
            include_negative_control=True,
        )
        claim = claims[-1]

        self.assertIsNotNone(expected_best)
        self.assertEqual(
            claim["lag_weeks"],
            expected_best["lag_weeks"],
        )
        self.assertAlmostEqual(
            float(claim["score"]),
            expected_best["pearson_correlation"],
            places=6,
        )
        self.assertEqual(
            claim["status"],
            (
                "present"
                if expected_best["pearson_correlation"] >= 0.60
                else "missing"
            ),
        )

    def test_negative_control_is_not_present_and_appears_in_lag_scan(self):
        claims, scan = build_empirical_outputs(
            normalized_rows(
                all_candidates(SMOOTH_SEQUENCE),
                SMOOTH_SEQUENCE,
            ),
            include_negative_control=True,
        )
        claim = claims[-1]
        control_scan = [
            row for row in scan if row["candidate_id"] == NEGATIVE_CONTROL_ID
        ]

        self.assertIn(claim["status"], {"missing", "insufficient"})
        self.assertEqual(
            [row["lag_weeks"] for row in control_scan],
            [0, 1, 2, 3, 4],
        )

    def test_negative_control_limitation_is_explicit(self):
        claims, _scan = build_empirical_outputs(
            normalized_rows(
                all_candidates(SMOOTH_SEQUENCE),
                SMOOTH_SEQUENCE,
            ),
            include_negative_control=True,
        )

        self.assertIn(NEGATIVE_CONTROL_LIMITATION, claims[-1]["limitation"])
        self.assertIn(
            "deterministic permutation",
            claims[-1]["limitation"],
        )
        self.assertIn(
            "not a real epidemiological driver",
            claims[-1]["limitation"],
        )

    def test_cli_accepts_include_negative_control(self):
        with patch(
            "sys.argv",
            [
                "build_empirical_influenza_evidence_claims.py",
                "--include-negative-control",
            ],
        ):
            args = parse_args()

        self.assertTrue(args.include_negative_control)


if __name__ == "__main__":
    unittest.main()
