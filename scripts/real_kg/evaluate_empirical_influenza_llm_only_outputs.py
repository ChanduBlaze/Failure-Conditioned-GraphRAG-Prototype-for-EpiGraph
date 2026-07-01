"""Evaluate manual empirical influenza LLM-only responses.

The evaluator is deterministic and offline. It never calls an LLM, reads no
retrieval context, and scores responses against empirical EvidenceClaims.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_CLAIMS = Path(
    "data/real_processed/real_empirical_influenza_evidence_claims.csv"
)
DEFAULT_OUTPUTS = Path(
    "evals/results_real/real_empirical_influenza_llm_only_outputs.json"
)
DEFAULT_RESULTS = Path(
    "evals/results_real/real_empirical_influenza_llm_only_results.csv"
)
DEFAULT_SUMMARY = Path(
    "evals/results_real/real_empirical_influenza_llm_only_summary.csv"
)
METHOD = "empirical_llm_only"
MISSING_STATUSES = {"missing", "insufficient"}
NUMBER_PATTERN = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"

CLAIM_COLUMNS = [
    "case_id",
    "candidate_id",
    "candidate_name",
    "target_signal_id",
    "target_signal_name",
    "edge_type",
    "status",
    "source_dataset",
    "method",
    "region",
    "time_window_start",
    "time_window_end",
    "lag_weeks",
    "score",
    "threshold",
    "paired_week_count",
    "minimum_paired_weeks",
    "evidence_sentence",
    "limitation",
]

RESULT_COLUMNS = [
    "case_id",
    "method",
    "candidate_id",
    "candidate_name",
    "target_signal_id",
    "target_signal_name",
    "expected_status",
    "predicted_status",
    "status_correct",
    "expected_edge_type",
    "mentioned_evidence_edges",
    "present_edge_recall",
    "missing_edge_recall",
    "expected_lag_weeks",
    "mentioned_lag",
    "lag_correct",
    "expected_score",
    "mentioned_score",
    "score_claimed",
    "expected_threshold",
    "mentioned_threshold",
    "threshold_claimed",
    "must_not_include_violations",
    "notes",
]

SUMMARY_COLUMNS = [
    "method",
    "case_count",
    "status_accuracy",
    "avg_present_edge_recall",
    "avg_missing_edge_recall",
    "lag_accuracy",
    "false_positive_edge_claims",
    "score_claims",
    "threshold_claims",
    "total_must_not_include_violations",
]

INSUFFICIENT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\binsufficient\b",
        r"\bcannot determine\b",
        r"\bcan't determine\b",
        r"\bunable to determine\b",
        r"\bcannot assess\b",
        r"\bnot enough information\b",
    )
]

MISSING_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bmissing\b",
        r"\bunsupported\b",
        r"\bnot supported\b",
        r"\bnot enough evidence\b",
        r"\bno evidence\b",
        r"\blacks? evidence\b",
        r"\breject(?:s|ed|ing)?\b",
        r"\bshould not be treated\b",
        r"\bnot (?:a |an )?(?:valid )?leading[- _]indicator\b",
        r"\bdoes not (?:qualify|support)\b",
    )
]

PRESENT_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bstatus\s*(?:is|:)?\s*present\b",
        r"\bsupported as (?:a )?leading[- _]indicator\b",
        r"\bvalid leading[- _]indicator\b",
        r"\bshould be treated as (?:a )?leading[- _]indicator\b",
        r"\bis (?:a )?leading[- _]indicator\b",
        r"\bpresent leading[- _]indicator\b",
        r"\brelationship (?:is|appears) present\b",
    )
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate manual empirical influenza LLM-only responses without "
            "calling an LLM."
        )
    )
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIMS)
    parser.add_argument("--outputs", type=Path, default=DEFAULT_OUTPUTS)
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    return parser.parse_args()


def read_claims(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Empirical claims file not found: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        fieldnames = reader.fieldnames or []
        missing = [
            column for column in CLAIM_COLUMNS if column not in fieldnames
        ]
        if missing:
            raise ValueError(
                "Empirical claims CSV is missing required columns: "
                + ", ".join(missing)
            )
        rows = [
            {
                column: (row.get(column) or "").strip()
                for column in CLAIM_COLUMNS
            }
            for row in reader
        ]
    if not rows:
        raise ValueError("Empirical claims CSV contains no rows.")
    return rows


def read_json(path: Path, expected_type: type, description: str) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"{description} file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as input_file:
            value = json.load(input_file)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON in {description} {path}: {exc}"
        ) from exc
    if not isinstance(value, expected_type):
        raise ValueError(
            f"{description} must contain a {expected_type.__name__}."
        )
    return value


def classify_response(response: str) -> str:
    if any(pattern.search(response) for pattern in INSUFFICIENT_PATTERNS):
        return "insufficient"
    if any(pattern.search(response) for pattern in MISSING_PATTERNS):
        return "missing"
    if any(pattern.search(response) for pattern in PRESENT_PATTERNS):
        return "present"
    return ""


def extract_lag(response: str) -> str:
    patterns = [
        rf"\blag\s*(?:of|=|:|is)?\s*(\d+)\s*weeks?\b",
        rf"\b(\d+)\s*[- ]week\s+lag\b",
        rf"\bleads?\b.{{0,30}}\bby\s+(\d+)\s*weeks?\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def extract_score(response: str) -> str:
    pattern = (
        rf"\b(?:pearson\s+)?(?:correlation(?:\s+coefficient)?|score)"
        rf"\s*(?:of|=|:|is|was|at)?\s*({NUMBER_PATTERN})\b"
    )
    match = re.search(pattern, response, re.IGNORECASE)
    return match.group(1) if match else ""


def extract_threshold(response: str) -> str:
    patterns = [
        rf"\bthreshold\s*(?:of|=|:|is|was|at)?\s*"
        rf"({NUMBER_PATTERN})\b",
        rf"\b({NUMBER_PATTERN})\s+(?:decision\s+)?threshold\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            return match.group(1)
    return ""


def exact_integer_match(actual: str, expected: str) -> bool:
    if not expected:
        return False
    try:
        return int(actual) == int(expected)
    except (TypeError, ValueError):
        return False


def failure_result(
    claim: dict[str, str],
    note: str,
) -> dict[str, Any]:
    expected_status = claim["status"]
    return {
        "case_id": claim["case_id"],
        "method": METHOD,
        "candidate_id": claim["candidate_id"],
        "candidate_name": claim["candidate_name"],
        "target_signal_id": claim["target_signal_id"],
        "target_signal_name": claim["target_signal_name"],
        "expected_status": expected_status,
        "predicted_status": "",
        "status_correct": False,
        "expected_edge_type": claim["edge_type"],
        "mentioned_evidence_edges": "",
        "present_edge_recall": (
            0.0 if expected_status == "present" else 1.0
        ),
        "missing_edge_recall": (
            1.0 if expected_status == "present" else 0.0
        ),
        "expected_lag_weeks": claim["lag_weeks"],
        "mentioned_lag": "",
        "lag_correct": False,
        "expected_score": claim["score"],
        "mentioned_score": "",
        "score_claimed": False,
        "expected_threshold": claim["threshold"],
        "mentioned_threshold": "",
        "threshold_claimed": False,
        "must_not_include_violations": 0,
        "notes": note,
    }


def evaluate_response(
    claim: dict[str, str],
    output: dict[str, Any],
) -> dict[str, Any]:
    response = str(output.get("response", "")).strip()
    if not response:
        return failure_result(claim, "LLM-only response is empty.")

    predicted_status = classify_response(response)
    status_correct = predicted_status == claim["status"]
    supports_edge = predicted_status == "present"
    mentioned_edges = claim["edge_type"] if supports_edge else ""
    expected_status = claim["status"]
    if expected_status == "present":
        present_recall = 1.0 if supports_edge else 0.0
        missing_recall = 1.0
    else:
        present_recall = 1.0
        missing_recall = (
            1.0
            if predicted_status in MISSING_STATUSES and not supports_edge
            else 0.0
        )
    violation = int(
        expected_status in MISSING_STATUSES and supports_edge
    )

    mentioned_lag = extract_lag(response)
    mentioned_score = extract_score(response)
    mentioned_threshold = extract_threshold(response)
    lag_correct = exact_integer_match(
        mentioned_lag,
        claim["lag_weeks"],
    )

    notes = []
    if not predicted_status:
        notes.append("No clear present, missing, or insufficient status.")
    if not status_correct:
        notes.append("Status mismatch.")
    if violation:
        notes.append("Non-present evidence promoted as a positive edge.")
    model = str(output.get("model", "")).strip()
    if model:
        notes.append(f"Model: {model}.")

    return {
        "case_id": claim["case_id"],
        "method": METHOD,
        "candidate_id": claim["candidate_id"],
        "candidate_name": claim["candidate_name"],
        "target_signal_id": claim["target_signal_id"],
        "target_signal_name": claim["target_signal_name"],
        "expected_status": expected_status,
        "predicted_status": predicted_status,
        "status_correct": status_correct,
        "expected_edge_type": claim["edge_type"],
        "mentioned_evidence_edges": mentioned_edges,
        "present_edge_recall": present_recall,
        "missing_edge_recall": missing_recall,
        "expected_lag_weeks": claim["lag_weeks"],
        "mentioned_lag": mentioned_lag,
        "lag_correct": lag_correct,
        "expected_score": claim["score"],
        "mentioned_score": mentioned_score,
        "score_claimed": bool(mentioned_score),
        "expected_threshold": claim["threshold"],
        "mentioned_threshold": mentioned_threshold,
        "threshold_claimed": bool(mentioned_threshold),
        "must_not_include_violations": violation,
        "notes": " ".join(notes) or "Response classified.",
    }


def evaluate_outputs(
    claims: list[dict[str, str]],
    outputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    outputs_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for output in outputs:
        if not isinstance(output, dict):
            raise ValueError("Every LLM-only output must be a JSON object.")
        case_id = str(output.get("case_id", "")).strip()
        candidate_id = str(output.get("candidate_id", "")).strip()
        if not case_id or not candidate_id:
            raise ValueError(
                "Every output needs case_id and candidate_id metadata."
            )
        key = (case_id, candidate_id)
        if key in outputs_by_key:
            raise ValueError(
                f"Duplicate LLM-only output for {case_id!r}/{candidate_id!r}."
            )
        outputs_by_key[key] = output

    rows = []
    for claim in claims:
        key = (claim["case_id"], claim["candidate_id"])
        output = outputs_by_key.get(key)
        if output is None:
            rows.append(
                failure_result(
                    claim,
                    "No LLM-only output found for this candidate.",
                )
            )
        else:
            rows.append(evaluate_response(claim, output))
    return rows


def build_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        raise ValueError("No empirical LLM-only evaluation rows.")
    count = len(rows)
    average = lambda field: sum(
        float(row[field]) for row in rows
    ) / count
    violations = sum(
        int(row["must_not_include_violations"]) for row in rows
    )
    return [
        {
            "method": METHOD,
            "case_count": count,
            "status_accuracy": average("status_correct"),
            "avg_present_edge_recall": average(
                "present_edge_recall"
            ),
            "avg_missing_edge_recall": average(
                "missing_edge_recall"
            ),
            "lag_accuracy": average("lag_correct"),
            "false_positive_edge_claims": violations,
            "score_claims": sum(bool(row["score_claimed"]) for row in rows),
            "threshold_claims": sum(
                bool(row["threshold_claimed"]) for row in rows
            ),
            "total_must_not_include_violations": violations,
        }
    ]


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    columns: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=columns,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    try:
        claims = read_claims(args.claims)
        outputs = read_json(args.outputs, list, "Manual LLM-only outputs")
        rows = evaluate_outputs(claims, outputs)
        summary = build_summary(rows)
        write_csv(args.results, rows, RESULT_COLUMNS)
        write_csv(args.summary, summary, SUMMARY_COLUMNS)
    except (csv.Error, FileNotFoundError, OSError, ValueError) as exc:
        print(
            f"Empirical LLM-only evaluation failed: {exc}",
            file=sys.stderr,
        )
        return 1
    print(f"Responses evaluated: {len(rows)}")
    print(f"Results output: {args.results}")
    print(f"Summary output: {args.summary}")
    print("No LLM was called.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
