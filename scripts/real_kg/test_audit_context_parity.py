"""Tests for deterministic real-artifact context parity auditing."""

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.real_kg.audit_context_parity import (
    CLAIM_COLUMNS,
    OUTPUT_COLUMNS,
    audit_parity,
    write_audit,
)


REAL_KG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = REAL_KG_DIR.parents[1]
AUDIT_PATH = REAL_KG_DIR / "audit_context_parity.py"

CASE_ID = "real_failure_case_001"
TARGET_ID = "real_target_signal"
TARGET_NAME = "Target signal"
EDGE_TYPE = "LEADING_INDICATOR_FOR"
METHOD = "lagged_pearson_correlation_v1"
REGION = "Test region"
START = "2025-W01"
END = "2025-W10"
THRESHOLD = "0.60"
LIMITATION = "Associational screening evidence only; not causal proof."

CANDIDATES = [
    ("candidate_wastewater", "Wastewater activity", "present", "2", "0.99"),
    ("candidate_ili", "Outpatient ILI activity", "present", "1", "0.88"),
    ("candidate_positivity", "Test positivity", "present", "1", "0.71"),
    ("candidate_humidity", "Humidity anomaly", "missing", "4", "0.40"),
]


def evidence_id(candidate_id):
    return f"evidence_{candidate_id}"


def dataset_name(candidate_name):
    return f"Target dataset; {candidate_name} dataset"


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
            "source_dataset": dataset_name(candidate_name),
            "method": METHOD,
            "region": REGION,
            "time_window_start": START,
            "time_window_end": END,
            "lag_weeks": lag_weeks,
            "score": score,
            "threshold": THRESHOLD,
            "evidence_sentence": (
                f"{candidate_name} has {status} screening evidence."
            ),
            "limitation": LIMITATION,
        }
        for candidate_id, candidate_name, status, lag_weeks, score in CANDIDATES
    ]


def make_text_corpus():
    return [
        {
            "chunk_id": f"chunk_{candidate_id}",
            "case_id": CASE_ID,
            "candidate_id": candidate_id,
            "target_signal_id": TARGET_ID,
            "edge_type": EDGE_TYPE,
            "status": status,
            "text": (
                f"Status: {status}.\n"
                f"Candidate: {candidate_name} ({candidate_id}).\n"
                f"Target signal: {TARGET_NAME} ({TARGET_ID}).\n"
                f"Edge type: {EDGE_TYPE}.\n"
                f"Region: {REGION}.\n"
                f"Time window: {START} through {END}.\n"
                f"Lag weeks: {lag_weeks}.\n"
                f"Score: {score}.\n"
                f"Threshold: {THRESHOLD}.\n"
                f"Method: {METHOD}.\n"
                f"Source dataset: {dataset_name(candidate_name)}.\n"
                f"Limitation: {LIMITATION}"
            ),
        }
        for candidate_id, candidate_name, status, lag_weeks, score in CANDIDATES
    ]


def make_graph_context():
    candidates = []
    support_nodes = []
    support_edges = []
    for candidate_id, candidate_name, status, lag_weeks, score in CANDIDATES:
        claim_id = evidence_id(candidate_id)
        candidates.append(
            {
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                # Humidity has no positive typed-edge ranking contribution.
                "score": float(score) if status == "present" else 0,
                "evidence_edges": [
                    {
                        "evidence_claim_id": claim_id,
                        "target_signal_id": TARGET_ID,
                        "edge_type": EDGE_TYPE,
                        "status": status,
                        "score": float(score),
                        "lag_weeks": int(lag_weeks),
                        "method": METHOD,
                        "source_dataset": dataset_name(candidate_name),
                        "region": REGION,
                        "time_window_start": START,
                        "time_window_end": END,
                        "limitation": LIMITATION,
                    }
                ],
            }
        )
        support_nodes.extend(
            [
                {
                    "type": "CandidateDriver",
                    "id": candidate_id,
                    "name": candidate_name,
                },
                {
                    "type": "EvidenceClaim",
                    "id": claim_id,
                    "threshold": float(THRESHOLD),
                    "status": status,
                    "score": float(score),
                    "lag_weeks": int(lag_weeks),
                    "method": METHOD,
                    "limitation": LIMITATION,
                },
            ]
        )
        if status == "present":
            support_edges.append(
                {
                    "source_id": candidate_id,
                    "edge_type": EDGE_TYPE,
                    "target_id": TARGET_ID,
                    "evidence_id": claim_id,
                }
            )
    return {
        "case_id": CASE_ID,
        "candidates": candidates,
        "support_nodes": support_nodes,
        "support_edges": support_edges,
    }


def find_row(rows, candidate_id):
    return next(row for row in rows if row["candidate_id"] == candidate_id)


class ContextParityAuditTests(unittest.TestCase):
    def test_four_claims_have_full_text_and_graph_parity(self):
        rows = audit_parity(
            make_claims(),
            make_text_corpus(),
            make_graph_context(),
        )

        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row["_text_parity_pass"] for row in rows))
        self.assertTrue(all(row["_graph_parity_pass"] for row in rows))
        self.assertTrue(all(row["parity_pass"] for row in rows))

    def test_humidity_missing_evidence_and_original_score_pass(self):
        graph_context = make_graph_context()
        humidity_candidate = next(
            candidate
            for candidate in graph_context["candidates"]
            if candidate["candidate_id"] == "candidate_humidity"
        )
        self.assertEqual(humidity_candidate["score"], 0)
        self.assertLess(
            humidity_candidate["evidence_edges"][0]["score"],
            float(THRESHOLD),
        )

        rows = audit_parity(
            make_claims(),
            make_text_corpus(),
            graph_context,
        )
        humidity_row = find_row(rows, "candidate_humidity")
        self.assertTrue(humidity_row["graph_evidence_found"])
        self.assertTrue(humidity_row["graph_has_score"])
        self.assertTrue(humidity_row["parity_pass"])

    def test_missing_text_chunk_fails_candidate_parity(self):
        text_corpus = [
            chunk
            for chunk in make_text_corpus()
            if chunk["candidate_id"] != "candidate_ili"
        ]

        rows = audit_parity(make_claims(), text_corpus, make_graph_context())

        row = find_row(rows, "candidate_ili")
        self.assertFalse(row["text_chunk_found"])
        self.assertFalse(row["_text_parity_pass"])
        self.assertFalse(row["parity_pass"])

    def test_missing_graph_evidence_edge_fails_candidate_parity(self):
        graph_context = make_graph_context()
        candidate = next(
            candidate
            for candidate in graph_context["candidates"]
            if candidate["candidate_id"] == "candidate_positivity"
        )
        candidate["evidence_edges"] = []

        rows = audit_parity(make_claims(), make_text_corpus(), graph_context)

        row = find_row(rows, "candidate_positivity")
        self.assertTrue(row["graph_candidate_found"])
        self.assertFalse(row["graph_evidence_found"])
        self.assertFalse(row["_graph_parity_pass"])
        self.assertFalse(row["parity_pass"])

    def test_missing_claim_promoted_to_positive_edge_fails(self):
        graph_context = make_graph_context()
        graph_context["support_edges"].append(
            {
                "source_id": "candidate_humidity",
                "edge_type": EDGE_TYPE,
                "target_id": TARGET_ID,
                "evidence_id": evidence_id("candidate_humidity"),
            }
        )

        rows = audit_parity(make_claims(), make_text_corpus(), graph_context)

        row = find_row(rows, "candidate_humidity")
        self.assertFalse(row["_graph_parity_pass"])
        self.assertFalse(row["parity_pass"])
        self.assertIn("positive typed edge", row["notes"])

    def test_output_csv_has_required_columns(self):
        rows = audit_parity(
            make_claims(),
            make_text_corpus(),
            make_graph_context(),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "audit.csv"
            write_audit(output, rows)

            with output.open("r", newline="", encoding="utf-8") as input_file:
                reader = csv.DictReader(input_file)
                written_rows = list(reader)

            self.assertEqual(reader.fieldnames, OUTPUT_COLUMNS)
            self.assertEqual(len(written_rows), 4)

    def test_cli_writes_output_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            claims_path = temp_path / "claims.csv"
            text_path = temp_path / "text.json"
            graph_path = temp_path / "graph.json"
            output_path = temp_path / "audit.csv"

            with claims_path.open(
                "w",
                newline="",
                encoding="utf-8",
            ) as claims_file:
                writer = csv.DictWriter(
                    claims_file,
                    fieldnames=CLAIM_COLUMNS,
                )
                writer.writeheader()
                writer.writerows(make_claims())
            with text_path.open("w", encoding="utf-8") as text_file:
                json.dump(make_text_corpus(), text_file)
            with graph_path.open("w", encoding="utf-8") as graph_file:
                json.dump(make_graph_context(), graph_file)

            result = subprocess.run(
                [
                    sys.executable,
                    str(AUDIT_PATH),
                    "--claims",
                    str(claims_path),
                    "--text-corpus",
                    str(text_path),
                    "--graph-context",
                    str(graph_path),
                    "--output",
                    str(output_path),
                ],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output_path.is_file())
            self.assertIn("Total evidence claims: 4", result.stdout)
            self.assertIn("Full parity passes: 4", result.stdout)


if __name__ == "__main__":
    unittest.main()
