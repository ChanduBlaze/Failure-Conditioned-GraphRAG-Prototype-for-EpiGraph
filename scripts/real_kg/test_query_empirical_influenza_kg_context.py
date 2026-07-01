"""Tests for empirical influenza GraphRAG context construction."""

import unittest

from scripts.real_kg.query_empirical_influenza_kg_context import (
    CONTEXT_QUERY,
    PIPELINE,
    build_context,
)


CASE_ID = "real_us_flu_empirical_multicandidate_001"
TARGET_ID = "real_signal_us_influenza_hospitalization_rate_flusurv"
TARGET_NAME = "U.S. influenza hospitalization rate from FluSurv-NET"


def make_row(
    candidate_id,
    candidate_name,
    status="present",
    score=0.9,
    lag_weeks=1,
):
    evidence_id = (
        f"empirical_claim__{CASE_ID}__{candidate_id}__{TARGET_ID}__"
        "LEADING_INDICATOR_FOR"
    )
    return {
        "failure_case": {
            "id": CASE_ID,
            "name": "Empirical influenza hospitalization underprediction case",
            "pipeline": PIPELINE,
        },
        # Some CandidateDriver IDs are intentionally shared with the fixture
        # graph and therefore need not carry the empirical node marker.
        "candidate": {
            "id": candidate_id,
            "name": candidate_name,
        },
        "target_signal": {
            "id": TARGET_ID,
            "name": TARGET_NAME,
            "role": "target",
            "pipeline": PIPELINE,
        },
        "evidence": {
            "id": evidence_id,
            "pipeline": PIPELINE,
            "status": status,
            "edge_type": "LEADING_INDICATOR_FOR",
            "score": score,
            "threshold": 0.60,
            "lag_weeks": lag_weeks,
            "paired_week_count": 29,
            "minimum_paired_weeks": 8,
            "method": "lagged_pearson_correlation_empirical_v1",
            "source_dataset": "Empirical source dataset",
            "region": "United States / FluSurv-NET catchment",
            "time_window_start": "2024-W40",
            "time_window_end": "2025-W20",
            "evidence_sentence": "Controlled empirical evidence sentence.",
            "limitation": (
                "Empirical screening evidence only; not causal proof."
            ),
        },
        "typed_edge": (
            {
                "pipeline": PIPELINE,
                "evidence_claim_id": evidence_id,
                "status": "present",
                "score": score,
            }
            if status == "present"
            else None
        ),
    }


class QueryEmpiricalInfluenzaKgContextTests(unittest.TestCase):
    def test_builds_required_top_level_context(self):
        context = build_context(
            CASE_ID,
            TARGET_ID,
            [
                make_row(
                    "real_signal_outpatient_ili_activity",
                    "Outpatient ILI activity",
                )
            ],
        )

        self.assertEqual(context["case_id"], CASE_ID)
        self.assertEqual(context["target_signal_id"], TARGET_ID)
        self.assertEqual(context["target_signal_name"], TARGET_NAME)
        self.assertEqual(context["pipeline"], PIPELINE)
        self.assertEqual(
            set(context),
            {
                "case_id",
                "target_signal_id",
                "target_signal_name",
                "pipeline",
                "candidates",
                "evidence_edges",
            },
        )

    def test_includes_candidates_and_evidence_edges(self):
        context = build_context(
            CASE_ID,
            TARGET_ID,
            [
                make_row(
                    "real_signal_outpatient_ili_activity",
                    "Outpatient ILI activity",
                ),
                make_row(
                    "real_signal_influenza_test_positivity",
                    "Influenza test positivity",
                    score=0.8,
                ),
            ],
        )

        self.assertEqual(len(context["candidates"]), 2)
        self.assertEqual(len(context["evidence_edges"]), 2)
        self.assertEqual(
            {
                edge["candidate_id"]
                for edge in context["evidence_edges"]
            },
            {
                "real_signal_outpatient_ili_activity",
                "real_signal_influenza_test_positivity",
            },
        )

    def test_present_candidates_rank_by_descending_score(self):
        rows = [
            make_row("candidate_low", "Low candidate", score=0.70),
            make_row("candidate_high", "High candidate", score=0.95),
            make_row("candidate_middle", "Middle candidate", score=0.82),
        ]

        context = build_context(CASE_ID, TARGET_ID, rows)

        self.assertEqual(
            [candidate["candidate_id"] for candidate in context["candidates"]],
            ["candidate_high", "candidate_middle", "candidate_low"],
        )

    def test_missing_and_insufficient_claims_are_retained_last(self):
        rows = [
            make_row(
                "candidate_insufficient",
                "Insufficient candidate",
                status="insufficient",
                score=None,
                lag_weeks=None,
            ),
            make_row(
                "candidate_missing",
                "Missing candidate",
                status="missing",
                score=0.30,
            ),
            make_row(
                "candidate_present",
                "Present candidate",
                status="present",
                score=0.80,
            ),
        ]

        context = build_context(CASE_ID, TARGET_ID, rows)

        self.assertEqual(
            [
                (candidate["candidate_id"], candidate["status"])
                for candidate in context["candidates"]
            ],
            [
                ("candidate_present", "present"),
                ("candidate_missing", "missing"),
                ("candidate_insufficient", "insufficient"),
            ],
        )
        self.assertEqual(len(context["evidence_edges"]), 3)
        self.assertEqual(
            {edge["status"] for edge in context["evidence_edges"]},
            {"present", "missing", "insufficient"},
        )

    def test_query_is_scoped_to_empirical_pipeline(self):
        for graph_element in (
            "failure.pipeline = $pipeline",
            "target.pipeline = $pipeline",
            "has_target.pipeline = $pipeline",
            "has_candidate.pipeline = $pipeline",
            "has_evidence.pipeline = $pipeline",
            "evidence.pipeline = $pipeline",
            "supports_target.pipeline = $pipeline",
            "typed.pipeline = $pipeline",
        ):
            self.assertIn(graph_element, CONTEXT_QUERY)

    def test_preserves_empirical_evidence_properties(self):
        row = make_row(
            "real_signal_outpatient_ili_activity",
            "Outpatient ILI activity",
            score=0.958037,
        )

        context = build_context(CASE_ID, TARGET_ID, [row])
        candidate = context["candidates"][0]
        evidence_edge = context["evidence_edges"][0]

        for field in (
            "score",
            "threshold",
            "lag_weeks",
            "paired_week_count",
            "minimum_paired_weeks",
            "method",
            "source_dataset",
            "region",
            "time_window_start",
            "time_window_end",
            "evidence_sentence",
            "limitation",
        ):
            self.assertEqual(candidate[field], row["evidence"][field])
            self.assertEqual(evidence_edge[field], row["evidence"][field])
        self.assertEqual(evidence_edge["target_signal_id"], TARGET_ID)
        self.assertEqual(evidence_edge["target_signal_name"], TARGET_NAME)


if __name__ == "__main__":
    unittest.main()
