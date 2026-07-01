"""Tests for the offline real-data LLM-only baseline framework."""

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.real_kg.build_real_llm_only_prompts import (
    RESTRICTED_PROMPT_TERMS,
    build_prompts,
    write_prompts,
)
from scripts.real_kg.evaluate_real_llm_only_outputs import (
    RESULT_COLUMNS,
    evaluate_outputs,
    forbidden_phrase_count,
    write_results,
)


FAILURE_CASE_ID = "real_us_flu_wastewater_leading_indicator_001"
TARGET_NAME = "U.S. influenza hospitalization rate"
EDGE_TYPE = "LEADING_INDICATOR_FOR"

CANDIDATES = [
    (
        "real_signal_influenza_a_wastewater_activity",
        "Influenza A wastewater activity",
        "present",
        2,
    ),
    (
        "real_signal_outpatient_ili_activity",
        "Outpatient ILI activity",
        "present",
        1,
    ),
    (
        "real_signal_influenza_test_positivity",
        "Influenza test positivity",
        "present",
        1,
    ),
    (
        "real_signal_humidity_anomaly",
        "Humidity anomaly",
        "missing",
        4,
    ),
]


def make_cases():
    cases = []
    for index, (candidate_id, candidate_name, status, lag) in enumerate(
        CANDIDATES,
        start=1,
    ):
        present = status == "present"
        case = {
            "id": f"real_case_{index:03d}",
            "failure_case_id": FAILURE_CASE_ID,
            "expected_candidate_id": candidate_id,
            "expected_present_edges": [EDGE_TYPE] if present else [],
            "expected_missing_edges": [] if present else [EDGE_TYPE],
            "expected_status": status,
            "expected_lag_weeks": lag,
            "must_not_include": [
                "proves causality",
                "definitively causes",
            ],
            "question": (
                "Using the real-data evidence graph, determine whether "
                f"{candidate_name} has {EDGE_TYPE} evidence for {TARGET_NAME}."
            ),
            "notes": "Synthetic LLM-only baseline test case.",
        }
        if present:
            case["minimum_expected_score"] = 0.6
        else:
            case["maximum_expected_score"] = 0.6
        cases.append(case)
    return cases


def make_graph_context():
    return {
        "case_id": FAILURE_CASE_ID,
        "failure_case": {
            "id": FAILURE_CASE_ID,
            "name": FAILURE_CASE_ID,
        },
        "target_signal": {
            "id": "target_signal",
            "name": TARGET_NAME,
        },
        # Deliberately include restricted evidence fields. The prompt builder
        # must extract names only and never serialize these values.
        "candidates": [
            {
                "candidate_id": candidate_id,
                "candidate_name": candidate_name,
                "score": 0.9 - index / 10,
                "evidence_edges": [
                    {
                        "edge_type": EDGE_TYPE,
                        "threshold": 0.6,
                        "lag_weeks": lag,
                        "source_dataset": "restricted source",
                        "evidence_sentence": "restricted evidence",
                    }
                ],
            }
            for index, (
                candidate_id,
                candidate_name,
                _status,
                lag,
            ) in enumerate(CANDIDATES)
        ],
        "support_edges": [{"edge_type": EDGE_TYPE}],
    }


def make_outputs():
    outputs = []
    for index, (candidate_id, candidate_name, status, _lag) in enumerate(
        CANDIDATES,
        start=1,
    ):
        if status == "present":
            response = (
                f"{candidate_name} ({candidate_id}) is supported as a "
                "leading indicator for the target."
            )
        else:
            response = (
                f"{candidate_name} ({candidate_id}) is unsupported as a "
                "leading indicator and has weak evidence."
            )
        outputs.append(
            {
                "case_id": f"real_case_{index:03d}",
                "method": "llm_only",
                "model": "manual_or_external",
                "response": response,
            }
        )
    return outputs


class RealLlmOnlyBaselineTests(unittest.TestCase):
    def test_prompt_builder_creates_four_safe_prompts(self):
        prompts = build_prompts(make_cases(), make_graph_context())

        self.assertEqual(len(prompts), 4)
        for prompt_record in prompts:
            prompt = prompt_record["prompt"]
            self.assertEqual(prompt_record["method"], "llm_only")
            self.assertIn(TARGET_NAME, prompt)
            for candidate_id, candidate_name, _status, _lag in CANDIDATES:
                self.assertIn(candidate_id, prompt)
                self.assertIn(candidate_name, prompt)

    def test_prompts_exclude_all_restricted_evidence_content(self):
        prompts = build_prompts(make_cases(), make_graph_context())

        for prompt_record in prompts:
            lowered = prompt_record["prompt"].lower()
            self.assertEqual(
                prompt_record["failure_case_id"],
                FAILURE_CASE_ID,
            )
            self.assertNotIn(FAILURE_CASE_ID.lower(), lowered)
            self.assertNotIn("wastewater_leading_indicator", lowered)
            self.assertNotIn("leading_indicator", lowered)
            for term in RESTRICTED_PROMPT_TERMS:
                self.assertNotIn(term, lowered)
            self.assertNotIn("restricted source", lowered)
            self.assertNotIn("restricted evidence", lowered)
            self.assertNotIn(EDGE_TYPE.lower(), lowered)

            wastewater_lines = [
                line
                for line in prompt_record["prompt"].splitlines()
                if "wastewater" in line.lower()
            ]
            self.assertTrue(wastewater_lines)
            self.assertTrue(
                all(
                    line.startswith(
                        "- Influenza A wastewater activity "
                        "(real_signal_influenza_a_wastewater_activity)"
                    )
                    or line.startswith(
                        "Candidate to assess: Influenza A wastewater activity "
                        "(real_signal_influenza_a_wastewater_activity)"
                    )
                    for line in wastewater_lines
                )
            )

    def test_present_candidate_support_is_scored(self):
        rows = evaluate_outputs(make_cases(), make_outputs())
        row = rows[0]

        self.assertTrue(row["candidate_correct"])
        self.assertTrue(row["status_correct"])
        self.assertEqual(row["mentioned_evidence_edges"], EDGE_TYPE)
        self.assertEqual(row["present_edge_recall"], 1.0)
        self.assertFalse(row["lag_correct"])
        self.assertTrue(row["score_meets_minimum"])

    def test_humidity_unsupported_response_is_scored_as_missing(self):
        rows = evaluate_outputs(make_cases(), make_outputs())
        row = rows[-1]

        self.assertTrue(row["candidate_correct"])
        self.assertTrue(row["status_correct"])
        self.assertEqual(row["mentioned_evidence_edges"], "")
        self.assertEqual(row["identified_missing_edges"], EDGE_TYPE)
        self.assertEqual(row["missing_edge_recall"], 1.0)
        self.assertFalse(row["lag_correct"])
        self.assertTrue(row["score_meets_minimum"])

    def test_affirmative_definitively_causes_counts_as_violation(self):
        outputs = make_outputs()
        outputs[0]["response"] += (
            " Influenza A wastewater activity definitively causes "
            "hospitalizations."
        )

        rows = evaluate_outputs(make_cases(), outputs)

        self.assertEqual(rows[0]["must_not_include_violations"], 1)

    def test_negated_definitively_causes_is_not_a_violation(self):
        outputs = make_outputs()
        outputs[0]["response"] += (
            " This does not mean Influenza A wastewater activity "
            "definitively causes hospitalizations."
        )

        rows = evaluate_outputs(make_cases(), outputs)

        self.assertEqual(rows[0]["must_not_include_violations"], 0)

    def test_affirmative_proves_causality_counts_as_violation(self):
        outputs = make_outputs()
        outputs[0]["response"] += " This proves causality."

        rows = evaluate_outputs(make_cases(), outputs)

        self.assertEqual(rows[0]["must_not_include_violations"], 1)

    def test_does_not_prove_causality_is_not_a_violation(self):
        outputs = make_outputs()
        outputs[0]["response"] += " This does not prove causality."

        rows = evaluate_outputs(make_cases(), outputs)

        self.assertEqual(rows[0]["must_not_include_violations"], 0)

    def test_all_negated_causal_caveats_produce_zero_violations(self):
        outputs = make_outputs()
        for output, (_id, candidate_name, _status, _lag) in zip(
            outputs,
            CANDIDATES,
        ):
            output["response"] += (
                " This does not prove causality and does not mean "
                f"{candidate_name} definitively causes changes."
            )

        rows = evaluate_outputs(make_cases(), outputs)

        self.assertTrue(
            all(row["must_not_include_violations"] == 0 for row in rows)
        )

    def test_other_documented_negated_caveats_are_not_violations(self):
        examples = [
            (
                "Do not claim that humidity definitively causes changes.",
                ["definitively causes"],
            ),
            ("This is not causal proof.", ["causal proof"]),
            (
                "The association does not imply causality.",
                ["imply causality"],
            ),
        ]
        for response, phrases in examples:
            with self.subTest(response=response):
                self.assertEqual(
                    forbidden_phrase_count(response, phrases),
                    0,
                )

    def test_invented_numeric_score_fails_score_check(self):
        outputs = make_outputs()
        outputs[0]["response"] += " The score is 0.95."

        rows = evaluate_outputs(make_cases(), outputs)

        self.assertTrue(rows[0]["status_correct"])
        self.assertFalse(rows[0]["score_meets_minimum"])

    def test_missing_output_creates_clear_failure_row(self):
        outputs = make_outputs()[:-1]

        rows = evaluate_outputs(make_cases(), outputs)
        row = rows[-1]

        self.assertFalse(row["candidate_correct"])
        self.assertFalse(row["status_correct"])
        self.assertIn("No LLM-only output found", row["notes"])

    def test_writers_create_expected_json_and_csv_shapes(self):
        prompts = build_prompts(make_cases(), make_graph_context())
        rows = evaluate_outputs(make_cases(), make_outputs())
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            prompt_path = temp_path / "prompts.json"
            result_path = temp_path / "results.csv"

            write_prompts(prompt_path, prompts)
            write_results(result_path, rows)

            self.assertTrue(prompt_path.is_file())
            with result_path.open(
                "r",
                newline="",
                encoding="utf-8",
            ) as result_file:
                reader = csv.DictReader(result_file)
                written_rows = list(reader)

            self.assertEqual(reader.fieldnames, RESULT_COLUMNS)
            self.assertEqual(len(written_rows), 4)


if __name__ == "__main__":
    unittest.main()
