"""Audit empirical influenza evidence parity across text and graph contexts.

The empirical EvidenceClaim CSV is the source of truth. This script performs
a deterministic artifact comparison and does not call Neo4j or an LLM.
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
DEFAULT_OUTPUT = Path(
    "data/real_processed/"
    "real_empirical_influenza_context_parity_audit.csv"
)
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

OUTPUT_COLUMNS = [
    "case_id",
    "candidate_id",
    "candidate_name",
    "target_signal_id",
    "target_signal_name",
    "edge_type",
    "status",
    "expected_score",
    "expected_threshold",
    "expected_lag_weeks",
    "expected_paired_week_count",
    "expected_method",
    "expected_source_dataset",
    "expected_time_window_start",
    "expected_time_window_end",
    "text_chunk_found",
    "text_status_match",
    "text_score_match",
    "text_threshold_match",
    "text_lag_match",
    "text_paired_week_count_match",
    "text_method_match",
    "text_source_dataset_match",
    "graph_edge_found",
    "graph_status_match",
    "graph_score_match",
    "graph_threshold_match",
    "graph_lag_match",
    "graph_paired_week_count_match",
    "graph_method_match",
    "graph_source_dataset_match",
    "full_parity_pass",
    "notes",
]

TEXT_CHECKS = [
    "text_chunk_found",
    "text_status_match",
    "text_score_match",
    "text_threshold_match",
    "text_lag_match",
    "text_paired_week_count_match",
    "text_method_match",
    "text_source_dataset_match",
]

GRAPH_CHECKS = [
    "graph_edge_found",
    "graph_status_match",
    "graph_score_match",
    "graph_threshold_match",
    "graph_lag_match",
    "graph_paired_week_count_match",
    "graph_method_match",
    "graph_source_dataset_match",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit evidence-fact parity among empirical claims, Text-RAG "
            "cards, and GraphRAG context."
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
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
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
        and str(chunk.get("edge_type", "")) == claim["edge_type"]
        and str(chunk.get("status", "")) == claim["status"]
    ]
    if not matches:
        return None
    return min(matches, key=lambda chunk: str(chunk.get("chunk_id", "")))


def graph_scope_matches(
    claim: dict[str, str],
    graph_context: dict[str, Any],
) -> bool:
    return (
        str(graph_context.get("case_id", "")) == claim["case_id"]
        and str(graph_context.get("target_signal_id", ""))
        == claim["target_signal_id"]
        and str(graph_context.get("pipeline", "")) == PIPELINE
    )


def choose_graph_edge(
    claim: dict[str, str],
    graph_context: dict[str, Any],
) -> dict[str, Any] | None:
    if not graph_scope_matches(claim, graph_context):
        return None
    matches = [
        edge
        for edge in graph_context.get("evidence_edges", [])
        if isinstance(edge, dict)
        and str(edge.get("candidate_id", "")) == claim["candidate_id"]
        and str(edge.get("target_signal_id", ""))
        == claim["target_signal_id"]
        and str(edge.get("edge_type", "")) == claim["edge_type"]
        and str(edge.get("status", "")) == claim["status"]
    ]
    if not matches:
        return None
    return matches[0]


def audit_parity(
    claims: list[dict[str, str]],
    text_corpus: list[dict[str, Any]],
    graph_context: dict[str, Any],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for claim in claims:
        chunk = choose_text_chunk(claim, text_corpus)
        text = str(chunk.get("text", "")) if chunk else ""
        edge = choose_graph_edge(claim, graph_context)

        row: dict[str, Any] = {
            "case_id": claim["case_id"],
            "candidate_id": claim["candidate_id"],
            "candidate_name": claim["candidate_name"],
            "target_signal_id": claim["target_signal_id"],
            "target_signal_name": claim["target_signal_name"],
            "edge_type": claim["edge_type"],
            "status": claim["status"],
            "expected_score": claim["score"],
            "expected_threshold": claim["threshold"],
            "expected_lag_weeks": claim["lag_weeks"],
            "expected_paired_week_count": claim["paired_week_count"],
            "expected_method": claim["method"],
            "expected_source_dataset": claim["source_dataset"],
            "expected_time_window_start": claim["time_window_start"],
            "expected_time_window_end": claim["time_window_end"],
            "text_chunk_found": chunk is not None,
            "text_status_match": (
                chunk is not None
                and text_line_value(text, "Status") == claim["status"]
            ),
            "text_score_match": (
                chunk is not None
                and numeric_match(
                    text_line_value(text, "Score"),
                    claim["score"],
                )
            ),
            "text_threshold_match": (
                chunk is not None
                and numeric_match(
                    text_line_value(text, "Threshold"),
                    claim["threshold"],
                )
            ),
            "text_lag_match": (
                chunk is not None
                and integer_match(
                    text_line_value(text, "Lag weeks"),
                    claim["lag_weeks"],
                )
            ),
            "text_paired_week_count_match": (
                chunk is not None
                and integer_match(
                    text_line_value(text, "Paired week count"),
                    claim["paired_week_count"],
                )
            ),
            "text_method_match": (
                chunk is not None
                and text_line_value(text, "Method") == claim["method"]
            ),
            "text_source_dataset_match": (
                chunk is not None
                and text_line_value(text, "Source dataset")
                == claim["source_dataset"]
            ),
            "graph_edge_found": edge is not None,
            "graph_status_match": (
                edge is not None
                and normalized(edge.get("status")) == claim["status"]
            ),
            "graph_score_match": (
                edge is not None
                and numeric_match(edge.get("score"), claim["score"])
            ),
            "graph_threshold_match": (
                edge is not None
                and numeric_match(edge.get("threshold"), claim["threshold"])
            ),
            "graph_lag_match": (
                edge is not None
                and integer_match(edge.get("lag_weeks"), claim["lag_weeks"])
            ),
            "graph_paired_week_count_match": (
                edge is not None
                and integer_match(
                    edge.get("paired_week_count"),
                    claim["paired_week_count"],
                )
            ),
            "graph_method_match": (
                edge is not None
                and normalized(edge.get("method")) == claim["method"]
            ),
            "graph_source_dataset_match": (
                edge is not None
                and normalized(edge.get("source_dataset"))
                == claim["source_dataset"]
            ),
        }
        text_pass = all(bool(row[column]) for column in TEXT_CHECKS)
        graph_pass = all(bool(row[column]) for column in GRAPH_CHECKS)
        row["_text_parity_pass"] = text_pass
        row["_graph_parity_pass"] = graph_pass
        row["full_parity_pass"] = text_pass and graph_pass

        failures = [
            column
            for column in [*TEXT_CHECKS, *GRAPH_CHECKS]
            if not row[column]
        ]
        row["notes"] = (
            "Full empirical context parity."
            if not failures
            else "Failed checks: " + ", ".join(failures) + "."
        )
        output.append(row)
    return output


def write_audit(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=OUTPUT_COLUMNS,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows: list[dict[str, Any]], output_path: Path) -> None:
    print(f"Claims audited: {len(rows)}")
    print(
        "Text parity passes: "
        f"{sum(bool(row['_text_parity_pass']) for row in rows)}"
    )
    print(
        "Graph parity passes: "
        f"{sum(bool(row['_graph_parity_pass']) for row in rows)}"
    )
    print(
        "Full parity passes: "
        f"{sum(bool(row['full_parity_pass']) for row in rows)}"
    )
    print(f"Output path: {output_path}")


def main() -> int:
    args = parse_args()
    try:
        claims = read_claims(args.claims)
        text_corpus = read_json(
            args.text_corpus,
            list,
            "Empirical Text-RAG corpus",
        )
        graph_context = read_json(
            args.graph_context,
            dict,
            "Empirical GraphRAG context",
        )
        rows = audit_parity(claims, text_corpus, graph_context)
        write_audit(args.output, rows)
        print_summary(rows, args.output)
    except (csv.Error, FileNotFoundError, OSError, ValueError) as exc:
        print(
            f"Empirical context parity audit failed: {exc}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
