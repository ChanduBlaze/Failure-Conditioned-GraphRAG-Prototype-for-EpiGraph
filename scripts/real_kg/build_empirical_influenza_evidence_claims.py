"""Build empirical influenza EvidenceClaims from normalized real signals.

This standard-library-only step scans lagged Pearson correlations and writes
auditable claim and lag-scan CSVs. It does not create graph edges, load Neo4j,
call an LLM, or modify the fixture-based evidence claims.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any


DEFAULT_INPUT = Path(
    "data/real_processed/real_influenza_normalized_signals.csv"
)
DEFAULT_CLAIMS_OUTPUT = Path(
    "data/real_processed/real_empirical_influenza_evidence_claims.csv"
)
DEFAULT_LAG_SCAN_OUTPUT = Path(
    "data/real_processed/real_empirical_influenza_lag_scan.csv"
)
DEFAULT_THRESHOLD = 0.60
DEFAULT_MINIMUM_PAIRED_WEEKS = 8
DEFAULT_MAX_LAG_WEEKS = 4
DEFAULT_MINIMUM_LEAD_WEEKS = 1

CASE_ID = "real_us_flu_empirical_multicandidate_001"
TARGET_SIGNAL_ID = (
    "real_signal_us_influenza_hospitalization_rate_flusurv"
)
EDGE_TYPE = "LEADING_INDICATOR_FOR"
METHOD = "lagged_pearson_correlation_empirical_v1"
LIMITATION = (
    "Empirical screening evidence only; not causal proof. Result depends on "
    "source coverage, reporting lag, normalization, aggregation, lag window, "
    "threshold, and data quality. Lag 0 was retained only as a "
    "concurrent-association diagnostic."
)

CANDIDATE_IDS = [
    "real_signal_influenza_a_wastewater_concentration",
    "real_signal_outpatient_ili_activity",
    "real_signal_influenza_test_positivity",
]

REQUIRED_INPUT_COLUMNS = [
    "case_id",
    "signal_id",
    "signal_name",
    "signal_role",
    "source_dataset",
    "region",
    "week",
    "normalized_value",
]

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

LAG_SCAN_COLUMNS = [
    "case_id",
    "candidate_id",
    "candidate_name",
    "target_signal_id",
    "target_signal_name",
    "edge_type",
    "lag_weeks",
    "paired_week_count",
    "pearson_correlation",
    "minimum_paired_weeks",
    "eligible",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build empirical influenza EvidenceClaims and a transparent "
            "lag-correlation scan from normalized real signals."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument(
        "--claims-output",
        type=Path,
        default=DEFAULT_CLAIMS_OUTPUT,
    )
    parser.add_argument(
        "--lag-scan-output",
        type=Path,
        default=DEFAULT_LAG_SCAN_OUTPUT,
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
    )
    parser.add_argument(
        "--minimum-paired-weeks",
        type=int,
        default=DEFAULT_MINIMUM_PAIRED_WEEKS,
    )
    parser.add_argument(
        "--max-lag-weeks",
        type=int,
        default=DEFAULT_MAX_LAG_WEEKS,
    )
    parser.add_argument(
        "--minimum-lead-weeks",
        type=int,
        default=DEFAULT_MINIMUM_LEAD_WEEKS,
        help=(
            "Smallest positive lag eligible for LEADING_INDICATOR_FOR "
            "best-lag selection."
        ),
    )
    return parser.parse_args()


def validate_options(
    threshold: float,
    minimum_paired_weeks: int,
    max_lag_weeks: int,
    minimum_lead_weeks: int = DEFAULT_MINIMUM_LEAD_WEEKS,
) -> None:
    if not math.isfinite(threshold):
        raise ValueError("--threshold must be a finite number.")
    if minimum_paired_weeks < 2:
        raise ValueError("--minimum-paired-weeks must be at least 2.")
    if max_lag_weeks < 0:
        raise ValueError("--max-lag-weeks must be zero or greater.")
    if minimum_lead_weeks < 1:
        raise ValueError("--minimum-lead-weeks must be at least 1.")


def parse_week(value: str) -> tuple[str, date]:
    text = str(value).strip().upper()
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


def date_to_week(value: date) -> str:
    iso_year, iso_week, _weekday = value.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def parse_normalized_value(value: str, signal_id: str, week: str) -> float:
    text = str(value).strip()
    if not text:
        raise ValueError(
            f"Missing normalized_value for signal {signal_id!r} at {week}."
        )
    try:
        number = float(text)
    except ValueError as exc:
        raise ValueError(
            f"Non-numeric normalized_value {value!r} for signal "
            f"{signal_id!r} at {week}."
        ) from exc
    if not math.isfinite(number):
        raise ValueError(
            f"Non-finite normalized_value for signal {signal_id!r} "
            f"at {week}."
        )
    return number


def read_normalized_rows(path: Path) -> list[dict[str, str]]:
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


def collect_signals(
    rows: list[dict[str, str]],
) -> dict[str, dict[str, Any]]:
    wanted_ids = {TARGET_SIGNAL_ID, *CANDIDATE_IDS}
    signals: dict[str, dict[str, Any]] = {}
    for row in rows:
        signal_id = row.get("signal_id", "").strip()
        if signal_id not in wanted_ids:
            continue
        case_id = row.get("case_id", "").strip()
        if case_id != CASE_ID:
            continue
        week, monday = parse_week(row.get("week", ""))
        value = parse_normalized_value(
            row.get("normalized_value", ""),
            signal_id,
            week,
        )
        group = signals.setdefault(
            signal_id,
            {
                "signal_id": signal_id,
                "signal_name": row.get("signal_name", "").strip(),
                "signal_role": row.get("signal_role", "").strip().lower(),
                "source_datasets": [],
                "regions": [],
                "values": {},
            },
        )
        for field in ("signal_name", "signal_role"):
            current = (
                row.get(field, "").strip().lower()
                if field == "signal_role"
                else row.get(field, "").strip()
            )
            if current != group[field]:
                raise ValueError(
                    f"Inconsistent {field} for signal {signal_id!r}."
                )
        if monday in group["values"]:
            raise ValueError(
                f"Duplicate week {week} for signal {signal_id!r}."
            )
        group["values"][monday] = value
        for source_field, collection in (
            ("source_dataset", group["source_datasets"]),
            ("region", group["regions"]),
        ):
            item = row.get(source_field, "").strip()
            if item and item not in collection:
                collection.append(item)

    required_ids = [TARGET_SIGNAL_ID, *CANDIDATE_IDS]
    missing_ids = [
        signal_id for signal_id in required_ids if signal_id not in signals
    ]
    if missing_ids:
        raise ValueError(
            "Normalized signal CSV is missing required signal_id values: "
            + ", ".join(missing_ids)
        )
    if signals[TARGET_SIGNAL_ID]["signal_role"] != "target":
        raise ValueError(
            f"Signal {TARGET_SIGNAL_ID!r} must have signal_role 'target'."
        )
    for candidate_id in CANDIDATE_IDS:
        if signals[candidate_id]["signal_role"] != "candidate":
            raise ValueError(
                f"Signal {candidate_id!r} must have "
                "signal_role 'candidate'."
            )
    return signals


def pearson_correlation(
    first: list[float],
    second: list[float],
) -> float | None:
    if len(first) != len(second):
        raise ValueError("Pearson inputs must have the same length.")
    if len(first) < 2:
        return None
    first_mean = sum(first) / len(first)
    second_mean = sum(second) / len(second)
    first_deltas = [value - first_mean for value in first]
    second_deltas = [value - second_mean for value in second]
    numerator = sum(
        first_delta * second_delta
        for first_delta, second_delta in zip(
            first_deltas,
            second_deltas,
        )
    )
    first_sum_squares = sum(value * value for value in first_deltas)
    second_sum_squares = sum(value * value for value in second_deltas)
    denominator = math.sqrt(first_sum_squares * second_sum_squares)
    if math.isclose(denominator, 0.0):
        return None
    return numerator / denominator


def compute_lag_scan(
    candidate_values: dict[date, float],
    target_values: dict[date, float],
    minimum_paired_weeks: int,
    max_lag_weeks: int,
    minimum_lead_weeks: int = DEFAULT_MINIMUM_LEAD_WEEKS,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for lag_weeks in range(max_lag_weeks + 1):
        paired = [
            (candidate_value, target_values[candidate_week + timedelta(
                weeks=lag_weeks
            )])
            for candidate_week, candidate_value in sorted(
                candidate_values.items()
            )
            if candidate_week + timedelta(weeks=lag_weeks) in target_values
        ]
        correlation = pearson_correlation(
            [pair[0] for pair in paired],
            [pair[1] for pair in paired],
        )
        enough_pairs = len(paired) >= minimum_paired_weeks
        eligible = enough_pairs and correlation is not None
        if not enough_pairs:
            notes = (
                f"Below minimum paired weeks ({len(paired)} < "
                f"{minimum_paired_weeks})."
            )
        elif correlation is None:
            notes = (
                "Pearson correlation is undefined because at least one "
                "paired series has no variance."
            )
        elif lag_weeks < minimum_lead_weeks:
            notes = (
                "Eligible diagnostic lag but excluded from "
                "LEADING_INDICATOR_FOR best-lag selection because "
                f"minimum_lead_weeks = {minimum_lead_weeks}."
            )
        else:
            notes = "Eligible for leading-indicator best-lag selection."
        results.append(
            {
                "lag_weeks": lag_weeks,
                "paired_week_count": len(paired),
                "pearson_correlation": correlation,
                "eligible": eligible,
                "notes": notes,
            }
        )
    return results


def select_best_lag(
    lag_results: list[dict[str, Any]],
    minimum_lead_weeks: int = DEFAULT_MINIMUM_LEAD_WEEKS,
) -> dict[str, Any] | None:
    eligible = [
        result
        for result in lag_results
        if result["eligible"]
        and int(result["lag_weeks"]) >= minimum_lead_weeks
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda result: (
            float(result["pearson_correlation"]),
            int(result["paired_week_count"]),
            -int(result["lag_weeks"]),
        ),
    )


def join_unique(values: list[str]) -> str:
    output: list[str] = []
    for value in values:
        if value and value not in output:
            output.append(value)
    return "; ".join(output)


def build_evidence_sentence(
    candidate_name: str,
    target_name: str,
    status: str,
    lag_weeks: int | None,
    score: float | None,
    paired_week_count: int,
    threshold: float,
) -> str:
    if status == "insufficient":
        return (
            f"{candidate_name} has insufficient overlapping data to evaluate "
            f"empirical {EDGE_TYPE} evidence for {target_name}."
        )
    assert lag_weeks is not None
    assert score is not None
    score_text = f"{score:.6f}"
    threshold_text = f"{threshold:.2f}"
    if status == "present":
        return (
            f"{candidate_name} has empirical {EDGE_TYPE} evidence for "
            f"{target_name}: best positive lag = {lag_weeks} weeks, Pearson "
            f"correlation = {score_text}, paired weeks = "
            f"{paired_week_count}, threshold = {threshold_text}."
        )
    return (
        f"{candidate_name} does not meet empirical {EDGE_TYPE} evidence for "
        f"{target_name} under the configured threshold: best positive lag = "
        f"{lag_weeks} weeks, Pearson correlation = {score_text}, paired "
        f"weeks = {paired_week_count}, threshold = {threshold_text}."
    )


def evaluate_candidate(
    candidate: dict[str, Any],
    target: dict[str, Any],
    threshold: float,
    minimum_paired_weeks: int,
    max_lag_weeks: int,
    minimum_lead_weeks: int = DEFAULT_MINIMUM_LEAD_WEEKS,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    lag_results = compute_lag_scan(
        candidate["values"],
        target["values"],
        minimum_paired_weeks,
        max_lag_weeks,
        minimum_lead_weeks,
    )
    best = select_best_lag(lag_results, minimum_lead_weeks)
    if best is None:
        status = "insufficient"
        lag_weeks = None
        score = None
        positive_lag_results = [
            result
            for result in lag_results
            if int(result["lag_weeks"]) >= minimum_lead_weeks
        ]
        paired_week_count = max(
            (
                int(result["paired_week_count"])
                for result in positive_lag_results
            ),
            default=0,
        )
    else:
        lag_weeks = int(best["lag_weeks"])
        score = float(best["pearson_correlation"])
        paired_week_count = int(best["paired_week_count"])
        status = "present" if score >= threshold else "missing"

    all_dates = [*candidate["values"], *target["values"]]
    source_dataset = join_unique(
        [*target["source_datasets"], *candidate["source_datasets"]]
    )
    target_region = join_unique(target["regions"])
    candidate_name = str(candidate["signal_name"])
    target_name = str(target["signal_name"])

    claim = {
        "case_id": CASE_ID,
        "candidate_id": candidate["signal_id"],
        "candidate_name": candidate_name,
        "target_signal_id": TARGET_SIGNAL_ID,
        "target_signal_name": target_name,
        "edge_type": EDGE_TYPE,
        "status": status,
        "source_dataset": source_dataset,
        "method": METHOD,
        "region": target_region,
        "time_window_start": date_to_week(min(all_dates)),
        "time_window_end": date_to_week(max(all_dates)),
        "lag_weeks": "" if lag_weeks is None else lag_weeks,
        "score": "" if score is None else f"{score:.6f}",
        "threshold": f"{threshold:.2f}",
        "paired_week_count": paired_week_count,
        "minimum_paired_weeks": minimum_paired_weeks,
        "evidence_sentence": build_evidence_sentence(
            candidate_name,
            target_name,
            status,
            lag_weeks,
            score,
            paired_week_count,
            threshold,
        ),
        "limitation": LIMITATION,
    }

    scan_rows = []
    for result in lag_results:
        correlation = result["pearson_correlation"]
        scan_rows.append(
            {
                "case_id": CASE_ID,
                "candidate_id": candidate["signal_id"],
                "candidate_name": candidate_name,
                "target_signal_id": TARGET_SIGNAL_ID,
                "target_signal_name": target_name,
                "edge_type": EDGE_TYPE,
                "lag_weeks": result["lag_weeks"],
                "paired_week_count": result["paired_week_count"],
                "pearson_correlation": (
                    ""
                    if correlation is None
                    else f"{float(correlation):.6f}"
                ),
                "minimum_paired_weeks": minimum_paired_weeks,
                "eligible": result["eligible"],
                "notes": result["notes"],
            }
        )
    return claim, scan_rows


def build_empirical_outputs(
    rows: list[dict[str, str]],
    threshold: float = DEFAULT_THRESHOLD,
    minimum_paired_weeks: int = DEFAULT_MINIMUM_PAIRED_WEEKS,
    max_lag_weeks: int = DEFAULT_MAX_LAG_WEEKS,
    minimum_lead_weeks: int = DEFAULT_MINIMUM_LEAD_WEEKS,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    validate_options(
        threshold,
        minimum_paired_weeks,
        max_lag_weeks,
        minimum_lead_weeks,
    )
    signals = collect_signals(rows)
    target = signals[TARGET_SIGNAL_ID]
    claims: list[dict[str, Any]] = []
    lag_scan: list[dict[str, Any]] = []
    for candidate_id in CANDIDATE_IDS:
        claim, candidate_scan = evaluate_candidate(
            signals[candidate_id],
            target,
            threshold,
            minimum_paired_weeks,
            max_lag_weeks,
            minimum_lead_weeks,
        )
        claims.append(claim)
        lag_scan.extend(candidate_scan)
    return claims, lag_scan


def write_csv(
    path: Path,
    rows: list[dict[str, Any]],
    columns: list[str],
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
    claims: list[dict[str, Any]],
    claims_output: Path,
    lag_scan_output: Path,
) -> None:
    statuses = {
        status: sum(claim["status"] == status for claim in claims)
        for status in ("present", "missing", "insufficient")
    }
    print(f"Candidates evaluated: {len(claims)}")
    print(f"Claims written: {len(claims)}")
    print(f"Present claims: {statuses['present']}")
    print(f"Missing claims: {statuses['missing']}")
    print(f"Insufficient claims: {statuses['insufficient']}")
    print(f"Claims output: {claims_output}")
    print(f"Lag scan output: {lag_scan_output}")


def main() -> int:
    args = parse_args()
    try:
        rows = read_normalized_rows(args.input)
        claims, lag_scan = build_empirical_outputs(
            rows,
            threshold=args.threshold,
            minimum_paired_weeks=args.minimum_paired_weeks,
            max_lag_weeks=args.max_lag_weeks,
            minimum_lead_weeks=args.minimum_lead_weeks,
        )
        # EvidenceClaim rows preserve the empirical audit trail. They do not
        # create positive typed graph edges or establish causal effects.
        write_csv(args.claims_output, claims, CLAIM_COLUMNS)
        write_csv(args.lag_scan_output, lag_scan, LAG_SCAN_COLUMNS)
        print_summary(claims, args.claims_output, args.lag_scan_output)
    except (csv.Error, FileNotFoundError, OSError, ValueError) as exc:
        print(f"Empirical evidence claim build failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
