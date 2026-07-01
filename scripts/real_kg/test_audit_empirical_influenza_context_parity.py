"""Tests for empirical Text-RAG/GraphRAG context parity auditing."""

import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.real_kg.audit_empirical_influenza_context_parity import (
    CLAIM_COLUMNS,
    OUTPUT_COLUMNS,
    PIPELINE,
    audit_parity,
    read_claims,
    read_json,
    write_audit,
)


CASE_ID = "real_us_flu_empirical_multicandidate_001"
CANDIDATE_ID = "real_signal_outpatient_ili_activity"
CANDIDATE_NAME = "Outpatient ILI activity"
TARGET_ID = "real_signal_us_influenza_hospitalization_rate_flusurv"
TARGET_NAME = "U.S. influenza hospitalization rate from FluSurv-NET"
EDGE_TYPE = "LEADING_INDICATOR_FOR"
METHOD = "lagged_pearson_correlation_empirical_v1"
SOURCE_DATASET = "FluSurv target; outpatient ILI candidate"


def make_claim():
    return {
        "case_id": CASE_ID,
        "candidate_id": CANDIDATE_ID,
        "candidate_name": CANDIDATE_NAME,
        "target_signal_id": TARGET_ID,
        "target_signal_name": TARGET_NAME,
        "edge_type": EDGE_TYPE,
        "status": "present",
        "source_dataset": SOURCE_DATASET,
        "method": METHOD,
        "region": "United States / FluSurv-NET catchment",
        "time_window_start": "2024-W40",
        "time_window_end": "2025-W20",
        "lag_weeks": "1",
        "score": "0.958037",
        "threshold": "0.60",
        "paired_week_count": "29",
        "minimum_paired_weeks": "8",
        "evidence_sentence": "Controlled empirical evidence.",
        "limitation": "Empirical evidence only; not causal proof.",
    }


def make_text_corpus():
    claim = make_claim()
    return [
        {
            "chunk_id": "empirical_chunk_001",
            "source_type": "empirical_evidence_claim",
            "case_id": CASE_ID,
            "candidate_id": CANDIDATE_ID,
            "target_signal_id": TARGET_ID,
            "edge_type": EDGE_TYPE,
            "status": "present",
            "text": (
                "Status: present.\n"
                f"Score: {claim['score']}.\n"
                f"Threshold: {claim['threshold']}.\n"
                f"Lag weeks: {claim['lag_weeks']}.\n"
                f"Paired week count: {claim['paired_week_count']}.\n"
                f"Method: {METHOD}.\n"
                f"Source dataset: {SOURCE_DATASET}."
            ),
        }
    ]


def make_graph_context():
    claim = make_claim()
    return {
        "case_id": CASE_ID,
        "target_signal_id": TARGET_ID,
        "target_signal_name": TARGET_NAME,
        "pipeline": PIPELINE,
        "candidates": [],
        "evidence_edges": [
            {
                "candidate_id": CANDIDATE_ID,
                "candidate_name": CANDIDATE_NAME,
                "target_signal_id": TARGET_ID,
                "target_signal_name": TARGET_NAME,
                "edge_type": EDGE_TYPE,
                "status": "present",
                "score": float(claim["score"]),
                "threshold": float(claim["threshold"]),
                "lag_weeks": int(claim["lag_weeks"]),
                "paired_week_count": int(claim["paired_week_count"]),
                "minimum_paired_weeks": 8,
                "method": METHOD,
                "source_dataset": SOURCE_DATASET,
                "region": claim["region"],
                "time_window_start": claim["time_window_start"],
                "time_window_end": claim["time_window_end"],
                "evidence_sentence": claim["evidence_sentence"],
                "limitation": claim["limitation"],
            }
        ],
    }


def audit_from_temporary_files(
    claims=None,
    text_corpus=None,
    graph_context=None,
):
    claims = copy.deepcopy(claims if claims is not None else [make_claim()])
    text_corpus = copy.deepcopy(
        text_corpus if text_corpus is not None else make_text_corpus()
    )
    graph_context = copy.deepcopy(
        graph_context if graph_context is not None else make_graph_context()
    )
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        claims_path = temp_path / "claims.csv"
        text_path = temp_path / "text.json"
        graph_path = temp_path / "graph.json"
        with claims_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as output_file:
            writer = csv.DictWriter(
                output_file,
                fieldnames=CLAIM_COLUMNS,
            )
            writer.writeheader()
            writer.writerows(claims)
        text_path.write_text(
            json.dumps(text_corpus),
            encoding="utf-8",
        )
        graph_path.write_text(
            json.dumps(graph_context),
            encoding="utf-8",
        )
        loaded_claims = read_claims(claims_path)
        loaded_text = read_json(text_path, list, "text fixture")
        loaded_graph = read_json(graph_path, dict, "graph fixture")
        return audit_parity(loaded_claims, loaded_text, loaded_graph)


class AuditEmpiricalInfluenzaContextParityTests(unittest.TestCase):
    def test_full_parity_passes_when_artifacts_match_claim(self):
        rows = audit_from_temporary_files()

        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["_text_parity_pass"])
        self.assertTrue(rows[0]["_graph_parity_pass"])
        self.assertTrue(rows[0]["full_parity_pass"])

    def test_missing_text_chunk_fails_text_parity(self):
        rows = audit_from_temporary_files(text_corpus=[])

        self.assertFalse(rows[0]["text_chunk_found"])
        self.assertFalse(rows[0]["_text_parity_pass"])
        self.assertFalse(rows[0]["full_parity_pass"])

    def test_missing_graph_edge_fails_graph_parity(self):
        graph = make_graph_context()
        graph["evidence_edges"] = []

        rows = audit_from_temporary_files(graph_context=graph)

        self.assertFalse(rows[0]["graph_edge_found"])
        self.assertFalse(rows[0]["_graph_parity_pass"])
        self.assertFalse(rows[0]["full_parity_pass"])

    def test_score_mismatch_fails_numeric_parity(self):
        text = make_text_corpus()
        text[0]["text"] = text[0]["text"].replace(
            "Score: 0.958037.",
            "Score: 0.700000.",
        )
        graph = make_graph_context()
        graph["evidence_edges"][0]["score"] = 0.70

        rows = audit_from_temporary_files(
            text_corpus=text,
            graph_context=graph,
        )

        self.assertFalse(rows[0]["text_score_match"])
        self.assertFalse(rows[0]["graph_score_match"])
        self.assertFalse(rows[0]["full_parity_pass"])

    def test_lag_mismatch_fails_parity(self):
        text = make_text_corpus()
        text[0]["text"] = text[0]["text"].replace(
            "Lag weeks: 1.",
            "Lag weeks: 2.",
        )
        graph = make_graph_context()
        graph["evidence_edges"][0]["lag_weeks"] = 2

        rows = audit_from_temporary_files(
            text_corpus=text,
            graph_context=graph,
        )

        self.assertFalse(rows[0]["text_lag_match"])
        self.assertFalse(rows[0]["graph_lag_match"])
        self.assertFalse(rows[0]["full_parity_pass"])

    def test_source_dataset_mismatch_fails_parity(self):
        text = make_text_corpus()
        text[0]["text"] = text[0]["text"].replace(
            SOURCE_DATASET,
            "Wrong text dataset",
        )
        graph = make_graph_context()
        graph["evidence_edges"][0]["source_dataset"] = "Wrong graph dataset"

        rows = audit_from_temporary_files(
            text_corpus=text,
            graph_context=graph,
        )

        self.assertFalse(rows[0]["text_source_dataset_match"])
        self.assertFalse(rows[0]["graph_source_dataset_match"])
        self.assertFalse(rows[0]["full_parity_pass"])

    def test_output_csv_has_required_columns(self):
        rows = audit_from_temporary_files()
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "audit.csv"
            write_audit(output_path, rows)
            with output_path.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as input_file:
                reader = csv.DictReader(input_file)
                written = list(reader)

        self.assertEqual(reader.fieldnames, OUTPUT_COLUMNS)
        self.assertEqual(len(written), 1)
        self.assertEqual(written[0]["full_parity_pass"], "True")


if __name__ == "__main__":
    unittest.main()
