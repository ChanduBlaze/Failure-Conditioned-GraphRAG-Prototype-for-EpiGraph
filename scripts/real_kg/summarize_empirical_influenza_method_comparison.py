"""Combine empirical influenza method summaries into one comparison CSV.

This is a deterministic CSV harmonization step. It does not call an LLM,
query Neo4j, download data, or modify its input summaries.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any


DEFAULT_LLM_SUMMARY = Path(
    "evals/results_real/real_empirical_influenza_llm_only_summary.csv"
)
DEFAULT_ARTIFACT_SUMMARY = Path(
    "evals/results_real/real_empirical_influenza_summary.csv"
)
DEFAULT_OUTPUT = Path(
    "evals/results_real/"
    "real_empirical_influenza_method_comparison_summary.csv"
)

METHOD_ORDER = [
    "empirical_llm_only",
    "empirical_text_rag",
    "empirical_graphrag_context",
]

LLM_COLUMNS = [
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

ARTIFACT_COLUMNS = [
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

OUTPUT_COLUMNS = [
    "method",
    "case_count",
    "status_accuracy",
    "avg_present_edge_recall",
    "avg_missing_edge_recall",
    "lag_accuracy",
    "score_accuracy",
    "threshold_accuracy",
    "paired_week_count_accuracy",
    "false_positive_edge_claims",
    "score_claims",
    "threshold_claims",
    "total_must_not_include_violations",
    "notes",
]

COMMON_COLUMNS = [
    "method",
    "case_count",
    "status_accuracy",
    "avg_present_edge_recall",
    "avg_missing_edge_recall",
    "lag_accuracy",
    "total_must_not_include_violations",
]

NOTES = {
    "empirical_llm_only": (
        "LLM-only used general epidemiological reasoning without empirical "
        "score, threshold, lag, paired-week, Text-RAG, or graph evidence."
    ),
    "empirical_text_rag": (
        "Text-RAG evaluated artifact preservation from empirical "
        "evidence-claim chunks."
    ),
    "empirical_graphrag_context": (
        "GraphRAG evaluated artifact preservation from pipeline-scoped "
        "Neo4j graph context."
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Combine empirical LLM-only, Text-RAG, and GraphRAG summary "
            "metrics into one comparison CSV."
        )
    )
    parser.add_argument(
        "--llm-summary",
        type=Path,
        default=DEFAULT_LLM_SUMMARY,
    )
    parser.add_argument(
        "--artifact-summary",
        type=Path,
        default=DEFAULT_ARTIFACT_SUMMARY,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def read_summary(
    path: Path,
    required_columns: list[str],
    description: str,
) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"{description} file not found: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        fieldnames = reader.fieldnames or []
        missing = [
            column for column in required_columns if column not in fieldnames
        ]
        if missing:
            raise ValueError(
                f"{description} is missing required columns: "
                + ", ".join(missing)
            )
        rows = [
            {
                column: (row.get(column) or "").strip()
                for column in required_columns
            }
            for row in reader
        ]
    if not rows:
        raise ValueError(f"{description} contains no rows.")
    return rows


def rows_by_method(
    rows: list[dict[str, str]],
    expected_methods: set[str],
    description: str,
) -> dict[str, dict[str, str]]:
    indexed: dict[str, dict[str, str]] = {}
    for row in rows:
        method = row["method"]
        if method not in expected_methods:
            raise ValueError(
                f"{description} contains unexpected method {method!r}."
            )
        if method in indexed:
            raise ValueError(
                f"{description} contains duplicate method {method!r}."
            )
        indexed[method] = row
    missing = sorted(expected_methods - set(indexed))
    if missing:
        raise ValueError(
            f"{description} is missing methods: " + ", ".join(missing)
        )
    return indexed


def common_values(row: dict[str, str]) -> dict[str, str]:
    return {column: row[column] for column in COMMON_COLUMNS}


def build_comparison(
    llm_rows: list[dict[str, str]],
    artifact_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    llm = rows_by_method(
        llm_rows,
        {"empirical_llm_only"},
        "LLM-only summary",
    )["empirical_llm_only"]
    artifacts = rows_by_method(
        artifact_rows,
        {"empirical_text_rag", "empirical_graphrag_context"},
        "Text-RAG/GraphRAG summary",
    )

    output_by_method: dict[str, dict[str, str]] = {}
    output_by_method["empirical_llm_only"] = {
        **common_values(llm),
        "score_accuracy": "",
        "threshold_accuracy": "",
        "paired_week_count_accuracy": "",
        "false_positive_edge_claims": llm[
            "false_positive_edge_claims"
        ],
        "score_claims": llm["score_claims"],
        "threshold_claims": llm["threshold_claims"],
        "notes": NOTES["empirical_llm_only"],
    }

    for method in ("empirical_text_rag", "empirical_graphrag_context"):
        source = artifacts[method]
        output_by_method[method] = {
            **common_values(source),
            "score_accuracy": source["score_accuracy"],
            "threshold_accuracy": source["threshold_accuracy"],
            "paired_week_count_accuracy": source[
                "paired_week_count_accuracy"
            ],
            "false_positive_edge_claims": "",
            "score_claims": "",
            "threshold_claims": "",
            "notes": NOTES[method],
        }
    return [output_by_method[method] for method in METHOD_ORDER]


def write_comparison(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=OUTPUT_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    args = parse_args()
    try:
        llm_rows = read_summary(
            args.llm_summary,
            LLM_COLUMNS,
            "LLM-only summary",
        )
        artifact_rows = read_summary(
            args.artifact_summary,
            ARTIFACT_COLUMNS,
            "Text-RAG/GraphRAG summary",
        )
        comparison = build_comparison(llm_rows, artifact_rows)
        write_comparison(args.output, comparison)
    except (csv.Error, FileNotFoundError, OSError, ValueError) as exc:
        print(
            f"Empirical method comparison failed: {exc}",
            file=sys.stderr,
        )
        return 1

    print(f"Methods summarized: {len(comparison)}")
    print(f"Output path: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
