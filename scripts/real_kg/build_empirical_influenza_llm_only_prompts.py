"""Build leakage-controlled empirical influenza LLM-only prompts.

The output is intended for manual or external use. This script never calls an
LLM and includes no empirical evidence measurements in prompt text.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_CLAIMS = Path(
    "data/real_processed/real_empirical_influenza_evidence_claims.csv"
)
DEFAULT_OUTPUT = Path(
    "evals/results_real/real_empirical_influenza_llm_only_prompts.json"
)
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

RESTRICTED_PROMPT_TERMS = [
    "score",
    "threshold",
    "lag",
    "paired week",
    "paired_week",
    "source dataset",
    "source_dataset",
    "evidence sentence",
    "evidence_sentence",
    "text-rag",
    "graphrag",
    "graph context",
]

PROMPT_TEMPLATE = (
    "Failure case: influenza hospitalization forecast underprediction.\n"
    "Target signal: U.S. influenza hospitalization rate from FluSurv-NET.\n"
    "Candidate signal: {candidate_name}.\n"
    "Question: Based only on general epidemiological reasoning, assess "
    "whether this candidate should be treated as a LEADING_INDICATOR_FOR "
    "the target signal. Explain your reasoning and state whether you would "
    "treat the relationship as present, missing, or insufficient."
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build empirical influenza LLM-only prompts without evidence "
            "scores, lags, thresholds, provenance, or retrieval context."
        )
    )
    parser.add_argument("--claims", type=Path, default=DEFAULT_CLAIMS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def read_claims(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Empirical claims file not found: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        fieldnames = reader.fieldnames or []
        missing = [
            column for column in REQUIRED_COLUMNS if column not in fieldnames
        ]
        if missing:
            raise ValueError(
                "Empirical claims CSV is missing required columns: "
                + ", ".join(missing)
            )
        rows = [
            {
                column: (row.get(column) or "").strip()
                for column in REQUIRED_COLUMNS
            }
            for row in reader
        ]
    if not rows:
        raise ValueError("Empirical claims CSV contains no rows.")
    return rows


def validate_prompt(
    prompt: str,
    claim: dict[str, str],
) -> None:
    lowered = prompt.lower()
    leaked_terms = [
        term for term in RESTRICTED_PROMPT_TERMS if term in lowered
    ]
    restricted_values = [
        claim["case_id"],
        claim["candidate_id"],
        claim["target_signal_id"],
        claim["score"],
        claim["threshold"],
        claim["lag_weeks"],
        claim["paired_week_count"],
        claim["source_dataset"],
        claim["evidence_sentence"],
    ]
    leaked_values = [
        value
        for value in restricted_values
        if value and value.lower() in lowered
    ]
    if leaked_terms or leaked_values:
        raise ValueError(
            "Generated prompt leaks restricted empirical evidence: "
            + ", ".join([*leaked_terms, *leaked_values])
        )


def build_prompts(
    claims: list[dict[str, str]],
) -> list[dict[str, str]]:
    prompts: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row_number, claim in enumerate(claims, start=2):
        status = claim.get("status", "")
        if status not in VALID_STATUSES:
            raise ValueError(
                f"CSV row {row_number}: invalid status {status!r}."
            )
        required_identity = [
            "case_id",
            "candidate_id",
            "candidate_name",
            "target_signal_id",
            "target_signal_name",
            "edge_type",
        ]
        missing = [
            field for field in required_identity if not claim.get(field)
        ]
        if missing:
            raise ValueError(
                f"CSV row {row_number}: blank prompt metadata: "
                + ", ".join(missing)
            )
        key = (claim["case_id"], claim["candidate_id"])
        if key in seen:
            raise ValueError(
                f"CSV row {row_number}: duplicate case/candidate prompt."
            )
        seen.add(key)

        prompt = PROMPT_TEMPLATE.format(
            candidate_name=claim["candidate_name"]
        )
        validate_prompt(prompt, claim)
        prompts.append(
            {
                "case_id": claim["case_id"],
                "candidate_id": claim["candidate_id"],
                "candidate_name": claim["candidate_name"],
                "target_signal_id": claim["target_signal_id"],
                "target_signal_name": claim["target_signal_name"],
                "expected_status": status,
                "expected_edge_type": claim["edge_type"],
                "prompt": prompt,
            }
        )
    return prompts


def write_prompts(path: Path, prompts: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(prompts, output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")


def main() -> int:
    args = parse_args()
    try:
        claims = read_claims(args.claims)
        prompts = build_prompts(claims)
        write_prompts(args.output, prompts)
    except (csv.Error, FileNotFoundError, OSError, ValueError) as exc:
        print(
            f"Empirical LLM-only prompt build failed: {exc}",
            file=sys.stderr,
        )
        return 1
    print(f"Prompts written: {len(prompts)}")
    print(f"Output path: {args.output}")
    print("No LLM was called.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
