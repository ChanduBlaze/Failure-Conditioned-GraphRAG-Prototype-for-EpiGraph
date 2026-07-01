"""Combine and summarize deterministic real-method evaluation results.

This script reads existing LLM-only, Text-RAG, and GraphRAG-context CSVs. It
does not call an LLM or Neo4j and does not alter the source result files.
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
DEFAULT_LLM_RESULTS = Path(
    "evals/results_real/real_llm_only_results.csv"
)
DEFAULT_TEXT_RESULTS = Path(
    "evals/results_real/real_text_rag_results.csv"
)
DEFAULT_GRAPH_RESULTS = Path(
    "evals/results_real/real_graphrag_context_results.csv"
)
DEFAULT_COMBINED_OUTPUT = Path(
    "evals/results_real/real_method_comparison_results.csv"
)
DEFAULT_SUMMARY_OUTPUT = Path(
    "evals/results_real/real_method_comparison_summary.csv"
)

METHOD_ORDER = ["llm_only", "text_rag", "graphrag_context"]

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

SUMMARY_COLUMNS = [
    "method",
    "case_count",
    "candidate_accuracy",
    "avg_present_edge_recall",
    "avg_missing_edge_recall",
    "status_accuracy",
    "lag_accuracy",
    "score_threshold_accuracy",
    "false_positive_edge_claims",
    "total_must_not_include_violations",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Combine and summarize real LLM-only, Text-RAG, and GraphRAG "
            "evaluation result CSVs."
        )
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument(
        "--llm-results",
        type=Path,
        default=DEFAULT_LLM_RESULTS,
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
        "--combined-output",
        type=Path,
        default=DEFAULT_COMBINED_OUTPUT,
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=DEFAULT_SUMMARY_OUTPUT,
    )
    return parser.parse_args()


def read_cases(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Evaluation cases file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as input_file:
            cases = json.load(input_file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid evaluation cases JSON {path}: {exc}") from exc
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation cases must be a non-empty JSON list.")
    case_ids = [
        str(case.get("id", ""))
        for case in cases
        if isinstance(case, dict)
    ]
    if len(case_ids) != len(cases) or any(not case_id for case_id in case_ids):
        raise ValueError("Every evaluation case must be an object with an id.")
    if len(case_ids) != len(set(case_ids)):
        raise ValueError("Evaluation case ids must be unique.")
    return cases


def read_result_rows(
    path: Path,
    expected_method: str,
) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(
            f"{expected_method} result CSV not found: {path}"
        )
    with path.open("r", newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            raise ValueError(f"Result CSV has no header: {path}")
        missing = [
            column for column in RESULT_COLUMNS if column not in reader.fieldnames
        ]
        if missing:
            raise ValueError(
                f"{expected_method} result CSV is missing columns: "
                + ", ".join(missing)
            )
        rows = [
            {
                column: (row.get(column) or "").strip()
                for column in RESULT_COLUMNS
            }
            for row in reader
        ]
    wrong_methods = sorted(
        {
            row["method"]
            for row in rows
            if row["method"] != expected_method
        }
    )
    if wrong_methods:
        raise ValueError(
            f"{expected_method} result CSV contains unexpected methods: "
            + ", ".join(wrong_methods)
        )
    return rows


def combine_results(
    cases: list[dict[str, Any]],
    rows_by_method: dict[str, list[dict[str, str]]],
) -> list[dict[str, str]]:
    case_ids = [str(case["id"]) for case in cases]
    expected_case_ids = set(case_ids)
    combined: list[dict[str, str]] = []

    for method in METHOD_ORDER:
        rows = rows_by_method.get(method)
        if rows is None:
            raise ValueError(f"Missing result rows for method {method}.")
        by_case: dict[str, dict[str, str]] = {}
        for row in rows:
            case_id = row["case_id"]
            if case_id in by_case:
                raise ValueError(
                    f"Duplicate {method} result for case {case_id!r}."
                )
            by_case[case_id] = row
        missing = [case_id for case_id in case_ids if case_id not in by_case]
        extras = sorted(set(by_case) - expected_case_ids)
        if missing or extras:
            details = []
            if missing:
                details.append("missing: " + ", ".join(missing))
            if extras:
                details.append("unexpected: " + ", ".join(extras))
            raise ValueError(
                f"{method} result coverage mismatch (" + "; ".join(details) + ")"
            )
        combined.extend(by_case[case_id] for case_id in case_ids)
    return combined


def parse_bool(value: Any) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes"}:
        return True
    if normalized in {"false", "0", "no"}:
        return False
    raise ValueError(f"Invalid boolean result value: {value!r}")


def parse_float(value: Any, column: str) -> float:
    try:
        return float(str(value).strip())
    except ValueError as exc:
        raise ValueError(
            f"Invalid numeric value for {column}: {value!r}"
        ) from exc


def parse_int(value: Any, column: str) -> int:
    try:
        return int(str(value).strip())
    except ValueError as exc:
        raise ValueError(
            f"Invalid integer value for {column}: {value!r}"
        ) from exc


def parse_edges(value: Any) -> set[str]:
    return {
        edge.strip()
        for edge in re.split(r"[;,]", str(value))
        if edge.strip()
    }


def summarize_results(
    cases: list[dict[str, Any]],
    combined_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    cases_by_id = {str(case["id"]): case for case in cases}
    summary_rows: list[dict[str, Any]] = []

    for method in METHOD_ORDER:
        rows = [row for row in combined_rows if row["method"] == method]
        case_count = len(rows)
        if not case_count:
            raise ValueError(f"No combined rows found for method {method}.")

        false_positive_edges = 0
        for row in rows:
            case = cases_by_id.get(row["case_id"])
            if case is None:
                raise ValueError(
                    f"Unknown case id in combined results: {row['case_id']}"
                )
            expected_present = {
                str(edge)
                for edge in case.get("expected_present_edges", [])
            }
            mentioned = parse_edges(row["mentioned_evidence_edges"])
            false_positive_edges += len(mentioned - expected_present)

        def average_bool(column: str) -> float:
            return sum(parse_bool(row[column]) for row in rows) / case_count

        def average_float(column: str) -> float:
            return (
                sum(parse_float(row[column], column) for row in rows)
                / case_count
            )

        summary_rows.append(
            {
                "method": method,
                "case_count": case_count,
                "candidate_accuracy": average_bool("candidate_correct"),
                "avg_present_edge_recall": average_float(
                    "present_edge_recall"
                ),
                "avg_missing_edge_recall": average_float(
                    "missing_edge_recall"
                ),
                "status_accuracy": average_bool("status_correct"),
                "lag_accuracy": average_bool("lag_correct"),
                "score_threshold_accuracy": average_bool(
                    "score_meets_minimum"
                ),
                "false_positive_edge_claims": false_positive_edges,
                "total_must_not_include_violations": sum(
                    parse_int(
                        row["must_not_include_violations"],
                        "must_not_include_violations",
                    )
                    for row in rows
                ),
            }
        )
    return summary_rows


def validate_output_path(path: Path) -> None:
    forbidden = (Path.cwd() / "evals" / "results").resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(forbidden)
    except ValueError:
        return
    raise ValueError(
        "Refusing to write real method comparison under evals/results/."
    )


def write_csv(
    path: Path,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> None:
    validate_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=columns,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def build_comparison(
    cases: list[dict[str, Any]],
    llm_rows: list[dict[str, str]],
    text_rows: list[dict[str, str]],
    graph_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    combined = combine_results(
        cases,
        {
            "llm_only": llm_rows,
            "text_rag": text_rows,
            "graphrag_context": graph_rows,
        },
    )
    return combined, summarize_results(cases, combined)


def main() -> int:
    args = parse_args()
    try:
        cases = read_cases(args.cases)
        llm_rows = read_result_rows(args.llm_results, "llm_only")
        text_rows = read_result_rows(args.text_results, "text_rag")
        graph_rows = read_result_rows(
            args.graph_results,
            "graphrag_context",
        )
        combined, summary = build_comparison(
            cases,
            llm_rows,
            text_rows,
            graph_rows,
        )
        write_csv(args.combined_output, RESULT_COLUMNS, combined)
        write_csv(args.summary_output, SUMMARY_COLUMNS, summary)
    except (csv.Error, FileNotFoundError, OSError, ValueError) as exc:
        print(f"Real method comparison failed: {exc}", file=sys.stderr)
        return 1

    print("Methods summarized: " + ", ".join(METHOD_ORDER))
    print(f"Output result path: {args.combined_output}")
    print(f"Output summary path: {args.summary_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
