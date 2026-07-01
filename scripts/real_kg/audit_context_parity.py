"""Audit evidence-fact parity across real KG pipeline artifacts.

The evidence-claim CSV is the source of truth. This deterministic audit checks
whether the Text-RAG corpus and exported GraphRAG context preserve each claim's
candidate-specific facts. It does not call Neo4j or an LLM.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_CLAIMS = Path("data/real_processed/real_evidence_claims.csv")
DEFAULT_TEXT_CORPUS = Path(
    "data/real_processed/real_text_rag_corpus.json"
)
DEFAULT_GRAPH_CONTEXT = Path(
    "data/real_processed/real_graph_context.json"
)
DEFAULT_OUTPUT = Path("evals/results_real/context_parity_audit.csv")

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
    "expected_status",
    "expected_score",
    "expected_threshold",
    "expected_lag_weeks",
    "expected_method",
    "expected_source_dataset",
    "expected_region",
    "expected_time_window_start",
    "expected_time_window_end",
    "text_chunk_found",
    "text_has_candidate_id",
    "text_has_candidate_name",
    "text_has_target_signal_id",
    "text_has_edge_type",
    "text_has_status",
    "text_has_score",
    "text_has_threshold",
    "text_has_lag_weeks",
    "text_has_method",
    "text_has_source_dataset",
    "text_has_region",
    "text_has_time_window",
    "text_has_limitation",
    "graph_candidate_found",
    "graph_evidence_found",
    "graph_has_candidate_id",
    "graph_has_candidate_name",
    "graph_has_target_signal_id",
    "graph_has_edge_type",
    "graph_has_status",
    "graph_has_score",
    "graph_has_threshold",
    "graph_has_lag_weeks",
    "graph_has_method",
    "graph_has_source_dataset",
    "graph_has_region",
    "graph_has_time_window",
    "graph_has_limitation",
    "parity_pass",
    "notes",
]

TEXT_CHECK_COLUMNS = [
    column for column in OUTPUT_COLUMNS if column.startswith("text_")
]
GRAPH_CHECK_COLUMNS = [
    column for column in OUTPUT_COLUMNS if column.startswith("graph_")
]

NUMBER_PATTERN = re.compile(
    r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Compare real EvidenceClaim facts with Text-RAG and GraphRAG "
            "context artifacts."
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
        raise FileNotFoundError(f"Evidence claims file not found: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            raise ValueError(f"Evidence claims CSV has no header: {path}")
        missing = [
            column for column in CLAIM_COLUMNS if column not in reader.fieldnames
        ]
        if missing:
            raise ValueError(
                "Evidence claims CSV is missing required columns: "
                + ", ".join(missing)
            )
        return [
            {
                column: (row.get(column) or "").strip()
                for column in CLAIM_COLUMNS
            }
            for row in reader
        ]


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


def normalized(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def normalized_without_period(value: Any) -> str:
    return normalized(value).removesuffix(".")


def numeric_value(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    match = NUMBER_PATTERN.search(str(value))
    if match is None:
        return None
    try:
        number = float(match.group(0))
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def numeric_equal(actual: Any, expected: Any) -> bool:
    actual_number = numeric_value(actual)
    expected_number = numeric_value(expected)
    if actual_number is None or expected_number is None:
        return normalized(actual) == normalized(expected)
    return math.isclose(
        actual_number,
        expected_number,
        rel_tol=1e-9,
        abs_tol=1e-9,
    )


def text_line_value(text: str, label: str) -> str | None:
    prefix = f"{label.lower()}:"
    for line in text.splitlines():
        if line.lower().startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def choose_text_chunk(
    claim: dict[str, str],
    text_corpus: list[dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = [
        chunk
        for chunk in text_corpus
        if isinstance(chunk, dict)
        and str(chunk.get("case_id", "")) == claim["case_id"]
        and str(chunk.get("candidate_id", "")) == claim["candidate_id"]
    ]
    if not candidates:
        return None
    candidates.sort(
        key=lambda chunk: (
            str(chunk.get("target_signal_id", ""))
            != claim["target_signal_id"],
            str(chunk.get("edge_type", "")) != claim["edge_type"],
            str(chunk.get("chunk_id", "")),
        )
    )
    return candidates[0]


def choose_graph_candidate(
    claim: dict[str, str],
    graph_context: dict[str, Any],
) -> dict[str, Any] | None:
    candidates = [
        candidate
        for candidate in graph_context.get("candidates", [])
        if isinstance(candidate, dict)
        and str(candidate.get("candidate_id", "")) == claim["candidate_id"]
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda candidate: str(candidate.get("candidate_id", "")))
    return candidates[0]


def choose_graph_evidence(
    claim: dict[str, str],
    candidate: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if candidate is None:
        return None
    edges = [
        edge
        for edge in candidate.get("evidence_edges", [])
        if isinstance(edge, dict)
    ]
    if not edges:
        return None
    edges.sort(
        key=lambda edge: (
            str(edge.get("target_signal_id", ""))
            != claim["target_signal_id"],
            str(edge.get("edge_type", "")) != claim["edge_type"],
            str(edge.get("evidence_claim_id", "")),
        )
    )
    return edges[0]


def support_nodes_by_type_and_id(
    graph_context: dict[str, Any],
) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(node.get("type", "")), str(node.get("id", ""))): node
        for node in graph_context.get("support_nodes", [])
        if isinstance(node, dict) and node.get("id")
    }


def first_defined(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def missing_claim_has_positive_projection(
    claim: dict[str, str],
    evidence: dict[str, Any] | None,
    graph_context: dict[str, Any],
) -> bool:
    if claim["status"] not in {"missing", "insufficient_data"}:
        return False
    evidence_id = (
        str(evidence.get("evidence_claim_id", "")) if evidence else ""
    )
    return any(
        isinstance(edge, dict)
        and edge.get("edge_type") == "LEADING_INDICATOR_FOR"
        and str(edge.get("source_id", "")) == claim["candidate_id"]
        and str(edge.get("target_id", "")) == claim["target_signal_id"]
        and (
            not edge.get("evidence_id")
            or not evidence_id
            or str(edge.get("evidence_id")) == evidence_id
        )
        for edge in graph_context.get("support_edges", [])
    )


def audit_claim(
    claim: dict[str, str],
    text_corpus: list[dict[str, Any]],
    graph_context: dict[str, Any],
    support_nodes: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    chunk = choose_text_chunk(claim, text_corpus)
    text = str(chunk.get("text", "")) if chunk else ""
    text_time_window = text_line_value(text, "Time window")

    candidate = choose_graph_candidate(claim, graph_context)
    evidence = choose_graph_evidence(claim, candidate)
    evidence_id = (
        str(evidence.get("evidence_claim_id", "")) if evidence else ""
    )
    support_claim = support_nodes.get(("EvidenceClaim", evidence_id), {})
    support_candidate = support_nodes.get(
        ("CandidateDriver", claim["candidate_id"]),
        {},
    )

    graph_candidate_name = first_defined(
        candidate.get("candidate_name") if candidate else None,
        support_candidate.get("name"),
    )
    graph_threshold = first_defined(
        evidence.get("threshold") if evidence else None,
        support_claim.get("threshold"),
    )
    graph_limitation = first_defined(
        evidence.get("limitation") if evidence else None,
        support_claim.get("limitation"),
    )

    row: dict[str, Any] = {
        "case_id": claim["case_id"],
        "candidate_id": claim["candidate_id"],
        "candidate_name": claim["candidate_name"],
        "target_signal_id": claim["target_signal_id"],
        "target_signal_name": claim["target_signal_name"],
        "edge_type": claim["edge_type"],
        "expected_status": claim["status"],
        "expected_score": claim["score"],
        "expected_threshold": claim["threshold"],
        "expected_lag_weeks": claim["lag_weeks"],
        "expected_method": claim["method"],
        "expected_source_dataset": claim["source_dataset"],
        "expected_region": claim["region"],
        "expected_time_window_start": claim["time_window_start"],
        "expected_time_window_end": claim["time_window_end"],
        "text_chunk_found": chunk is not None,
        "text_has_candidate_id": (
            chunk is not None
            and str(chunk.get("candidate_id", "")) == claim["candidate_id"]
        ),
        "text_has_candidate_name": (
            chunk is not None
            and normalized(claim["candidate_name"]) in normalized(text)
        ),
        "text_has_target_signal_id": (
            chunk is not None
            and str(chunk.get("target_signal_id", ""))
            == claim["target_signal_id"]
        ),
        "text_has_edge_type": (
            chunk is not None
            and str(chunk.get("edge_type", "")) == claim["edge_type"]
        ),
        "text_has_status": (
            chunk is not None
            and str(chunk.get("status", "")) == claim["status"]
        ),
        "text_has_score": numeric_equal(
            text_line_value(text, "Score"),
            claim["score"],
        ),
        "text_has_threshold": numeric_equal(
            text_line_value(text, "Threshold"),
            claim["threshold"],
        ),
        "text_has_lag_weeks": numeric_equal(
            text_line_value(text, "Lag weeks"),
            claim["lag_weeks"],
        ),
        "text_has_method": (
            normalized_without_period(text_line_value(text, "Method"))
            == normalized(claim["method"])
        ),
        "text_has_source_dataset": (
            normalized_without_period(
                text_line_value(text, "Source dataset")
            )
            == normalized(claim["source_dataset"])
        ),
        "text_has_region": (
            normalized_without_period(text_line_value(text, "Region"))
            == normalized(claim["region"])
        ),
        "text_has_time_window": (
            text_time_window is not None
            and claim["time_window_start"] in text_time_window
            and claim["time_window_end"] in text_time_window
        ),
        "text_has_limitation": (
            normalized(text_line_value(text, "Limitation"))
            == normalized(claim["limitation"])
        ),
        "graph_candidate_found": candidate is not None,
        "graph_evidence_found": evidence is not None,
        "graph_has_candidate_id": (
            candidate is not None
            and str(candidate.get("candidate_id", ""))
            == claim["candidate_id"]
        ),
        "graph_has_candidate_name": (
            normalized(graph_candidate_name) == normalized(claim["candidate_name"])
        ),
        "graph_has_target_signal_id": (
            evidence is not None
            and str(evidence.get("target_signal_id", ""))
            == claim["target_signal_id"]
        ),
        "graph_has_edge_type": (
            evidence is not None
            and str(evidence.get("edge_type", "")) == claim["edge_type"]
        ),
        "graph_has_status": (
            evidence is not None
            and str(evidence.get("status", "")) == claim["status"]
        ),
        # Use the evidence edge's score, never the candidate ranking score.
        "graph_has_score": (
            evidence is not None
            and numeric_equal(evidence.get("score"), claim["score"])
        ),
        "graph_has_threshold": numeric_equal(
            graph_threshold,
            claim["threshold"],
        ),
        "graph_has_lag_weeks": (
            evidence is not None
            and numeric_equal(evidence.get("lag_weeks"), claim["lag_weeks"])
        ),
        "graph_has_method": (
            evidence is not None
            and normalized(evidence.get("method")) == normalized(claim["method"])
        ),
        "graph_has_source_dataset": (
            evidence is not None
            and normalized(evidence.get("source_dataset"))
            == normalized(claim["source_dataset"])
        ),
        "graph_has_region": (
            evidence is not None
            and normalized(evidence.get("region")) == normalized(claim["region"])
        ),
        "graph_has_time_window": (
            evidence is not None
            and normalized(evidence.get("time_window_start"))
            == normalized(claim["time_window_start"])
            and normalized(evidence.get("time_window_end"))
            == normalized(claim["time_window_end"])
        ),
        "graph_has_limitation": (
            normalized(graph_limitation) == normalized(claim["limitation"])
        ),
    }

    text_parity = all(bool(row[column]) for column in TEXT_CHECK_COLUMNS)
    graph_parity = all(bool(row[column]) for column in GRAPH_CHECK_COLUMNS)
    positive_projection = missing_claim_has_positive_projection(
        claim,
        evidence,
        graph_context,
    )
    if positive_projection:
        graph_parity = False

    notes: list[str] = []
    if not text_parity:
        failed = [
            column for column in TEXT_CHECK_COLUMNS if not bool(row[column])
        ]
        notes.append("Text mismatch: " + ", ".join(failed))
    if not graph_parity:
        failed = [
            column for column in GRAPH_CHECK_COLUMNS if not bool(row[column])
        ]
        if failed:
            notes.append("Graph mismatch: " + ", ".join(failed))
    if positive_projection:
        notes.append(
            "Missing evidence was promoted to a positive typed edge"
        )

    row["_text_parity_pass"] = text_parity
    row["_graph_parity_pass"] = graph_parity
    row["parity_pass"] = text_parity and graph_parity
    row["notes"] = "; ".join(notes)
    return row


def audit_parity(
    claims: list[dict[str, str]],
    text_corpus: list[dict[str, Any]],
    graph_context: dict[str, Any],
) -> list[dict[str, Any]]:
    support_nodes = support_nodes_by_type_and_id(graph_context)
    return [
        audit_claim(claim, text_corpus, graph_context, support_nodes)
        for claim in claims
    ]


def validate_output_path(path: Path) -> None:
    forbidden = (Path.cwd() / "evals" / "results").resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(forbidden)
    except ValueError:
        return
    raise ValueError("Refusing to write context parity output under evals/results/.")


def write_audit(path: Path, rows: list[dict[str, Any]]) -> None:
    validate_output_path(path)
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


def print_summary(rows: list[dict[str, Any]], output: Path) -> None:
    print(f"Total evidence claims: {len(rows)}")
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
        f"{sum(bool(row['parity_pass']) for row in rows)}"
    )
    print(f"Output path: {output}")


def main() -> int:
    args = parse_args()
    try:
        claims = read_claims(args.claims)
        text_corpus = read_json(args.text_corpus, list, "Text-RAG corpus")
        graph_context = read_json(
            args.graph_context,
            dict,
            "GraphRAG context",
        )
        rows = audit_parity(claims, text_corpus, graph_context)
        write_audit(args.output, rows)
        print_summary(rows, args.output)
    except (csv.Error, FileNotFoundError, OSError, ValueError) as exc:
        print(f"Context parity audit failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
