"""Build Text-RAG evidence cards from empirical influenza EvidenceClaims.

This parallel artifact builder preserves the facts and row order of the
empirical claim CSV. It does not add evidence, modify fixture artifacts, call
Neo4j, or call an LLM.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


DEFAULT_INPUT = Path(
    "data/real_processed/real_empirical_influenza_evidence_claims.csv"
)
DEFAULT_OUTPUT = Path(
    "data/real_processed/real_empirical_influenza_text_rag_corpus.json"
)

SOURCE_TYPE = "empirical_evidence_claim"
VALID_STATUSES = {"present", "missing", "insufficient"}

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

OUTPUT_FIELDS = [
    "chunk_id",
    "title",
    "text",
    "source_type",
    "case_id",
    "candidate_id",
    "target_signal_id",
    "edge_type",
    "status",
    "evidence_claim_id",
]

EVIDENCE_ID_FIELDS = [
    "case_id",
    "candidate_id",
    "target_signal_id",
    "edge_type",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build empirical influenza Text-RAG evidence-card chunks from "
            "the empirical EvidenceClaim CSV."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def clean_row(row: dict[str, str | None]) -> dict[str, str]:
    return {
        column: "" if row.get(column) is None else str(row[column]).strip()
        for column in REQUIRED_COLUMNS
    }


def load_claim_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Empirical claim file not found: {path}")
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
        rows = [clean_row(row) for row in reader]
    if not rows:
        raise ValueError("Empirical claim CSV contains no rows.")
    return rows


def build_evidence_claim_id(row: dict[str, str]) -> str:
    missing = [field for field in EVIDENCE_ID_FIELDS if not row[field]]
    if missing:
        raise ValueError(
            "Cannot build evidence_claim_id because these fields are blank: "
            + ", ".join(missing)
        )
    suffix = "__".join(row[field] for field in EVIDENCE_ID_FIELDS)
    return f"empirical_claim__{suffix}"


def build_chunk_id(evidence_claim_id: str) -> str:
    prefix = "empirical_claim__"
    if not evidence_claim_id.startswith(prefix):
        raise ValueError(
            f"Unexpected empirical evidence_claim_id: {evidence_claim_id}"
        )
    return "empirical_chunk__" + evidence_claim_id[len(prefix):]


def display_value(value: str) -> str:
    return value if value else "not available"


def build_status_statement(status: str) -> str:
    if status == "present":
        return "The empirical evidence threshold was met."
    if status == "missing":
        return (
            "The empirical evidence threshold was not met; this is not a "
            "positive evidence claim."
        )
    return (
        "Overlapping data were insufficient to evaluate the empirical "
        "evidence claim; this is not a positive evidence claim."
    )


def build_chunk(row: dict[str, str]) -> dict[str, str]:
    status = row["status"]
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status {status!r}. Expected one of: "
            + ", ".join(sorted(VALID_STATUSES))
        )
    evidence_claim_id = build_evidence_claim_id(row)
    text_lines = [
        f"Status: {status}.",
        build_status_statement(status),
        f"Case ID: {row['case_id']}.",
        f"Candidate: {row['candidate_name']} ({row['candidate_id']}).",
        (
            f"Target signal: {row['target_signal_name']} "
            f"({row['target_signal_id']})."
        ),
        f"Edge type: {row['edge_type']}.",
        f"Score: {display_value(row['score'])}.",
        f"Threshold: {display_value(row['threshold'])}.",
        f"Lag weeks: {display_value(row['lag_weeks'])}.",
        (
            "Paired week count: "
            f"{display_value(row['paired_week_count'])}."
        ),
        (
            "Minimum paired weeks: "
            f"{display_value(row['minimum_paired_weeks'])}."
        ),
        f"Method: {row['method']}.",
        f"Source dataset: {row['source_dataset']}.",
        f"Region: {row['region']}.",
        (
            f"Time window: {row['time_window_start']} through "
            f"{row['time_window_end']}."
        ),
        f"Evidence sentence: {row['evidence_sentence']}",
        f"Limitation: {row['limitation']}",
    ]
    return {
        "chunk_id": build_chunk_id(evidence_claim_id),
        "title": (
            f"{row['candidate_name']} - empirical {row['edge_type']} - "
            f"{row['target_signal_name']} ({status})"
        ),
        "text": "\n".join(text_lines),
        "source_type": SOURCE_TYPE,
        "case_id": row["case_id"],
        "candidate_id": row["candidate_id"],
        "target_signal_id": row["target_signal_id"],
        "edge_type": row["edge_type"],
        "status": status,
        "evidence_claim_id": evidence_claim_id,
    }


def build_corpus(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    chunks: list[dict[str, str]] = []
    seen_ids: set[str] = set()
    for row_number, row in enumerate(rows, start=2):
        try:
            chunk = build_chunk(row)
        except ValueError as exc:
            raise ValueError(f"CSV row {row_number}: {exc}") from exc
        evidence_claim_id = chunk["evidence_claim_id"]
        if evidence_claim_id in seen_ids:
            raise ValueError(
                f"Duplicate evidence_claim_id: {evidence_claim_id}"
            )
        seen_ids.add(evidence_claim_id)
        # Do not sort here: source CSV order is the canonical candidate order.
        chunks.append(chunk)
    return chunks


def write_corpus(path: Path, chunks: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump(chunks, output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")


def print_summary(
    input_path: Path,
    output_path: Path,
    chunk_count: int,
) -> None:
    print("Empirical influenza Text-RAG corpus built.")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Chunks written: {chunk_count}")


def main() -> int:
    args = parse_args()
    try:
        rows = load_claim_rows(args.input)
        chunks = build_corpus(rows)
        write_corpus(args.output, chunks)
        print_summary(args.input, args.output, len(chunks))
    except (csv.Error, FileNotFoundError, OSError, ValueError) as exc:
        print(
            f"Empirical Text-RAG corpus build failed: {exc}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
