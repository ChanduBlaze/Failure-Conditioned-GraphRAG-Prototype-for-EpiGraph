"""Tests for deterministic, artifact-level real-data evaluation."""

import unittest
from pathlib import Path

from scripts.real_kg.run_real_eval import (
    evaluate_graph_case,
    evaluate_text_case,
    run_evaluation,
    validate_output_dir,
)


CASE_ID = "real_case_001"
FAILURE_CASE_ID = "real_failure_case_001"
CANDIDATE_ID = "real_candidate_001"
EDGE_TYPE = "LEADING_INDICATOR_FOR"


def make_case():
    return {
        "id": CASE_ID,
        "failure_case_id": FAILURE_CASE_ID,
        "expected_candidate_id": CANDIDATE_ID,
        "expected_present_edges": [EDGE_TYPE],
        "expected_missing_edges": [],
        "expected_status": "present",
        "expected_lag_weeks": 2,
        "minimum_expected_score": 0.6,
        "must_not_include": ["proves causality"],
        "notes": "Synthetic unit-test case.",
    }


def make_text_corpus(overclaim=""):
    return [
        {
            "chunk_id": "real_chunk_001",
            "case_id": FAILURE_CASE_ID,
            "candidate_id": CANDIDATE_ID,
            "edge_type": EDGE_TYPE,
            "status": "present",
            "text": (
                "Status: present.\n"
                "Lag weeks: 2.\n"
                "Score: 0.90.\n"
                f"{overclaim}"
            ),
        }
    ]


def make_graph_context(case_id=FAILURE_CASE_ID, overclaim=""):
    return {
        "case_id": case_id,
        "candidates": [
            {
                "candidate_id": CANDIDATE_ID,
                "score": 0.9,
                "evidence_edges": [
                    {
                        "evidence_claim_id": "evidence_claim_001",
                        "edge_type": EDGE_TYPE,
                        "status": "present",
                        "lag_weeks": 2,
                        "score": 0.9,
                        "evidence_sentence": (
                            "The candidate has qualifying evidence. "
                            f"{overclaim}"
                        ),
                        "limitation": "Associational evidence only.",
                    }
                ],
            }
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

    def test_text_and_graph_context_produce_perfect_metrics(self):
        case = make_case()

        text_result = evaluate_text_case(case, make_text_corpus())
        graph_result = evaluate_graph_case(case, make_graph_context())

        self.assertEqual(text_result["method"], "text_rag")
        self.assertEqual(graph_result["method"], "graphrag_context")
        self.assert_perfect_metrics(text_result)
        self.assert_perfect_metrics(graph_result)

    def test_forbidden_overclaim_is_counted(self):
        case = make_case()
        overclaim = "This proves causality."

        text_result = evaluate_text_case(
            case,
            make_text_corpus(overclaim),
        )
        graph_result = evaluate_graph_case(
            case,
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
            make_case(),
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
