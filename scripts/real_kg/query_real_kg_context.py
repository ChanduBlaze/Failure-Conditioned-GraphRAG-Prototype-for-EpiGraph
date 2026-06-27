"""Export read-only real-data graph retrieval context for GraphRAG.

The exported evidence is retrieval context: it preserves graph assertions and
their provenance for downstream inspection, but it does not prove causality.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


DEFAULT_CASE_ID = "real_us_flu_wastewater_leading_indicator_001"
DEFAULT_OUTPUT = Path("data/real_processed/real_graph_context.json")

CASE_QUERY = """
MATCH (failure_case:FailureCase {id: $case_id})
OPTIONAL MATCH (failure_case)-[:HAS_TARGET_SIGNAL]->(target_signal:Signal)
RETURN properties(failure_case) AS failure_case,
       properties(target_signal) AS target_signal
ORDER BY target_signal.id
"""

EVIDENCE_QUERY = """
MATCH (failure_case:FailureCase {id: $case_id})
MATCH (failure_case)-[:HAS_TARGET_SIGNAL]->(target_signal:Signal)
MATCH (failure_case)-[:HAS_CANDIDATE]->(candidate:CandidateDriver)
OPTIONAL MATCH
    (candidate)-[:HAS_EVIDENCE]->(evidence:EvidenceClaim)
    -[:SUPPORTS_TARGET]->(target_signal)
OPTIONAL MATCH (evidence)-[:DERIVED_FROM]->(dataset:Dataset)
OPTIONAL MATCH (evidence)-[:OBSERVED_IN]->(region:Region)
OPTIONAL MATCH (evidence)-[:EVALUATED_DURING]->(time_window:TimeWindow)
OPTIONAL MATCH
    (candidate)-[typed:LEADING_INDICATOR_FOR]->(target_signal)
WHERE typed.evidence_id = evidence.id
RETURN properties(candidate) AS candidate,
       properties(target_signal) AS target_signal,
       properties(evidence) AS evidence,
       properties(dataset) AS dataset,
       properties(region) AS region,
       properties(time_window) AS time_window,
       properties(typed) AS typed_edge
ORDER BY candidate.id, evidence.id, dataset.id, region.id, time_window.id
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Query one real FailureCase from Neo4j and export deterministic "
            "GraphRAG-style evidence context."
        )
    )
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def get_connection_settings() -> tuple[str, str, str, str]:
    settings = {
        "NEO4J_URI": os.environ.get("NEO4J_URI", "").strip(),
        "NEO4J_USER": os.environ.get("NEO4J_USER", "").strip(),
        "NEO4J_PASSWORD": os.environ.get("NEO4J_PASSWORD", ""),
    }
    missing = [name for name, value in settings.items() if not value]
    if missing:
        raise ValueError(
            "Missing Neo4j connection environment variables: "
            + ", ".join(missing)
        )

    database = os.environ.get("NEO4J_DATABASE", "neo4j").strip() or "neo4j"
    return (
        settings["NEO4J_URI"],
        settings["NEO4J_USER"],
        settings["NEO4J_PASSWORD"],
        database,
    )


def fetch_graph_rows(
    case_id: str,
    settings: tuple[str, str, str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError(
            "The neo4j Python driver is required to export graph context."
        ) from exc

    uri, user, password, database = settings
    try:
        driver = GraphDatabase.driver(uri, auth=(user, password))
    except Exception as exc:
        raise RuntimeError(f"Neo4j connection failed: {exc}") from exc

    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            case_rows = [
                record.data()
                for record in session.run(CASE_QUERY, case_id=case_id)
            ]
            evidence_rows = [
                record.data()
                for record in session.run(EVIDENCE_QUERY, case_id=case_id)
            ]
    except Exception as exc:
        raise RuntimeError(f"Neo4j connection or query failed: {exc}") from exc
    finally:
        driver.close()

    return case_rows, evidence_rows


def add_support_node(
    nodes: dict[tuple[str, str], dict[str, Any]],
    node_type: str,
    properties: dict[str, Any] | None,
) -> None:
    if not properties or not properties.get("id"):
        return
    node = {"type": node_type, **properties}
    nodes[(node_type, str(properties["id"]))] = node


def add_support_edge(
    edges: dict[tuple[str, str, str, str], dict[str, Any]],
    source_id: str,
    edge_type: str,
    target_id: str,
    properties: dict[str, Any] | None = None,
) -> None:
    edge = {
        "source_id": source_id,
        "edge_type": edge_type,
        "target_id": target_id,
    }
    if properties:
        edge.update(properties)
    evidence_id = str(edge.get("evidence_id", ""))
    edges[(source_id, edge_type, target_id, evidence_id)] = edge


def first_properties(
    properties_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not properties_by_id:
        return None
    first_id = sorted(properties_by_id)[0]
    return properties_by_id[first_id]


def build_context(
    case_id: str,
    case_rows: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any], int, int]:
    if not case_rows:
        raise ValueError(f"FailureCase not found: {case_id}")

    failure_case = dict(case_rows[0]["failure_case"])
    targets = {
        str(row["target_signal"]["id"]): dict(row["target_signal"])
        for row in case_rows
        if row.get("target_signal") and row["target_signal"].get("id")
    }
    if not targets:
        raise ValueError(f"FailureCase {case_id!r} has no target signal.")
    if len(targets) > 1:
        raise ValueError(
            f"FailureCase {case_id!r} has multiple target signals; "
            "this exporter requires exactly one."
        )
    target_signal = targets[sorted(targets)[0]]

    candidates: dict[str, dict[str, Any]] = {}
    support_nodes: dict[tuple[str, str], dict[str, Any]] = {}
    support_edges: dict[tuple[str, str, str, str], dict[str, Any]] = {}

    add_support_node(support_nodes, "FailureCase", failure_case)
    add_support_node(support_nodes, "Signal", target_signal)
    add_support_edge(
        support_edges,
        str(failure_case["id"]),
        "HAS_TARGET_SIGNAL",
        str(target_signal["id"]),
    )

    for row in evidence_rows:
        candidate = dict(row["candidate"])
        candidate_id = str(candidate["id"])
        candidate_entry = candidates.setdefault(
            candidate_id,
            {
                "properties": candidate,
                "claims": {},
            },
        )
        add_support_node(support_nodes, "CandidateDriver", candidate)
        add_support_edge(
            support_edges,
            str(failure_case["id"]),
            "HAS_CANDIDATE",
            candidate_id,
        )

        evidence = row.get("evidence")
        if not evidence:
            continue
        evidence = dict(evidence)
        evidence_id = str(evidence["id"])
        claim_entry = candidate_entry["claims"].setdefault(
            evidence_id,
            {
                "properties": evidence,
                "datasets": {},
                "regions": {},
                "time_windows": {},
                "typed_edges": {},
            },
        )

        dataset = dict(row["dataset"]) if row.get("dataset") else None
        region = dict(row["region"]) if row.get("region") else None
        time_window = (
            dict(row["time_window"]) if row.get("time_window") else None
        )
        for collection_name, properties in (
            ("datasets", dataset),
            ("regions", region),
            ("time_windows", time_window),
        ):
            if properties and properties.get("id"):
                claim_entry[collection_name][str(properties["id"])] = properties

        add_support_node(support_nodes, "EvidenceClaim", evidence)
        add_support_node(support_nodes, "Dataset", dataset)
        add_support_node(support_nodes, "Region", region)
        add_support_node(support_nodes, "TimeWindow", time_window)
        add_support_edge(
            support_edges,
            candidate_id,
            "HAS_EVIDENCE",
            evidence_id,
        )
        add_support_edge(
            support_edges,
            evidence_id,
            "SUPPORTS_TARGET",
            str(target_signal["id"]),
        )
        if dataset:
            add_support_edge(
                support_edges,
                evidence_id,
                "DERIVED_FROM",
                str(dataset["id"]),
            )
        if region:
            add_support_edge(
                support_edges,
                evidence_id,
                "OBSERVED_IN",
                str(region["id"]),
            )
        if time_window:
            add_support_edge(
                support_edges,
                evidence_id,
                "EVALUATED_DURING",
                str(time_window["id"]),
            )

        typed_edge = dict(row["typed_edge"]) if row.get("typed_edge") else None
        # A typed edge is a retrieval projection only. Missing and
        # insufficient_data claims remain in context but are never promoted to
        # positive typed evidence, and even a present association is not causal
        # proof.
        if evidence.get("status") == "present" and typed_edge:
            typed_key = (
                str(typed_edge.get("evidence_id", evidence_id)),
                str(target_signal["id"]),
            )
            claim_entry["typed_edges"][typed_key] = typed_edge
            add_support_edge(
                support_edges,
                candidate_id,
                "LEADING_INDICATOR_FOR",
                str(target_signal["id"]),
                typed_edge,
            )

    if not candidates:
        raise ValueError(f"FailureCase {case_id!r} has no candidates.")

    evidence_claim_count = sum(
        len(candidate["claims"]) for candidate in candidates.values()
    )
    if evidence_claim_count == 0:
        raise ValueError(f"FailureCase {case_id!r} has no evidence claims.")

    output_candidates: list[dict[str, Any]] = []
    typed_present_edge_count = 0
    for candidate_id, candidate_entry in candidates.items():
        evidence_edges: list[dict[str, Any]] = []
        candidate_score: int | float = 0
        for evidence_id in sorted(candidate_entry["claims"]):
            claim = candidate_entry["claims"][evidence_id]
            evidence = claim["properties"]
            dataset = first_properties(claim["datasets"])
            region = first_properties(claim["regions"])
            time_window = first_properties(claim["time_windows"])

            evidence_edges.append(
                {
                    "edge_type": evidence.get("edge_type"),
                    "status": evidence.get("status"),
                    "evidence_claim_id": evidence_id,
                    "target_signal_id": target_signal["id"],
                    "score": evidence.get("score"),
                    "lag_weeks": evidence.get("lag_weeks"),
                    "method": evidence.get("method"),
                    "evidence_sentence": evidence.get("evidence_sentence"),
                    "limitation": evidence.get("limitation"),
                    "source_dataset": dataset.get("name") if dataset else None,
                    "region": region.get("name") if region else None,
                    "time_window_start": (
                        time_window.get("start") if time_window else None
                    ),
                    "time_window_end": (
                        time_window.get("end") if time_window else None
                    ),
                }
            )

            if evidence.get("status") == "present":
                for typed_edge in claim["typed_edges"].values():
                    typed_present_edge_count += 1
                    typed_score = typed_edge.get("score")
                    if isinstance(typed_score, (int, float)) and not isinstance(
                        typed_score,
                        bool,
                    ):
                        candidate_score += typed_score

        candidate_properties = candidate_entry["properties"]
        output_candidates.append(
            {
                "candidate_id": candidate_id,
                "candidate_name": candidate_properties.get("name"),
                "score": candidate_score,
                "evidence_edges": evidence_edges,
            }
        )

    output_candidates.sort(
        key=lambda candidate: (-candidate["score"], candidate["candidate_id"])
    )
    sorted_support_nodes = sorted(
        support_nodes.values(),
        key=lambda node: (str(node["type"]), str(node["id"])),
    )
    sorted_support_edges = sorted(
        support_edges.values(),
        key=lambda edge: (
            str(edge["source_id"]),
            str(edge["edge_type"]),
            str(edge["target_id"]),
            str(edge.get("evidence_id", "")),
        ),
    )

    context = {
        "case_id": case_id,
        "failure_case": failure_case,
        "target_signal": target_signal,
        "candidates": output_candidates,
        "support_nodes": sorted_support_nodes,
        "support_edges": sorted_support_edges,
    }
    return context, evidence_claim_count, typed_present_edge_count


def validate_output_path(output_path: Path) -> None:
    forbidden = (Path.cwd() / "evals" / "results").resolve()
    resolved_output = output_path.resolve()
    try:
        resolved_output.relative_to(forbidden)
    except ValueError:
        return
    raise ValueError("Refusing to write graph context under evals/results/.")


def write_context(output_path: Path, context: dict[str, Any]) -> None:
    validate_output_path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as output_file:
        json.dump(context, output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")


def print_summary(
    case_id: str,
    output_path: Path,
    candidate_count: int,
    evidence_claim_count: int,
    typed_present_edge_count: int,
) -> None:
    print("Real graph context exported.")
    print(f"Case ID: {case_id}")
    print(f"Output path: {output_path}")
    print(f"Candidate count: {candidate_count}")
    print(f"Evidence claim count: {evidence_claim_count}")
    print(f"Typed present edge count: {typed_present_edge_count}")


def main() -> int:
    args = parse_args()
    try:
        settings = get_connection_settings()
        case_rows, evidence_rows = fetch_graph_rows(args.case_id, settings)
        context, evidence_claim_count, typed_present_edge_count = build_context(
            args.case_id,
            case_rows,
            evidence_rows,
        )
        write_context(args.output, context)
        print_summary(
            args.case_id,
            args.output,
            len(context["candidates"]),
            evidence_claim_count,
            typed_present_edge_count,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Real graph context export failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
