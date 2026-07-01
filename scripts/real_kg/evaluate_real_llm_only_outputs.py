"""Deterministically score externally generated real-data LLM-only responses.

This evaluator never calls an LLM. It reads manually or externally produced
responses and applies conservative artifact-level text checks.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_CASES = Path("evals/real_eval_cases.json")
DEFAULT_OUTPUTS = Path("evals/results_real/real_llm_only_outputs.json")
DEFAULT_RESULTS = Path("evals/results_real/real_llm_only_results.csv")

RESULT_COLUMNS = [
    "case_id",
    "method",
    "predicted_candidate_id",
    "candidate_correct",
    "mentioned_evidence_edges",
    "identified_missing_edges",
    "status_correct",
    "present_edge_recall",
    "missing_edge_recall",
    "lag_correct",
    "score_meets_minimum",
    "must_not_include_violations",
    "notes",
]

MISSING_STATUSES = {"missing", "insufficient_data"}
NUMBER_PATTERN = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)"

NEGATIVE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bunsupported\b",
        r"\bnot present\b",
        r"\bmissing\b",
        r"\bmissing evidence\b",
        r"\binsufficient evidence\b",
        r"\bweak\b",
        r"\bweak (?:evidence|support)\b",
        r"\bbelow[- ]evidence\b",
        r"\bbelow[- ]threshold\b",
        r"\bbelow (?:the )?(?:evidence|support) threshold\b",
        r"\bnot supported\b",
        r"\bno (?:evidence|support)\b",
        r"\blacks? (?:evidence|support)\b",
        r"\bnot a positive leading[- ]indicator\b",
        r"\bdoes not (?:have|show) (?:evidence|support)\b",
    )
]

POSITIVE_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bsupported\b",
        r"\bpresent\b",
        r"\bpresent evidence\b",
        r"\bhas (?:qualifying |positive )?(?:evidence|support)\b",
        r"\bpositive leading[- ]indicator\b",
        r"\bis (?:a )?(?:supported )?leading[- ]indicator\b",
        r"\bappears to be (?:a )?leading[- ]indicator\b",
    )
]

QUESTION_CANDIDATE_PATTERN = re.compile(
    r"determine whether\s+(.+?)\s+has\s+LEADING_INDICATOR_FOR",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Score externally generated real-data LLM-only responses without "
            "calling an LLM."
        )
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--outputs", type=Path, default=DEFAULT_OUTPUTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_RESULTS)
    return parser.parse_args()


def read_json(path: Path, expected_type: type, description: str) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"{description} file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as input_file:
            value = json.load(input_file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {description} {path}: {exc}") from exc
    if not isinstance(value, expected_type):
        raise ValueError(
            f"{description} must contain a {expected_type.__name__}."
        )
    return value


def normalize_set(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {
        str(value)
        for value in values
        if value is not None and str(value)
    }


def recall(expected: set[str], observed: set[str]) -> float:
    return 1.0 if expected.issubset(observed) else 0.0


def expected_candidate_name(case: dict[str, Any]) -> str:
    question = str(case.get("question", ""))
    match = QUESTION_CANDIDATE_PATTERN.search(question)
    if match:
        return match.group(1).strip()
    candidate_id = str(case.get("expected_candidate_id", ""))
    return candidate_id.removeprefix("real_signal_").replace("_", " ")


def response_mentions_expected_candidate(
    response: str,
    case: dict[str, Any],
) -> bool:
    lowered = response.lower()
    candidate_id = str(case.get("expected_candidate_id", "")).lower()
    candidate_name = expected_candidate_name(case).lower()
    return bool(
        (candidate_id and candidate_id in lowered)
        or (candidate_name and candidate_name in lowered)
    )


def predicted_candidate_id(
    response: str,
    case: dict[str, Any],
    cases: list[dict[str, Any]],
) -> str:
    if response_mentions_expected_candidate(response, case):
        return str(case.get("expected_candidate_id", ""))

    lowered = response.lower()
    candidates: list[tuple[int, str]] = []
    for other_case in cases:
        candidate_id = str(other_case.get("expected_candidate_id", ""))
        candidate_name = expected_candidate_name(other_case)
        positions = [
            position
            for position in (
                lowered.find(candidate_id.lower()),
                lowered.find(candidate_name.lower()),
            )
            if position >= 0
        ]
        if positions:
            candidates.append((min(positions), candidate_id))
    if not candidates:
        return ""
    candidates.sort()
    return candidates[0][1]


def classify_response(response: str) -> tuple[bool, bool]:
    negative = any(pattern.search(response) for pattern in NEGATIVE_PATTERNS)
    raw_positive = any(
        pattern.search(response) for pattern in POSITIVE_PATTERNS
    )
    positive = raw_positive and not negative
    return positive, negative


def response_has_expected_lag(response: str, expected_lag: Any) -> bool:
    try:
        lag = int(expected_lag)
    except (TypeError, ValueError):
        return False
    patterns = [
        rf"\blag\s*(?:of|=|:|is)?\s*{lag}\s*weeks?\b",
        rf"\b{lag}\s*[- ]week\s+lag\b",
        rf"\bleads?\b.{{0,30}}\bby\s+{lag}\s*weeks?\b",
    ]
    return any(re.search(pattern, response, re.IGNORECASE) for pattern in patterns)


def response_invents_numeric_score(response: str) -> bool:
    score_context = re.search(
        rf"\b(?:score|correlation|confidence|probability)\b"
        rf".{{0,24}}{NUMBER_PATTERN}",
        response,
        re.IGNORECASE,
    )
    percentage = re.search(rf"{NUMBER_PATTERN}\s*%", response)
    decimal = re.search(r"\b0?\.\d+\b", response)
    return bool(score_context or percentage or decimal)


def forbidden_phrase_count(response: str, phrases: Any) -> int:
    if not isinstance(phrases, list):
        return 0
    lowered = response.lower()
    return sum(
        1
        for phrase in phrases
        if phrase is not None
        and str(phrase).strip()
        and str(phrase).strip().lower() in lowered
    )


def failure_result(case: dict[str, Any], note: str) -> dict[str, Any]:
    expected_present = normalize_set(case.get("expected_present_edges", []))
    expected_missing = normalize_set(case.get("expected_missing_edges", []))
    return {
        "case_id": str(case.get("id", "")),
        "method": "llm_only",
        "predicted_candidate_id": "",
        "candidate_correct": False,
        "mentioned_evidence_edges": "",
        "identified_missing_edges": "",
        "status_correct": False,
        "present_edge_recall": recall(expected_present, set()),
        "missing_edge_recall": recall(expected_missing, set()),
        "lag_correct": False,
        "score_meets_minimum": False,
        "must_not_include_violations": 0,
        "notes": note,
    }


def evaluate_response(
    case: dict[str, Any],
    output: dict[str, Any],
    cases: list[dict[str, Any]],
) -> dict[str, Any]:
    response = str(output.get("response", "")).strip()
    if not response:
        return failure_result(case, "LLM-only response is empty.")

    predicted = predicted_candidate_id(response, case, cases)
    candidate_correct = (
        predicted == str(case.get("expected_candidate_id", ""))
    )
    positive, negative = classify_response(response)
    expected_status = str(case.get("expected_status", ""))
    if expected_status == "present":
        status_correct = positive
    elif expected_status in MISSING_STATUSES:
        status_correct = negative and not positive
    else:
        status_correct = False

    leading_indicator_language = bool(
        re.search(r"\bleading[- ]indicator\b", response, re.IGNORECASE)
    )
    claims_present_support = (
        candidate_correct and positive and leading_indicator_language
    )
    identifies_missing = (
        candidate_correct
        and expected_status in MISSING_STATUSES
        and negative
        and not positive
    )

    expected_present = normalize_set(case.get("expected_present_edges", []))
    expected_missing = normalize_set(case.get("expected_missing_edges", []))
    mentioned_edges = (
        {"LEADING_INDICATOR_FOR"} if claims_present_support else set()
    )
    missing_edges = (
        {"LEADING_INDICATOR_FOR"} if identifies_missing else set()
    )
    lag_correct = response_has_expected_lag(
        response,
        case.get("expected_lag_weeks"),
    )
    # The historical column name is retained for cross-method CSV parity. For
    # LLM-only it means status was correct without inventing numeric evidence.
    score_meets_minimum = (
        status_correct
        and candidate_correct
        and not response_invents_numeric_score(response)
    )
    violations = forbidden_phrase_count(
        response,
        case.get("must_not_include", []),
    )
    model = str(output.get("model", "")).strip()
    case_note = str(case.get("notes", "")).strip()
    notes = case_note
    if model:
        notes = f"{case_note} Model: {model}.".strip()

    return {
        "case_id": str(case.get("id", "")),
        "method": "llm_only",
        "predicted_candidate_id": predicted,
        "candidate_correct": candidate_correct,
        "mentioned_evidence_edges": ";".join(sorted(mentioned_edges)),
        "identified_missing_edges": ";".join(sorted(missing_edges)),
        "status_correct": status_correct,
        "present_edge_recall": recall(expected_present, mentioned_edges),
        "missing_edge_recall": recall(expected_missing, missing_edges),
        "lag_correct": lag_correct,
        "score_meets_minimum": score_meets_minimum,
        "must_not_include_violations": violations,
        "notes": notes,
    }


def evaluate_outputs(
    cases: list[dict[str, Any]],
    outputs: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    outputs_by_case: dict[str, dict[str, Any]] = {}
    for output in outputs:
        if not isinstance(output, dict):
            raise ValueError("Every LLM-only output must be a JSON object.")
        case_id = str(output.get("case_id", ""))
        if not case_id:
            raise ValueError("Every LLM-only output needs a case_id.")
        if case_id in outputs_by_case:
            raise ValueError(f"Duplicate LLM-only output for case {case_id!r}.")
        if str(output.get("method", "llm_only")) != "llm_only":
            raise ValueError(
                f"Output for case {case_id!r} must use method 'llm_only'."
            )
        outputs_by_case[case_id] = output

    rows: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Every evaluation case must be a JSON object.")
        case_id = str(case.get("id", ""))
        output = outputs_by_case.get(case_id)
        if output is None:
            rows.append(
                failure_result(
                    case,
                    f"No LLM-only output found for case {case_id}.",
                )
            )
        else:
            rows.append(evaluate_response(case, output, cases))
    return rows


def validate_output_path(path: Path) -> None:
    forbidden = (Path.cwd() / "evals" / "results").resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(forbidden)
    except ValueError:
        return
    raise ValueError("Refusing to write LLM-only results under evals/results/.")


def write_results(path: Path, rows: list[dict[str, Any]]) -> None:
    validate_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=RESULT_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    try:
        cases = read_json(args.cases, list, "Evaluation cases")
        outputs = read_json(args.outputs, list, "LLM-only outputs")
        rows = evaluate_outputs(cases, outputs)
        write_results(args.output, rows)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"LLM-only evaluation failed: {exc}", file=sys.stderr)
        return 1

    print(f"LLM-only cases evaluated: {len(rows)}")
    print(f"Output: {args.output}")
    print("No LLM was called.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
