"""Render the final real-results index as a thesis-ready Markdown report.

This deterministic renderer uses only the Python standard library. It does
not call an LLM, query Neo4j, download data, or modify its input CSV.

It includes three result layers:
1. Controlled fixture real-KG comparison.
2. Empirical influenza real-data extension.
3. Empirical hard-pilot stress evaluation.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


DEFAULT_INPUT = Path("evals/results_real/real_results_index.csv")
DEFAULT_OUTPUT = Path("evals/results_real/real_results_report.md")
DEFAULT_HARD_PILOT_SUMMARY = Path(
    "evals/empirical_hard_pilot/empirical_hard_pilot_summary_by_method.csv"
)

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

HARD_PILOT_COLUMNS = [
    "method",
    "case_count",
    "overall_pass_rate",
    "avg_include_score",
    "forbidden_ok_rate",
    "failed_case_count",
    "forbidden_violation_count",
    "avg_answer_length_chars",
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
    parser.add_argument(
        "--hard-pilot-summary",
        type=Path,
        default=DEFAULT_HARD_PILOT_SUMMARY,
    )
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


def read_optional_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []

    with path.open("r", newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        fieldnames = reader.fieldnames or []
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


def markdown_table_for_columns(
    rows: list[dict[str, str]],
    columns: list[str],
) -> str:
    header = "| " + " | ".join(columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| "
        + " | ".join(
            markdown_cell(row.get(column, "")) for column in columns
        )
        + " |"
        for row in rows
    ]
    return "\n".join([header, separator, *body])


def markdown_table(rows: list[dict[str, str]]) -> str:
    return markdown_table_for_columns(rows, TABLE_COLUMNS)


def hard_pilot_markdown_table(rows: list[dict[str, str]]) -> str:
    return markdown_table_for_columns(rows, HARD_PILOT_COLUMNS)


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
    hard_pilot_rows: list[dict[str, str]],
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

    hard_pilot_section: list[str] = []

    if hard_pilot_rows:
        hard_pilot_summary = (
            f"Methods included: {methods_text(hard_pilot_rows)}. "
            f"{case_count_text(hard_pilot_rows, 'empirical hard-pilot stress cases')} "
            "Overall pass rate was "
            f"{metric_text(hard_pilot_rows, 'overall_pass_rate')}. "
            "Average include score was "
            f"{metric_text(hard_pilot_rows, 'avg_include_score')}. "
            "Forbidden-content compliance was "
            f"{metric_text(hard_pilot_rows, 'forbidden_ok_rate')}."
        )

        hard_pilot_section = [
            "## 3. Empirical Hard-Pilot Stress Evaluation",
            "",
            (
                "To make the empirical extension more comparable to the "
                "controlled hard-pilot benchmark, I built 24 empirical "
                "evidence-preservation stress cases from the four real "
                "influenza KG evidence claims. These are not 24 independent "
                "outbreaks. They are stress cases over real surveillance-derived "
                "evidence claims."
            ),
            "",
            hard_pilot_summary,
            "",
            (
                "The main observation is that LLM-only avoided forbidden "
                "overclaims but failed most exact-evidence preservation cases "
                "because empirical lag, score, paired-week count, threshold, "
                "and KG edge evidence were intentionally withheld. Clean "
                "Text-RAG, blended Text-RAG, and GraphRAG context all preserved "
                "the supplied empirical evidence in this 24-case stress set."
            ),
            "",
            hard_pilot_markdown_table(hard_pilot_rows),
            "",
        ]

        interpretation_header = "## 4. Interpretation"
        limitations_header = "## 5. Limitations"
        takeaway_header = "## 6. Thesis-Ready Takeaway"
    else:
        interpretation_header = "## 3. Interpretation"
        limitations_header = "## 4. Limitations"
        takeaway_header = "## 5. Thesis-Ready Takeaway"

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
        *hard_pilot_section,
        interpretation_header,
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
        (
            "The empirical hard-pilot stress evaluation adds a harder "
            "evidence-preservation layer over the same real influenza claims. "
            "It shows that exact evidence facts are not recoverable from "
            "LLM-only context when they are withheld, but can be preserved when "
            "they are supplied through Text-RAG or GraphRAG context. In this "
            "small empirical stress set, Text-RAG and GraphRAG show preservation "
            "parity; the stronger GraphRAG-over-Text-RAG separation remains in "
            "the controlled 50-case benchmark."
        ),
        "",
        limitations_header,
        "",
        "- The empirical extension is small.",
        "- It covers one influenza target case.",
        "- The negative control is deterministic and synthetic.",
        (
            "- The empirical hard-pilot stress cases are generated from four "
            "real evidence claims; they are not independent outbreaks."
        ),
        (
            "- The LLM-only and filled-output baselines are single-sample "
            "outputs rather than repeated stochastic runs."
        ),
        (
            "- Empirical evidence depends on source coverage, normalization, "
            "the lag window, the threshold, and reporting artifacts."
        ),
        "- Lagged correlation is screening evidence, not causal proof.",
        "",
        takeaway_header,
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
        (
            "The empirical hard-pilot comparison further shows that retrieval "
            "context is necessary for exact empirical evidence preservation: "
            "LLM-only failed most exact-evidence cases when evidence was "
            "withheld, while clean Text-RAG, blended Text-RAG, and GraphRAG "
            "context all preserved the supplied evidence in the 24-case stress "
            "set."
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
    hard_pilot_summary_path: Path,
) -> tuple[int, int, int]:
    rows = read_results_index(input_path)
    fixture_rows, empirical_rows = partition_rows(rows)
    hard_pilot_rows = read_optional_csv(hard_pilot_summary_path)

    write_report(
        output_path,
        render_report(fixture_rows, empirical_rows, hard_pilot_rows),
    )

    return len(fixture_rows), len(empirical_rows), len(hard_pilot_rows)


def main() -> int:
    args = parse_args()
    try:
        fixture_count, empirical_count, hard_pilot_count = generate_report(
            args.input,
            args.output,
            args.hard_pilot_summary,
        )
    except (csv.Error, FileNotFoundError, OSError, ValueError) as exc:
        print(f"Real results report failed: {exc}", file=sys.stderr)
        return 1

    print(f"input path: {args.input}")
    print(f"fixture rows: {fixture_count}")
    print(f"empirical rows: {empirical_count}")
    print(f"hard-pilot summary rows: {hard_pilot_count}")
    print(f"output path: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
