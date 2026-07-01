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


FAILURE_CASE_ID = "real_us_flu_wastewater_leading_indicator_001"
WASTEWATER_ID = "real_signal_influenza_a_wastewater_activity"
OUTPATIENT_ILI_ID = "real_signal_outpatient_ili_activity"
TEST_POSITIVITY_ID = "real_signal_influenza_test_positivity"
HUMIDITY_ID = "real_signal_humidity_anomaly"
EDGE_TYPE = "LEADING_INDICATOR_FOR"


def make_cases():
    shared = {
        "failure_case_id": FAILURE_CASE_ID,
        "must_not_include": ["proves causality", "definitively causes"],
    }
    return [
        {
            **shared,
            "id": "real_case_001",
            "expected_candidate_id": WASTEWATER_ID,
            "expected_present_edges": [EDGE_TYPE],
            "expected_missing_edges": [],
            "expected_status": "present",
            "expected_lag_weeks": 2,
            "minimum_expected_score": 0.6,
        },
        {
            **shared,
            "id": "real_case_002",
            "expected_candidate_id": OUTPATIENT_ILI_ID,
            "expected_present_edges": [EDGE_TYPE],
            "expected_missing_edges": [],
            "expected_status": "present",
            "expected_lag_weeks": 1,
            "minimum_expected_score": 0.6,
        },
        {
            **shared,
            "id": "real_case_003",
            "expected_candidate_id": TEST_POSITIVITY_ID,
            "expected_present_edges": [EDGE_TYPE],
            "expected_missing_edges": [],
            "expected_status": "present",
            "expected_lag_weeks": 1,
            "minimum_expected_score": 0.6,
        },
        {
            **shared,
            "id": "real_case_004",
            "expected_candidate_id": HUMIDITY_ID,
            "expected_present_edges": [],
            "expected_missing_edges": [EDGE_TYPE],
            "expected_status": "missing",
            "expected_lag_weeks": 4,
            "maximum_expected_score": 0.6,
        },
    ]


def make_text_corpus(overclaim=""):
    # Deliberately not sorted by score or expected ranking. Candidate-specific
    # evaluation must select by candidate_id, not by chunk position.
    rows = [
        ("001_test_positivity", TEST_POSITIVITY_ID, "present", 1, 0.71),
        ("002_humidity", HUMIDITY_ID, "missing", 4, 0.40),
        ("003_outpatient_ili", OUTPATIENT_ILI_ID, "present", 1, 0.88),
        ("004_wastewater", WASTEWATER_ID, "present", 2, 0.99),
    ]
    return [
        {
            "chunk_id": f"chunk_{chunk_suffix}",
            "case_id": FAILURE_CASE_ID,
            "candidate_id": candidate_id,
            "edge_type": EDGE_TYPE,
            "status": status,
            "text": (
                f"Status: {status}.\n"
                f"Lag weeks: {lag_weeks}.\n"
                f"Score: {score:.2f}.\n"
                f"{overclaim}"
            ),
        }
        for chunk_suffix, candidate_id, status, lag_weeks, score in rows
    ]


def make_graph_context(case_id=FAILURE_CASE_ID, overclaim=""):
    rows = [
        (WASTEWATER_ID, "present", 2, 0.99),
        (OUTPATIENT_ILI_ID, "present", 1, 0.88),
        (TEST_POSITIVITY_ID, "present", 1, 0.71),
        (HUMIDITY_ID, "missing", 4, 0.40),
    ]
    candidates = []
    for candidate_id, status, lag_weeks, evidence_score in rows:
        candidate_score = evidence_score if status == "present" else 0
        candidates.append(
            {
                "candidate_id": candidate_id,
                "score": candidate_score,
                "evidence_edges": [
                    {
                        "evidence_claim_id": (
                            f"evidence_claim_{candidate_id}"
                        ),
                        "edge_type": EDGE_TYPE,
                        "status": status,
                        "lag_weeks": lag_weeks,
                        "score": evidence_score,
                        "evidence_sentence": (
                            f"{candidate_id} has {status} evidence. "
                            f"{overclaim}"
                        ),
                        "limitation": "Associational screening evidence only.",
                    }
                ],
            }
        )
    return {"case_id": case_id, "candidates": candidates}


class RunRealEvalTests(unittest.TestCase):
    def assert_perfect_metrics(self, result):
        self.assertTrue(result["candidate_correct"])
        self.assertTrue(result["status_correct"])
        self.assertEqual(result["present_edge_recall"], 1.0)
        self.assertEqual(result["missing_edge_recall"], 1.0)
        self.assertTrue(result["lag_correct"])
        self.assertTrue(result["score_meets_minimum"])
        self.assertEqual(result["must_not_include_violations"], 0)

    def test_text_selects_all_candidates_from_unsorted_chunks(self):
        for case in make_cases():
            with self.subTest(case_id=case["id"]):
                result = evaluate_text_case(case, make_text_corpus())
                self.assertEqual(
                    result["predicted_candidate_id"],
                    case["expected_candidate_id"],
                )
                self.assert_perfect_metrics(result)

    def test_graph_selects_all_candidate_specific_evidence(self):
        for case in make_cases():
            with self.subTest(case_id=case["id"]):
                result = evaluate_graph_case(case, make_graph_context())
                self.assertEqual(
                    result["predicted_candidate_id"],
                    case["expected_candidate_id"],
                )
                self.assert_perfect_metrics(result)

    def test_humidity_is_missing_without_positive_mentioned_edge(self):
        humidity_case = make_cases()[-1]
        for evaluator, artifact in (
            (evaluate_text_case, make_text_corpus()),
            (evaluate_graph_case, make_graph_context()),
        ):
            with self.subTest(method=evaluator.__name__):
                result = evaluator(humidity_case, artifact)
                self.assertEqual(result["mentioned_evidence_edges"], "")
                self.assertEqual(
                    result["identified_missing_edges"],
                    EDGE_TYPE,
                )
                self.assertEqual(result["missing_edge_recall"], 1.0)
                self.assertTrue(result["score_meets_minimum"])

    def test_summary_over_four_cases_has_perfect_metrics(self):
        cases = make_cases()
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
            self.assertEqual(result["case_count"], 4)
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
        present_case = make_cases()[0]
        text_result = evaluate_text_case(
            present_case,
            make_text_corpus(overclaim),
        )
        graph_result = evaluate_graph_case(
            present_case,
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
            make_cases()[0],
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
