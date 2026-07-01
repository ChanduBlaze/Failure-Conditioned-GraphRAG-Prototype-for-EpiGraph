"""Tests for the combined real-method comparison summary."""

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.real_kg.summarize_real_method_comparison import (
    METHOD_ORDER,
    RESULT_COLUMNS,
    SUMMARY_COLUMNS,
    build_comparison,
    write_csv,
)


REAL_KG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = REAL_KG_DIR.parents[1]
SCRIPT_PATH = REAL_KG_DIR / "summarize_real_method_comparison.py"
EDGE_TYPE = "LEADING_INDICATOR_FOR"


def make_cases():
    return [
        {
            "id": f"real_case_{index:03d}",
            "expected_present_edges": [EDGE_TYPE] if index < 4 else [],
            "expected_missing_edges": [] if index < 4 else [EDGE_TYPE],
        }
        for index in range(1, 5)
    ]


def make_rows(method):
    rows = []
    for index in range(1, 5):
        humidity = index == 4
        llm_failure = method == "llm_only" and humidity
        if humidity and method != "llm_only":
            mentioned_edges = ""
            missing_edges = EDGE_TYPE
        else:
            mentioned_edges = EDGE_TYPE
            missing_edges = ""

        rows.append(
            {
                "case_id": f"real_case_{index:03d}",
                "method": method,
                "predicted_candidate_id": f"candidate_{index}",
                "candidate_correct": True,
                "mentioned_evidence_edges": mentioned_edges,
                "identified_missing_edges": missing_edges,
                "status_correct": not llm_failure,
                "present_edge_recall": 1.0,
                "missing_edge_recall": 0.0 if llm_failure else 1.0,
                "lag_correct": False if method == "llm_only" else True,
                "score_meets_minimum": not llm_failure,
                "must_not_include_violations": 0,
                "notes": "Synthetic comparison row.",
            }
        )
    return rows


def make_comparison():
    return build_comparison(
        make_cases(),
        make_rows("llm_only"),
        make_rows("text_rag"),
        make_rows("graphrag_context"),
    )


def summary_by_method(summary):
    return {row["method"]: row for row in summary}


class RealMethodComparisonTests(unittest.TestCase):
    def test_combined_output_has_twelve_rows_in_method_order(self):
        combined, _summary = make_comparison()

        self.assertEqual(len(combined), 12)
        self.assertEqual(
            [row["method"] for row in combined],
            [
                method
                for method in METHOD_ORDER
                for _case_index in range(4)
            ],
        )

    def test_summary_has_three_methods_in_deterministic_order(self):
        _combined, summary = make_comparison()

        self.assertEqual(len(summary), 3)
        self.assertEqual(
            [row["method"] for row in summary],
            METHOD_ORDER,
        )

    def test_llm_only_summary_matches_expected_metrics(self):
        _combined, summary = make_comparison()
        row = summary_by_method(summary)["llm_only"]

        self.assertEqual(row["case_count"], 4)
        self.assertEqual(row["candidate_accuracy"], 1.0)
        self.assertEqual(row["avg_present_edge_recall"], 1.0)
        self.assertEqual(row["avg_missing_edge_recall"], 0.75)
        self.assertEqual(row["status_accuracy"], 0.75)
        self.assertEqual(row["lag_accuracy"], 0.0)
        self.assertEqual(row["score_threshold_accuracy"], 0.75)
        self.assertEqual(row["false_positive_edge_claims"], 1)
        self.assertEqual(row["total_must_not_include_violations"], 0)

    def assert_perfect_retrieval_summary(self, row):
        self.assertEqual(row["case_count"], 4)
        self.assertEqual(row["candidate_accuracy"], 1.0)
        self.assertEqual(row["avg_present_edge_recall"], 1.0)
        self.assertEqual(row["avg_missing_edge_recall"], 1.0)
        self.assertEqual(row["status_accuracy"], 1.0)
        self.assertEqual(row["lag_accuracy"], 1.0)
        self.assertEqual(row["score_threshold_accuracy"], 1.0)
        self.assertEqual(row["false_positive_edge_claims"], 0)
        self.assertEqual(row["total_must_not_include_violations"], 0)

    def test_text_rag_summary_is_perfect(self):
        _combined, summary = make_comparison()

        self.assert_perfect_retrieval_summary(
            summary_by_method(summary)["text_rag"]
        )

    def test_graphrag_context_summary_is_perfect(self):
        _combined, summary = make_comparison()

        self.assert_perfect_retrieval_summary(
            summary_by_method(summary)["graphrag_context"]
        )

    def test_output_csvs_have_required_columns(self):
        combined, summary = make_comparison()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            combined_path = temp_path / "combined.csv"
            summary_path = temp_path / "summary.csv"
            write_csv(combined_path, RESULT_COLUMNS, combined)
            write_csv(summary_path, SUMMARY_COLUMNS, summary)

            with combined_path.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as combined_file:
                combined_reader = csv.DictReader(combined_file)
                combined_rows = list(combined_reader)
            with summary_path.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as summary_file:
                summary_reader = csv.DictReader(summary_file)
                summary_rows = list(summary_reader)

            self.assertEqual(combined_reader.fieldnames, RESULT_COLUMNS)
            self.assertEqual(summary_reader.fieldnames, SUMMARY_COLUMNS)
            self.assertEqual(len(combined_rows), 12)
            self.assertEqual(len(summary_rows), 3)

    def test_cli_writes_both_outputs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            cases_path = temp_path / "cases.json"
            input_paths = {
                "llm_only": temp_path / "llm.csv",
                "text_rag": temp_path / "text.csv",
                "graphrag_context": temp_path / "graph.csv",
            }
            combined_path = temp_path / "combined.csv"
            summary_path = temp_path / "summary.csv"

            with cases_path.open("w", encoding="utf-8") as cases_file:
                json.dump(make_cases(), cases_file)
            for method, input_path in input_paths.items():
                write_csv(
                    input_path,
                    RESULT_COLUMNS,
                    make_rows(method),
                )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    "--cases",
                    str(cases_path),
                    "--llm-results",
                    str(input_paths["llm_only"]),
                    "--text-results",
                    str(input_paths["text_rag"]),
                    "--graph-results",
                    str(input_paths["graphrag_context"]),
                    "--combined-output",
                    str(combined_path),
                    "--summary-output",
                    str(summary_path),
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(combined_path.is_file())
            self.assertTrue(summary_path.is_file())
            self.assertIn(
                "Methods summarized: llm_only, text_rag, graphrag_context",
                result.stdout,
            )


if __name__ == "__main__":
    unittest.main()
