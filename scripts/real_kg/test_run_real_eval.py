"""Tests for deterministic, candidate-specific real-data evaluation."""

import unittest
from pathlib import Path

from scripts.real_kg.run_real_eval import (
    evaluate_graph_case,
    evaluate_text_case,
    run_evaluation,
    summarize,
    validate_output_dir,
)


FAILURE_CASE_ID = "real_failure_case_001"
WASTEWATER_ID = "real_candidate_wastewater"
HUMIDITY_ID = "real_candidate_humidity"
EDGE_TYPE = "LEADING_INDICATOR_FOR"


def make_present_case():
    return {
        "id": "real_case_001",
        "failure_case_id": FAILURE_CASE_ID,
        "expected_candidate_id": WASTEWATER_ID,
        "expected_present_edges": [EDGE_TYPE],
        "expected_missing_edges": [],
        "expected_status": "present",
        "expected_lag_weeks": 2,
        "minimum_expected_score": 0.6,
        "must_not_include": ["proves causality"],
        "notes": "Synthetic present-evidence unit-test case.",
    }


def make_missing_case():
    return {
        "id": "real_case_002",
        "failure_case_id": FAILURE_CASE_ID,
        "expected_candidate_id": HUMIDITY_ID,
        "expected_present_edges": [],
        "expected_missing_edges": [EDGE_TYPE],
        "expected_status": "missing",
        "expected_lag_weeks": 4,
        "maximum_expected_score": 0.6,
        "must_not_include": ["proves causality"],
        "notes": "Synthetic missing-evidence unit-test case.",
    }


def make_text_corpus(overclaim=""):
    # Humidity deliberately appears first to verify candidate-specific
    # selection rather than reliance on corpus order.
    return [
        {
            "chunk_id": "chunk_001_humidity",
            "case_id": FAILURE_CASE_ID,
            "candidate_id": HUMIDITY_ID,
            "edge_type": EDGE_TYPE,
            "status": "missing",
            "text": (
                "Status: missing.\n"
                "Lag weeks: 4.\n"
                "Score: 0.40.\n"
                f"{overclaim}"
            ),
        },
        {
            "chunk_id": "chunk_002_wastewater",
            "case_id": FAILURE_CASE_ID,
            "candidate_id": WASTEWATER_ID,
            "edge_type": EDGE_TYPE,
            "status": "present",
            "text": (
                "Status: present.\n"
                "Lag weeks: 2.\n"
                "Score: 0.90.\n"
                f"{overclaim}"
            ),
        },
    ]


def make_graph_context(case_id=FAILURE_CASE_ID, overclaim=""):
    return {
        "case_id": case_id,
        "candidates": [
            {
                "candidate_id": WASTEWATER_ID,
                "score": 0.9,
                "evidence_edges": [
                    {
                        "evidence_claim_id": "evidence_claim_wastewater",
                        "edge_type": EDGE_TYPE,
                        "status": "present",
                        "lag_weeks": 2,
                        "score": 0.9,
                        "evidence_sentence": (
                            "Wastewater has qualifying evidence. "
                            f"{overclaim}"
                        ),
                        "limitation": "Associational evidence only.",
                    }
                ],
            },
            {
                "candidate_id": HUMIDITY_ID,
                # Missing evidence has no positive typed-edge contribution.
                "score": 0,
                "evidence_edges": [
                    {
                        "evidence_claim_id": "evidence_claim_humidity",
                        "edge_type": EDGE_TYPE,
                        "status": "missing",
                        "lag_weeks": 4,
                        "score": 0.4,
                        "evidence_sentence": (
                            "Humidity is below the configured threshold. "
                            f"{overclaim}"
                        ),
                        "limitation": "Associational screening evidence only.",
                    }
                ],
            },
        ],
    }


class RunRealEvalTests(unittest.TestCase):
    def assert_perfect_metrics(self, result):
        self.assertTrue(result["candidate_correct"])
        self.assertTrue(result["status_correct"])
        self.assertEqual(result["present_edge_recall"], 1.0)
        self.assertEqual(result["missing_edge_recall"], 1.0)
        self.assertTrue(result["lag_correct"])
        self.assertTrue(result["score_meets_minimum"])
        self.assertEqual(result["must_not_include_violations"], 0)

    def test_text_selects_wastewater_even_when_humidity_appears_first(self):
        result = evaluate_text_case(
            make_present_case(),
            make_text_corpus(),
        )

        self.assertEqual(result["predicted_candidate_id"], WASTEWATER_ID)
        self.assertEqual(result["mentioned_evidence_edges"], EDGE_TYPE)
        self.assert_perfect_metrics(result)

    def test_text_selects_humidity_missing_evidence(self):
        result = evaluate_text_case(
            make_missing_case(),
            make_text_corpus(),
        )

        self.assertEqual(result["predicted_candidate_id"], HUMIDITY_ID)
        self.assertEqual(result["mentioned_evidence_edges"], "")
        self.assertEqual(result["identified_missing_edges"], EDGE_TYPE)
        self.assertEqual(result["missing_edge_recall"], 1.0)
        self.assert_perfect_metrics(result)

    def test_graph_selects_humidity_and_uses_evidence_score(self):
        result = evaluate_graph_case(
            make_missing_case(),
            make_graph_context(),
        )

        self.assertEqual(result["predicted_candidate_id"], HUMIDITY_ID)
        self.assertEqual(result["mentioned_evidence_edges"], "")
        self.assertEqual(result["identified_missing_edges"], EDGE_TYPE)
        self.assertTrue(result["score_meets_minimum"])
        self.assert_perfect_metrics(result)

    def test_graph_present_candidate_has_perfect_metrics(self):
        result = evaluate_graph_case(
            make_present_case(),
            make_graph_context(),
        )

        self.assertEqual(result["predicted_candidate_id"], WASTEWATER_ID)
        self.assertEqual(result["mentioned_evidence_edges"], EDGE_TYPE)
        self.assert_perfect_metrics(result)

    def test_summary_over_two_cases_has_perfect_metrics(self):
        cases = [make_present_case(), make_missing_case()]
        text_rows = [
            evaluate_text_case(case, make_text_corpus()) for case in cases
        ]
        graph_rows = [
            evaluate_graph_case(case, make_graph_context()) for case in cases
        ]

        for method, rows in (
            ("text_rag", text_rows),
            ("graphrag_context", graph_rows),
        ):
            result = summarize(method, rows)
            self.assertEqual(result["case_count"], 2)
            self.assertEqual(result["candidate_accuracy"], 1.0)
            self.assertEqual(result["avg_present_edge_recall"], 1.0)
            self.assertEqual(result["avg_missing_edge_recall"], 1.0)
            self.assertEqual(result["status_accuracy"], 1.0)
            self.assertEqual(result["lag_accuracy"], 1.0)
            self.assertEqual(result["score_threshold_accuracy"], 1.0)
            self.assertEqual(
                result["total_must_not_include_violations"],
                0,
            )

    def test_forbidden_overclaim_is_counted(self):
        overclaim = "This proves causality."
        text_result = evaluate_text_case(
            make_present_case(),
            make_text_corpus(overclaim),
        )
        graph_result = evaluate_graph_case(
            make_present_case(),
            make_graph_context(overclaim=overclaim),
        )

        self.assertEqual(text_result["must_not_include_violations"], 1)
        self.assertEqual(graph_result["must_not_include_violations"], 1)

    def test_validate_output_dir_rejects_simulated_results(self):
        with self.assertRaisesRegex(ValueError, "evals/results"):
            validate_output_dir(Path("evals/results/real_eval"))

    def test_validate_output_dir_rejects_outside_directory(self):
        with self.assertRaisesRegex(ValueError, "evals/results_real"):
            validate_output_dir(Path("temporary_real_results"))

    def test_wrong_graph_case_id_returns_explanatory_failure(self):
        result = evaluate_graph_case(
            make_present_case(),
            make_graph_context(case_id="different_case"),
        )

        self.assertFalse(result["candidate_correct"])
        self.assertEqual(result["predicted_candidate_id"], "")
        self.assertIn("does not match", result["notes"])

    def test_empty_case_list_raises_without_writing(self):
        with self.assertRaisesRegex(ValueError, "case list is empty"):
            run_evaluation([], [], {}, Path("unused_output"))


if __name__ == "__main__":
    unittest.main()
