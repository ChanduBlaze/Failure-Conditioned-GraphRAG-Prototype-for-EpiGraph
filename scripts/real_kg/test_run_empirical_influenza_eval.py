"""Tests for deterministic empirical influenza artifact evaluation."""

import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.real_kg.run_empirical_influenza_eval import (
    CLAIM_COLUMNS,
    METHODS,
    RESULT_COLUMNS,
    SUMMARY_COLUMNS,
    evaluate_files,
    write_csv,
)


CASE_ID = "real_us_flu_empirical_multicandidate_001"
TARGET_ID = "real_signal_us_influenza_hospitalization_rate_flusurv"
TARGET_NAME = "U.S. influenza hospitalization rate from FluSurv-NET"
EDGE_TYPE = "LEADING_INDICATOR_FOR"
METHOD = "lagged_pearson_correlation_empirical_v1"

CANDIDATES = [
    (
        "real_signal_influenza_a_wastewater_concentration",
        "Influenza A wastewater concentration",
        "present",
        "1",
        "0.947016",
        "30",
    ),
    (
        "real_signal_outpatient_ili_activity",
        "Outpatient ILI activity",
        "present",
        "1",
        "0.958037",
        "29",
    ),
    (
        "real_signal_influenza_test_positivity",
        "Influenza test positivity",
        "missing",
        "2",
        "0.400000",
        "28",
    ),
]


def make_claims():
    return [
        {
            "case_id": CASE_ID,
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            "target_signal_id": TARGET_ID,
            "target_signal_name": TARGET_NAME,
            "edge_type": EDGE_TYPE,
            "status": status,
            "source_dataset": f"Source for {candidate_name}",
            "method": METHOD,
            "region": "United States / FluSurv-NET catchment",
            "time_window_start": "2024-W40",
            "time_window_end": "2025-W20",
            "lag_weeks": lag,
            "score": score,
            "threshold": "0.60",
            "paired_week_count": paired,
            "minimum_paired_weeks": "8",
            "evidence_sentence": (
                f"Controlled empirical evidence for {candidate_name}."
            ),
            "limitation": (
                "Empirical screening evidence only; not causal proof."
            ),
        }
        for candidate_id, candidate_name, status, lag, score, paired
        in CANDIDATES
    ]


def make_text_corpus():
    chunks = []
    for claim in make_claims():
        chunks.append(
            {
                "chunk_id": f"chunk_{claim['candidate_id']}",
                "case_id": CASE_ID,
                "candidate_id": claim["candidate_id"],
                "target_signal_id": TARGET_ID,
                "edge_type": EDGE_TYPE,
                "status": claim["status"],
                "text": (
                    f"Status: {claim['status']}.\n"
                    f"Lag weeks: {claim['lag_weeks']}.\n"
                    f"Score: {claim['score']}.\n"
                    f"Threshold: {claim['threshold']}.\n"
                    "Paired week count: "
                    f"{claim['paired_week_count']}.\n"
                    f"Method: {claim['method']}.\n"
                    f"Source dataset: {claim['source_dataset']}."
                ),
            }
        )
    return chunks


def make_graph_context():
    return {
        "case_id": CASE_ID,
        "target_signal_id": TARGET_ID,
        "target_signal_name": TARGET_NAME,
        "pipeline": "empirical_influenza",
        "candidates": [],
        "evidence_edges": [
            {
                "candidate_id": claim["candidate_id"],
                "candidate_name": claim["candidate_name"],
                "target_signal_id": TARGET_ID,
                "target_signal_name": TARGET_NAME,
                "edge_type": EDGE_TYPE,
                "status": claim["status"],
                "score": float(claim["score"]),
                "threshold": float(claim["threshold"]),
                "lag_weeks": int(claim["lag_weeks"]),
                "paired_week_count": int(claim["paired_week_count"]),
                "minimum_paired_weeks": 8,
                "method": METHOD,
                "source_dataset": claim["source_dataset"],
                "region": claim["region"],
                "time_window_start": claim["time_window_start"],
                "time_window_end": claim["time_window_end"],
                "evidence_sentence": claim["evidence_sentence"],
                "limitation": claim["limitation"],
            }
            for claim in make_claims()
        ],
    }


def evaluate_temporary_artifacts(
    claims=None,
    text_corpus=None,
    graph_context=None,
):
    claims = copy.deepcopy(claims if claims is not None else make_claims())
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
        text_path.write_text(json.dumps(text_corpus), encoding="utf-8")
        graph_path.write_text(json.dumps(graph_context), encoding="utf-8")
        return evaluate_files(claims_path, text_path, graph_path)


class RunEmpiricalInfluenzaEvalTests(unittest.TestCase):
    def test_three_claims_create_six_result_rows(self):
        text_results, graph_results, _summary = (
            evaluate_temporary_artifacts()
        )

        self.assertEqual(len(text_results), 3)
        self.assertEqual(len(graph_results), 3)
        self.assertEqual(len(text_results) + len(graph_results), 6)
        self.assertEqual(
            [row["candidate_id"] for row in text_results],
            [claim["candidate_id"] for claim in make_claims()],
        )

    def test_text_rag_is_perfect_when_chunks_match(self):
        text_results, _graph_results, _summary = (
            evaluate_temporary_artifacts()
        )

        for row in text_results:
            self.assertTrue(row["status_correct"])
            self.assertEqual(row["present_edge_recall"], 1.0)
            self.assertEqual(row["missing_edge_recall"], 1.0)
            self.assertTrue(row["lag_correct"])
            self.assertTrue(row["score_match"])
            self.assertTrue(row["threshold_match"])
            self.assertTrue(row["paired_week_count_match"])
            self.assertEqual(row["must_not_include_violations"], 0)

    def test_graphrag_is_perfect_when_context_matches(self):
        _text_results, graph_results, _summary = (
            evaluate_temporary_artifacts()
        )

        for row in graph_results:
            self.assertTrue(row["status_correct"])
            self.assertEqual(row["present_edge_recall"], 1.0)
            self.assertEqual(row["missing_edge_recall"], 1.0)
            self.assertTrue(row["lag_correct"])
            self.assertTrue(row["score_match"])
            self.assertTrue(row["threshold_match"])
            self.assertTrue(row["paired_week_count_match"])
            self.assertEqual(row["must_not_include_violations"], 0)

    def test_score_mismatch_is_detected(self):
        graph = make_graph_context()
        graph["evidence_edges"][0]["score"] = 0.50

        _text_results, graph_results, _summary = (
            evaluate_temporary_artifacts(graph_context=graph)
        )

        self.assertFalse(graph_results[0]["score_match"])
        self.assertIn("score mismatch", graph_results[0]["notes"])

    def test_lag_mismatch_is_detected(self):
        text = make_text_corpus()
        text[1]["text"] = text[1]["text"].replace(
            "Lag weeks: 1.",
            "Lag weeks: 3.",
        )

        text_results, _graph_results, _summary = (
            evaluate_temporary_artifacts(text_corpus=text)
        )

        self.assertFalse(text_results[1]["lag_correct"])
        self.assertIn("lag mismatch", text_results[1]["notes"])

    def test_missing_claim_promoted_as_present_is_a_violation(self):
        text = make_text_corpus()
        missing_chunk = text[2]
        missing_chunk["status"] = "present"
        missing_chunk["text"] = missing_chunk["text"].replace(
            "Status: missing.",
            "Status: present.",
        )

        text_results, _graph_results, _summary = (
            evaluate_temporary_artifacts(text_corpus=text)
        )
        result = text_results[2]

        self.assertFalse(result["status_correct"])
        self.assertEqual(result["mentioned_evidence_edges"], EDGE_TYPE)
        self.assertEqual(result["missing_edge_recall"], 0.0)
        self.assertEqual(result["must_not_include_violations"], 1)

    def test_summary_has_required_columns_and_two_methods(self):
        text_results, graph_results, summary = (
            evaluate_temporary_artifacts()
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            text_path = temp_path / "text_results.csv"
            graph_path = temp_path / "graph_results.csv"
            summary_path = temp_path / "summary.csv"
            write_csv(text_path, text_results, RESULT_COLUMNS)
            write_csv(graph_path, graph_results, RESULT_COLUMNS)
            write_csv(summary_path, summary, SUMMARY_COLUMNS)
            with summary_path.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as input_file:
                reader = csv.DictReader(input_file)
                written_summary = list(reader)
            with text_path.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as input_file:
                result_reader = csv.DictReader(input_file)
                list(result_reader)

        self.assertEqual(reader.fieldnames, SUMMARY_COLUMNS)
        self.assertEqual(result_reader.fieldnames, RESULT_COLUMNS)
        self.assertEqual(len(written_summary), 2)
        self.assertEqual(
            [row["method"] for row in written_summary],
            METHODS,
        )
        for row in summary:
            self.assertEqual(row["case_count"], 3)
            self.assertEqual(row["status_accuracy"], 1.0)
            self.assertEqual(row["avg_present_edge_recall"], 1.0)
            self.assertEqual(row["avg_missing_edge_recall"], 1.0)
            self.assertEqual(row["lag_accuracy"], 1.0)
            self.assertEqual(row["score_accuracy"], 1.0)
            self.assertEqual(row["threshold_accuracy"], 1.0)
            self.assertEqual(row["paired_week_count_accuracy"], 1.0)
            self.assertEqual(
                row["total_must_not_include_violations"],
                0,
            )


if __name__ == "__main__":
    unittest.main()
