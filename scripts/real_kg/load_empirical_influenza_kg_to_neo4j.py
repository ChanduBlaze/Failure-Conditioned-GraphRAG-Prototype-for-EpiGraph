"""Load empirical influenza EvidenceClaims into an isolated Neo4j subgraph.

Only graph records marked ``pipeline = empirical_influenza`` are replaced.
Cleanup and loading run in one transaction so a failed load rolls back the
scoped cleanup. This script never invokes the fixture-based loader.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path(
    "data/real_processed/real_empirical_influenza_evidence_claims.csv"
)
PIPELINE = "empirical_influenza"
FAILURE_CASE_NAME = (
    "Empirical influenza hospitalization underprediction case"
)
VALID_STATUSES = {"present", "missing", "insufficient"}
VALID_EDGE_TYPE = "LEADING_INDICATOR_FOR"

REQUIRED_COLUMNS = [
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

REQUIRED_VALUES = [
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
    "threshold",
    "paired_week_count",
    "minimum_paired_weeks",
    "evidence_sentence",
    "limitation",
]

# Relationships are deleted first. Plain DELETE is intentionally used for
# nodes: an unexpected unmarked relationship blocks cleanup instead of being
# removed implicitly, preserving the pipeline boundary.
DELETE_RELATIONSHIPS_QUERY = """
MATCH ()-[relationship]-()
WHERE relationship.pipeline = $pipeline
DELETE relationship
"""

DELETE_NODES_QUERY = """
MATCH (node)
WHERE node.pipeline = $pipeline
DELETE node
"""

UPSERT_EVIDENCE_QUERY = """
UNWIND $rows AS row
MERGE (failure:FailureCase {id: row.case_id})
ON CREATE SET failure.name = row.failure_case_name,
    failure.pipeline = $pipeline
MERGE (candidate:CandidateDriver {id: row.candidate_id})
ON CREATE SET candidate.name = row.candidate_name,
    candidate.pipeline = $pipeline
MERGE (target:Signal {id: row.target_signal_id})
ON CREATE SET target.name = row.target_signal_name,
    target.pipeline = $pipeline,
    target.role = 'target'
MERGE (evidence:EvidenceClaim {id: row.evidence_claim_id})
ON CREATE SET evidence.pipeline = $pipeline
SET evidence.status = row.status,
    evidence.edge_type = row.edge_type,
    evidence.score = row.score,
    evidence.threshold = row.threshold,
    evidence.lag_weeks = row.lag_weeks,
    evidence.paired_week_count = row.paired_week_count,
    evidence.minimum_paired_weeks = row.minimum_paired_weeks,
    evidence.method = row.method,
    evidence.source_dataset = row.source_dataset,
    evidence.region = row.region,
    evidence.time_window_start = row.time_window_start,
    evidence.time_window_end = row.time_window_end,
    evidence.evidence_sentence = row.evidence_sentence,
    evidence.limitation = row.limitation
MERGE (failure)-[has_candidate:HAS_CANDIDATE {
    pipeline: $pipeline
}]->(candidate)
MERGE (failure)-[has_target:HAS_TARGET {
    pipeline: $pipeline
}]->(target)
MERGE (candidate)-[has_evidence:HAS_EVIDENCE {
    pipeline: $pipeline
}]->(evidence)
MERGE (evidence)-[supports_target:SUPPORTS_TARGET {
    pipeline: $pipeline
}]->(target)
"""

UPSERT_POSITIVE_EDGE_QUERY = """
UNWIND $rows AS row
MATCH (candidate:CandidateDriver {
    id: row.candidate_id
})
MATCH (target:Signal {id: row.target_signal_id})
MERGE (candidate)-[leading:LEADING_INDICATOR_FOR {
    evidence_claim_id: row.evidence_claim_id,
    pipeline: $pipeline
}]->(target)
SET leading.score = row.score,
    leading.threshold = row.threshold,
    leading.lag_weeks = row.lag_weeks,
    leading.paired_week_count = row.paired_week_count,
    leading.minimum_paired_weeks = row.minimum_paired_weeks,
    leading.method = row.method,
    leading.status = row.status
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Replace only the empirical influenza Neo4j subgraph and load "
            "auditable empirical EvidenceClaims."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
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


def build_evidence_claim_id(row: dict[str, str]) -> str:
    fields = [
        row["case_id"],
        row["candidate_id"],
        row["target_signal_id"],
        row["edge_type"],
    ]
    if any(not value for value in fields):
        raise ValueError(
            "Cannot build evidence_claim_id from blank identity fields."
        )
    return "empirical_claim__" + "__".join(fields)


def parse_optional_float(
    value: str,
    field: str,
    line_number: int,
) -> float | None:
    text = value.strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError as exc:
        raise ValueError(
            f"Row {line_number}: {field} must be numeric; got {value!r}."
        ) from exc
    if not math.isfinite(number):
        raise ValueError(
            f"Row {line_number}: {field} must be finite; got {value!r}."
        )
    return number


def parse_optional_int(
    value: str,
    field: str,
    line_number: int,
) -> int | None:
    text = value.strip()
    if not text:
        return None
    if re.fullmatch(r"[+-]?\d+", text) is None:
        raise ValueError(
            f"Row {line_number}: {field} must be an integer; got {value!r}."
        )
    return int(text)


def transform_claim(
    raw_row: dict[str, str | None],
    line_number: int,
) -> dict[str, Any]:
    row = {
        column: (raw_row.get(column) or "").strip()
        for column in REQUIRED_COLUMNS
    }
    empty = [column for column in REQUIRED_VALUES if not row[column]]
    if empty:
        raise ValueError(
            f"Row {line_number}: required values are empty: "
            + ", ".join(empty)
        )
    if row["status"] not in VALID_STATUSES:
        raise ValueError(
            f"Row {line_number}: invalid status {row['status']!r}; "
            f"expected one of {sorted(VALID_STATUSES)}."
        )
    if row["edge_type"] != VALID_EDGE_TYPE:
        raise ValueError(
            f"Row {line_number}: invalid edge_type {row['edge_type']!r}; "
            f"expected {VALID_EDGE_TYPE!r}."
        )

    score = parse_optional_float(row["score"], "score", line_number)
    threshold = parse_optional_float(
        row["threshold"],
        "threshold",
        line_number,
    )
    lag_weeks = parse_optional_int(
        row["lag_weeks"],
        "lag_weeks",
        line_number,
    )
    paired_week_count = parse_optional_int(
        row["paired_week_count"],
        "paired_week_count",
        line_number,
    )
    minimum_paired_weeks = parse_optional_int(
        row["minimum_paired_weeks"],
        "minimum_paired_weeks",
        line_number,
    )
    if threshold is None:
        raise ValueError(f"Row {line_number}: threshold must be provided.")
    if paired_week_count is None:
        raise ValueError(
            f"Row {line_number}: paired_week_count must be provided."
        )
    if minimum_paired_weeks is None:
        raise ValueError(
            f"Row {line_number}: minimum_paired_weeks must be provided."
        )

    transformed: dict[str, Any] = {
        "case_id": row["case_id"],
        "failure_case_name": FAILURE_CASE_NAME,
        "candidate_id": row["candidate_id"],
        "candidate_name": row["candidate_name"],
        "target_signal_id": row["target_signal_id"],
        "target_signal_name": row["target_signal_name"],
        "evidence_claim_id": build_evidence_claim_id(row),
        "edge_type": row["edge_type"],
        "status": row["status"],
        "score": score,
        "threshold": threshold,
        "lag_weeks": lag_weeks,
        "paired_week_count": paired_week_count,
        "minimum_paired_weeks": minimum_paired_weeks,
        "method": row["method"],
        "source_dataset": row["source_dataset"],
        "region": row["region"],
        "time_window_start": row["time_window_start"],
        "time_window_end": row["time_window_end"],
        "evidence_sentence": row["evidence_sentence"],
        "limitation": row["limitation"],
        "pipeline": PIPELINE,
        "creates_positive_edge": row["status"] == "present",
    }
    return transformed


def read_claims(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Empirical claim file not found: {path}")
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    with path.open("r", newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        fieldnames = reader.fieldnames or []
        missing = [
            column for column in REQUIRED_COLUMNS if column not in fieldnames
        ]
        if missing:
            raise ValueError(
                "Empirical claim CSV is missing required columns: "
                + ", ".join(missing)
            )
        for raw_row in reader:
            transformed = transform_claim(raw_row, reader.line_num)
            evidence_id = transformed["evidence_claim_id"]
            if evidence_id in seen_ids:
                raise ValueError(
                    f"Row {reader.line_num}: duplicate evidence_claim_id "
                    f"{evidence_id!r}."
                )
            seen_ids.add(evidence_id)
            rows.append(transformed)
    if not rows:
        raise ValueError("Empirical claim CSV contains no rows.")
    return rows


def execute_load_transaction(
    transaction: Any,
    rows: list[dict[str, Any]],
) -> None:
    transaction.run(
        DELETE_RELATIONSHIPS_QUERY,
        pipeline=PIPELINE,
    ).consume()
    transaction.run(
        DELETE_NODES_QUERY,
        pipeline=PIPELINE,
    ).consume()
    transaction.run(
        UPSERT_EVIDENCE_QUERY,
        rows=rows,
        pipeline=PIPELINE,
    ).consume()
    present_rows = [
        row for row in rows if bool(row["creates_positive_edge"])
    ]
    if present_rows:
        transaction.run(
            UPSERT_POSITIVE_EDGE_QUERY,
            rows=present_rows,
            pipeline=PIPELINE,
        ).consume()


def load_claims(
    rows: list[dict[str, Any]],
    uri: str,
    username: str,
    password: str,
    database: str | None,
) -> None:
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError(
            "The neo4j Python driver is required to load the empirical KG."
        ) from exc

    driver = GraphDatabase.driver(uri, auth=(username, password))
    try:
        driver.verify_connectivity()
        session_options = {"database": database} if database else {}
        with driver.session(**session_options) as session:
            session.execute_write(execute_load_transaction, rows)
    finally:
        driver.close()


def print_summary(rows: list[dict[str, Any]]) -> None:
    print(f"Claims loaded: {len(rows)}")
    print(
        "Candidates loaded: "
        f"{len({row['candidate_id'] for row in rows})}"
    )
    print(
        "Target signals loaded: "
        f"{len({row['target_signal_id'] for row in rows})}"
    )
    print(f"Evidence claims loaded: {len(rows)}")
    print(
        "Positive typed edges created: "
        f"{sum(row['creates_positive_edge'] for row in rows)}"
    )


def main() -> int:
    args = parse_args()
    try:
        rows = read_claims(args.input)
        load_claims(
            rows,
            uri=args.uri,
            username=args.username,
            password=args.password,
            database=args.database,
        )
        print_summary(rows)
    except (csv.Error, FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        print(f"Empirical influenza KG load failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # Driver errors are imported lazily so tests have no Neo4j dependency.
        print(f"Empirical influenza KG load failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
