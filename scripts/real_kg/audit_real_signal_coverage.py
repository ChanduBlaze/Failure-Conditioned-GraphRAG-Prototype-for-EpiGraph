"""Audit weekly coverage and target-candidate overlap for real signals.

This pre-evidence audit is read-only with respect to the KG. It determines
whether normalized candidate and target windows can support a conservative
lagged-correlation calculation.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path(
    "data/real_processed/real_influenza_normalized_signals.csv"
)
DEFAULT_COVERAGE_OUTPUT = Path(
    "data/real_processed/real_influenza_signal_coverage.csv"
)
DEFAULT_OVERLAP_OUTPUT = Path(
    "data/real_processed/real_influenza_signal_overlap.csv"
)
DEFAULT_MINIMUM_SHARED_WEEKS = 8
DEFAULT_MAX_LAG_WEEKS = 4

REQUIRED_INPUT_COLUMNS = [
    "case_id",
    "signal_id",
    "signal_name",
    "signal_role",
    "source_name",
    "region",
    "week",
    "normalized_value",
]

COVERAGE_COLUMNS = [
    "case_id",
    "signal_id",
    "signal_name",
    "signal_role",
    "source_name",
    "region",
    "week_count",
    "first_week",
    "last_week",
    "nonmissing_count",
    "notes",
]

OVERLAP_COLUMNS = [
    "case_id",
    "target_signal_id",
    "candidate_signal_id",
    "candidate_signal_name",
    "candidate_week_count",
    "target_week_count",
    "shared_week_count",
    "target_first_week",
    "target_last_week",
    "candidate_first_week",
    "candidate_last_week",
    "shared_first_week",
    "shared_last_week",
    "minimum_required_shared_weeks",
    "max_lag_weeks",
    "lagged_correlation_possible",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Audit normalized real influenza signal coverage before building "
            "empirical EvidenceClaims."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--coverage-output",
        type=Path,
        default=DEFAULT_COVERAGE_OUTPUT,
    )
    parser.add_argument(
        "--overlap-output",
        type=Path,
        default=DEFAULT_OVERLAP_OUTPUT,
    )
    parser.add_argument(
        "--minimum-required-shared-weeks",
        type=int,
        default=DEFAULT_MINIMUM_SHARED_WEEKS,
    )
    parser.add_argument(
        "--max-lag-weeks",
        type=int,
        default=DEFAULT_MAX_LAG_WEEKS,
    )
    return parser.parse_args()


def validate_args(
    minimum_required_shared_weeks: int,
    max_lag_weeks: int,
) -> None:
    if minimum_required_shared_weeks < 2:
        raise ValueError(
            "--minimum-required-shared-weeks must be at least 2."
        )
    if max_lag_weeks < 1:
        raise ValueError("--max-lag-weeks must be at least 1.")


def read_signal_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Normalized signal file not found: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as input_file:
        reader = csv.DictReader(input_file)
        if reader.fieldnames is None:
            raise ValueError(f"Normalized signal CSV has no header: {path}")
        missing = [
            column
            for column in REQUIRED_INPUT_COLUMNS
            if column not in reader.fieldnames
        ]
        if missing:
            raise ValueError(
                "Normalized signal CSV is missing required columns: "
                + ", ".join(missing)
            )
        rows = [
            {
                column: (row.get(column) or "").strip()
                for column in reader.fieldnames
            }
            for row in reader
        ]
    if not rows:
        raise ValueError("Normalized signal CSV contains no rows.")
    return rows


def parse_week(value: str) -> tuple[str, date]:
    text = value.strip().upper()
    if "-W" not in text:
        raise ValueError(f"Invalid week {value!r}; expected YYYY-Www.")
    year_text, week_text = text.split("-W", 1)
    try:
        year = int(year_text)
        week = int(week_text)
        monday = date.fromisocalendar(year, week, 1)
    except ValueError as exc:
        raise ValueError(
            f"Invalid week {value!r}; expected a valid ISO week."
        ) from exc
    return f"{year}-W{week:02d}", monday


def numeric_is_present(value: Any) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    if not text:
        return False
    try:
        number = float(text)
    except ValueError:
        return False
    return math.isfinite(number)


def collect_signal_groups(
    rows: list[dict[str, str]],
) -> dict[tuple[str, str, str], dict[str, Any]]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        case_id = row.get("case_id", "").strip()
        signal_id = row.get("signal_id", "").strip()
        region = row.get("region", "").strip()
        if not case_id or not signal_id or not region:
            raise ValueError(
                "Every normalized row needs case_id, signal_id, and region."
            )
        week, monday = parse_week(row.get("week", ""))
        key = (case_id, signal_id, region)
        group = groups.setdefault(
            key,
            {
                "case_id": case_id,
                "signal_id": signal_id,
                "signal_name": row.get("signal_name", "").strip(),
                "signal_role": row.get("signal_role", "").strip().lower(),
                "source_name": row.get("source_name", "").strip(),
                "region": region,
                "weeks": {},
                "row_count": 0,
            },
        )
        for field in ("signal_name", "signal_role", "source_name"):
            current = (
                row.get(field, "").strip().lower()
                if field == "signal_role"
                else row.get(field, "").strip()
            )
            if current != group[field]:
                raise ValueError(
                    f"Inconsistent {field} for signal {signal_id!r}."
                )
        group["row_count"] += 1
        week_entry = group["weeks"].setdefault(
            week,
            {"date": monday, "nonmissing": False},
        )
        if numeric_is_present(row.get("normalized_value")):
            week_entry["nonmissing"] = True
    return groups


def build_coverage_rows(
    groups: dict[tuple[str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for group in groups.values():
        weeks = sorted(group["weeks"])
        nonmissing_count = sum(
            bool(entry["nonmissing"])
            for entry in group["weeks"].values()
        )
        notes = "Weekly normalized signal coverage."
        duplicate_count = group["row_count"] - len(weeks)
        if duplicate_count:
            notes += f" {duplicate_count} duplicate weekly row(s) observed."
        if nonmissing_count < len(weeks):
            notes += (
                f" {len(weeks) - nonmissing_count} week(s) have no valid "
                "normalized value."
            )
        output.append(
            {
                "case_id": group["case_id"],
                "signal_id": group["signal_id"],
                "signal_name": group["signal_name"],
                "signal_role": group["signal_role"],
                "source_name": group["source_name"],
                "region": group["region"],
                "week_count": len(weeks),
                "first_week": weeks[0] if weeks else "",
                "last_week": weeks[-1] if weeks else "",
                "nonmissing_count": nonmissing_count,
                "notes": notes,
            }
        )
    output.sort(
        key=lambda row: (
            str(row["case_id"]),
            str(row["signal_role"]),
            str(row["signal_id"]),
            str(row["region"]),
        )
    )
    return output


def lag_pair_counts(
    candidate_dates: set[date],
    target_dates: set[date],
    max_lag_weeks: int,
) -> list[tuple[int, int]]:
    return [
        (
            lag,
            sum(
                candidate_date + timedelta(weeks=lag) in target_dates
                for candidate_date in candidate_dates
            ),
        )
        for lag in range(1, max_lag_weeks + 1)
    ]


def build_overlap_rows(
    groups: dict[tuple[str, str, str], dict[str, Any]],
    minimum_required_shared_weeks: int,
    max_lag_weeks: int,
) -> list[dict[str, Any]]:
    validate_args(minimum_required_shared_weeks, max_lag_weeks)
    by_case: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in groups.values():
        by_case[group["case_id"]].append(group)

    output: list[dict[str, Any]] = []
    for case_id in sorted(by_case):
        case_groups = by_case[case_id]
        targets = [
            group for group in case_groups if group["signal_role"] == "target"
        ]
        target_ids = {group["signal_id"] for group in targets}
        if not targets:
            raise ValueError(f"No target signal found for case {case_id!r}.")
        if len(target_ids) != 1:
            raise ValueError(
                f"Expected one target signal for case {case_id!r}, found "
                f"{sorted(target_ids)}."
            )
        candidates = [
            group
            for group in case_groups
            if group["signal_role"] == "candidate"
        ]
        if not candidates:
            raise ValueError(
                f"No candidate signals found for case {case_id!r}."
            )

        for candidate in candidates:
            matching_targets = [
                target
                for target in targets
                if target["region"] == candidate["region"]
            ]
            target = matching_targets[0] if matching_targets else targets[0]
            candidate_weeks = set(candidate["weeks"])
            target_weeks = set(target["weeks"])
            shared_weeks = sorted(candidate_weeks & target_weeks)
            candidate_dates = {
                entry["date"] for entry in candidate["weeks"].values()
            }
            target_dates = {
                entry["date"] for entry in target["weeks"].values()
            }
            pair_counts = lag_pair_counts(
                candidate_dates,
                target_dates,
                max_lag_weeks,
            )
            best_lag, best_count = max(
                pair_counts,
                key=lambda item: (item[1], -item[0]),
            )
            conservative_required = (
                minimum_required_shared_weeks + max_lag_weeks
            )
            enough_shared = len(shared_weeks) >= conservative_required
            enough_lagged_pairs = best_count >= minimum_required_shared_weeks
            possible = enough_shared and enough_lagged_pairs

            if not shared_weeks:
                notes = "Blocked: candidate and target have no shared weeks."
            elif not enough_shared:
                notes = (
                    f"Blocked: {len(shared_weeks)} shared week(s) is below "
                    f"the conservative requirement of "
                    f"{conservative_required}."
                )
            elif not enough_lagged_pairs:
                notes = (
                    "Blocked: no tested lag retains "
                    f"{minimum_required_shared_weeks} paired weeks; best was "
                    f"{best_count} at lag {best_lag}."
                )
            else:
                notes = (
                    f"Eligible: {best_count} paired weeks at lag {best_lag}."
                )

            output.append(
                {
                    "case_id": case_id,
                    "target_signal_id": target["signal_id"],
                    "candidate_signal_id": candidate["signal_id"],
                    "candidate_signal_name": candidate["signal_name"],
                    "candidate_week_count": len(candidate_weeks),
                    "target_week_count": len(target_weeks),
                    "shared_week_count": len(shared_weeks),
                    "target_first_week": (
                        min(target_weeks) if target_weeks else ""
                    ),
                    "target_last_week": (
                        max(target_weeks) if target_weeks else ""
                    ),
                    "candidate_first_week": (
                        min(candidate_weeks) if candidate_weeks else ""
                    ),
                    "candidate_last_week": (
                        max(candidate_weeks) if candidate_weeks else ""
                    ),
                    "shared_first_week": (
                        shared_weeks[0] if shared_weeks else ""
                    ),
                    "shared_last_week": (
                        shared_weeks[-1] if shared_weeks else ""
                    ),
                    "minimum_required_shared_weeks": (
                        minimum_required_shared_weeks
                    ),
                    "max_lag_weeks": max_lag_weeks,
                    "lagged_correlation_possible": possible,
                    "notes": notes,
                }
            )
    output.sort(
        key=lambda row: (
            str(row["case_id"]),
            str(row["candidate_signal_id"]),
        )
    )
    return output


def audit_rows(
    rows: list[dict[str, str]],
    minimum_required_shared_weeks: int,
    max_lag_weeks: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups = collect_signal_groups(rows)
    coverage = build_coverage_rows(groups)
    overlap = build_overlap_rows(
        groups,
        minimum_required_shared_weeks,
        max_lag_weeks,
    )
    return coverage, overlap


def write_csv(
    path: Path,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=columns,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def print_summary(
    coverage: list[dict[str, Any]],
    overlap: list[dict[str, Any]],
    coverage_output: Path,
    overlap_output: Path,
) -> None:
    eligible = sum(
        bool(row["lagged_correlation_possible"]) for row in overlap
    )
    print(f"Signals audited: {len(coverage)}")
    print(f"Candidate-target pairs audited: {len(overlap)}")
    print(f"Pairs eligible for lagged correlation: {eligible}")
    print(f"Pairs blocked: {len(overlap) - eligible}")
    print(f"Coverage output: {coverage_output}")
    print(f"Overlap output: {overlap_output}")


def main() -> int:
    args = parse_args()
    try:
        validate_args(
            args.minimum_required_shared_weeks,
            args.max_lag_weeks,
        )
        rows = read_signal_rows(args.input)
        coverage, overlap = audit_rows(
            rows,
            args.minimum_required_shared_weeks,
            args.max_lag_weeks,
        )
        write_csv(args.coverage_output, COVERAGE_COLUMNS, coverage)
        write_csv(args.overlap_output, OVERLAP_COLUMNS, overlap)
        print_summary(
            coverage,
            overlap,
            args.coverage_output,
            args.overlap_output,
        )
    except (csv.Error, FileNotFoundError, OSError, ValueError) as exc:
        print(f"Real signal coverage audit failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
