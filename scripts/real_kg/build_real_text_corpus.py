"""Build a deterministic Text-RAG corpus from canonical EvidenceClaims.

The real graph loader, Text-RAG corpus, and evaluation answer key should derive
from the same canonical evidence-claim CSV. This script creates the textual
representation without adding or removing facts, preserving information parity
between graph and text retrieval experiments.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


DEFAULT_INPUT = Path("data/real_processed/real_evidence_claims.csv")
DEFAULT_OUTPUT = Path("data/real_processed/real_text_rag_corpus.json")

SOURCE_TYPE = "real_evidence_claim"
VALID_STATUSES = {"present", "missing", "insufficient_data"}

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

EVIDENCE_ID_FIELDS = [
    "case_id",
    "candidate_id",
    "target_signal_id",
    "edge_type",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a real Text-RAG corpus from the canonical real evidence "
            "claim CSV."
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
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    with path.open("r", newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        fieldnames = reader.fieldnames or []
        missing_columns = [
            column for column in REQUIRED_COLUMNS if column not in fieldnames
        ]
        if missing_columns:
            raise ValueError(
                "Input is missing required columns: "
                + ", ".join(missing_columns)
            )

        return [clean_row(row) for row in reader]


def build_evidence_claim_id(row: dict[str, str]) -> str:
    missing_id_values = [
        field for field in EVIDENCE_ID_FIELDS if not row[field]
    ]
    if missing_id_values:
        raise ValueError(
            "Cannot build evidence_claim_id because these fields are blank: "
            + ", ".join(missing_id_values)
        )

    suffix = "__".join(row[field] for field in EVIDENCE_ID_FIELDS)
    return f"real_claim__{suffix}"


def build_chunk_id(evidence_claim_id: str) -> str:
    prefix = "real_claim__"
    if not evidence_claim_id.startswith(prefix):
        raise ValueError(
            f"Unexpected evidence_claim_id format: {evidence_claim_id}"
        )
    return "real_chunk__" + evidence_claim_id[len(prefix):]


def display_value(value: str) -> str:
    return value if value else "not available"


def build_status_statement(row: dict[str, str]) -> str:
    candidate_name = row["candidate_name"]
    target_name = row["target_signal_name"]
    edge_type = row["edge_type"]

    if row["status"] == "present":
        return (
            f"{candidate_name} has evidence for {edge_type} with respect to "
            f"{target_name}."
        )
    if row["status"] == "missing":
        return (
            f"The evidence threshold was not met for {candidate_name} to have "
            f"{edge_type} evidence with respect to {target_name}. This is not "
            "a positive evidence claim."
        )
    return (
        f"The {edge_type} relationship between {candidate_name} and "
        f"{target_name} could not be assessed due to insufficient data. This "
        "is not a positive evidence claim."
    )


def build_chunk(row: dict[str, str]) -> dict[str, str]:
    status = row["status"]
    if status not in VALID_STATUSES:
        raise ValueError(
            f"Invalid status '{status}'. Expected one of: "
            + ", ".join(sorted(VALID_STATUSES))
        )

    evidence_claim_id = build_evidence_claim_id(row)
    text_lines = [
        f"Status: {status}.",
        build_status_statement(row),
        f"Candidate: {row['candidate_name']} ({row['candidate_id']}).",
        (
            f"Target signal: {row['target_signal_name']} "
            f"({row['target_signal_id']})."
        ),
        f"Edge type: {row['edge_type']}.",
        f"Region: {row['region']}.",
        (
            f"Time window: {row['time_window_start']} through "
            f"{row['time_window_end']}."
        ),
        f"Lag weeks: {display_value(row['lag_weeks'])}.",
        f"Score: {display_value(row['score'])}.",
        f"Threshold: {display_value(row['threshold'])}.",
        f"Method: {row['method']}.",
        f"Source dataset: {row['source_dataset']}.",
        f"Evidence sentence: {row['evidence_sentence']}",
        f"Limitation: {row['limitation']}",
    ]

    return {
        "chunk_id": build_chunk_id(evidence_claim_id),
        "title": (
            f"{row['candidate_name']} - {row['edge_type']} - "
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
    chunks = []
    seen_evidence_claim_ids = set()

    for row_number, row in enumerate(rows, start=2):
        try:
            chunk = build_chunk(row)
        except ValueError as exc:
            raise ValueError(f"CSV row {row_number}: {exc}") from exc

        evidence_claim_id = chunk["evidence_claim_id"]
        if evidence_claim_id in seen_evidence_claim_ids:
            raise ValueError(
                f"Duplicate evidence_claim_id: {evidence_claim_id}"
            )

        seen_evidence_claim_ids.add(evidence_claim_id)
        chunks.append(chunk)

    return sorted(chunks, key=lambda chunk: chunk["chunk_id"])


def write_corpus(path: Path, chunks: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as output_file:
        json.dump(
            chunks,
            output_file,
            indent=2,
            ensure_ascii=False,
        )
        output_file.write("\n")


def print_summary(
    input_path: Path,
    output_path: Path,
    chunk_count: int,
) -> None:
    print("Real Text-RAG corpus built.")
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
    except (FileNotFoundError, OSError, ValueError, csv.Error) as exc:
        print(f"Real Text-RAG corpus build failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
