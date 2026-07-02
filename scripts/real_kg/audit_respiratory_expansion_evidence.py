"""
Audit respiratory expansion evidence claims by recomputing empirical evidence
from the processed weekly signal table.

This checks that each EvidenceClaim accurately represents:
- best lag
- Pearson r
- paired-week count
- evidence status
- promoted edge type

Inputs:
    data/real_processed/respiratory_expansion/respiratory_expansion_weekly_signals.csv
    data/real_processed/respiratory_expansion/respiratory_expansion_evidence_claims.csv

Outputs:
    evals/respiratory_expansion/respiratory_expansion_evidence_audit.csv
    evals/respiratory_expansion/respiratory_expansion_evidence_audit_summary.json

This script does not call an LLM.
"""

from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timedelta
from pathlib import Path


WEEKLY_SIGNALS = Path(
    "data/real_processed/respiratory_expansion/"
    "respiratory_expansion_weekly_signals.csv"
)
CLAIMS = Path(
    "data/real_processed/respiratory_expansion/"
    "respiratory_expansion_evidence_claims.csv"
)

OUT_CSV = Path(
    "evals/respiratory_expansion/"
    "respiratory_expansion_evidence_audit.csv"
)
OUT_SUMMARY = Path(
    "evals/respiratory_expansion/"
    "respiratory_expansion_evidence_audit_summary.json"
)

MAX_LAG_WEEKS = 4
MIN_PAIRED_WEEKS = 20
CORRELATION_THRESHOLD = 0.60


def parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def to_float(value: str):
    value = (value or "").strip()
    if not value:
        return None
    return float(value)


def pearson(xs: list[float], ys: list[float]):
    if len(xs) != len(ys) or len(xs) < 2:
        return None

    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)

    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den_x = sum((x - x_mean) ** 2 for x in xs)
    den_y = sum((y - y_mean) ** 2 for y in ys)

    if den_x == 0 or den_y == 0:
        return None

    return num / math.sqrt(den_x * den_y)


def read_weekly_signals():
    with WEEKLY_SIGNALS.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    series = {}
    columns = [c for c in rows[0].keys() if c != "week_end"]

    for col in columns:
        values = {}
        for row in rows:
            date = parse_date(row["week_end"])
            value = to_float(row.get(col, ""))
            if date is not None and value is not None:
                values[date] = value
        series[col] = values

    return series


def read_claims():
    with CLAIMS.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def best_lagged_correlation(target_values: dict, candidate_values: dict):
    best = {
        "best_lag_weeks": None,
        "pearson_r": None,
        "paired_weeks": 0,
    }

    all_lags = []

    for lag in range(MAX_LAG_WEEKS + 1):
        xs = []
        ys = []

        for target_date, target_value in target_values.items():
            candidate_date = target_date - timedelta(days=7 * lag)
            candidate_value = candidate_values.get(candidate_date)

            if candidate_value is None:
                continue

            xs.append(candidate_value)
            ys.append(target_value)

        corr = pearson(xs, ys)

        lag_record = {
            "lag": lag,
            "pearson_r": None if corr is None else round(corr, 6),
            "paired_weeks": len(xs),
        }
        all_lags.append(lag_record)

        if corr is None:
            continue

        if best["pearson_r"] is None or corr > best["pearson_r"]:
            best = {
                "best_lag_weeks": lag,
                "pearson_r": corr,
                "paired_weeks": len(xs),
            }

    return best, all_lags


def expected_decision(row: dict[str, str], corr, paired, lag):
    if row["candidate_family"] == "negative_control":
        return "missing", "NO_TYPED_EDGE"

    if (
        corr is not None
        and paired >= MIN_PAIRED_WEEKS
        and corr >= CORRELATION_THRESHOLD
    ):
        if lag is not None and lag >= 1:
            return "present", "LEADING_INDICATOR_FOR"
        return "present", "CONCURRENT_INDICATOR_FOR"

    return "missing", "NO_TYPED_EDGE"


def claim_float(value: str):
    value = (value or "").strip()
    if not value:
        return None
    return float(value)


def claim_int(value: str):
    value = (value or "").strip()
    if not value:
        return None
    return int(value)


def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    series = read_weekly_signals()
    claims = read_claims()

    audit_rows = []

    for row in claims:
        target_id = row["target_id"]
        candidate_id = row["candidate_id"]

        target_values = series[target_id]
        candidate_values = series[candidate_id]

        computed, all_lags = best_lagged_correlation(target_values, candidate_values)

        computed_lag = computed["best_lag_weeks"]
        computed_corr = computed["pearson_r"]
        computed_paired = computed["paired_weeks"]

        recorded_lag = claim_int(row["best_lag_weeks"])
        recorded_corr = claim_float(row["pearson_r"])
        recorded_paired = claim_int(row["paired_weeks"])

        expected_status, expected_edge = expected_decision(
            row,
            computed_corr,
            computed_paired,
            computed_lag,
        )

        corr_match = (
            recorded_corr is None and computed_corr is None
        ) or (
            recorded_corr is not None
            and computed_corr is not None
            and abs(recorded_corr - computed_corr) <= 0.000001
        )

        lag_match = recorded_lag == computed_lag
        paired_match = recorded_paired == computed_paired
        status_match = row["evidence_status"] == expected_status
        edge_match = row["promoted_edge_type"] == expected_edge

        audit_pass = (
            corr_match
            and lag_match
            and paired_match
            and status_match
            and edge_match
        )

        audit_rows.append(
            {
                "claim_id": row["claim_id"],
                "target_label": row["target_label"],
                "candidate_label": row["candidate_label"],
                "recorded_lag": "" if recorded_lag is None else str(recorded_lag),
                "computed_lag": "" if computed_lag is None else str(computed_lag),
                "lag_match": str(lag_match),
                "recorded_pearson_r": "" if recorded_corr is None else f"{recorded_corr:.6f}",
                "computed_pearson_r": "" if computed_corr is None else f"{computed_corr:.6f}",
                "pearson_match": str(corr_match),
                "recorded_paired_weeks": "" if recorded_paired is None else str(recorded_paired),
                "computed_paired_weeks": str(computed_paired),
                "paired_weeks_match": str(paired_match),
                "recorded_evidence_status": row["evidence_status"],
                "expected_evidence_status": expected_status,
                "evidence_status_match": str(status_match),
                "recorded_edge_type": row["promoted_edge_type"],
                "expected_edge_type": expected_edge,
                "edge_type_match": str(edge_match),
                "audit_pass": str(audit_pass),
                "all_lags_json": json.dumps(all_lags),
            }
        )

    fieldnames = [
        "claim_id",
        "target_label",
        "candidate_label",
        "recorded_lag",
        "computed_lag",
        "lag_match",
        "recorded_pearson_r",
        "computed_pearson_r",
        "pearson_match",
        "recorded_paired_weeks",
        "computed_paired_weeks",
        "paired_weeks_match",
        "recorded_evidence_status",
        "expected_evidence_status",
        "evidence_status_match",
        "recorded_edge_type",
        "expected_edge_type",
        "edge_type_match",
        "audit_pass",
        "all_lags_json",
    ]

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(audit_rows)

    summary = {
        "claim_count": len(audit_rows),
        "audit_pass_count": sum(1 for r in audit_rows if r["audit_pass"] == "True"),
        "audit_fail_count": sum(1 for r in audit_rows if r["audit_pass"] != "True"),
        "audit_pass_rate": (
            sum(1 for r in audit_rows if r["audit_pass"] == "True") / len(audit_rows)
            if audit_rows else 0.0
        ),
        "lag_mismatch_count": sum(1 for r in audit_rows if r["lag_match"] != "True"),
        "pearson_mismatch_count": sum(1 for r in audit_rows if r["pearson_match"] != "True"),
        "paired_week_mismatch_count": sum(1 for r in audit_rows if r["paired_weeks_match"] != "True"),
        "status_mismatch_count": sum(1 for r in audit_rows if r["evidence_status_match"] != "True"),
        "edge_type_mismatch_count": sum(1 for r in audit_rows if r["edge_type_match"] != "True"),
        "threshold": CORRELATION_THRESHOLD,
        "min_paired_weeks": MIN_PAIRED_WEEKS,
        "max_lag_weeks": MAX_LAG_WEEKS,
        "output_csv": str(OUT_CSV),
    }

    OUT_SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))

    failed = [r for r in audit_rows if r["audit_pass"] != "True"]
    if failed:
        print("\nFAILED CLAIMS")
        for r in failed:
            print(
                r["claim_id"],
                r["lag_match"],
                r["pearson_match"],
                r["paired_weeks_match"],
                r["evidence_status_match"],
                r["edge_type_match"],
            )


if __name__ == "__main__":
    main()
