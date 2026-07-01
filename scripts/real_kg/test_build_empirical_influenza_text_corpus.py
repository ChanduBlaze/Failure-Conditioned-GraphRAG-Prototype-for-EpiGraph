"""Tests for the empirical influenza Text-RAG corpus builder."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.real_kg.build_empirical_influenza_text_corpus import (
    OUTPUT_FIELDS,
    REQUIRED_COLUMNS,
    build_corpus,
    load_claim_rows,
    write_corpus,
)


CANDIDATES = [
    (
        "real_signal_outpatient_ili_activity",
        "Outpatient ILI activity",
    ),
    (
        "real_signal_influenza_a_wastewater_concentration",
        "Influenza A wastewater concentration",
    ),
    (
        "real_signal_influenza_test_positivity",
        "Influenza test positivity",
    ),
]


def make_claim(candidate, status):
    candidate_id, candidate_name = candidate
    insufficient = status == "insufficient"
    return {
        "case_id": "real_us_flu_empirical_multicandidate_001",
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "target_signal_id": (
            "real_signal_us_influenza_hospitalization_rate_flusurv"
        ),
        "target_signal_name": (
            "U.S. influenza hospitalization rate from FluSurv-NET"
        ),
        "edge_type": "LEADING_INDICATOR_FOR",
        "status": status,
        "source_dataset": (
            "Delphi Epidata FluSurv / CDC FluSurv-NET; candidate dataset"
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
        "evidence_sentence": (
            f"Controlled empirical evidence sentence for {candidate_name}."
        ),
        "limitation": (
            "Empirical screening evidence only; not causal proof. Lag 0 was "
            "retained only as a concurrent-association diagnostic."
        ),
    }


def write_claims(path, claims):
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(claims)


class BuildEmpiricalInfluenzaTextCorpusTests(unittest.TestCase):
    def test_generates_one_chunk_per_empirical_claim(self):
        claims = [
            make_claim(CANDIDATES[0], "present"),
            make_claim(CANDIDATES[1], "missing"),
            make_claim(CANDIDATES[2], "insufficient"),
        ]

        chunks = build_corpus(claims)

        self.assertEqual(len(chunks), 3)
        self.assertEqual(
            [chunk["candidate_id"] for chunk in chunks],
            [claim["candidate_id"] for claim in claims],
        )

    def test_chunk_includes_all_empirical_evidence_facts(self):
        claim = make_claim(CANDIDATES[0], "present")

        chunk = build_corpus([claim])[0]

        for value in [
            claim["candidate_name"],
            claim["target_signal_name"],
            claim["lag_weeks"],
            claim["score"],
            claim["threshold"],
            claim["paired_week_count"],
            claim["minimum_paired_weeks"],
            claim["method"],
            claim["source_dataset"],
            claim["region"],
            claim["time_window_start"],
            claim["time_window_end"],
            claim["evidence_sentence"],
            claim["limitation"],
        ]:
            self.assertIn(value, chunk["text"])
        self.assertIn("empirical evidence threshold was met", chunk["text"])

    def test_preserves_claim_csv_candidate_order(self):
        claims = [
            make_claim(CANDIDATES[0], "present"),
            make_claim(CANDIDATES[1], "present"),
            make_claim(CANDIDATES[2], "present"),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "claims.csv"
            write_claims(path, claims)

            chunks = build_corpus(load_claim_rows(path))

        self.assertEqual(
            [chunk["candidate_id"] for chunk in chunks],
            [candidate[0] for candidate in CANDIDATES],
        )

    def test_present_missing_and_insufficient_status_text(self):
        claims = [
            make_claim(CANDIDATES[0], "present"),
            make_claim(CANDIDATES[1], "missing"),
            make_claim(CANDIDATES[2], "insufficient"),
        ]

        chunks = build_corpus(claims)
        texts = {chunk["status"]: chunk["text"].lower() for chunk in chunks}

        self.assertIn(
            "empirical evidence threshold was met",
            texts["present"],
        )
        self.assertIn(
            "empirical evidence threshold was not met",
            texts["missing"],
        )
        self.assertIn(
            "overlapping data were insufficient",
            texts["insufficient"],
        )

    def test_output_json_has_expected_fields(self):
        chunks = build_corpus(
            [make_claim(CANDIDATES[0], "present")]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "corpus.json"
            write_corpus(output_path, chunks)
            with output_path.open("r", encoding="utf-8") as input_file:
                written = json.load(input_file)

        self.assertEqual(set(written[0]), set(OUTPUT_FIELDS))
        self.assertEqual(
            written[0]["source_type"],
            "empirical_evidence_claim",
        )
        self.assertTrue(
            written[0]["chunk_id"].startswith("empirical_chunk__")
        )
        self.assertTrue(
            written[0]["evidence_claim_id"].startswith(
                "empirical_claim__"
            )
        )


if __name__ == "__main__":
    unittest.main()
