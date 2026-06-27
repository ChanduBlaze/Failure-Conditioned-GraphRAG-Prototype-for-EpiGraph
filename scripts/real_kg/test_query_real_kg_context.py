"""Pure helper tests for the real-data graph context exporter."""

import unittest
from pathlib import Path

from scripts.real_kg.query_real_kg_context import (
    build_context,
    validate_output_path,
)


CASE_ID = "real_case_001"
FAILURE_CASE = {"id": CASE_ID, "name": "Real failure case"}
TARGET_SIGNAL = {"id": "real_target_signal", "name": "Target signal"}
CANDIDATE = {"id": "real_candidate_signal", "name": "Candidate signal"}


def make_case_rows():
    return [
        {
            "failure_case": FAILURE_CASE.copy(),
            "target_signal": TARGET_SIGNAL.copy(),
        }
    ]


def make_evidence_row(status="present", include_typed_edge=True):
    evidence_id = "evidence_claim_001"
    return {
        "candidate": CANDIDATE.copy(),
        "target_signal": TARGET_SIGNAL.copy(),
        "evidence": {
            "id": evidence_id,
            "edge_type": "LEADING_INDICATOR_FOR",
            "status": status,
            "method": "lagged_pearson_correlation_v1",
            "lag_weeks": 2,
            "score": 0.9,
            "threshold": 0.6,
            "evidence_sentence": "Candidate leads the target by two weeks.",
            "limitation": "Associational evidence only; not causal proof.",
        },
        "dataset": {"id": "dataset_001", "name": "Test dataset"},
        "region": {"id": "region_001", "name": "Test region"},
        "time_window": {
            "id": "time_window_001",
            "start": "2025-W01",
            "end": "2025-W10",
        },
        "typed_edge": (
            {
                "evidence_id": evidence_id,
                "score": 0.9,
                "lag_weeks": 2,
                "method": "lagged_pearson_correlation_v1",
                "status": "present",
            }
            if include_typed_edge
            else None
        ),
    }


class BuildContextTests(unittest.TestCase):
    def test_present_claim_builds_complete_context(self):
        context, evidence_count, typed_edge_count = build_context(
            CASE_ID,
            make_case_rows(),
            [make_evidence_row()],
        )

        self.assertEqual(context["case_id"], CASE_ID)
        self.assertEqual(context["target_signal"], TARGET_SIGNAL)
        self.assertEqual(len(context["candidates"]), 1)
        candidate = context["candidates"][0]
        self.assertEqual(candidate["candidate_id"], CANDIDATE["id"])
        self.assertEqual(candidate["score"], 0.9)
        self.assertEqual(len(candidate["evidence_edges"]), 1)
        self.assertEqual(evidence_count, 1)
        self.assertEqual(typed_edge_count, 1)

        node_types = {node["type"] for node in context["support_nodes"]}
        self.assertEqual(
            node_types,
            {
                "FailureCase",
                "CandidateDriver",
                "Signal",
                "EvidenceClaim",
                "Dataset",
                "Region",
                "TimeWindow",
            },
        )
        edge_types = {
            edge["edge_type"] for edge in context["support_edges"]
        }
        self.assertEqual(
            edge_types,
            {
                "HAS_CANDIDATE",
                "HAS_TARGET_SIGNAL",
                "HAS_EVIDENCE",
                "SUPPORTS_TARGET",
                "DERIVED_FROM",
                "OBSERVED_IN",
                "EVALUATED_DURING",
                "LEADING_INDICATOR_FOR",
            },
        )

    def test_missing_claim_is_retained_without_positive_typed_edge(self):
        context, evidence_count, typed_edge_count = build_context(
            CASE_ID,
            make_case_rows(),
            [make_evidence_row(status="missing", include_typed_edge=False)],
        )

        candidate = context["candidates"][0]
        self.assertEqual(candidate["score"], 0)
        self.assertEqual(len(candidate["evidence_edges"]), 1)
        self.assertEqual(
            candidate["evidence_edges"][0]["status"],
            "missing",
        )
        self.assertEqual(evidence_count, 1)
        self.assertEqual(typed_edge_count, 0)
        edge_types = {
            edge["edge_type"] for edge in context["support_edges"]
        }
        self.assertNotIn("LEADING_INDICATOR_FOR", edge_types)

    def test_missing_failure_case_raises(self):
        with self.assertRaisesRegex(ValueError, "FailureCase not found"):
            build_context(CASE_ID, [], [])

    def test_no_candidates_raises(self):
        with self.assertRaisesRegex(ValueError, "no candidates"):
            build_context(CASE_ID, make_case_rows(), [])

    def test_validate_output_path_rejects_evaluation_results(self):
        with self.assertRaisesRegex(ValueError, "evals/results"):
            validate_output_path(Path("evals/results/real_context.json"))


if __name__ == "__main__":
    unittest.main()
