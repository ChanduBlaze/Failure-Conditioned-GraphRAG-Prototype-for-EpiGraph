"""Render the final real-results index as a thesis-ready Markdown report.

This deterministic renderer uses only the Python standard library. It does
not call an LLM, query Neo4j, download data, or modify its input CSV.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


DEFAULT_INPUT = Path("evals/results_real/real_results_index.csv")
DEFAULT_OUTPUT = Path("evals/results_real/real_results_report.md")

TABLE_COLUMNS = [
    "method",
    "case_count",
    "status_accuracy",
    "candidate_accuracy",
    "avg_present_edge_recall",
    "avg_missing_edge_recall",
    "lag_accuracy",
    "score_accuracy",
    "threshold_accuracy",
    "paired_week_count_accuracy",
    "false_positive_edge_claims",
    "total_must_not_include_violations",
    "notes",
]

REQUIRED_INPUT_COLUMNS = [
    "result_family",
    "method",
    "case_count",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write a human-readable report from the real-results index."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def read_results_index(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Real results index not found: {path}")

    with path.open("r", newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        fieldnames = reader.fieldnames or []
        missing = [
            column
            for column in REQUIRED_INPUT_COLUMNS
            if column not in fieldnames
        ]
        if missing:
            raise ValueError(
                "Real results index is missing required columns: "
                + ", ".join(missing)
            )
        return [
            {
                column: (row.get(column) or "").strip()
                for column in fieldnames
            }
            for row in reader
        ]


def partition_rows(
    rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    fixture_rows = [
        row for row in rows if row["result_family"] == "fixture_real_kg"
    ]
    empirical_rows = [
        row for row in rows if row["result_family"] == "empirical_influenza"
    ]
    unexpected = sorted(
        {
            row["result_family"]
            for row in rows
            if row["result_family"]
            not in {"fixture_real_kg", "empirical_influenza"}
        }
    )
    if unexpected:
        raise ValueError(
            "Real results index contains unexpected result families: "
            + ", ".join(unexpected)
        )
    if not fixture_rows:
        raise ValueError("Real results index contains no fixture rows.")
    if not empirical_rows:
        raise ValueError("Real results index contains no empirical rows.")
    return fixture_rows, empirical_rows


def markdown_cell(value: str) -> str:
    return value.replace("\\", "\\\\").replace("|", "\\|").replace(
        "\r", " "
    ).replace("\n", " ")


def markdown_table(rows: list[dict[str, str]]) -> str:
    header = "| " + " | ".join(TABLE_COLUMNS) + " |"
    separator = "| " + " | ".join("---" for _ in TABLE_COLUMNS) + " |"
    body = [
        "| "
        + " | ".join(
            markdown_cell(row.get(column, "")) for column in TABLE_COLUMNS
        )
        + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def methods_text(rows: list[dict[str, str]]) -> str:
    return ", ".join(f"`{row['method']}`" for row in rows)


def case_count_text(rows: list[dict[str, str]], subject: str) -> str:
    counts = list(dict.fromkeys(row["case_count"] for row in rows))
    if len(counts) == 1:
        return f"Each method reports {counts[0]} {subject}."
    details = "; ".join(
        f"{row['method']}: {row['case_count']}" for row in rows
    )
    return f"Reported {subject} counts are {details}."


def metric_text(rows: list[dict[str, str]], column: str) -> str:
    return "; ".join(
        f"{row['method']}={row.get(column, '') or 'not reported'}"
        for row in rows
    )


def render_report(
    fixture_rows: list[dict[str, str]],
    empirical_rows: list[dict[str, str]],
) -> str:
    fixture_summary = (
        f"Methods included: {methods_text(fixture_rows)}. "
        f"{case_count_text(fixture_rows, 'controlled cases')} "
        f"Candidate accuracy was {metric_text(fixture_rows, 'candidate_accuracy')}; "
        f"status accuracy was {metric_text(fixture_rows, 'status_accuracy')}. "
        "Average present-edge recall was "
        f"{metric_text(fixture_rows, 'avg_present_edge_recall')}, and average "
        "missing-edge recall was "
        f"{metric_text(fixture_rows, 'avg_missing_edge_recall')}."
    )
    empirical_summary = (
        f"Methods included: {methods_text(empirical_rows)}. "
        f"{case_count_text(empirical_rows, 'empirical claims')} "
        "The LLM-only baseline used general epidemiological reasoning. "
        "Text-RAG and GraphRAG preserved empirical evidence artifacts supplied "
        "through their retrieval contexts."
    )

    lines = [
        "# Real-KG and Empirical Influenza Results Report",
        "",
        "## 1. Controlled Fixture Real-KG Comparison",
        "",
        fixture_summary,
        "",
        (
            "The main observation is that LLM-only selected candidates well but "
            "had weaker evidence-status preservation, while Text-RAG and "
            "GraphRAG preserved the evidence structure."
        ),
        "",
        markdown_table(fixture_rows),
        "",
        "## 2. Empirical Influenza Real-Data Extension",
        "",
        empirical_summary,
        "",
        (
            "The main observation is that LLM-only recovered status but not "
            "exact empirical lag evidence, while Text-RAG and GraphRAG "
            "preserved lag, score, threshold, and paired-week evidence."
        ),
        "",
        markdown_table(empirical_rows),
        "",
        "## 3. Interpretation",
        "",
        (
            "The controlled fixture result shows why evidence-status "
            "preservation matters when candidate relationships are known. "
            "Accurate candidate selection alone does not ensure that present "
            "and missing evidence is represented correctly. This comparison "
            "evaluates evidence preservation, not causal discovery."
        ),
        "",
        (
            "The empirical result shows that the evidence-claim representation "
            "can be populated from real surveillance signals and that retrieval "
            "contexts can preserve score, threshold, lag, and paired-week "
            "details. The empirical evidence is screening evidence, not causal "
            "proof, and this small extension does not prove generalization to "
            "all disease systems."
        ),
        "",
        "## 4. Limitations",
        "",
        "- The empirical extension is small.",
        "- It covers one influenza target case.",
        "- The negative control is deterministic and synthetic.",
        (
            "- The LLM-only manual baseline is based on one fresh-chat sample."
        ),
        (
            "- Empirical evidence depends on source coverage, normalization, "
            "the lag window, the threshold, and reporting artifacts."
        ),
        "",
        "## 5. Thesis-Ready Takeaway",
        "",
        (
            "The real-data extension supports the thesis by showing that "
            "GraphRAG can preserve candidate-specific evidence facts from a "
            "pipeline-scoped KG context, while LLM-only reasoning may be "
            "plausible but does not recover exact empirical evidence details "
            "such as lag, score, threshold, and paired-week counts unless those "
            "facts are supplied."
        ),
        "",
    ]
    return "\n".join(lines)


def write_report(path: Path, report: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8", newline="\n")


def generate_report(
    input_path: Path,
    output_path: Path,
) -> tuple[int, int]:
    rows = read_results_index(input_path)
    fixture_rows, empirical_rows = partition_rows(rows)
    write_report(
        output_path,
        render_report(fixture_rows, empirical_rows),
    )
    return len(fixture_rows), len(empirical_rows)


def main() -> int:
    args = parse_args()
    try:
        fixture_count, empirical_count = generate_report(
            args.input,
            args.output,
        )
    except (csv.Error, FileNotFoundError, OSError, ValueError) as exc:
        print(f"Real results report failed: {exc}", file=sys.stderr)
        return 1

    print(f"input path: {args.input}")
    print(f"fixture rows: {fixture_count}")
    print(f"empirical rows: {empirical_count}")
    print(f"output path: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
