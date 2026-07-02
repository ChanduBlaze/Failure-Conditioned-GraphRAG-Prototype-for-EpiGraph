"""
Process respiratory expansion surveillance sources into weekly signals and
evidence claims.

Inputs:
    data/raw/respiratory_expansion/resp_net_hospitalization_rates.csv
    data/raw/respiratory_expansion/cdc_wastewater_viral_activity.csv
    data/raw/respiratory_expansion/cdc_respiratory_pathogen_test_positivity.csv

Outputs:
    data/real_processed/respiratory_expansion/respiratory_expansion_weekly_signals.csv
    data/real_processed/respiratory_expansion/respiratory_expansion_evidence_claims.csv
    data/real_processed/respiratory_expansion/respiratory_expansion_graph_context.json
    data/real_processed/respiratory_expansion/respiratory_expansion_processing_summary.json

This script does not call an LLM.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


RAW_DIR = Path("data/raw/respiratory_expansion")
OUT_DIR = Path("data/real_processed/respiratory_expansion")

RESP_NET = RAW_DIR / "resp_net_hospitalization_rates.csv"
WASTEWATER = RAW_DIR / "cdc_wastewater_viral_activity.csv"
TEST_POS = RAW_DIR / "cdc_respiratory_pathogen_test_positivity.csv"

WEEKLY_SIGNALS = OUT_DIR / "respiratory_expansion_weekly_signals.csv"
EVIDENCE_CLAIMS = OUT_DIR / "respiratory_expansion_evidence_claims.csv"
GRAPH_CONTEXT = OUT_DIR / "respiratory_expansion_graph_context.json"
SUMMARY = OUT_DIR / "respiratory_expansion_processing_summary.json"

MIN_PAIRED_WEEKS = 20
CORRELATION_THRESHOLD = 0.60
MAX_LAG_WEEKS = 4


TARGETS = {
    "FluSurv-NET": {
        "target_id": "target_flu_hospitalization_rate",
        "target_label": "FluSurv-NET influenza hospitalization rate",
        "disease": "influenza",
    },
    "COVID-NET": {
        "target_id": "target_covid_hospitalization_rate",
        "target_label": "COVID-NET COVID-19 hospitalization rate",
        "disease": "covid",
    },
    "RSV-NET": {
        "target_id": "target_rsv_hospitalization_rate",
        "target_label": "RSV-NET RSV hospitalization rate",
        "disease": "rsv",
    },
}

WASTEWATER_CANDIDATES = {
    "SARS-CoV-2": {
        "candidate_id": "candidate_wastewater_sars_cov_2",
        "candidate_label": "Wastewater SARS-CoV-2 viral activity",
        "candidate_family": "wastewater",
        "disease": "covid",
    },
    "Influenza A virus": {
        "candidate_id": "candidate_wastewater_influenza_a",
        "candidate_label": "Wastewater Influenza A viral activity",
        "candidate_family": "wastewater",
        "disease": "influenza",
    },
    "RSV": {
        "candidate_id": "candidate_wastewater_rsv",
        "candidate_label": "Wastewater RSV viral activity",
        "candidate_family": "wastewater",
        "disease": "rsv",
    },
}

TEST_POS_CANDIDATES = {
    "COVID-19": {
        "candidate_id": "candidate_test_positivity_covid_19",
        "candidate_label": "COVID-19 test positivity",
        "candidate_family": "test_positivity",
        "disease": "covid",
    },
    "Influenza": {
        "candidate_id": "candidate_test_positivity_influenza",
        "candidate_label": "Influenza test positivity",
        "candidate_family": "test_positivity",
        "disease": "influenza",
    },
    "RSV": {
        "candidate_id": "candidate_test_positivity_rsv",
        "candidate_label": "RSV test positivity",
        "candidate_family": "test_positivity",
        "disease": "rsv",
    },
}

NEGATIVE_CONTROL = {
    "candidate_id": "candidate_negative_control_deterministic",
    "candidate_label": "Deterministic negative-control surveillance signal",
    "candidate_family": "negative_control",
    "disease": "none",
}


def parse_date(value: str):
    value = (value or "").strip()
    if not value:
        return None

    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%f", "%m/%d/%Y %I:%M:%S %p"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    if "T" in value:
        try:
            return datetime.strptime(value.split("T", 1)[0], "%Y-%m-%d").date()
        except ValueError:
            pass

    return None


def to_float(value: str):
    value = (value or "").strip()
    if not value or value == ".":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def mean(values: list[float]) -> float | None:
    clean = [v for v in values if v is not None and math.isfinite(v)]
    if not clean:
        return None
    return sum(clean) / len(clean)


def pearson(xs: list[float], ys: list[float]) -> float | None:
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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        return list(csv.DictReader(f))


def load_targets() -> dict[str, dict]:
    rows = read_csv(RESP_NET)
    series: dict[str, dict] = {}

    for network, meta in TARGETS.items():
        values: dict = {}

        for row in rows:
            if row.get("Surveillance Network") != network:
                continue
            if row.get("rate_type") != "Observed":
                continue
            if row.get("Age group") != "Overall":
                continue
            if row.get("Sex") != "Overall":
                continue
            if row.get("Race/Ethnicity") != "Overall":
                continue
            if row.get("Site") != "Overall":
                continue

            date = parse_date(row.get("Week Ending Date", ""))
            value = to_float(row.get("Weekly Rate", ""))

            if date is not None and value is not None:
                values[date] = value

        series[meta["target_id"]] = {
            **meta,
            "signal_role": "target",
            "values": values,
            "source": "RESP-NET hospitalization rates",
        }

    return series


def load_wastewater_candidates() -> dict[str, dict]:
    rows = read_csv(WASTEWATER)
    grouped: dict[tuple, list[float]] = defaultdict(list)

    for row in rows:
        pathogen = row.get("Pathogen_Target", "")
        if pathogen not in WASTEWATER_CANDIDATES:
            continue

        date = parse_date(row.get("Week_End", ""))
        value = to_float(row.get("Site_WVAL", ""))

        if date is not None and value is not None:
            grouped[(pathogen, date)].append(value)

    series: dict[str, dict] = {}

    for pathogen, meta in WASTEWATER_CANDIDATES.items():
        values = {
            date: avg
            for (pathogen_key, date), vals in grouped.items()
            if pathogen_key == pathogen
            for avg in [mean(vals)]
            if avg is not None
        }

        series[meta["candidate_id"]] = {
            **meta,
            "signal_role": "candidate",
            "values": values,
            "source": "CDC wastewater viral activity",
            "aggregation": "national mean of Site_WVAL by week and pathogen",
        }

    return series


def load_test_positivity_candidates() -> dict[str, dict]:
    rows = read_csv(TEST_POS)
    series: dict[str, dict] = {}

    for pathogen, meta in TEST_POS_CANDIDATES.items():
        values: dict = {}

        for row in rows:
            if row.get("pathogen") != pathogen:
                continue

            date = parse_date(row.get("week_end", ""))
            value = to_float(row.get("percent_test_positivity", ""))

            if date is not None and value is not None:
                values[date] = value

        series[meta["candidate_id"]] = {
            **meta,
            "signal_role": "candidate",
            "values": values,
            "source": "CDC respiratory pathogen test positivity",
        }

    return series


def build_negative_control(all_dates: list) -> dict[str, dict]:
    values = {}
    for index, date in enumerate(sorted(all_dates)):
        # Deterministic non-epidemiological signal.
        values[date] = ((index * 37) % 101) / 100.0

    return {
        NEGATIVE_CONTROL["candidate_id"]: {
            **NEGATIVE_CONTROL,
            "signal_role": "candidate",
            "values": values,
            "source": "deterministic synthetic negative control",
        }
    }


def best_lagged_correlation(
    target_values: dict,
    candidate_values: dict,
) -> dict[str, object]:
    best = {
        "best_lag_weeks": None,
        "pearson_r": None,
        "paired_weeks": 0,
    }

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

        if corr is None:
            continue

        if best["pearson_r"] is None or corr > best["pearson_r"]:
            best = {
                "best_lag_weeks": lag,
                "pearson_r": corr,
                "paired_weeks": len(xs),
            }

    return best


def build_evidence_claims(targets: dict, candidates: dict) -> list[dict[str, str]]:
    claims = []

    for target_id, target in targets.items():
        for candidate_id, candidate in candidates.items():
            stats = best_lagged_correlation(target["values"], candidate["values"])
            corr = stats["pearson_r"]
            lag = stats["best_lag_weeks"]
            paired = stats["paired_weeks"]

            threshold = CORRELATION_THRESHOLD

            if candidate["candidate_family"] == "negative_control":
                evidence_status = "missing"
                edge_type = "NO_TYPED_EDGE"
            elif corr is not None and paired >= MIN_PAIRED_WEEKS and corr >= threshold:
                evidence_status = "present"
                edge_type = (
                    "LEADING_INDICATOR_FOR"
                    if lag is not None and lag >= 1
                    else "CONCURRENT_INDICATOR_FOR"
                )
            else:
                evidence_status = "missing"
                edge_type = "NO_TYPED_EDGE"

            claim_id = f"claim_{target_id}__{candidate_id}"

            claims.append(
                {
                    "claim_id": claim_id,
                    "pipeline": "respiratory_expansion",
                    "target_id": target_id,
                    "target_label": target["target_label"],
                    "target_disease": target["disease"],
                    "candidate_id": candidate_id,
                    "candidate_label": candidate["candidate_label"],
                    "candidate_family": candidate["candidate_family"],
                    "candidate_disease": candidate["disease"],
                    "best_lag_weeks": "" if lag is None else str(lag),
                    "pearson_r": "" if corr is None else f"{corr:.6f}",
                    "paired_weeks": str(paired),
                    "threshold": f"{threshold:.2f}",
                    "evidence_status": evidence_status,
                    "promoted_edge_type": edge_type,
                    "target_source": target["source"],
                    "candidate_source": candidate["source"],
                    "interpretation": (
                        "Lagged/concurrent correlation is screening evidence only; "
                        "not causal proof and not validated forecast improvement."
                    ),
                }
            )

    return claims


def write_weekly_signals(targets: dict, candidates: dict) -> None:
    all_series = {**targets, **candidates}
    all_dates = sorted(
        {
            date
            for series in all_series.values()
            for date in series["values"].keys()
        }
    )

    columns = ["week_end", *all_series.keys()]

    with WEEKLY_SIGNALS.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, lineterminator="\n")
        writer.writeheader()

        for date in all_dates:
            row = {"week_end": date.isoformat()}
            for key, series in all_series.items():
                value = series["values"].get(date)
                row[key] = "" if value is None else f"{value:.6f}"
            writer.writerow(row)


def write_claims(claims: list[dict[str, str]]) -> None:
    fieldnames = [
        "claim_id",
        "pipeline",
        "target_id",
        "target_label",
        "target_disease",
        "candidate_id",
        "candidate_label",
        "candidate_family",
        "candidate_disease",
        "best_lag_weeks",
        "pearson_r",
        "paired_weeks",
        "threshold",
        "evidence_status",
        "promoted_edge_type",
        "target_source",
        "candidate_source",
        "interpretation",
    ]

    with EVIDENCE_CLAIMS.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(claims)


def write_graph_context(claims: list[dict[str, str]]) -> None:
    claims_json = []
    edges_json = []

    for row in claims:
        claim = dict(row)
        claims_json.append(claim)

        if row["promoted_edge_type"] != "NO_TYPED_EDGE":
            edges_json.append(
                {
                    "source": row["candidate_label"],
                    "target": row["target_label"],
                    "edge_type": row["promoted_edge_type"],
                    "evidence_status": row["evidence_status"],
                    "best_lag_weeks": row["best_lag_weeks"],
                    "pearson_r": row["pearson_r"],
                    "paired_weeks": row["paired_weeks"],
                    "threshold": row["threshold"],
                    "claim_id": row["claim_id"],
                    "pipeline": row["pipeline"],
                }
            )

    graph = {
        "pipeline": "respiratory_expansion",
        "threshold": CORRELATION_THRESHOLD,
        "min_paired_weeks": MIN_PAIRED_WEEKS,
        "max_lag_weeks": MAX_LAG_WEEKS,
        "claims": claims_json,
        "typed_edges": edges_json,
        "interpretation_constraints": [
            "Evidence is screening evidence only.",
            "Do not claim causal discovery.",
            "Do not claim forecast improvement without downstream validation.",
            "EvidenceClaim existence does not imply typed edge promotion.",
            "Negative controls must remain unpromoted.",
        ],
    }

    GRAPH_CONTEXT.write_text(json.dumps(graph, indent=2), encoding="utf-8")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    targets = load_targets()
    candidates = {
        **load_wastewater_candidates(),
        **load_test_positivity_candidates(),
    }

    all_dates = {
        date
        for series in {**targets, **candidates}.values()
        for date in series["values"].keys()
    }

    candidates.update(build_negative_control(sorted(all_dates)))

    claims = build_evidence_claims(targets, candidates)

    write_weekly_signals(targets, candidates)
    write_claims(claims)
    write_graph_context(claims)

    summary = {
        "target_count": len(targets),
        "candidate_count": len(candidates),
        "claim_count": len(claims),
        "promoted_edge_count": sum(
            1 for row in claims if row["promoted_edge_type"] != "NO_TYPED_EDGE"
        ),
        "present_claim_count": sum(
            1 for row in claims if row["evidence_status"] == "present"
        ),
        "missing_claim_count": sum(
            1 for row in claims if row["evidence_status"] == "missing"
        ),
        "threshold": CORRELATION_THRESHOLD,
        "min_paired_weeks": MIN_PAIRED_WEEKS,
        "max_lag_weeks": MAX_LAG_WEEKS,
        "outputs": {
            "weekly_signals": str(WEEKLY_SIGNALS),
            "evidence_claims": str(EVIDENCE_CLAIMS),
            "graph_context": str(GRAPH_CONTEXT),
        },
    }

    SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
