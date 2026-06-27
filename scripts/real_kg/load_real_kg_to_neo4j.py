"""Additively load auditable real-data evidence claims into Neo4j.

This loader is intentionally isolated from ``neo4j_loader.py`` because that
legacy simulated-benchmark loader clears the graph before loading. This script
uses only MERGE/SET operations and never deletes graph data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path("data/real_processed/real_evidence_claims.csv")
VALID_STATUSES = {"present", "missing", "insufficient_data"}
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
]

CONSTRAINT_QUERIES = [
    (
        "CREATE CONSTRAINT failure_case_id_unique IF NOT EXISTS "
        "FOR (node:FailureCase) REQUIRE node.id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT candidate_driver_id_unique IF NOT EXISTS "
        "FOR (node:CandidateDriver) REQUIRE node.id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT signal_id_unique IF NOT EXISTS "
        "FOR (node:Signal) REQUIRE node.id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT evidence_claim_id_unique IF NOT EXISTS "
        "FOR (node:EvidenceClaim) REQUIRE node.id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT dataset_id_unique IF NOT EXISTS "
        "FOR (node:Dataset) REQUIRE node.id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT region_id_unique IF NOT EXISTS "
        "FOR (node:Region) REQUIRE node.id IS UNIQUE"
    ),
    (
        "CREATE CONSTRAINT time_window_id_unique IF NOT EXISTS "
        "FOR (node:TimeWindow) REQUIRE node.id IS UNIQUE"
    ),
]

UPSERT_QUERY = """
UNWIND $rows AS row
MERGE (failure_case:FailureCase {id: row.case_id})
SET failure_case.name = row.case_name
MERGE (candidate:CandidateDriver {id: row.candidate_id})
SET candidate.name = row.candidate_name
MERGE (signal:Signal {id: row.target_signal_id})
SET signal.name = row.target_signal_name
MERGE (evidence:EvidenceClaim {id: row.evidence_claim_id})
SET evidence += row.evidence_properties
MERGE (dataset:Dataset {id: row.dataset_id})
SET dataset.name = row.source_dataset
MERGE (region:Region {id: row.region_id})
SET region.name = row.region
MERGE (time_window:TimeWindow {id: row.time_window_id})
SET time_window.start = row.time_window_start,
    time_window.end = row.time_window_end
MERGE (failure_case)-[:HAS_CANDIDATE]->(candidate)
MERGE (failure_case)-[:HAS_TARGET_SIGNAL]->(signal)
MERGE (candidate)-[:HAS_EVIDENCE]->(evidence)
MERGE (evidence)-[:SUPPORTS_TARGET]->(signal)
MERGE (evidence)-[:DERIVED_FROM]->(dataset)
MERGE (evidence)-[:OBSERVED_IN]->(region)
MERGE (evidence)-[:EVALUATED_DURING]->(time_window)
FOREACH (_ IN CASE WHEN row.status = 'present' THEN [1] ELSE [] END |
    MERGE (candidate)-[leading:LEADING_INDICATOR_FOR {
        evidence_id: row.evidence_claim_id
    }]->(signal)
    SET leading += row.leading_properties
)
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Additively load real-data EvidenceClaim rows and provenance into "
            "Neo4j without clearing existing graph data."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and display derived graph records without connecting.",
    )
    return parser.parse_args()


def safe_slug(value: str, max_length: int = 64) -> str:
    """Return a deterministic ASCII identifier component."""
    normalized = unicodedata.normalize("NFKD", value.strip())
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "_", ascii_value).strip("_")
    return (slug or "value")[:max_length].rstrip("_")


def stable_digest(*values: str) -> str:
    encoded = json.dumps(
        list(values),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


def derive_evidence_claim_id(row: dict[str, str]) -> str:
    values = (
        row["case_id"],
        row["candidate_id"],
        row["target_signal_id"],
        row["edge_type"],
    )
    readable = "_".join(safe_slug(value, 28) for value in values)
    return f"evidence_claim_{readable}_{stable_digest(*values)}"


def derive_time_window_id(row: dict[str, str]) -> str:
    values = (
        row["region"],
        row["time_window_start"],
        row["time_window_end"],
    )
    readable = "_".join(safe_slug(value, 32) for value in values)
    return f"time_window_{readable}_{stable_digest(*values)}"


def derive_named_id(prefix: str, value: str) -> str:
    return f"{prefix}_{safe_slug(value)}_{stable_digest(value)}"


def parse_optional_float(value: str, field: str, line_number: int) -> float | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        parsed = float(stripped)
    except ValueError as exc:
        raise ValueError(
            f"Row {line_number}: {field} must be numeric when provided; "
            f"got {value!r}."
        ) from exc
    if not math.isfinite(parsed):
        raise ValueError(
            f"Row {line_number}: {field} must be finite when provided; "
            f"got {value!r}."
        )
    return parsed


def parse_optional_int(value: str, field: str, line_number: int) -> int | None:
    stripped = value.strip()
    if not stripped:
        return None
    if re.fullmatch(r"[+-]?\d+", stripped) is None:
        raise ValueError(
            f"Row {line_number}: {field} must be an integer when provided; "
            f"got {value!r}."
        )
    return int(stripped)


def validate_and_transform_row(
    raw_row: dict[str, str | None],
    line_number: int,
) -> dict[str, Any]:
    row = {
        column: (raw_row.get(column) or "").strip()
        for column in REQUIRED_COLUMNS
    }

    empty_values = [column for column in REQUIRED_VALUES if not row[column]]
    if empty_values:
        raise ValueError(
            f"Row {line_number}: required values are empty: "
            + ", ".join(empty_values)
        )
    if row["status"] not in VALID_STATUSES:
        raise ValueError(
            f"Row {line_number}: invalid status {row['status']!r}; expected "
            f"one of {sorted(VALID_STATUSES)}."
        )
    if row["edge_type"] != VALID_EDGE_TYPE:
        raise ValueError(
            f"Row {line_number}: invalid edge_type {row['edge_type']!r}; "
            f"v1 supports only {VALID_EDGE_TYPE!r}."
        )

    lag_weeks = parse_optional_int(row["lag_weeks"], "lag_weeks", line_number)
    score = parse_optional_float(row["score"], "score", line_number)
    threshold = parse_optional_float(
        row["threshold"],
        "threshold",
        line_number,
    )
    evidence_claim_id = derive_evidence_claim_id(row)

    # EvidenceClaim nodes preserve the method, measurements, provenance, and
    # limitations needed to audit why a graph assertion was made.
    evidence_properties: dict[str, Any] = {
        "edge_type": row["edge_type"],
        "status": row["status"],
        "method": row["method"],
        "evidence_sentence": row["evidence_sentence"],
        "limitation": row["limitation"],
    }
    optional_properties = {
        "lag_weeks": lag_weeks,
        "score": score,
        "threshold": threshold,
    }
    evidence_properties.update(
        {
            key: value
            for key, value in optional_properties.items()
            if value is not None
        }
    )

    # The typed edge is a retrieval projection only for qualifying "present"
    # evidence. It makes graph traversal convenient; it does not prove that the
    # candidate causes the target signal.
    leading_properties: dict[str, Any] = {
        "evidence_id": evidence_claim_id,
        "method": row["method"],
        "status": row["status"],
    }
    leading_properties.update(
        {
            key: value
            for key, value in {"score": score, "lag_weeks": lag_weeks}.items()
            if value is not None
        }
    )

    return {
        "case_id": row["case_id"],
        # The v1 CSV has no separate case display-name column, so its stable ID
        # is retained as the auditable FailureCase name.
        "case_name": row["case_id"],
        "candidate_id": row["candidate_id"],
        "candidate_name": row["candidate_name"],
        "target_signal_id": row["target_signal_id"],
        "target_signal_name": row["target_signal_name"],
        "evidence_claim_id": evidence_claim_id,
        "status": row["status"],
        "source_dataset": row["source_dataset"],
        "dataset_id": derive_named_id("dataset", row["source_dataset"]),
        "region": row["region"],
        "region_id": derive_named_id("region", row["region"]),
        "time_window_id": derive_time_window_id(row),
        "time_window_start": row["time_window_start"],
        "time_window_end": row["time_window_end"],
        "evidence_properties": evidence_properties,
        "leading_properties": leading_properties,
    }


def read_and_validate_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"Input file not found: {path}")

    rows: list[dict[str, Any]] = []
    seen_claim_ids: dict[str, int] = {}
    with path.open("r", newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            raise ValueError("Input CSV has no header row.")

        missing_columns = [
            column for column in REQUIRED_COLUMNS if column not in reader.fieldnames
        ]
        if missing_columns:
            raise ValueError(
                "Input is missing required columns: "
                + ", ".join(missing_columns)
            )

        for raw_row in reader:
            line_number = reader.line_num
            transformed = validate_and_transform_row(raw_row, line_number)
            claim_id = transformed["evidence_claim_id"]
            if claim_id in seen_claim_ids:
                raise ValueError(
                    f"Row {line_number}: duplicate evidence_claim_id "
                    f"{claim_id!r}; first derived at row "
                    f"{seen_claim_ids[claim_id]}."
                )
            seen_claim_ids[claim_id] = line_number
            rows.append(transformed)

    return rows


def print_safety_warning() -> None:
    print(
        "WARNING: existing neo4j_loader.py is destructive and should not be "
        "used when preserving these additive real-data graph records."
    )


def print_dry_run(rows: list[dict[str, Any]], input_path: Path) -> None:
    print("Dry run: validated input without connecting to Neo4j.")
    print(f"Input: {input_path}")
    for index, row in enumerate(rows, start=1):
        preview = {
            "row": index,
            "evidence_claim_id": row["evidence_claim_id"],
            "dataset_id": row["dataset_id"],
            "region_id": row["region_id"],
            "time_window_id": row["time_window_id"],
            "status": row["status"],
            "typed_leading_indicator_edge": row["status"] == "present",
        }
        print(json.dumps(preview, sort_keys=True))


def print_counts(rows: list[dict[str, Any]], dry_run: bool) -> None:
    present_count = sum(row["status"] == "present" for row in rows)
    without_typed_edge_count = len(rows) - present_count
    suffix = " (validated; not written)" if dry_run else ""
    merge_note = " (would be MERGEd)" if dry_run else " (MERGE; idempotent)"
    print(f"Rows read: {len(rows)}")
    print(f"Evidence claims loaded: {len(rows)}{suffix}")
    print(f"Present typed edges created: {present_count}{merge_note}")
    print(
        "Missing/insufficient claims loaded without typed edges: "
        f"{without_typed_edge_count}{suffix}"
    )


def get_connection_settings() -> tuple[str, str, str, str]:
    values = {
        "NEO4J_URI": os.environ.get("NEO4J_URI", "").strip(),
        "NEO4J_USER": os.environ.get("NEO4J_USER", "").strip(),
        "NEO4J_PASSWORD": os.environ.get("NEO4J_PASSWORD", ""),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise ValueError(
            "Missing Neo4j connection environment variables: "
            + ", ".join(missing)
        )
    database = os.environ.get("NEO4J_DATABASE", "neo4j").strip() or "neo4j"
    return (
        values["NEO4J_URI"],
        values["NEO4J_USER"],
        values["NEO4J_PASSWORD"],
        database,
    )


def load_rows(rows: list[dict[str, Any]]) -> None:
    uri, user, password, database = get_connection_settings()
    try:
        from neo4j import GraphDatabase
    except ImportError as exc:
        raise RuntimeError(
            "The neo4j Python driver is required for a live load."
        ) from exc

    driver = GraphDatabase.driver(uri, auth=(user, password))
    try:
        driver.verify_connectivity()
        with driver.session(database=database) as session:
            for query in CONSTRAINT_QUERIES:
                session.run(query).consume()
            if rows:
                session.execute_write(
                    lambda transaction: transaction.run(
                        UPSERT_QUERY,
                        rows=rows,
                    ).consume()
                )
    finally:
        driver.close()


def main() -> int:
    args = parse_args()
    print_safety_warning()

    try:
        rows = read_and_validate_rows(args.input)
        if args.dry_run:
            print_dry_run(rows, args.input)
        else:
            load_rows(rows)
            print(f"Additive Neo4j load complete: {args.input}")
        print_counts(rows, args.dry_run)
    except (csv.Error, FileNotFoundError, OSError, RuntimeError, ValueError) as exc:
        print(f"Real KG load failed: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # Neo4j driver exceptions are imported lazily so --dry-run has no
        # driver dependency; report any live connection/query failure cleanly.
        print(f"Real KG load failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
