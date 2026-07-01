"""Build a final index of fixture and empirical real-KG results.

This is a deterministic CSV harmonization step. It does not call an LLM,
query Neo4j, download data, or modify either input summary.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any


DEFAULT_FIXTURE_SUMMARY = Path(
    "evals/results_real/real_method_comparison_summary.csv"
)
DEFAULT_EMPIRICAL_SUMMARY = Path(
    "evals/results_real/"
    "real_empirical_influenza_method_comparison_summary.csv"
)
DEFAULT_OUTPUT = Path("evals/results_real/real_results_index.csv")

OUTPUT_COLUMNS = [
    "result_family",
    "result_type",
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
    "score_claims",
    "threshold_claims",
    "total_must_not_include_violations",
    "notes",
]

FIXTURE_NOTES = (
    "Controlled fixture real-KG comparison with known evidence status and "
    "candidate structure."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Combine fixture real-KG and empirical influenza method "
            "comparison summaries into one index."
        )
    )
    parser.add_argument(
        "--fixture-summary",
        type=Path,
        default=DEFAULT_FIXTURE_SUMMARY,
    )
    parser.add_argument(
        "--empirical-summary",
        type=Path,
        default=DEFAULT_EMPIRICAL_SUMMARY,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def read_summary(path: Path, description: str) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"{description} input not found: {path}")

    with path.open("r", newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        fieldnames = reader.fieldnames
        if fieldnames is None:
            raise ValueError(f"{description} input has no header: {path}")
        if "method" not in fieldnames:
            raise ValueError(
                f"{description} input is missing required column: method"
            )
        return [
            {
                column: (value or "").strip()
                for column, value in row.items()
                if column is not None
            }
            for row in reader
        ]


def index_row(
    source: dict[str, str],
    result_family: str,
    result_type: str,
    notes: str,
) -> dict[str, str]:
    row = {column: source.get(column, "") for column in OUTPUT_COLUMNS}
    row["result_family"] = result_family
    row["result_type"] = result_type
    row["notes"] = notes
    return row


def build_index(
    fixture_rows: list[dict[str, str]],
    empirical_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    fixture_index_rows = [
        index_row(
            row,
            "fixture_real_kg",
            "controlled_fixture_method_comparison",
            FIXTURE_NOTES,
        )
        for row in fixture_rows
    ]
    empirical_index_rows = [
        index_row(
            row,
            "empirical_influenza",
            "real_data_method_comparison",
            row.get("notes", ""),
        )
        for row in empirical_rows
    ]
    return fixture_index_rows + empirical_index_rows


def write_index(path: Path, rows: list[dict[str, Any]]) -> None:
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
        fixture_rows = read_summary(
            args.fixture_summary,
            "Fixture summary",
        )
        empirical_rows = read_summary(
            args.empirical_summary,
            "Empirical summary",
        )
        index_rows = build_index(fixture_rows, empirical_rows)
        write_index(args.output, index_rows)
    except (csv.Error, FileNotFoundError, OSError, ValueError) as exc:
        print(f"Real results index failed: {exc}", file=sys.stderr)
        return 1

    print(f"fixture rows loaded: {len(fixture_rows)}")
    print(f"empirical rows loaded: {len(empirical_rows)}")
    print(f"rows written: {len(index_rows)}")
    print(f"output path: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
