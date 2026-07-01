"""Normalize downloaded influenza snapshots into weekly long-form signals.

This is a first-pass source normalization step. It does not build
EvidenceClaims, modify the fixture-based KG, call Neo4j, or call an LLM.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any


CASE_ID = "real_us_flu_empirical_multicandidate_001"
DEFAULT_RAW_DIR = Path("data/real_raw/influenza")
DEFAULT_OUTPUT = Path(
    "data/real_processed/real_influenza_normalized_signals.csv"
)

HOSPITAL_FILE = "cdc_hospital_respiratory_admissions_sample.json"
FLUSURV_FILE = "delphi_flusurv_202440_202520.json"
WASTEWATER_FILE = "cdc_influenza_a_wastewater_sample.json"
ILI_FILE = "delphi_fluview_ili_nat_202440_202520.json"
CLINICAL_FILE = "delphi_fluview_clinical_nat_202440_202520.json"

OUTPUT_COLUMNS = [
    "case_id",
    "signal_id",
    "signal_name",
    "signal_role",
    "source_name",
    "source_dataset",
    "region",
    "week",
    "date",
    "raw_value",
    "normalized_value",
    "units",
    "aggregation_method",
    "raw_row_count",
    "notes",
]

NATIONAL_VALUES = {
    "nat",
    "national",
    "us",
    "usa",
    "united states",
    "united states of america",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Normalize downloaded CDC and Delphi influenza snapshots into a "
            "weekly long-form signal table."
        )
    )
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_json(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"Raw influenza source file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as input_file:
            return json.load(input_file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in raw source {path}: {exc}") from exc


def require_row_list(payload: Any, source_name: str) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        payload = payload.get("epidata")
    if not isinstance(payload, list):
        raise ValueError(
            f"{source_name} input must be a JSON list or contain epidata."
        )
    if any(not isinstance(row, dict) for row in payload):
        raise ValueError(f"{source_name} input contains a non-object row.")
    return payload


def parse_numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().replace(",", "")
    if not text or text.lower() in {
        "na",
        "n/a",
        "nan",
        "null",
        "none",
        "missing",
        "suppressed",
    }:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    return number if math.isfinite(number) else None


def first_numeric(
    row: dict[str, Any],
    preferred_columns: list[str],
) -> tuple[float | None, str | None]:
    for column in preferred_columns:
        value = parse_numeric(row.get(column))
        if value is not None:
            return value, column
    return None, None


def parse_source_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    candidates = [text, text[:10]]
    for candidate in candidates:
        try:
            return datetime.fromisoformat(
                candidate.replace("Z", "+00:00")
            ).date()
        except ValueError:
            pass
        for date_format in ("%Y-%m-%d", "%m/%d/%Y"):
            try:
                return datetime.strptime(candidate, date_format).date()
            except ValueError:
                continue
    return None


def parse_epiweek(value: Any) -> tuple[str, date] | None:
    text = str(value or "").strip().upper()
    if not text:
        return None
    if "-W" in text:
        year_text, week_text = text.split("-W", 1)
    elif len(text) == 6 and text.isdigit():
        year_text, week_text = text[:4], text[4:]
    else:
        return None
    try:
        year = int(year_text)
        week = int(week_text)
        monday = date.fromisocalendar(year, week, 1)
    except ValueError:
        return None
    return f"{year}-W{week:02d}", monday


def date_week(value: date) -> tuple[str, date]:
    iso_year, iso_week, _weekday = value.isocalendar()
    monday = date.fromisocalendar(iso_year, iso_week, 1)
    return f"{iso_year}-W{iso_week:02d}", monday


def is_national_row(row: dict[str, Any]) -> bool:
    for column in (
        "jurisdiction",
        "jurisdiction_name",
        "region",
        "geography",
        "location",
        "state",
        "state_territory",
    ):
        value = str(row.get(column, "")).strip().lower()
        if value in NATIONAL_VALUES:
            return True
    return False


def base_signal_row(
    signal_id: str,
    signal_name: str,
    signal_role: str,
    source_name: str,
    source_dataset: str,
    week: str,
    monday: date,
    raw_value: float,
    units: str,
    aggregation_method: str,
    raw_row_count: int,
    notes: str,
) -> dict[str, Any]:
    return {
        "case_id": CASE_ID,
        "signal_id": signal_id,
        "signal_name": signal_name,
        "signal_role": signal_role,
        "source_name": source_name,
        "source_dataset": source_dataset,
        "region": "United States",
        "week": week,
        "date": monday.isoformat(),
        "raw_value": raw_value,
        "normalized_value": "",
        "units": units,
        "aggregation_method": aggregation_method,
        "raw_row_count": raw_row_count,
        "notes": notes,
    }


def extract_hospital_signal(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    grouped: dict[
        str,
        dict[str, Any],
    ] = {}
    for row in rows:
        source_date = parse_source_date(row.get("weekendingdate"))
        value = parse_numeric(row.get("totalconfflunewadmper100k"))
        if source_date is None or value is None:
            continue
        week, monday = date_week(source_date)
        group = grouped.setdefault(
            week,
            {"monday": monday, "national": [], "states": []},
        )
        key = "national" if is_national_row(row) else "states"
        group[key].append(value)

    output = []
    for week in sorted(grouped):
        group = grouped[week]
        if group["national"]:
            values = group["national"]
            method = "select national / United States rows"
            notes = "National row selected."
        else:
            values = group["states"]
            method = "mean of nonmissing state values"
            notes = (
                "No national row was available; used mean across state rows."
            )
        if not values:
            continue
        output.append(
            base_signal_row(
                signal_id=(
                    "real_signal_us_influenza_hospital_admission_rate"
                ),
                signal_name="U.S. influenza hospital admission rate",
                signal_role="target",
                source_name="cdc_hospital_respiratory_admissions",
                source_dataset=(
                    "CDC Weekly Hospital Respiratory Admission Levels and "
                    "Rates"
                ),
                week=week,
                monday=group["monday"],
                raw_value=statistics.fmean(values),
                units="admissions per 100,000",
                aggregation_method=method,
                raw_row_count=len(values),
                notes=notes,
            )
        )
    return output


def extract_wastewater_signal(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    preferred = [
        "pcr_target_avg_conc_lin",
        "pcr_target_flowpop_lin",
        "pcr_target_avg_conc",
    ]
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        source_date = parse_source_date(row.get("sample_collect_date"))
        value, column = first_numeric(row, preferred)
        if source_date is None or value is None or column is None:
            continue
        week, monday = date_week(source_date)
        group = grouped.setdefault(
            week,
            {"monday": monday, "values": [], "columns": set()},
        )
        group["values"].append(value)
        group["columns"].add(column)

    output = []
    for week in sorted(grouped):
        group = grouped[week]
        values = group["values"]
        used_columns = [
            column for column in preferred if column in group["columns"]
        ]
        output.append(
            base_signal_row(
                signal_id=(
                    "real_signal_influenza_a_wastewater_concentration"
                ),
                signal_name="Influenza A wastewater concentration",
                signal_role="candidate",
                source_name="cdc_influenza_a_wastewater",
                source_dataset="CDC Influenza A Wastewater Surveillance",
                week=week,
                monday=group["monday"],
                raw_value=float(statistics.median(values)),
                units="copies/L wastewater",
                aggregation_method="weekly median across sites",
                raw_row_count=len(values),
                notes=(
                    "Value preference columns used: "
                    + ", ".join(used_columns)
                    + "."
                ),
            )
        )
    return output


def extract_flusurv_signal(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    preferred = ["rate_overall", "rate_flu_a"]
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        parsed_week = parse_epiweek(row.get("epiweek"))
        value, column = first_numeric(row, preferred)
        if parsed_week is None or value is None or column is None:
            continue
        week, monday = parsed_week
        location = str(
            row.get("location")
            or row.get("locations")
            or "unspecified catchment"
        ).strip()
        group = grouped.setdefault(
            week,
            {
                "monday": monday,
                "values": [],
                "columns": set(),
                "locations": set(),
            },
        )
        group["values"].append(value)
        group["columns"].add(column)
        group["locations"].add(location)

    output = []
    for week in sorted(grouped):
        group = grouped[week]
        used_columns = [
            column for column in preferred if column in group["columns"]
        ]
        selected_locations = ", ".join(sorted(group["locations"]))
        signal_row = base_signal_row(
            signal_id=(
                "real_signal_us_influenza_hospitalization_rate_flusurv"
            ),
            signal_name=(
                "U.S. influenza hospitalization rate from FluSurv-NET"
            ),
            signal_role="target",
            source_name="delphi_flusurv",
            source_dataset="Delphi Epidata FluSurv / CDC FluSurv-NET",
            week=week,
            monday=group["monday"],
            raw_value=statistics.fmean(group["values"]),
            units="hospitalizations per 100,000",
            aggregation_method=(
                "weekly FluSurv-NET rate from selected location/catchment"
            ),
            raw_row_count=len(group["values"]),
            notes=(
                f"Selected location(s): {selected_locations}. "
                "Value preference columns used: "
                + ", ".join(used_columns)
                + ". FluSurv-NET is catchment-based, not full U.S. "
                "population coverage."
            ),
        )
        signal_row["region"] = "United States / FluSurv-NET catchment"
        output.append(signal_row)
    return output


def extract_delphi_signal(
    rows: list[dict[str, Any]],
    *,
    signal_id: str,
    signal_name: str,
    source_name: str,
    source_dataset: str,
    preferred_columns: list[str],
) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        region = str(row.get("region", "nat")).strip().lower()
        if region not in NATIONAL_VALUES:
            continue
        parsed_week = parse_epiweek(row.get("epiweek"))
        value, column = first_numeric(row, preferred_columns)
        if parsed_week is None or value is None or column is None:
            continue
        week, monday = parsed_week
        group = grouped.setdefault(
            week,
            {"monday": monday, "values": [], "columns": set()},
        )
        group["values"].append(value)
        group["columns"].add(column)

    output = []
    for week in sorted(grouped):
        group = grouped[week]
        values = group["values"]
        method = (
            "national response row"
            if len(values) == 1
            else "mean of national response rows"
        )
        used_columns = [
            column
            for column in preferred_columns
            if column in group["columns"]
        ]
        output.append(
            base_signal_row(
                signal_id=signal_id,
                signal_name=signal_name,
                signal_role="candidate",
                source_name=source_name,
                source_dataset=source_dataset,
                week=week,
                monday=group["monday"],
                raw_value=statistics.fmean(values),
                units="percent",
                aggregation_method=method,
                raw_row_count=len(values),
                notes=(
                    "Value preference columns used: "
                    + ", ".join(used_columns)
                    + "."
                ),
            )
        )
    return output


def normalize_signal_rows(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_signal: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_signal[str(row["signal_id"])].append(row)

    for signal_rows in by_signal.values():
        values = [float(row["raw_value"]) for row in signal_rows]
        minimum = min(values)
        maximum = max(values)
        if math.isclose(minimum, maximum):
            for row in signal_rows:
                row["normalized_value"] = 0.0
                row["notes"] = (
                    f"{row['notes']} Constant signal; normalized_value "
                    "set to 0.0."
                ).strip()
        else:
            value_range = maximum - minimum
            for row in signal_rows:
                row["normalized_value"] = (
                    float(row["raw_value"]) - minimum
                ) / value_range
    return rows


def build_normalized_rows(raw_dir: Path) -> list[dict[str, Any]]:
    target_rows: list[dict[str, Any]] = []
    flusurv_path = raw_dir / FLUSURV_FILE
    if flusurv_path.is_file():
        flusurv_rows = require_row_list(
            load_json(flusurv_path),
            "Delphi FluSurv",
        )
        target_rows = extract_flusurv_signal(flusurv_rows)
    if not target_rows:
        hospital_rows = require_row_list(
            load_json(raw_dir / HOSPITAL_FILE),
            "CDC hospital respiratory admissions",
        )
        target_rows = extract_hospital_signal(hospital_rows)

    wastewater_rows = require_row_list(
        load_json(raw_dir / WASTEWATER_FILE),
        "CDC Influenza A wastewater",
    )
    ili_rows = require_row_list(
        load_json(raw_dir / ILI_FILE),
        "Delphi FluView ILINet",
    )
    clinical_rows = require_row_list(
        load_json(raw_dir / CLINICAL_FILE),
        "Delphi FluView Clinical",
    )

    rows = [
        *target_rows,
        *extract_wastewater_signal(wastewater_rows),
        *extract_delphi_signal(
            ili_rows,
            signal_id="real_signal_outpatient_ili_activity",
            signal_name="Outpatient ILI activity",
            source_name="delphi_fluview_ili",
            source_dataset="Delphi Epidata FluView ILINet / CDC FluView",
            preferred_columns=["wili", "ili"],
        ),
        *extract_delphi_signal(
            clinical_rows,
            signal_id="real_signal_influenza_test_positivity",
            signal_name="Influenza test positivity",
            source_name="delphi_fluview_clinical",
            source_dataset=(
                "Delphi Epidata FluView Clinical / CDC FluView"
            ),
            preferred_columns=["percent_positive", "percent_a"],
        ),
    ]
    if not rows:
        raise ValueError("No valid weekly influenza signal rows were found.")
    normalize_signal_rows(rows)
    rows.sort(
        key=lambda row: (
            str(row["week"]),
            str(row["signal_role"]),
            str(row["signal_id"]),
        )
    )
    return rows


def write_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=OUTPUT_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows: list[dict[str, Any]], output: Path) -> None:
    by_signal: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        by_signal[str(row["signal_id"])].append(str(row["week"]))
    print(f"Signals written: {len(by_signal)}")
    print(f"Rows written: {len(rows)}")
    print(f"Output path: {output}")
    print("Weeks covered by signal:")
    for signal_id in sorted(by_signal):
        weeks = sorted(set(by_signal[signal_id]))
        print(f"- {signal_id}: {weeks[0]} to {weeks[-1]} ({len(weeks)})")


def main() -> int:
    args = parse_args()
    try:
        rows = build_normalized_rows(args.raw_dir)
        write_rows(args.output, rows)
        print_summary(rows, args.output)
    except (csv.Error, FileNotFoundError, OSError, ValueError) as exc:
        print(f"Influenza signal normalization failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
