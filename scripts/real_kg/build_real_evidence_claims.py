"""Build auditable real-data EvidenceClaims from normalized weekly signals.

This first pipeline step deliberately has no Neo4j or LLM dependency. It turns
normalized observations into a deterministic, provenance-carrying evidence
claim table. The resulting associations are evidence to audit, not proof of
causality.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd


DEFAULT_INPUT = Path(
    "scripts/real_kg/fixtures/normalized_signals_fixture.csv"
)
DEFAULT_OUTPUT = Path("data/real_processed/real_evidence_claims.csv")
DEFAULT_CANDIDATE_ID = "real_signal_influenza_a_wastewater_activity"
DEFAULT_OUTPATIENT_ILI_CANDIDATE_ID = "real_signal_outpatient_ili_activity"
DEFAULT_TEST_POSITIVITY_CANDIDATE_ID = (
    "real_signal_influenza_test_positivity"
)
DEFAULT_HUMIDITY_CANDIDATE_ID = "real_signal_humidity_anomaly"
DEFAULT_CANDIDATE_IDS = [
    DEFAULT_CANDIDATE_ID,
    DEFAULT_OUTPATIENT_ILI_CANDIDATE_ID,
    DEFAULT_TEST_POSITIVITY_CANDIDATE_ID,
    DEFAULT_HUMIDITY_CANDIDATE_ID,
]
DEFAULT_TARGET_ID = "real_signal_us_influenza_hospitalization_rate"
DEFAULT_CASE_ID = "real_us_flu_wastewater_leading_indicator_001"
DEFAULT_REGION = "United States"

EDGE_TYPE = "LEADING_INDICATOR_FOR"
METHOD = "lagged_pearson_correlation_v1"
LIMITATION = (
    "Associational screening evidence only; not causal proof. Result depends "
    "on the selected time window, lag range, aggregation, threshold, and data "
    "quality."
)

REQUIRED_INPUT_COLUMNS = [
    "signal_id",
    "signal_name",
    "region",
    "epiweek",
    "value",
    "source_dataset",
]

OUTPUT_COLUMNS = [
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

EPIWEEK_PATTERN = re.compile(r"^(?P<year>\d{4})-W(?P<week>\d{2})$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build a deterministic LEADING_INDICATOR_FOR EvidenceClaim from "
            "normalized weekly candidate and target signals."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--candidate-id",
        action="append",
        default=None,
        help=(
            "Candidate signal ID to evaluate. Repeat for multiple candidates. "
            "Defaults to wastewater, outpatient ILI, test positivity, then "
            "humidity anomaly."
        ),
    )
    parser.add_argument("--target-id", default=DEFAULT_TARGET_ID)
    parser.add_argument("--case-id", default=DEFAULT_CASE_ID)
    parser.add_argument("--region", default=DEFAULT_REGION)
    parser.add_argument("--max-lag", type=int, default=4)
    parser.add_argument("--threshold", type=float, default=0.60)
    parser.add_argument("--min-overlap", type=int, default=6)
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.max_lag < 1:
        raise ValueError("--max-lag must be at least 1.")
    if args.min_overlap < 2:
        raise ValueError("--min-overlap must be at least 2 for correlation.")
    if not math.isfinite(args.threshold):
        raise ValueError("--threshold must be a finite number.")
    candidate_ids = resolve_candidate_ids(args)
    if any(candidate_id == args.target_id for candidate_id in candidate_ids):
        raise ValueError("--candidate-id and --target-id must be different.")
    if len(candidate_ids) != len(set(candidate_ids)):
        raise ValueError("--candidate-id values must be unique.")


def resolve_candidate_ids(args: argparse.Namespace) -> list[str]:
    candidate_ids = args.candidate_id
    if candidate_ids is None:
        return list(DEFAULT_CANDIDATE_IDS)
    if isinstance(candidate_ids, str):
        candidate_ids = [candidate_ids]
    normalized = [str(candidate_id).strip() for candidate_id in candidate_ids]
    if not normalized or any(not candidate_id for candidate_id in normalized):
        raise ValueError("--candidate-id must not be empty.")
    return normalized


def epiweek_to_date(epiweek: object) -> date:
    value = str(epiweek).strip()
    match = EPIWEEK_PATTERN.fullmatch(value)
    if not match:
        raise ValueError(
            f"Invalid epiweek '{value}'. Expected ISO format YYYY-Www."
        )

    year = int(match.group("year"))
    week = int(match.group("week"))
    try:
        return date.fromisocalendar(year, week, 1)
    except ValueError as exc:
        raise ValueError(f"Invalid ISO epiweek '{value}': {exc}") from exc


def date_to_epiweek(value: date) -> str:
    iso_year, iso_week, _ = value.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def load_normalized_signals(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    data = pd.read_csv(path, dtype=str)
    missing_columns = [
        column for column in REQUIRED_INPUT_COLUMNS if column not in data.columns
    ]
    if missing_columns:
        raise ValueError(
            "Input is missing required columns: "
            + ", ".join(missing_columns)
        )

    return data[REQUIRED_INPUT_COLUMNS].copy()


def filter_signal_rows(
    data: pd.DataFrame,
    signal_id: str,
    region: str,
    role: str,
) -> pd.DataFrame:
    rows = data[
        (data["signal_id"].str.strip() == signal_id)
        & (data["region"].str.strip() == region)
    ].copy()

    if rows.empty:
        raise ValueError(
            f"No {role} rows found for signal_id='{signal_id}' "
            f"and region='{region}'."
        )

    numeric_values = pd.to_numeric(rows["value"], errors="coerce")
    invalid_mask = numeric_values.isna()
    if invalid_mask.any():
        invalid_values = sorted(
            {str(value) for value in rows.loc[invalid_mask, "value"].tolist()}
        )
        raise ValueError(
            f"Non-numeric {role} values found: {invalid_values}"
        )
    rows["value"] = numeric_values.astype(float)

    try:
        rows["week_date"] = rows["epiweek"].map(epiweek_to_date)
    except ValueError as exc:
        raise ValueError(f"Invalid {role} epiweek: {exc}") from exc

    duplicate_weeks = rows.loc[
        rows["week_date"].duplicated(keep=False), "epiweek"
    ].tolist()
    if duplicate_weeks:
        raise ValueError(
            f"Duplicate {role} epiweeks found after filtering: "
            f"{sorted(set(duplicate_weeks))}"
        )

    return rows.sort_values("week_date").reset_index(drop=True)


def get_single_signal_name(rows: pd.DataFrame, role: str) -> str:
    names = sorted(
        {
            str(name).strip()
            for name in rows["signal_name"].tolist()
            if str(name).strip()
        }
    )
    if len(names) != 1:
        raise ValueError(
            f"Expected exactly one {role} signal_name, found: {names}"
        )
    return names[0]


def compute_lag_results(
    candidate_rows: pd.DataFrame,
    target_rows: pd.DataFrame,
    max_lag: int,
) -> list[dict[str, object]]:
    candidate = candidate_rows[["week_date", "value"]].rename(
        columns={"value": "candidate_value"}
    )
    target = target_rows[["week_date", "value"]].rename(
        columns={
            "week_date": "target_week_date",
            "value": "target_value",
        }
    )

    results: list[dict[str, object]] = []
    for lag_weeks in range(1, max_lag + 1):
        shifted = candidate.copy()

        # Lag convention: lag_weeks = 2 compares the candidate value at week t
        # with the target value at week t+2. The candidate therefore leads the
        # target by two weeks.
        shifted["target_week_date"] = shifted["week_date"].map(
            lambda week: week + pd.Timedelta(weeks=lag_weeks)
        )
        paired = shifted.merge(target, on="target_week_date", how="inner")
        overlap = len(paired)
        correlation = (
            paired["candidate_value"].corr(paired["target_value"])
            if overlap >= 2
            else float("nan")
        )

        results.append(
            {
                "lag_weeks": lag_weeks,
                "overlap": overlap,
                "correlation": float(correlation),
            }
        )

    return results


def select_best_lag(
    lag_results: list[dict[str, object]],
    min_overlap: int,
) -> dict[str, object] | None:
    eligible = [
        result
        for result in lag_results
        if int(result["overlap"]) >= min_overlap
        and math.isfinite(float(result["correlation"]))
    ]
    if not eligible:
        return None

    # A smaller lag wins an exact correlation tie, making selection stable.
    return max(
        eligible,
        key=lambda result: (
            float(result["correlation"]),
            int(result["overlap"]),
            -int(result["lag_weeks"]),
        ),
    )


def build_evidence_sentence(
    candidate_name: str,
    target_name: str,
    region: str,
    status: str,
    lag_weeks: int | None,
    score: float | None,
    threshold: float,
) -> str:
    if status == "insufficient_data":
        return (
            f"{candidate_name} has insufficient data to assess "
            f"{EDGE_TYPE} evidence for {target_name} in {region}: no tested "
            "lag met the minimum overlap requirement."
        )

    if status == "present":
        result_text = f"has {EDGE_TYPE} evidence"
    else:
        return (
            f"{candidate_name} does not meet {EDGE_TYPE} evidence for "
            f"{target_name} in {region} under the configured threshold: "
            f"best lag = {lag_weeks} weeks, Pearson correlation = "
            f"{score:.2f}, threshold = {threshold:.2f}."
        )

    return (
        f"{candidate_name} {result_text} for {target_name} in {region}: "
        f"best lag = {lag_weeks} weeks, Pearson correlation = {score:.2f}, "
        f"threshold = {threshold:.2f}."
    )


def build_claim(
    args: argparse.Namespace,
    candidate_rows: pd.DataFrame,
    target_rows: pd.DataFrame,
    candidate_id: str | None = None,
) -> dict[str, object]:
    if candidate_id is None:
        candidate_id = resolve_candidate_ids(args)[0]
    candidate_name = get_single_signal_name(candidate_rows, "candidate")
    target_name = get_single_signal_name(target_rows, "target")

    lag_results = compute_lag_results(
        candidate_rows,
        target_rows,
        args.max_lag,
    )
    if max(int(result["overlap"]) for result in lag_results) == 0:
        raise ValueError(
            "No overlapping candidate and target weeks exist for the tested "
            "lag range."
        )

    best = select_best_lag(lag_results, args.min_overlap)
    if best is None:
        lag_weeks = None
        score = None
        status = "insufficient_data"
    else:
        lag_weeks = int(best["lag_weeks"])
        score = float(best["correlation"])
        status = "present" if score >= args.threshold else "missing"

    all_week_dates = [
        *candidate_rows["week_date"].tolist(),
        *target_rows["week_date"].tolist(),
    ]
    time_window_start = date_to_epiweek(min(all_week_dates))
    time_window_end = date_to_epiweek(max(all_week_dates))

    datasets = sorted(
        {
            str(dataset).strip()
            for dataset in [
                *candidate_rows["source_dataset"].tolist(),
                *target_rows["source_dataset"].tolist(),
            ]
            if str(dataset).strip()
        }
    )
    source_dataset = "; ".join(datasets)

    evidence_sentence = build_evidence_sentence(
        candidate_name,
        target_name,
        args.region,
        status,
        lag_weeks,
        score,
        args.threshold,
    )

    # This row is an auditable EvidenceClaim: it preserves method, threshold,
    # provenance, time window, and limitations. A high correlation supports a
    # typed graph edge but does not establish an epidemiological causal effect.
    return {
        "case_id": args.case_id,
        "candidate_id": candidate_id,
        "candidate_name": candidate_name,
        "target_signal_id": args.target_id,
        "target_signal_name": target_name,
        "edge_type": EDGE_TYPE,
        "status": status,
        "source_dataset": source_dataset,
        "method": METHOD,
        "region": args.region,
        "time_window_start": time_window_start,
        "time_window_end": time_window_end,
        "lag_weeks": "" if lag_weeks is None else lag_weeks,
        "score": "" if score is None else f"{score:.6f}",
        "threshold": f"{args.threshold:.2f}",
        "evidence_sentence": evidence_sentence,
        "limitation": LIMITATION,
    }


def write_claims(
    path: Path,
    claims: list[dict[str, object]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(claims)


def write_claim(path: Path, claim: dict[str, object]) -> None:
    """Write one claim for compatibility with focused callers."""
    write_claims(path, [claim])


def print_summary(
    args: argparse.Namespace,
    claims: list[dict[str, object]],
) -> None:
    print("Real evidence claims built.")
    print(f"Input: {args.input}")
    print(f"Output: {args.output}")
    print(f"Target ID: {args.target_id}")
    print(f"Claim count: {len(claims)}")
    for claim in claims:
        selected_lag = (
            claim["lag_weeks"] if claim["lag_weeks"] != "" else "N/A"
        )
        score = claim["score"] if claim["score"] != "" else "N/A"
        print(
            f"Candidate: {claim['candidate_id']} | "
            f"status: {claim['status']} | lag: {selected_lag} | "
            f"score: {score}"
        )


def main() -> int:
    args = parse_args()

    try:
        validate_args(args)
        data = load_normalized_signals(args.input)
        target_rows = filter_signal_rows(
            data,
            args.target_id,
            args.region,
            "target",
        )
        claims = []
        for candidate_id in resolve_candidate_ids(args):
            candidate_rows = filter_signal_rows(
                data,
                candidate_id,
                args.region,
                "candidate",
            )
            claims.append(
                build_claim(
                    args,
                    candidate_rows,
                    target_rows,
                    candidate_id,
                )
            )
        write_claims(args.output, claims)
        print_summary(args, claims)
    except (FileNotFoundError, OSError, ValueError, pd.errors.ParserError) as exc:
        print(f"Evidence claim build failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
