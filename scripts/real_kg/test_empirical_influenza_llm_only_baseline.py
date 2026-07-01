"""Tests for the empirical influenza manual LLM-only baseline."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.real_kg.build_empirical_influenza_llm_only_prompts import (
    REQUIRED_COLUMNS,
    RESTRICTED_PROMPT_TERMS,
    build_prompts,
    read_claims as read_prompt_claims,
    write_prompts,
)
from scripts.real_kg.evaluate_empirical_influenza_llm_only_outputs import (
    RESULT_COLUMNS,
    SUMMARY_COLUMNS,
    build_summary,
    classify_response,
    evaluate_outputs,
    read_json,
    write_csv,
)


CASE_ID = "real_us_flu_empirical_multicandidate_001"
TARGET_ID = "real_signal_us_influenza_hospitalization_rate_flusurv"
TARGET_NAME = "U.S. influenza hospitalization rate from FluSurv-NET"
EDGE_TYPE = "LEADING_INDICATOR_FOR"

CANDIDATES = [
    (
        "real_signal_influenza_a_wastewater_concentration",
        "Influenza A wastewater concentration",
        "present",
        "1",
        "0.947016",
    ),
    (
        "real_signal_outpatient_ili_activity",
        "Outpatient ILI activity",
        "present",
        "1",
        "0.958037",
    ),
    (
        "real_signal_influenza_test_positivity",
        "Influenza test positivity",
        "present",
        "1",
        "0.925810",
    ),
    (
        "real_signal_negative_control_permuted_surveillance",
        "Negative-control permuted surveillance signal",
        "missing",
        "4",
        "-0.048027",
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
            "source_dataset": f"Restricted source for {candidate_name}",
            "method": "lagged_pearson_correlation_empirical_v1",
            "region": "United States / FluSurv-NET catchment",
            "time_window_start": "2024-W40",
            "time_window_end": "2025-W20",
            "lag_weeks": lag,
            "score": score,
            "threshold": "0.60",
            "paired_week_count": "29",
            "minimum_paired_weeks": "8",
            "evidence_sentence": (
                f"Restricted evidence sentence for {candidate_name}."
            ),
            "limitation": (
                "Empirical screening evidence only; not causal proof."
            ),
        }
        for candidate_id, candidate_name, status, lag, score in CANDIDATES
    ]


def write_claims(path, claims):
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(claims)


def make_output(claim, response):
    return {
        "case_id": claim["case_id"],
        "candidate_id": claim["candidate_id"],
        "model": "fresh_chat_manual",
        "response": response,
    }


class EmpiricalInfluenzaLlmOnlyBaselineTests(unittest.TestCase):
    def test_assessment_present_overrides_body_caveats(self):
        response = (
            "Assessment: Present — treat X as a plausible "
            "LEADING_INDICATOR_FOR Y."
        )

        self.assertEqual(classify_response(response), "present")

    def test_conclusion_marks_relationship_present(self):
        response = (
            "Conclusion: I would mark the relationship as present."
        )

        self.assertEqual(classify_response(response), "present")

    def test_present_edge_survives_insufficient_by_itself_caveat(self):
        response = (
            "LEADING_INDICATOR_FOR is present, with the caveat that X is "
            "insufficient by itself for reliable hospitalization magnitude "
            "forecasting."
        )

        self.assertEqual(classify_response(response), "present")

    def test_explicit_missing_assessment_is_missing(self):
        response = (
            "Assessment: Missing relationship. X should not be treated as a "
            "LEADING_INDICATOR_FOR."
        )

        self.assertEqual(classify_response(response), "missing")

    def test_not_enough_evidence_to_determine_is_insufficient(self):
        response = (
            "There is not enough evidence to determine whether the "
            "relationship holds."
        )

        self.assertEqual(classify_response(response), "insufficient")

    def test_prompt_builder_creates_one_prompt_per_claim(self):
        claims = make_claims()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            claims_path = temp_path / "claims.csv"
            prompt_path = temp_path / "prompts.json"
            write_claims(claims_path, claims)

            prompts = build_prompts(read_prompt_claims(claims_path))
            write_prompts(prompt_path, prompts)
            written = json.loads(prompt_path.read_text(encoding="utf-8"))

        self.assertEqual(len(written), 4)
        self.assertEqual(
            [record["candidate_id"] for record in written],
            [claim["candidate_id"] for claim in claims],
        )
        self.assertTrue(
            all(record["case_id"] == CASE_ID for record in written)
        )

    def test_prompt_text_does_not_leak_empirical_evidence(self):
        claims = make_claims()
        prompts = build_prompts(claims)

        for claim, record in zip(claims, prompts):
            prompt = record["prompt"]
            lowered = prompt.lower()
            self.assertEqual(record["expected_status"], claim["status"])
            self.assertNotIn(claim["candidate_id"].lower(), lowered)
            self.assertNotIn(claim["target_signal_id"].lower(), lowered)
            self.assertNotIn(claim["score"], prompt)
            self.assertNotIn(claim["threshold"], prompt)
            self.assertNotIn(claim["source_dataset"].lower(), lowered)
            self.assertNotIn(claim["evidence_sentence"].lower(), lowered)
            for term in RESTRICTED_PROMPT_TERMS:
                self.assertNotIn(term, lowered)
            self.assertIn(claim["candidate_name"], prompt)
            self.assertIn(TARGET_NAME, prompt)
            self.assertIn(
                "present, missing, or insufficient",
                prompt,
            )

    def test_present_response_is_correct_for_expected_present(self):
        claim = make_claims()[0]
        output = make_output(
            claim,
            (
                f"{claim['candidate_name']} should be treated as a valid "
                "leading indicator. Status: present."
            ),
        )

        row = evaluate_outputs([claim], [output])[0]

        self.assertEqual(row["predicted_status"], "present")
        self.assertTrue(row["status_correct"])
        self.assertEqual(row["mentioned_evidence_edges"], EDGE_TYPE)
        self.assertEqual(row["present_edge_recall"], 1.0)
        self.assertEqual(row["must_not_include_violations"], 0)

    def test_missing_and_insufficient_responses_preserve_missing_edge(self):
        claim = make_claims()[-1]
        missing_output = make_output(
            claim,
            (
                "There is not enough evidence to treat this as a leading "
                "indicator, so the relationship is missing."
            ),
        )
        insufficient_output = make_output(
            claim,
            (
                "I cannot determine whether it is a leading indicator due "
                "to lack of evidence; the result is insufficient."
            ),
        )

        missing_row = evaluate_outputs([claim], [missing_output])[0]
        insufficient_row = evaluate_outputs(
            [claim],
            [insufficient_output],
        )[0]

        self.assertEqual(missing_row["predicted_status"], "missing")
        self.assertTrue(missing_row["status_correct"])
        self.assertEqual(missing_row["missing_edge_recall"], 1.0)
        self.assertEqual(
            insufficient_row["predicted_status"],
            "insufficient",
        )
        self.assertFalse(insufficient_row["status_correct"])
        self.assertEqual(insufficient_row["missing_edge_recall"], 1.0)
        self.assertEqual(
            insufficient_row["must_not_include_violations"],
            0,
        )

    def test_missing_claim_promoted_as_present_is_a_violation(self):
        claim = make_claims()[-1]
        output = make_output(
            claim,
            (
                f"{claim['candidate_name']} should be treated as a valid "
                "leading indicator. Status: present."
            ),
        )

        row = evaluate_outputs([claim], [output])[0]

        self.assertFalse(row["status_correct"])
        self.assertEqual(row["mentioned_evidence_edges"], EDGE_TYPE)
        self.assertEqual(row["missing_edge_recall"], 0.0)
        self.assertEqual(row["must_not_include_violations"], 1)

    def test_invented_score_claim_is_detected(self):
        claim = make_claims()[0]
        output = make_output(
            claim,
            (
                "This is a valid leading indicator and the correlation is "
                "0.82. Status: present."
            ),
        )

        row = evaluate_outputs([claim], [output])[0]

        self.assertTrue(row["score_claimed"])
        self.assertEqual(row["mentioned_score"], "0.82")

    def test_invented_threshold_claim_is_detected(self):
        claim = make_claims()[0]
        output = make_output(
            claim,
            (
                "This is a valid leading indicator using a threshold of "
                "0.60. Status: present."
            ),
        )

        row = evaluate_outputs([claim], [output])[0]

        self.assertTrue(row["threshold_claimed"])
        self.assertEqual(row["mentioned_threshold"], "0.60")

    def test_summary_metrics_and_output_columns(self):
        present_claim = make_claims()[0]
        missing_claim = make_claims()[-1]
        outputs = [
            make_output(
                present_claim,
                (
                    "This is a valid leading indicator with correlation "
                    "0.82 and threshold 0.60. Status: present."
                ),
            ),
            make_output(
                missing_claim,
                (
                    "This is a valid leading indicator. Status: present. "
                    "This association is not causal proof."
                ),
            ),
        ]
        rows = evaluate_outputs(
            [present_claim, missing_claim],
            outputs,
        )
        summary = build_summary(rows)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            outputs_path = temp_path / "outputs.json"
            results_path = temp_path / "results.csv"
            summary_path = temp_path / "summary.csv"
            outputs_path.write_text(
                json.dumps(outputs),
                encoding="utf-8",
            )
            loaded_outputs = read_json(
                outputs_path,
                list,
                "manual outputs",
            )
            self.assertEqual(len(loaded_outputs), 2)
            write_csv(results_path, rows, RESULT_COLUMNS)
            write_csv(summary_path, summary, SUMMARY_COLUMNS)
            with results_path.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as input_file:
                result_reader = csv.DictReader(input_file)
                list(result_reader)
            with summary_path.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as input_file:
                summary_reader = csv.DictReader(input_file)
                written_summary = list(summary_reader)

        self.assertEqual(result_reader.fieldnames, RESULT_COLUMNS)
        self.assertEqual(summary_reader.fieldnames, SUMMARY_COLUMNS)
        self.assertEqual(len(written_summary), 1)
        summary_row = summary[0]
        self.assertEqual(summary_row["method"], "empirical_llm_only")
        self.assertEqual(summary_row["case_count"], 2)
        self.assertEqual(summary_row["status_accuracy"], 0.5)
        self.assertEqual(summary_row["avg_present_edge_recall"], 1.0)
        self.assertEqual(summary_row["avg_missing_edge_recall"], 0.5)
        self.assertEqual(summary_row["lag_accuracy"], 0.0)
        self.assertEqual(summary_row["false_positive_edge_claims"], 1)
        self.assertEqual(summary_row["score_claims"], 1)
        self.assertEqual(summary_row["threshold_claims"], 1)
        self.assertEqual(
            summary_row["total_must_not_include_violations"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
