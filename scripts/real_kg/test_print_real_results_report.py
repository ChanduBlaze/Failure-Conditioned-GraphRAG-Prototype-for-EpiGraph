"""Tests for the human-readable real-results Markdown report."""

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.real_kg.print_real_results_report import (
    TABLE_COLUMNS,
    generate_report,
    read_results_index,
)


INPUT_COLUMNS = ["result_family", "result_type", *TABLE_COLUMNS]


def sample_rows():
    fixture_common = {
        "result_family": "fixture_real_kg",
        "result_type": "controlled_fixture_method_comparison",
        "case_count": "4",
        "candidate_accuracy": "1.0",
        "avg_present_edge_recall": "1.0",
        "false_positive_edge_claims": "0",
        "total_must_not_include_violations": "0",
        "notes": "Controlled fixture.",
    }
    empirical_common = {
        "result_family": "empirical_influenza",
        "result_type": "real_data_method_comparison",
        "case_count": "4",
        "status_accuracy": "1.0",
        "avg_present_edge_recall": "1.0",
        "avg_missing_edge_recall": "1.0",
        "total_must_not_include_violations": "0",
    }
    return [
        {
            **fixture_common,
            "method": "llm_only",
            "status_accuracy": "0.75",
            "avg_missing_edge_recall": "0.75",
            "lag_accuracy": "0.0",
        },
        {
            **fixture_common,
            "method": "text_rag",
            "status_accuracy": "1.0",
            "avg_missing_edge_recall": "1.0",
            "lag_accuracy": "1.0",
        },
        {
            **fixture_common,
            "method": "graphrag_context",
            "status_accuracy": "1.0",
            "avg_missing_edge_recall": "1.0",
            "lag_accuracy": "1.0",
        },
        {
            **empirical_common,
            "method": "empirical_llm_only",
            "lag_accuracy": "0.0",
            "notes": "Used general epidemiological reasoning.",
        },
        {
            **empirical_common,
            "method": "empirical_text_rag",
            "lag_accuracy": "1.0",
            "score_accuracy": "1.0",
            "threshold_accuracy": "1.0",
            "paired_week_count_accuracy": "1.0",
            "notes": "Preserved text evidence.",
        },
        {
            **empirical_common,
            "method": "empirical_graphrag_context",
            "lag_accuracy": "1.0",
            "score_accuracy": "1.0",
            "threshold_accuracy": "1.0",
            "paired_week_count_accuracy": "1.0",
            "notes": "Preserved graph evidence.",
        },
    ]


def write_input(path):
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=INPUT_COLUMNS,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(sample_rows())


class PrintRealResultsReportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        self.input_path = temp_path / "real_results_index.csv"
        self.output_path = temp_path / "real_results_report.md"
        write_input(self.input_path)
        self.fixture_count, self.empirical_count = generate_report(
            self.input_path,
            self.output_path,
        )
        self.report = self.output_path.read_text(encoding="utf-8")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_writes_markdown_report(self):
        self.assertTrue(self.output_path.is_file())
        self.assertTrue(self.report.startswith("# Real-KG"))

    def test_report_contains_all_five_required_sections(self):
        sections = [
            "## 1. Controlled Fixture Real-KG Comparison",
            "## 2. Empirical Influenza Real-Data Extension",
            "## 3. Interpretation",
            "## 4. Limitations",
            "## 5. Thesis-Ready Takeaway",
        ]
        for section in sections:
            with self.subTest(section=section):
                self.assertIn(section, self.report)

    def test_fixture_and_empirical_rows_are_separated(self):
        fixture_section = self.report.split(
            "## 1. Controlled Fixture Real-KG Comparison",
            1,
        )[1].split("## 2. Empirical Influenza Real-Data Extension", 1)[0]
        empirical_section = self.report.split(
            "## 2. Empirical Influenza Real-Data Extension",
            1,
        )[1].split("## 3. Interpretation", 1)[0]

        self.assertEqual(self.fixture_count, 3)
        self.assertEqual(self.empirical_count, 3)
        self.assertIn("| llm_only |", fixture_section)
        self.assertNotIn("| empirical_llm_only |", fixture_section)
        self.assertIn("| empirical_llm_only |", empirical_section)
        self.assertNotIn("| llm_only |", empirical_section)

    def test_report_includes_thesis_safe_causal_limitation(self):
        self.assertIn("not causal discovery", self.report)
        self.assertIn("screening evidence, not causal proof", self.report)
        self.assertIn(
            "does not prove generalization to all disease systems",
            self.report,
        )

    def test_report_includes_llm_only_lag_interpretation(self):
        self.assertIn(
            "LLM-only recovered status but not exact empirical lag evidence",
            self.report,
        )

    def test_markdown_tables_include_required_method_names(self):
        for method in (
            "llm_only",
            "text_rag",
            "graphrag_context",
            "empirical_llm_only",
            "empirical_text_rag",
            "empirical_graphrag_context",
        ):
            with self.subTest(method=method):
                self.assertIn(f"| {method} |", self.report)

    def test_missing_input_file_raises_clear_error(self):
        missing = Path(self.temp_dir.name) / "missing.csv"

        with self.assertRaisesRegex(
            FileNotFoundError,
            "Real results index not found",
        ):
            read_results_index(missing)


if __name__ == "__main__":
    unittest.main()
