"""Lightweight validation tests for the real EvidenceClaim builder."""

import csv
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REAL_KG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = REAL_KG_DIR.parents[1]
BUILDER_PATH = REAL_KG_DIR / "build_real_evidence_claims.py"
FIXTURE_PATH = REAL_KG_DIR / "fixtures" / "normalized_signals_fixture.csv"

CANDIDATE_ID = "real_signal_influenza_a_wastewater_activity"
CANDIDATE_NAME = "Influenza A wastewater activity"
OUTPATIENT_ILI_CANDIDATE_ID = "real_signal_outpatient_ili_activity"
OUTPATIENT_ILI_CANDIDATE_NAME = "Outpatient ILI activity"
TEST_POSITIVITY_CANDIDATE_ID = "real_signal_influenza_test_positivity"
TEST_POSITIVITY_CANDIDATE_NAME = "Influenza test positivity"
HUMIDITY_CANDIDATE_ID = "real_signal_humidity_anomaly"
HUMIDITY_CANDIDATE_NAME = "Humidity anomaly"
TARGET_ID = "real_signal_us_influenza_hospitalization_rate"
TARGET_NAME = "U.S. influenza hospitalization rate"
REGION = "United States"

INPUT_COLUMNS = [
    "signal_id",
    "signal_name",
    "region",
    "epiweek",
    "value",
    "source_dataset",
]

REQUIRED_OUTPUT_COLUMNS = {
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
}


class BuildRealEvidenceClaimsTests(unittest.TestCase):
    def run_builder(
        self,
        input_path: Path,
        output_path: Path,
        candidate_ids=None,
    ):
        command = [
            sys.executable,
            str(BUILDER_PATH),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ]
        for candidate_id in candidate_ids or []:
            command.extend(["--candidate-id", candidate_id])
        return subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )

    def write_signal_fixture(
        self,
        path: Path,
        candidate_values,
        target_values,
    ) -> None:
        rows = []
        for week, value in enumerate(candidate_values, start=1):
            rows.append(
                {
                    "signal_id": CANDIDATE_ID,
                    "signal_name": CANDIDATE_NAME,
                    "region": REGION,
                    "epiweek": f"2025-W{week:02d}",
                    "value": value,
                    "source_dataset": "candidate_test_fixture",
                }
            )

        for week, value in enumerate(target_values, start=1):
            rows.append(
                {
                    "signal_id": TARGET_ID,
                    "signal_name": TARGET_NAME,
                    "region": REGION,
                    "epiweek": f"2025-W{week:02d}",
                    "value": value,
                    "source_dataset": "target_test_fixture",
                }
            )

        with path.open("w", newline="", encoding="utf-8") as fixture_file:
            writer = csv.DictWriter(fixture_file, fieldnames=INPUT_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    def read_claims(self, path: Path):
        with path.open("r", newline="", encoding="utf-8") as output_file:
            reader = csv.DictReader(output_file)
            rows = list(reader)

        return rows, set(reader.fieldnames or [])

    def read_single_claim(self, path: Path):
        rows, columns = self.read_claims(path)
        self.assertEqual(len(rows), 1)
        return rows[0], columns

    def test_existing_fixture_produces_four_ranked_claims(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "claims.csv"
            result = self.run_builder(FIXTURE_PATH, output_path)

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            claims, columns = self.read_claims(output_path)

            self.assertTrue(REQUIRED_OUTPUT_COLUMNS.issubset(columns))
            self.assertEqual(len(claims), 4)
            self.assertEqual(
                [claim["candidate_id"] for claim in claims],
                [
                    CANDIDATE_ID,
                    OUTPATIENT_ILI_CANDIDATE_ID,
                    TEST_POSITIVITY_CANDIDATE_ID,
                    HUMIDITY_CANDIDATE_ID,
                ],
            )

            (
                wastewater_claim,
                outpatient_ili_claim,
                test_positivity_claim,
                humidity_claim,
            ) = claims
            self.assertEqual(
                wastewater_claim["candidate_name"],
                CANDIDATE_NAME,
            )
            self.assertEqual(wastewater_claim["status"], "present")
            self.assertEqual(wastewater_claim["lag_weeks"], "2")
            wastewater_score = float(wastewater_claim["score"])
            self.assertGreater(wastewater_score, 0.90)
            self.assertEqual(
                wastewater_claim["source_dataset"],
                (
                    "CDC FluSurv-NET synthetic fixture; "
                    "CDC Influenza A Wastewater synthetic fixture"
                ),
            )

            self.assertEqual(
                outpatient_ili_claim["candidate_name"],
                OUTPATIENT_ILI_CANDIDATE_NAME,
            )
            self.assertEqual(outpatient_ili_claim["status"], "present")
            self.assertEqual(outpatient_ili_claim["lag_weeks"], "1")
            outpatient_ili_score = float(outpatient_ili_claim["score"])
            self.assertGreater(outpatient_ili_score, 0.70)
            self.assertLess(outpatient_ili_score, wastewater_score)
            self.assertEqual(
                outpatient_ili_claim["source_dataset"],
                (
                    "CDC FluSurv-NET synthetic fixture; "
                    "CDC Outpatient ILI synthetic fixture"
                ),
            )

            self.assertEqual(
                test_positivity_claim["candidate_name"],
                TEST_POSITIVITY_CANDIDATE_NAME,
            )
            self.assertEqual(test_positivity_claim["status"], "present")
            self.assertEqual(test_positivity_claim["lag_weeks"], "1")
            test_positivity_score = float(test_positivity_claim["score"])
            self.assertGreater(test_positivity_score, 0.60)
            self.assertLess(test_positivity_score, outpatient_ili_score)
            self.assertEqual(
                test_positivity_claim["source_dataset"],
                (
                    "CDC FluSurv-NET synthetic fixture; "
                    "CDC Influenza Test Positivity synthetic fixture"
                ),
            )

            self.assertEqual(
                humidity_claim["candidate_name"],
                HUMIDITY_CANDIDATE_NAME,
            )
            self.assertEqual(humidity_claim["status"], "missing")
            self.assertEqual(humidity_claim["lag_weeks"], "4")
            self.assertLess(
                float(humidity_claim["score"]),
                float(humidity_claim["threshold"]),
            )
            self.assertEqual(
                humidity_claim["source_dataset"],
                (
                    "CDC FluSurv-NET synthetic fixture; "
                    "NOAA Humidity Anomaly synthetic fixture"
                ),
            )
            self.assertIn(
                "Humidity anomaly does not meet LEADING_INDICATOR_FOR evidence",
                humidity_claim["evidence_sentence"],
            )
            self.assertIn(
                TARGET_NAME,
                humidity_claim["evidence_sentence"],
            )
            self.assertIn(
                "under the configured threshold",
                humidity_claim["evidence_sentence"],
            )

            for claim in claims:
                self.assertTrue(claim["candidate_id"])
                self.assertTrue(claim["candidate_name"])
                self.assertEqual(claim["target_signal_id"], TARGET_ID)
                self.assertEqual(claim["target_signal_name"], TARGET_NAME)
                self.assertEqual(
                    claim["edge_type"],
                    "LEADING_INDICATOR_FOR",
                )
                self.assertIn(claim["status"], {"present", "missing"})
                self.assertTrue(claim["lag_weeks"])
                self.assertTrue(claim["score"])
                self.assertEqual(claim["threshold"], "0.60")
                self.assertTrue(claim["source_dataset"])
                self.assertTrue(claim["evidence_sentence"])
                if claim["status"] == "present":
                    self.assertIn(
                        "has LEADING_INDICATOR_FOR evidence",
                        claim["evidence_sentence"],
                    )
                self.assertIn(
                    "Associational screening evidence only",
                    claim["limitation"],
                )
                self.assertIn("not causal proof", claim["limitation"])

    def test_weak_correlation_produces_missing_claim(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "weak_signals.csv"
            output_path = temp_path / "claims.csv"

            self.write_signal_fixture(
                input_path,
                candidate_values=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                target_values=[3, 8, 1, 9, 4, 10, 2, 7, 5, 6],
            )
            result = self.run_builder(
                input_path,
                output_path,
                candidate_ids=[CANDIDATE_ID],
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            claim, _columns = self.read_single_claim(output_path)

            self.assertEqual(claim["status"], "missing")
            self.assertEqual(claim["edge_type"], "LEADING_INDICATOR_FOR")
            self.assertLess(float(claim["score"]), float(claim["threshold"]))

    def test_insufficient_data_produces_blank_lag_and_score(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "short_signals.csv"
            output_path = temp_path / "claims.csv"

            self.write_signal_fixture(
                input_path,
                candidate_values=[1.0, 2.0, 3.0, 4.0],
                target_values=[0.5, 1.0, 2.0, 3.0],
            )
            result = self.run_builder(
                input_path,
                output_path,
                candidate_ids=[CANDIDATE_ID],
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            claim, _columns = self.read_single_claim(output_path)

            self.assertEqual(claim["status"], "insufficient_data")
            self.assertEqual(claim["lag_weeks"], "")
            self.assertEqual(claim["score"], "")

    def test_missing_required_columns_returns_nonzero(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            input_path = temp_path / "missing_columns.csv"
            output_path = temp_path / "claims.csv"

            with input_path.open("w", newline="", encoding="utf-8") as fixture_file:
                writer = csv.DictWriter(
                    fixture_file,
                    fieldnames=[
                        "signal_id",
                        "signal_name",
                        "region",
                        "epiweek",
                        "value",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "signal_id": CANDIDATE_ID,
                        "signal_name": CANDIDATE_NAME,
                        "region": REGION,
                        "epiweek": "2025-W01",
                        "value": 1.0,
                    }
                )

            result = self.run_builder(input_path, output_path)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source_dataset", result.stderr)
            self.assertFalse(output_path.exists())


if __name__ == "__main__":
    unittest.main()
