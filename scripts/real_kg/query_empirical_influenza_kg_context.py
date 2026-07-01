"""Export GraphRAG context from the empirical influenza Neo4j subgraph.

EvidenceClaim properties are the source of the exported evidence facts.
Positive typed edges are retrieval projections only and do not establish
causality. No graph data is modified by this script.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


DEFAULT_CASE_ID = "real_us_flu_empirical_multicandidate_001"
DEFAULT_TARGET_SIGNAL_ID = (
    "real_signal_us_influenza_hospitalization_rate_flusurv"
)
DEFAULT_OUTPUT = Path(
    "data/real_processed/real_empirical_influenza_graph_context.json"
)
PIPELINE = "empirical_influenza"
VALID_STATUSES = {"present", "missing", "insufficient"}

# Pipeline-marked relationships define the empirical traversal boundary.
# CandidateDriver nodes may be shared by stable ID with the fixture graph, so
# they are reached only through an empirical HAS_CANDIDATE/HAS_EVIDENCE path
# rather than requiring the shared node itself to be relabeled.
CONTEXT_QUERY = """
MATCH (failure:FailureCase {id: $case_id})
MATCH (failure)-[has_target:HAS_TARGET]->(target:Signal {
    id: $target_signal_id
})
WHERE failure.pipeline = $pipeline
  AND target.pipeline = $pipeline
  AND has_target.pipeline = $pipeline
MATCH (failure)-[has_candidate:HAS_CANDIDATE]->(candidate:CandidateDriver)
WHERE has_candidate.pipeline = $pipeline
MATCH (candidate)-[has_evidence:HAS_EVIDENCE]->(evidence:EvidenceClaim)
MATCH (evidence)-[supports_target:SUPPORTS_TARGET]->(target)
WHERE has_evidence.pipeline = $pipeline
  AND evidence.pipeline = $pipeline
  AND supports_target.pipeline = $pipeline
OPTIONAL MATCH
    (candidate)-[typed:LEADING_INDICATOR_FOR]->(target)
WHERE typed.pipeline = $pipeline
  AND typed.evidence_claim_id = evidence.id
RETURN properties(failure) AS failure_case,
       properties(candidate) AS candidate,
       properties(target) AS target_signal,
       properties(evidence) AS evidence,
       properties(typed) AS typed_edge
ORDER BY candidate.id, evidence.id
"""

CLAIM_FIELDS = [
    "status",
    "edge_type",
    "score",
    "threshold",
    "lag_weeks",
    "paired_week_count",
    "minimum_paired_weeks",
    "method",
    "source_dataset",
    "region",
    "time_window_start",
    "time_window_end",
    "evidence_sentence",
    "limitation",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Query the empirical influenza Neo4j subgraph and export "
            "GraphRAG-style evidence context."
        )
    )
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument(
        "--target-signal-id",
        default=DEFAULT_TARGET_SIGNAL_ID,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--uri",
        default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"),
    )
    parser.add_argument(
        "--username",
        default=os.environ.get("NEO4J_USERNAME", "neo4j"),
    )
    parser.add_argument(
        "--password",
        default=os.environ.get("NEO4J_PASSWORD", "password"),
    )
    parser.add_argument(
        "--database",
        default=os.environ.get("NEO4J_DATABASE") or None,
    )
    return parser.parse_args()


def fetch_context_rows(
    case_id: str,
    target_signal_id: str,
    uri: str,
    username: str,
    password: str,
    database: str | None,
) -> list[dict[str, Any]]:
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError(
            "The neo4j Python driver is required to query empirical context."
        ) from exc

    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        driver.verify_connectivity()
        session_options = {"database": database} if database else {}
        with driver.session(**session_options) as session:
            result = session.run(
                CONTEXT_QUERY,
                case_id=case_id,
                target_signal_id=target_signal_id,
                pipeline=PIPELINE,
            )
            return [record.data() for record in result]
    except Exception as exc:
        raise RuntimeError(
            f"Neo4j empirical context query failed: {exc}"
        ) from exc
    finally:
        driver.close()


def status_rank(status: str) -> int:
    return {
        "present": 0,
        "missing": 1,
        "insufficient": 2,
    }[status]


def sortable_score(value: Any) -> float:
    if isinstance(value, bool) or value is None:
        return float("-inf")
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except ValueError:
        return float("-inf")


def claim_sort_key(claim: dict[str, Any]) -> tuple[int, float, str]:
    return (
        status_rank(str(claim["status"])),
        -sortable_score(claim.get("score")),
        str(claim["evidence_claim_id"]),
    )


def build_context(
    case_id: str,
    target_signal_id: str,
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    if not rows:
        raise ValueError(
            f"No empirical evidence found for case {case_id!r} and target "
            f"{target_signal_id!r}."
        )

    target_name: str | None = None
    claims_by_id: dict[str, dict[str, Any]] = {}
    candidate_claims: dict[str, list[dict[str, Any]]] = {}

    for row_number, row in enumerate(rows, start=1):
        failure = dict(row.get("failure_case") or {})
        candidate = dict(row.get("candidate") or {})
        target = dict(row.get("target_signal") or {})
        evidence = dict(row.get("evidence") or {})
        typed_edge = (
            dict(row["typed_edge"]) if row.get("typed_edge") else None
        )

        if failure.get("id") != case_id:
            raise ValueError(
                f"Query row {row_number} has unexpected FailureCase id."
            )
        if failure.get("pipeline") != PIPELINE:
            raise ValueError(
                f"Query row {row_number} is outside pipeline {PIPELINE!r}."
            )
        if target.get("id") != target_signal_id:
            raise ValueError(
                f"Query row {row_number} has unexpected target signal id."
            )
        if target.get("pipeline") != PIPELINE:
            raise ValueError(
                f"Query row {row_number} target is outside the empirical "
                "pipeline."
            )
        if evidence.get("pipeline") != PIPELINE:
            raise ValueError(
                f"Query row {row_number} evidence is outside the empirical "
                "pipeline."
            )

        candidate_id = str(candidate.get("id") or "")
        candidate_name = str(candidate.get("name") or "")
        evidence_id = str(evidence.get("id") or "")
        status = str(evidence.get("status") or "")
        if not candidate_id or not candidate_name or not evidence_id:
            raise ValueError(
                f"Query row {row_number} is missing candidate or evidence "
                "identity properties."
            )
        if status not in VALID_STATUSES:
            raise ValueError(
                f"Query row {row_number} has invalid status {status!r}."
            )
        if typed_edge:
            if typed_edge.get("pipeline") != PIPELINE:
                raise ValueError(
                    f"Query row {row_number} typed edge is outside the "
                    "empirical pipeline."
                )
            if status != "present":
                raise ValueError(
                    f"Query row {row_number} promotes non-present evidence "
                    "to a positive typed edge."
                )

        current_target_name = str(target.get("name") or "")
        if not current_target_name:
            raise ValueError(
                f"Query row {row_number} has no target signal name."
            )
        if target_name is None:
            target_name = current_target_name
        elif target_name != current_target_name:
            raise ValueError("Query rows contain inconsistent target names.")

        claim = {
            "evidence_claim_id": evidence_id,
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            **{field: evidence.get(field) for field in CLAIM_FIELDS},
        }
        existing = claims_by_id.get(evidence_id)
        if existing is not None and existing != claim:
            raise ValueError(
                f"Inconsistent duplicate EvidenceClaim {evidence_id!r}."
            )
        if existing is None:
            claims_by_id[evidence_id] = claim
            candidate_claims.setdefault(candidate_id, []).append(claim)

    candidates: list[dict[str, Any]] = []
    for candidate_id, claims in candidate_claims.items():
        primary = min(claims, key=claim_sort_key)
        candidates.append(
            {
                "candidate_id": candidate_id,
                "candidate_name": primary["candidate_name"],
                **{
                    field: primary.get(field)
                    for field in CLAIM_FIELDS
                },
            }
        )
    candidates.sort(
        key=lambda candidate: (
            status_rank(str(candidate["status"])),
            -sortable_score(candidate.get("score")),
            str(candidate["candidate_id"]),
        )
    )
    candidate_order = {
        candidate["candidate_id"]: index
        for index, candidate in enumerate(candidates)
    }

    evidence_edges = [
        {
            "candidate_id": claim["candidate_id"],
            "candidate_name": claim["candidate_name"],
            "target_signal_id": target_signal_id,
            "target_signal_name": target_name,
            **{field: claim.get(field) for field in CLAIM_FIELDS},
        }
        for claim in sorted(
            claims_by_id.values(),
            key=lambda claim: (
                candidate_order[claim["candidate_id"]],
                str(claim["evidence_claim_id"]),
            ),
        )
    ]

    return {
        "case_id": case_id,
        "target_signal_id": target_signal_id,
        "target_signal_name": target_name,
        "pipeline": PIPELINE,
        "candidates": candidates,
        "evidence_edges": evidence_edges,
    }


def write_context(path: Path, context: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(context, output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")


def print_summary(
    case_id: str,
    candidate_count: int,
    evidence_edge_count: int,
    output_path: Path,
) -> None:
    print(f"Case ID: {case_id}")
    print(f"Candidates returned: {candidate_count}")
    print(f"Evidence edges returned: {evidence_edge_count}")
    print(f"Output path: {output_path}")


def main() -> int:
    args = parse_args()
    try:
        rows = fetch_context_rows(
            case_id=args.case_id,
            target_signal_id=args.target_signal_id,
            uri=args.uri,
            username=args.username,
            password=args.password,
            database=args.database,
        )
        context = build_context(
            args.case_id,
            args.target_signal_id,
            rows,
        )
        write_context(args.output, context)
        print_summary(
            args.case_id,
            len(context["candidates"]),
            len(context["evidence_edges"]),
            args.output,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(
            f"Empirical influenza graph context export failed: {exc}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
