"""Tests for weekly normalization of downloaded influenza snapshots."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.real_kg.normalize_real_influenza_signals import (
    CLINICAL_FILE,
    FLUSURV_FILE,
    HOSPITAL_FILE,
    ILI_FILE,
    OUTPUT_COLUMNS,
    WASTEWATER_FILE,
    base_signal_row,
    build_normalized_rows,
    extract_delphi_signal,
    extract_flusurv_signal,
    extract_hospital_signal,
    extract_wastewater_signal,
    normalize_signal_rows,
    write_rows,
)


def extract_ili(rows):
    return extract_delphi_signal(
        rows,
        signal_id="real_signal_outpatient_ili_activity",
        signal_name="Outpatient ILI activity",
        source_name="delphi_fluview_ili",
        source_dataset="Delphi Epidata FluView ILINet / CDC FluView",
        preferred_columns=["wili", "ili"],
    )


def extract_clinical(rows):
    return extract_delphi_signal(
        rows,
        signal_id="real_signal_influenza_test_positivity",
        signal_name="Influenza test positivity",
        source_name="delphi_fluview_clinical",
        source_dataset="Delphi Epidata FluView Clinical / CDC FluView",
        preferred_columns=["percent_positive", "percent_a"],
    )


def simple_signal_row(signal_id, week, raw_value):
    year = int(week[:4])
    week_number = int(week[-2:])
    from datetime import date

    monday = date.fromisocalendar(year, week_number, 1)
    return base_signal_row(
        signal_id=signal_id,
        signal_name=signal_id,
        signal_role="candidate",
        source_name="test",
        source_dataset="test",
        week=week,
        monday=monday,
        raw_value=raw_value,
        units="test units",
        aggregation_method="test",
        raw_row_count=1,
        notes="Test row.",
    )


class NormalizeRealInfluenzaSignalsTests(unittest.TestCase):
    def test_hospital_target_selects_national_rows(self):
        rows = [
            {
                "jurisdiction": "CA",
                "weekendingdate": "2025-01-11",
                "totalconfflunewadmper100k": "2.0",
            },
            {
                "jurisdiction": "US",
                "weekendingdate": "2025-01-11",
                "totalconfflunewadmper100k": "7.5",
            },
        ]

        output = extract_hospital_signal(rows)

        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["raw_value"], 7.5)
        self.assertEqual(output[0]["raw_row_count"], 1)
        self.assertEqual(
            output[0]["aggregation_method"],
            "select national / United States rows",
        )

    def test_hospital_falls_back_to_mean_across_states(self):
        rows = [
            {
                "jurisdiction": "CA",
                "weekendingdate": "2025-01-11",
                "totalconfflunewadmper100k": "2.0",
            },
            {
                "jurisdiction": "NY",
                "weekendingdate": "2025-01-11",
                "totalconfflunewadmper100k": "4.0",
            },
        ]

        output = extract_hospital_signal(rows)

        self.assertEqual(output[0]["raw_value"], 3.0)
        self.assertEqual(output[0]["raw_row_count"], 2)
        self.assertIn("No national row", output[0]["notes"])

    def test_flusurv_target_extracts_rate_overall(self):
        rows = [
            {
                "location": "network_all",
                "epiweek": 202440,
                "rate_overall": "1.25",
                "rate_flu_a": "0.8",
            }
        ]

        output = extract_flusurv_signal(rows)

        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["raw_value"], 1.25)
        self.assertEqual(output[0]["week"], "2024-W40")
        self.assertEqual(output[0]["date"], "2024-09-30")
        self.assertEqual(output[0]["signal_role"], "target")
        self.assertEqual(output[0]["source_name"], "delphi_flusurv")
        self.assertEqual(
            output[0]["region"],
            "United States / FluSurv-NET catchment",
        )
        self.assertIn("network_all", output[0]["notes"])
        self.assertIn("catchment-based", output[0]["notes"])

    def test_flusurv_target_falls_back_to_rate_flu_a(self):
        rows = [
            {
                "location": "CA",
                "epiweek": 202440,
                "rate_overall": "",
                "rate_flu_a": "0.65",
            }
        ]

        output = extract_flusurv_signal(rows)

        self.assertEqual(output[0]["raw_value"], 0.65)
        self.assertIn("rate_flu_a", output[0]["notes"])
        self.assertEqual(
            output[0]["units"],
            "hospitalizations per 100,000",
        )

    def test_wastewater_uses_weekly_site_median_and_fallback(self):
        rows = [
            {
                "sample_collect_date": "2025-01-06",
                "pcr_target_avg_conc_lin": "10",
            },
            {
                "sample_collect_date": "2025-01-08",
                "pcr_target_avg_conc_lin": "30",
            },
            {
                "sample_collect_date": "2025-01-09",
                "pcr_target_avg_conc_lin": "",
                "pcr_target_flowpop_lin": "20",
            },
        ]

        output = extract_wastewater_signal(rows)

        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["week"], "2025-W02")
        self.assertEqual(output[0]["raw_value"], 20.0)
        self.assertEqual(output[0]["raw_row_count"], 3)
        self.assertIn("pcr_target_flowpop_lin", output[0]["notes"])

    def test_delphi_ili_extracts_national_epiweek(self):
        rows = [
            {"region": "nat", "epiweek": 202440, "wili": 2.5, "ili": 1.5},
            {"region": "state", "epiweek": 202440, "wili": 9.9},
        ]

        output = extract_ili(rows)

        self.assertEqual(len(output), 1)
        self.assertEqual(output[0]["week"], "2024-W40")
        self.assertEqual(output[0]["date"], "2024-09-30")
        self.assertEqual(output[0]["raw_value"], 2.5)
        self.assertIn("wili", output[0]["notes"])

    def test_delphi_clinical_extracts_percent_positive(self):
        rows = [
            {
                "region": "nat",
                "epiweek": 202440,
                "percent_positive": 4.2,
                "percent_a": 3.8,
            }
        ]

        output = extract_clinical(rows)

        self.assertEqual(output[0]["raw_value"], 4.2)
        self.assertEqual(output[0]["units"], "percent")
        self.assertIn("percent_positive", output[0]["notes"])

    def test_min_max_normalization_is_per_signal(self):
        rows = [
            simple_signal_row("signal_a", "2025-W01", 10.0),
            simple_signal_row("signal_a", "2025-W02", 20.0),
            simple_signal_row("signal_b", "2025-W01", 100.0),
            simple_signal_row("signal_b", "2025-W02", 300.0),
        ]

        normalize_signal_rows(rows)

        self.assertEqual(
            [row["normalized_value"] for row in rows],
            [0.0, 1.0, 0.0, 1.0],
        )

    def test_constant_signal_normalizes_to_zero_with_note(self):
        rows = [
            simple_signal_row("constant", "2025-W01", 5.0),
            simple_signal_row("constant", "2025-W02", 5.0),
        ]

        normalize_signal_rows(rows)

        self.assertTrue(
            all(row["normalized_value"] == 0.0 for row in rows)
        )
        self.assertTrue(
            all("Constant signal" in row["notes"] for row in rows)
        )

    def test_invalid_and_missing_numeric_values_are_skipped(self):
        rows = [
            {
                "region": "nat",
                "epiweek": 202440,
                "wili": "not-a-number",
                "ili": "",
            },
            {
                "region": "nat",
                "epiweek": 202441,
                "wili": "2.0",
            },
            {
                "region": "nat",
                "epiweek": 202442,
                "wili": None,
                "ili": "3.0",
            },
        ]

        output = extract_ili(rows)

        self.assertEqual(len(output), 2)
        self.assertEqual(
            [row["week"] for row in output],
            ["2024-W41", "2024-W42"],
        )

    def test_output_csv_has_required_columns(self):
        rows = [simple_signal_row("signal", "2025-W01", 5.0)]
        normalize_signal_rows(rows)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "normalized.csv"
            write_rows(path, rows)
            with path.open("r", newline="", encoding="utf-8") as input_file:
                reader = csv.DictReader(input_file)
                written_rows = list(reader)

        self.assertEqual(reader.fieldnames, OUTPUT_COLUMNS)
        self.assertEqual(len(written_rows), 1)

    def test_full_build_reads_four_sources_and_sorts_rows(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_dir = Path(temp_dir)
            payloads = {
                HOSPITAL_FILE: [
                    {
                        "jurisdiction": "US",
                        "weekendingdate": "2025-01-11",
                        "totalconfflunewadmper100k": "2.0",
                    },
                    {
                        "jurisdiction": "US",
                        "weekendingdate": "2025-01-18",
                        "totalconfflunewadmper100k": "4.0",
                    },
                ],
                WASTEWATER_FILE: [
                    {
                        "sample_collect_date": "2025-01-06",
                        "pcr_target_avg_conc_lin": "10",
                    },
                    {
                        "sample_collect_date": "2025-01-13",
                        "pcr_target_avg_conc_lin": "20",
                    },
                ],
                ILI_FILE: {
                    "result": 1,
                    "epidata": [
                        {"region": "nat", "epiweek": 202502, "wili": 1.0},
                        {"region": "nat", "epiweek": 202503, "wili": 2.0},
                    ],
                },
                CLINICAL_FILE: {
                    "result": 1,
                    "epidata": [
                        {
                            "region": "nat",
                            "epiweek": 202502,
                            "percent_positive": 3.0,
                        },
                        {
                            "region": "nat",
                            "epiweek": 202503,
                            "percent_positive": 5.0,
                        },
                    ],
                },
            }
            for filename, payload in payloads.items():
                with (raw_dir / filename).open(
                    "w",
                    encoding="utf-8",
                ) as output_file:
                    json.dump(payload, output_file)

            rows = build_normalized_rows(raw_dir)

        self.assertEqual(len(rows), 8)
        self.assertEqual(len({row["signal_id"] for row in rows}), 4)
        self.assertEqual(
            rows,
            sorted(
                rows,
                key=lambda row: (
                    row["week"],
                    row["signal_role"],
                    row["signal_id"],
                ),
            ),
        )

    def test_full_build_prefers_flusurv_target_over_socrata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            raw_dir = Path(temp_dir)
            payloads = {
                FLUSURV_FILE: {
                    "result": 1,
                    "epidata": [
                        {
                            "location": "network_all",
                            "epiweek": 202440,
                            "rate_overall": 1.2,
                        },
                        {
                            "location": "network_all",
                            "epiweek": 202441,
                            "rate_overall": 1.8,
                        },
                    ],
                },
                HOSPITAL_FILE: [
                    {
                        "jurisdiction": "US",
                        "weekendingdate": "2024-10-05",
                        "totalconfflunewadmper100k": "99.0",
                    }
                ],
                WASTEWATER_FILE: [
                    {
                        "sample_collect_date": "2024-09-30",
                        "pcr_target_avg_conc_lin": "10",
                    }
                ],
                ILI_FILE: {
                    "result": 1,
                    "epidata": [
                        {"region": "nat", "epiweek": 202440, "wili": 2.0}
                    ],
                },
                CLINICAL_FILE: {
                    "result": 1,
                    "epidata": [
                        {
                            "region": "nat",
                            "epiweek": 202440,
                            "percent_positive": 4.0,
                        }
                    ],
                },
            }
            for filename, payload in payloads.items():
                with (raw_dir / filename).open(
                    "w",
                    encoding="utf-8",
                ) as output_file:
                    json.dump(payload, output_file)

            rows = build_normalized_rows(raw_dir)

        target_rows = [
            row for row in rows if row["signal_role"] == "target"
        ]
        self.assertEqual(len({row["signal_id"] for row in rows}), 4)
        self.assertEqual(len(target_rows), 2)
        self.assertTrue(
            all(row["source_name"] == "delphi_flusurv" for row in target_rows)
        )
        self.assertTrue(
            all(
                row["signal_id"]
                == "real_signal_us_influenza_hospitalization_rate_flusurv"
                for row in target_rows
            )
        )
        self.assertNotIn(
            "real_signal_us_influenza_hospital_admission_rate",
            {row["signal_id"] for row in rows},
        )


if __name__ == "__main__":
    unittest.main()
