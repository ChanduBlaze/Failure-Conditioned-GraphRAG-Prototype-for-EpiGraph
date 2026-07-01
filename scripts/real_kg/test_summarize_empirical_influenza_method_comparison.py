"""Tests for the empirical influenza method-comparison summary."""

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.real_kg.summarize_empirical_influenza_method_comparison import (
    ARTIFACT_COLUMNS,
    LLM_COLUMNS,
    METHOD_ORDER,
    OUTPUT_COLUMNS,
    build_comparison,
    read_summary,
    write_comparison,
)


def make_llm_rows():
    return [
        {
            "method": "empirical_llm_only",
            "case_count": "4",
            "status_accuracy": "0.75",
            "avg_present_edge_recall": "1.0",
            "avg_missing_edge_recall": "0.75",
            "lag_accuracy": "0.0",
            "false_positive_edge_claims": "1",
            "score_claims": "0",
            "threshold_claims": "0",
            "total_must_not_include_violations": "1",
        }
    ]


def make_artifact_rows():
    return [
        {
            "method": method,
            "case_count": "4",
            "status_accuracy": "1.0",
            "avg_present_edge_recall": "1.0",
            "avg_missing_edge_recall": "1.0",
            "lag_accuracy": "1.0",
            "score_accuracy": "1.0",
            "threshold_accuracy": "1.0",
            "paired_week_count_accuracy": "1.0",
            "total_must_not_include_violations": "0",
        }
        for method in (
            "empirical_text_rag",
            "empirical_graphrag_context",
        )
    ]


def write_rows(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


class SummarizeEmpiricalInfluenzaMethodComparisonTests(unittest.TestCase):
    def test_writes_exactly_three_rows(self):
        comparison = build_comparison(
            make_llm_rows(),
            make_artifact_rows(),
        )

        self.assertEqual(len(comparison), 3)

    def test_method_order_is_deterministic(self):
        comparison = build_comparison(
            make_llm_rows(),
            list(reversed(make_artifact_rows())),
        )

        self.assertEqual(
            [row["method"] for row in comparison],
            METHOD_ORDER,
        )

    def test_llm_only_not_applicable_fields_are_blank(self):
        comparison = build_comparison(
            make_llm_rows(),
            make_artifact_rows(),
        )
        llm = comparison[0]

        self.assertEqual(llm["score_accuracy"], "")
        self.assertEqual(llm["threshold_accuracy"], "")
        self.assertEqual(llm["paired_week_count_accuracy"], "")
        self.assertEqual(llm["false_positive_edge_claims"], "1")
        self.assertEqual(llm["score_claims"], "0")
        self.assertEqual(llm["threshold_claims"], "0")
        self.assertIn(
            "without empirical score, threshold, lag, paired-week",
            llm["notes"],
        )

    def test_artifact_accuracy_fields_are_preserved(self):
        artifacts = make_artifact_rows()
        artifacts[0]["score_accuracy"] = "0.90"
        artifacts[0]["threshold_accuracy"] = "0.80"
        artifacts[0]["paired_week_count_accuracy"] = "0.70"

        comparison = build_comparison(make_llm_rows(), artifacts)
        text = comparison[1]
        graph = comparison[2]

        self.assertEqual(text["score_accuracy"], "0.90")
        self.assertEqual(text["threshold_accuracy"], "0.80")
        self.assertEqual(text["paired_week_count_accuracy"], "0.70")
        self.assertEqual(graph["score_accuracy"], "1.0")
        self.assertEqual(graph["threshold_accuracy"], "1.0")
        self.assertEqual(graph["paired_week_count_accuracy"], "1.0")
        for row in (text, graph):
            self.assertEqual(row["false_positive_edge_claims"], "")
            self.assertEqual(row["score_claims"], "")
            self.assertEqual(row["threshold_claims"], "")

    def test_missing_input_file_has_clear_error(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            missing = Path(temp_dir) / "missing.csv"

            with self.assertRaisesRegex(
                FileNotFoundError,
                "LLM-only summary file not found",
            ):
                read_summary(
                    missing,
                    LLM_COLUMNS,
                    "LLM-only summary",
                )

    def test_output_csv_has_required_columns(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            llm_path = temp_path / "llm.csv"
            artifact_path = temp_path / "artifacts.csv"
            output_path = temp_path / "comparison.csv"
            write_rows(llm_path, LLM_COLUMNS, make_llm_rows())
            write_rows(
                artifact_path,
                ARTIFACT_COLUMNS,
                make_artifact_rows(),
            )
            llm_rows = read_summary(
                llm_path,
                LLM_COLUMNS,
                "LLM-only summary",
            )
            artifact_rows = read_summary(
                artifact_path,
                ARTIFACT_COLUMNS,
                "Text-RAG/GraphRAG summary",
            )
            write_comparison(
                output_path,
                build_comparison(llm_rows, artifact_rows),
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
        self.assertEqual(
            [row["method"] for row in rows],
            METHOD_ORDER,
        )


if __name__ == "__main__":
    unittest.main()
