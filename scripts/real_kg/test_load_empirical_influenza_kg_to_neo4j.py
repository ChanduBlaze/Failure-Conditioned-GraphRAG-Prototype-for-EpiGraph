"""Tests for the isolated empirical influenza Neo4j loader."""

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.real_kg.load_empirical_influenza_kg_to_neo4j import (
    DELETE_NODES_QUERY,
    DELETE_RELATIONSHIPS_QUERY,
    PIPELINE,
    REQUIRED_COLUMNS,
    UPSERT_EVIDENCE_QUERY,
    UPSERT_POSITIVE_EDGE_QUERY,
    build_evidence_claim_id,
    execute_load_transaction,
    read_claims,
    transform_claim,
)


def make_claim(status="present"):
    insufficient = status == "insufficient"
    return {
        "case_id": "real_us_flu_empirical_multicandidate_001",
        "candidate_id": (
            "real_signal_influenza_a_wastewater_concentration"
        ),
        "candidate_name": "Influenza A wastewater concentration",
        "target_signal_id": (
            "real_signal_us_influenza_hospitalization_rate_flusurv"
        ),
        "target_signal_name": (
            "U.S. influenza hospitalization rate from FluSurv-NET"
        ),
        "edge_type": "LEADING_INDICATOR_FOR",
        "status": status,
        "source_dataset": (
            "Delphi Epidata FluSurv / CDC FluSurv-NET; "
            "CDC Influenza A Wastewater Surveillance"
        ),
        "method": "lagged_pearson_correlation_empirical_v1",
        "region": "United States / FluSurv-NET catchment",
        "time_window_start": "2024-W40",
        "time_window_end": "2025-W20",
        "lag_weeks": "" if insufficient else "1",
        "score": "" if insufficient else "0.947016",
        "threshold": "0.60",
        "paired_week_count": "32",
        "minimum_paired_weeks": "8",
        "evidence_sentence": "Controlled empirical evidence statement.",
        "limitation": (
            "Empirical screening evidence only; not causal proof."
        ),
    }


class FakeResult:
    def consume(self):
        return None


class FakeTransaction:
    def __init__(self):
        self.calls = []

    def run(self, query, **parameters):
        self.calls.append((query, parameters))
        return FakeResult()


class LoadEmpiricalInfluenzaKgTests(unittest.TestCase):
    def test_reads_empirical_claim_csv(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "claims.csv"
            with path.open("w", newline="", encoding="utf-8") as output_file:
                writer = csv.DictWriter(
                    output_file,
                    fieldnames=REQUIRED_COLUMNS,
                )
                writer.writeheader()
                writer.writerow(make_claim())

            rows = read_claims(path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["status"], "present")
        self.assertEqual(rows[0]["pipeline"], PIPELINE)
        self.assertEqual(rows[0]["score"], 0.947016)

    def test_builds_deterministic_evidence_claim_id(self):
        claim = make_claim()

        evidence_id = build_evidence_claim_id(claim)

        self.assertEqual(
            evidence_id,
            "empirical_claim__"
            "real_us_flu_empirical_multicandidate_001__"
            "real_signal_influenza_a_wastewater_concentration__"
            "real_signal_us_influenza_hospitalization_rate_flusurv__"
            "LEADING_INDICATOR_FOR",
        )
        self.assertEqual(evidence_id, build_evidence_claim_id(claim))

    def test_present_claim_executes_positive_edge_query(self):
        row = transform_claim(make_claim("present"), 2)
        transaction = FakeTransaction()

        execute_load_transaction(transaction, [row])

        self.assertEqual(len(transaction.calls), 4)
        query, parameters = transaction.calls[-1]
        self.assertEqual(query, UPSERT_POSITIVE_EDGE_QUERY)
        self.assertEqual(parameters["rows"], [row])
        self.assertEqual(parameters["pipeline"], PIPELINE)
        self.assertTrue(row["creates_positive_edge"])

    def test_missing_claim_does_not_execute_positive_edge_query(self):
        row = transform_claim(make_claim("missing"), 2)
        transaction = FakeTransaction()

        execute_load_transaction(transaction, [row])

        self.assertEqual(len(transaction.calls), 3)
        self.assertNotIn(
            UPSERT_POSITIVE_EDGE_QUERY,
            [query for query, _parameters in transaction.calls],
        )
        self.assertFalse(row["creates_positive_edge"])

    def test_insufficient_claim_does_not_execute_positive_edge_query(self):
        row = transform_claim(make_claim("insufficient"), 2)
        transaction = FakeTransaction()

        execute_load_transaction(transaction, [row])

        self.assertEqual(len(transaction.calls), 3)
        self.assertNotIn(
            UPSERT_POSITIVE_EDGE_QUERY,
            [query for query, _parameters in transaction.calls],
        )
        self.assertFalse(row["creates_positive_edge"])
        self.assertIsNone(row["score"])
        self.assertIsNone(row["lag_weeks"])

    def test_delete_queries_are_scoped_to_empirical_pipeline(self):
        for query in (DELETE_RELATIONSHIPS_QUERY, DELETE_NODES_QUERY):
            self.assertIn("pipeline = $pipeline", query)
            self.assertIn("DELETE", query)
            self.assertNotIn("DETACH DELETE", query)

        transaction = FakeTransaction()
        execute_load_transaction(
            transaction,
            [transform_claim(make_claim("missing"), 2)],
        )
        for _query, parameters in transaction.calls[:2]:
            self.assertEqual(parameters, {"pipeline": PIPELINE})

    def test_required_node_and_relationship_properties_are_preserved(self):
        row = transform_claim(make_claim("present"), 2)

        expected_values = {
            "failure_case_name": (
                "Empirical influenza hospitalization underprediction case"
            ),
            "candidate_name": "Influenza A wastewater concentration",
            "status": "present",
            "edge_type": "LEADING_INDICATOR_FOR",
            "score": 0.947016,
            "threshold": 0.60,
            "lag_weeks": 1,
            "paired_week_count": 32,
            "minimum_paired_weeks": 8,
            "method": "lagged_pearson_correlation_empirical_v1",
            "region": "United States / FluSurv-NET catchment",
            "pipeline": PIPELINE,
        }
        for field, value in expected_values.items():
            self.assertEqual(row[field], value)

        for relationship_type in (
            "HAS_CANDIDATE",
            "HAS_TARGET",
            "HAS_EVIDENCE",
            "SUPPORTS_TARGET",
        ):
            self.assertIn(relationship_type, UPSERT_EVIDENCE_QUERY)
        for node_pipeline_property in (
            "failure.pipeline",
            "candidate.pipeline",
            "target.pipeline",
            "evidence.pipeline",
        ):
            self.assertIn(node_pipeline_property, UPSERT_EVIDENCE_QUERY)
        for evidence_property in (
            "evidence.status",
            "evidence.edge_type",
            "evidence.score",
            "evidence.threshold",
            "evidence.lag_weeks",
            "evidence.paired_week_count",
            "evidence.minimum_paired_weeks",
            "evidence.method",
            "evidence.source_dataset",
            "evidence.region",
            "evidence.time_window_start",
            "evidence.time_window_end",
            "evidence.evidence_sentence",
            "evidence.limitation",
        ):
            self.assertIn(evidence_property, UPSERT_EVIDENCE_QUERY)
        for property_name in (
            "score",
            "threshold",
            "lag_weeks",
            "paired_week_count",
            "minimum_paired_weeks",
            "method",
            "evidence_claim_id",
            "status",
            "pipeline",
        ):
            self.assertIn(property_name, UPSERT_POSITIVE_EDGE_QUERY)


if __name__ == "__main__":
    unittest.main()
