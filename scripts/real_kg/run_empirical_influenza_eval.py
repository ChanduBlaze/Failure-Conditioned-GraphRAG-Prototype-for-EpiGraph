"""Deterministically evaluate empirical Text-RAG and GraphRAG artifacts.

This is artifact-level evidence-preservation evaluation. It does not assess
LLM reasoning, query Neo4j, or infer facts beyond the empirical EvidenceClaim
CSV and the two generated retrieval artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any


DEFAULT_CLAIMS = Path(
    "data/real_processed/real_empirical_influenza_evidence_claims.csv"
)
DEFAULT_TEXT_CORPUS = Path(
    "data/real_processed/real_empirical_influenza_text_rag_corpus.json"
)
DEFAULT_GRAPH_CONTEXT = Path(
    "data/real_processed/real_empirical_influenza_graph_context.json"
)
DEFAULT_TEXT_RESULTS = Path(
    "evals/results_real/real_empirical_influenza_text_rag_results.csv"
)
DEFAULT_GRAPH_RESULTS = Path(
    "evals/results_real/"
    "real_empirical_influenza_graphrag_context_results.csv"
)
DEFAULT_SUMMARY = Path(
    "evals/results_real/real_empirical_influenza_summary.csv"
)

METHODS = ["empirical_text_rag", "empirical_graphrag_context"]
MISSING_STATUSES = {"missing", "insufficient"}
PIPELINE = "empirical_influenza"
NUMERIC_TOLERANCE = 1e-6

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
    "predicted_lag_weeks",
    "lag_correct",
    "expected_score",
    "predicted_score",
    "score_match",
    "expected_threshold",
    "predicted_threshold",
    "threshold_match",
    "expected_paired_week_count",
    "predicted_paired_week_count",
    "paired_week_count_match",
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
    "score_accuracy",
    "threshold_accuracy",
    "paired_week_count_accuracy",
    "total_must_not_include_violations",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate empirical influenza Text-RAG and GraphRAG context "
            "against empirical EvidenceClaims."
        )
    )
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIMS)
    parser.add_argument(
        "--text-corpus",
        type=Path,
        default=DEFAULT_TEXT_CORPUS,
    )
    parser.add_argument(
        "--graph-context",
        type=Path,
        default=DEFAULT_GRAPH_CONTEXT,
    )
    parser.add_argument(
        "--text-results",
        type=Path,
        default=DEFAULT_TEXT_RESULTS,
    )
    parser.add_argument(
        "--graph-results",
        type=Path,
        default=DEFAULT_GRAPH_RESULTS,
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=DEFAULT_SUMMARY,
    )
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


def normalized(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def is_missing_value(value: Any) -> bool:
    return normalized(value).lower().removesuffix(".") in {
        "",
        "not available",
        "none",
        "null",
    }


def numeric_value(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(str(value).strip().removesuffix("."))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def numeric_match(actual: Any, expected: Any) -> bool:
    if is_missing_value(expected):
        return is_missing_value(actual)
    actual_number = numeric_value(actual)
    expected_number = numeric_value(expected)
    if actual_number is None or expected_number is None:
        return False
    return math.isclose(
        actual_number,
        expected_number,
        rel_tol=0.0,
        abs_tol=NUMERIC_TOLERANCE,
    )


def integer_match(actual: Any, expected: Any) -> bool:
    if is_missing_value(expected):
        return is_missing_value(actual)
    actual_number = numeric_value(actual)
    expected_number = numeric_value(expected)
    if actual_number is None or expected_number is None:
        return False
    return (
        actual_number.is_integer()
        and expected_number.is_integer()
        and int(actual_number) == int(expected_number)
    )


def output_value(value: Any) -> Any:
    return "" if value is None else value


def text_line_value(text: str, label: str) -> str | None:
    prefix = f"{label}:".lower()
    for line in text.splitlines():
        if line.lower().startswith(prefix):
            return line[len(prefix) :].strip().removesuffix(".")
    return None


def choose_text_chunk(
    claim: dict[str, str],
    text_corpus: list[dict[str, Any]],
) -> dict[str, Any] | None:
    matches = [
        chunk
        for chunk in text_corpus
        if isinstance(chunk, dict)
        and str(chunk.get("case_id", "")) == claim["case_id"]
        and str(chunk.get("candidate_id", "")) == claim["candidate_id"]
        and str(chunk.get("target_signal_id", ""))
        == claim["target_signal_id"]
    ]
    if not matches:
        return None
    matches.sort(
        key=lambda chunk: (
            str(chunk.get("edge_type", "")) != claim["edge_type"],
            str(chunk.get("chunk_id", "")),
        )
    )
    return matches[0]


def choose_graph_edge(
    claim: dict[str, str],
    graph_context: dict[str, Any],
) -> dict[str, Any] | None:
    if (
        str(graph_context.get("case_id", "")) != claim["case_id"]
        or str(graph_context.get("target_signal_id", ""))
        != claim["target_signal_id"]
        or str(graph_context.get("pipeline", "")) != PIPELINE
    ):
        return None
    matches = [
        edge
        for edge in graph_context.get("evidence_edges", [])
        if isinstance(edge, dict)
        and str(edge.get("candidate_id", "")) == claim["candidate_id"]
        and str(edge.get("target_signal_id", ""))
        == claim["target_signal_id"]
    ]
    if not matches:
        return None
    matches.sort(
        key=lambda edge: (
            str(edge.get("edge_type", "")) != claim["edge_type"],
            str(edge.get("edge_type", "")),
        )
    )
    return matches[0]


def build_result(
    claim: dict[str, str],
    method: str,
    artifact_found: bool,
    predicted_status: Any,
    predicted_edge_type: Any,
    predicted_lag: Any,
    predicted_score: Any,
    predicted_threshold: Any,
    predicted_paired_weeks: Any,
) -> dict[str, Any]:
    status = normalized(predicted_status)
    edge_type = normalized(predicted_edge_type)
    positive_edge_claimed = (
        artifact_found
        and status == "present"
        and edge_type == claim["edge_type"]
    )
    mentioned_edges = claim["edge_type"] if positive_edge_claimed else ""
    expected_status = claim["status"]
    status_correct = status == expected_status

    if expected_status == "present":
        present_edge_recall = 1.0 if positive_edge_claimed else 0.0
        missing_edge_recall = 1.0
    else:
        present_edge_recall = 1.0
        missing_edge_recall = (
            1.0
            if status_correct and not positive_edge_claimed
            else 0.0
        )

    violation = int(
        expected_status in MISSING_STATUSES and positive_edge_claimed
    )
    lag_correct = artifact_found and integer_match(
        predicted_lag,
        claim["lag_weeks"],
    )
    score_correct = artifact_found and numeric_match(
        predicted_score,
        claim["score"],
    )
    threshold_correct = artifact_found and numeric_match(
        predicted_threshold,
        claim["threshold"],
    )
    paired_correct = artifact_found and integer_match(
        predicted_paired_weeks,
        claim["paired_week_count"],
    )

    failures = []
    if not artifact_found:
        failures.append("candidate-specific artifact not found")
    for passed, label in (
        (status_correct, "status mismatch"),
        (present_edge_recall == 1.0, "present edge recall failure"),
        (missing_edge_recall == 1.0, "missing edge recall failure"),
        (lag_correct, "lag mismatch"),
        (score_correct, "score mismatch"),
        (threshold_correct, "threshold mismatch"),
        (paired_correct, "paired week count mismatch"),
    ):
        if not passed:
            failures.append(label)
    if violation:
        failures.append("non-present evidence promoted as a positive edge")

    return {
        "case_id": claim["case_id"],
        "method": method,
        "candidate_id": claim["candidate_id"],
        "candidate_name": claim["candidate_name"],
        "target_signal_id": claim["target_signal_id"],
        "target_signal_name": claim["target_signal_name"],
        "expected_status": expected_status,
        "predicted_status": status,
        "status_correct": status_correct,
        "expected_edge_type": claim["edge_type"],
        "mentioned_evidence_edges": mentioned_edges,
        "present_edge_recall": present_edge_recall,
        "missing_edge_recall": missing_edge_recall,
        "expected_lag_weeks": claim["lag_weeks"],
        "predicted_lag_weeks": output_value(predicted_lag),
        "lag_correct": lag_correct,
        "expected_score": claim["score"],
        "predicted_score": output_value(predicted_score),
        "score_match": score_correct,
        "expected_threshold": claim["threshold"],
        "predicted_threshold": output_value(predicted_threshold),
        "threshold_match": threshold_correct,
        "expected_paired_week_count": claim["paired_week_count"],
        "predicted_paired_week_count": output_value(
            predicted_paired_weeks
        ),
        "paired_week_count_match": paired_correct,
        "must_not_include_violations": violation,
        "notes": "Perfect artifact match." if not failures else "; ".join(
            failures
        )
        + ".",
    }


def evaluate_text_claim(
    claim: dict[str, str],
    text_corpus: list[dict[str, Any]],
) -> dict[str, Any]:
    chunk = choose_text_chunk(claim, text_corpus)
    text = str(chunk.get("text", "")) if chunk else ""
    return build_result(
        claim=claim,
        method="empirical_text_rag",
        artifact_found=chunk is not None,
        predicted_status=(
            chunk.get("status", "") if chunk else ""
        ),
        predicted_edge_type=(
            chunk.get("edge_type", "") if chunk else ""
        ),
        predicted_lag=text_line_value(text, "Lag weeks"),
        predicted_score=text_line_value(text, "Score"),
        predicted_threshold=text_line_value(text, "Threshold"),
        predicted_paired_weeks=text_line_value(
            text,
            "Paired week count",
        ),
    )


def evaluate_graph_claim(
    claim: dict[str, str],
    graph_context: dict[str, Any],
) -> dict[str, Any]:
    edge = choose_graph_edge(claim, graph_context)
    return build_result(
        claim=claim,
        method="empirical_graphrag_context",
        artifact_found=edge is not None,
        predicted_status=edge.get("status", "") if edge else "",
        predicted_edge_type=edge.get("edge_type", "") if edge else "",
        predicted_lag=edge.get("lag_weeks") if edge else None,
        predicted_score=edge.get("score") if edge else None,
        predicted_threshold=edge.get("threshold") if edge else None,
        predicted_paired_weeks=(
            edge.get("paired_week_count") if edge else None
        ),
    )


def build_summary(
    results_by_method: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    summary = []
    for method in METHODS:
        rows = results_by_method[method]
        if not rows:
            raise ValueError(f"No evaluation rows for method {method!r}.")
        count = len(rows)
        average = lambda field: sum(
            float(row[field]) for row in rows
        ) / count
        summary.append(
            {
                "method": method,
                "case_count": count,
                "status_accuracy": average("status_correct"),
                "avg_present_edge_recall": average(
                    "present_edge_recall"
                ),
                "avg_missing_edge_recall": average(
                    "missing_edge_recall"
                ),
                "lag_accuracy": average("lag_correct"),
                "score_accuracy": average("score_match"),
                "threshold_accuracy": average("threshold_match"),
                "paired_week_count_accuracy": average(
                    "paired_week_count_match"
                ),
                "total_must_not_include_violations": sum(
                    int(row["must_not_include_violations"])
                    for row in rows
                ),
            }
        )
    return summary


def evaluate_artifacts(
    claims: list[dict[str, str]],
    text_corpus: list[dict[str, Any]],
    graph_context: dict[str, Any],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    text_results = [
        evaluate_text_claim(claim, text_corpus) for claim in claims
    ]
    graph_results = [
        evaluate_graph_claim(claim, graph_context) for claim in claims
    ]
    summary = build_summary(
        {
            "empirical_text_rag": text_results,
            "empirical_graphrag_context": graph_results,
        }
    )
    return text_results, graph_results, summary


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


def evaluate_files(
    claims_path: Path,
    text_path: Path,
    graph_path: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    claims = read_claims(claims_path)
    text_corpus = read_json(text_path, list, "Empirical Text-RAG corpus")
    graph_context = read_json(
        graph_path,
        dict,
        "Empirical GraphRAG context",
    )
    return evaluate_artifacts(claims, text_corpus, graph_context)


def main() -> int:
    args = parse_args()
    try:
        text_results, graph_results, summary = evaluate_files(
            args.claims,
            args.text_corpus,
            args.graph_context,
        )
        write_csv(args.text_results, text_results, RESULT_COLUMNS)
        write_csv(args.graph_results, graph_results, RESULT_COLUMNS)
        write_csv(args.summary, summary, SUMMARY_COLUMNS)
        print(
            f"Rows written: {len(text_results) + len(graph_results)}"
        )
        print(f"Methods summarized: {len(summary)}")
        print(f"Text-RAG results: {args.text_results}")
        print(f"GraphRAG context results: {args.graph_results}")
        print(f"Summary: {args.summary}")
    except (csv.Error, FileNotFoundError, OSError, ValueError) as exc:
        print(
            f"Empirical influenza evaluation failed: {exc}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
