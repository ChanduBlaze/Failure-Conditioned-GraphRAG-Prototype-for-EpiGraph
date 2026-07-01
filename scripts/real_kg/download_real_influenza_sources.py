"""Download or inspect public influenza source snapshots.

This script is source ingestion only. It writes raw source responses and an
inventory, but it does not normalize signals, build evidence claims, call
Neo4j, or call an LLM.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_DIR = Path("data/real_raw/influenza")
DEFAULT_INVENTORY_OUTPUT = Path(
    "data/real_processed/real_influenza_source_inventory.csv"
)
DEFAULT_START_EPIWEEK = 202440
DEFAULT_END_EPIWEEK = 202520
DEFAULT_SOCRATA_LIMIT = 5000
DEFAULT_FLUSURV_LOCATIONS = "network_all"
DEFAULT_FLUSURV_FALLBACK_LOCATIONS = "CA,NY_albany,OR,MN,GA"
HTTP_TIMEOUT_SECONDS = 60

SOCRATA_SOURCES = [
    {
        "source_name": "cdc_hospital_respiratory_admissions",
        "dataset_id": "vdzy-6i9v",
        "date_column": "weekendingdate",
        "order": "weekendingdate,jurisdiction",
        "intended_signal_role": (
            "target signal candidate for U.S. influenza hospital "
            "admission/hospitalization burden"
        ),
    },
    {
        "source_name": "cdc_influenza_a_wastewater",
        "dataset_id": "ymmh-divb",
        "date_column": "sample_collect_date",
        "order": "sample_collect_date,state_territory,site",
        "intended_signal_role": "candidate leading indicator signal",
    },
]

DELPHI_SOURCES = [
    {
        "source_name": "delphi_fluview_ili",
        "endpoint": "fluview",
        "intended_signal_role": "outpatient ILI candidate signal",
    },
    {
        "source_name": "delphi_fluview_clinical",
        "endpoint": "fluview_clinical",
        "intended_signal_role": "influenza test positivity candidate signal",
    },
]

FLUSURV_SOURCE = {
    "source_name": "delphi_flusurv",
    "endpoint": "flusurv",
    "intended_signal_role": (
        "target signal for laboratory-confirmed influenza hospitalization rate"
    ),
}

INVENTORY_COLUMNS = [
    "source_name",
    "source_type",
    "dataset_id_or_endpoint",
    "intended_signal_role",
    "raw_output_path",
    "row_count",
    "column_count",
    "columns",
    "time_range_requested",
    "date_accessed_utc",
    "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download or inspect public influenza source snapshots without "
            "changing the evaluated real KG."
        )
    )
    parser.add_argument(
        "--start-epiweek",
        type=int,
        default=DEFAULT_START_EPIWEEK,
    )
    parser.add_argument(
        "--end-epiweek",
        type=int,
        default=DEFAULT_END_EPIWEEK,
    )
    parser.add_argument(
        "--socrata-limit",
        type=int,
        default=DEFAULT_SOCRATA_LIMIT,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--inventory-output",
        type=Path,
        default=DEFAULT_INVENTORY_OUTPUT,
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="Fetch Socrata metadata only; skip all row-data endpoints.",
    )
    parser.add_argument(
        "--disable-socrata-date-filter",
        action="store_true",
        help=(
            "Fetch unfiltered Socrata samples using the legacy limit-only "
            "query."
        ),
    )
    parser.add_argument(
        "--flusurv-locations",
        default=DEFAULT_FLUSURV_LOCATIONS,
        help="Primary Delphi FluSurv location or comma-separated locations.",
    )
    parser.add_argument(
        "--flusurv-fallback-locations",
        default=DEFAULT_FLUSURV_FALLBACK_LOCATIONS,
        help=(
            "Comma-separated FluSurv locations requested when the primary "
            "location response is empty."
        ),
    )
    return parser.parse_args()


def epiweek_monday(value: int, option_name: str) -> date:
    year, week = divmod(value, 100)
    if year < 2000 or not 1 <= week <= 53:
        raise ValueError(
            f"{option_name} must be a six-digit epiweek YYYYWW; got {value}."
        )
    try:
        return date.fromisocalendar(year, week, 1)
    except ValueError as exc:
        raise ValueError(
            f"{option_name} is not a valid ISO epiweek: {value}."
        ) from exc


def epiweek_date_window(
    start_epiweek: int,
    end_epiweek: int,
) -> tuple[date, date]:
    start_monday = epiweek_monday(
        start_epiweek,
        "--start-epiweek",
    )
    end_monday = epiweek_monday(end_epiweek, "--end-epiweek")
    buffered_start = start_monday - timedelta(days=7)
    buffered_end = end_monday + timedelta(days=13)
    return buffered_start, buffered_end


def validate_args(args: argparse.Namespace) -> None:
    epiweek_monday(args.start_epiweek, "--start-epiweek")
    epiweek_monday(args.end_epiweek, "--end-epiweek")
    if args.start_epiweek > args.end_epiweek:
        raise ValueError("--start-epiweek must not exceed --end-epiweek.")
    if args.socrata_limit < 1:
        raise ValueError("--socrata-limit must be at least 1.")
    if not str(
        getattr(
            args,
            "flusurv_locations",
            DEFAULT_FLUSURV_LOCATIONS,
        )
    ).strip():
        raise ValueError("--flusurv-locations must not be empty.")


def fetch_json(url: str, source_name: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "KG-LLM-GraphRAG-source-inspection/1.0",
        },
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=HTTP_TIMEOUT_SECONDS,
        ) as response:
            payload = response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"HTTP {exc.code} while fetching {source_name} from {url}."
        ) from exc
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError(
            f"Network failure while fetching {source_name} from {url}: "
            f"{exc}"
        ) from exc

    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Invalid JSON returned for {source_name} from {url}: {exc}"
        ) from exc


def parse_socrata_metadata(payload: Any, source_name: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(
            f"Socrata metadata for {source_name} must be a JSON object."
        )
    columns = payload.get("columns", [])
    if not isinstance(columns, list):
        raise ValueError(
            f"Socrata metadata columns for {source_name} must be a list."
        )
    return payload


def parse_socrata_sample(payload: Any, source_name: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError(
            f"Socrata sample for {source_name} must be a JSON list."
        )
    if any(not isinstance(row, dict) for row in payload):
        raise ValueError(
            f"Socrata sample for {source_name} contains a non-object row."
        )
    return payload


def fetch_socrata_metadata(
    dataset_id: str,
    source_name: str,
) -> dict[str, Any]:
    url = f"https://data.cdc.gov/api/views/{dataset_id}"
    return parse_socrata_metadata(fetch_json(url, source_name), source_name)


def fetch_socrata_sample(
    dataset_id: str,
    source_name: str,
    limit: int,
    date_column: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    order: str | None = None,
) -> list[dict[str, Any]]:
    url = build_socrata_sample_url(
        dataset_id=dataset_id,
        limit=limit,
        date_column=date_column,
        start_date=start_date,
        end_date=end_date,
        order=order,
    )
    return parse_socrata_sample(fetch_json(url, source_name), source_name)


def build_socrata_sample_url(
    dataset_id: str,
    limit: int,
    date_column: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    order: str | None = None,
) -> str:
    base_url = f"https://data.cdc.gov/resource/{dataset_id}.json"
    if date_column is None:
        return f"{base_url}?$limit={limit}"
    if start_date is None or end_date is None or not order:
        raise ValueError(
            "Filtered Socrata requests require start_date, end_date, and order."
        )
    where = (
        f"{date_column} >= '{start_date.isoformat()}T00:00:00' AND "
        f"{date_column} <= '{end_date.isoformat()}T23:59:59'"
    )
    query = urllib.parse.urlencode(
        {
            "$limit": limit,
            "$where": where,
            "$order": order,
        }
    )
    return f"{base_url}?{query}"


def parse_delphi_response(
    payload: Any,
    source_name: str,
    allow_empty_result: bool = False,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError(
            f"Delphi response for {source_name} must be a JSON object."
        )
    result_code = payload.get("result")
    message = str(payload.get("message", "")).strip()
    if result_code != 1:
        if allow_empty_result and result_code in {-2, 0}:
            return []
        raise ValueError(
            f"Delphi source {source_name} returned result code "
            f"{result_code!r}: {message or 'no message'}."
        )
    rows = payload.get("epidata")
    if not isinstance(rows, list):
        raise ValueError(
            f"Delphi source {source_name} returned no epidata list."
        )
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError(
            f"Delphi source {source_name} contains a non-object row."
        )
    return rows


def fetch_delphi_source(
    endpoint: str,
    source_name: str,
    start_epiweek: int,
    end_epiweek: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    url = (
        f"https://api.delphi.cmu.edu/epidata/{endpoint}/"
        f"?regions=nat&epiweeks={start_epiweek}-{end_epiweek}"
    )
    payload = fetch_json(url, source_name)
    rows = parse_delphi_response(payload, source_name)
    return payload, rows


def fetch_flusurv_source(
    locations: str,
    start_epiweek: int,
    end_epiweek: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    query = urllib.parse.urlencode(
        {
            "locations": locations,
            "epiweeks": f"{start_epiweek}-{end_epiweek}",
        }
    )
    url = (
        "https://api.delphi.cmu.edu/epidata/flusurv/"
        f"?{query}"
    )
    payload = fetch_json(url, "delphi_flusurv")
    rows = parse_delphi_response(
        payload,
        "delphi_flusurv",
        allow_empty_result=True,
    )
    return payload, rows


def metadata_column_names(metadata: dict[str, Any]) -> list[str]:
    names = []
    for column in metadata.get("columns", []):
        if not isinstance(column, dict):
            continue
        name = column.get("fieldName") or column.get("name")
        if name:
            names.append(str(name))
    return sorted(set(names))


def row_column_names(rows: list[dict[str, Any]]) -> list[str]:
    return sorted({str(key) for row in rows for key in row})


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(payload, output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")


def write_inventory(
    path: Path,
    rows: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=INVENTORY_COLUMNS,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def inventory_row(
    source_name: str,
    source_type: str,
    dataset_id_or_endpoint: str,
    intended_signal_role: str,
    raw_output_path: Path | None,
    rows: list[dict[str, Any]],
    columns: list[str],
    time_range_requested: str,
    date_accessed_utc: str,
    notes: str,
) -> dict[str, Any]:
    return {
        "source_name": source_name,
        "source_type": source_type,
        "dataset_id_or_endpoint": dataset_id_or_endpoint,
        "intended_signal_role": intended_signal_role,
        "raw_output_path": (
            raw_output_path.as_posix() if raw_output_path else ""
        ),
        "row_count": len(rows),
        "column_count": len(columns),
        "columns": ";".join(columns),
        "time_range_requested": time_range_requested,
        "date_accessed_utc": date_accessed_utc,
        "notes": notes,
    }


def ingest_sources(args: argparse.Namespace) -> list[dict[str, Any]]:
    validate_args(args)
    accessed_at = datetime.now(timezone.utc).isoformat()
    inventory: list[dict[str, Any]] = []
    buffered_start, buffered_end = epiweek_date_window(
        args.start_epiweek,
        args.end_epiweek,
    )
    date_filter_disabled = bool(
        getattr(args, "disable_socrata_date_filter", False)
    )
    requested_range = f"{args.start_epiweek}-{args.end_epiweek}"

    for source in SOCRATA_SOURCES:
        source_name = source["source_name"]
        dataset_id = source["dataset_id"]
        metadata = fetch_socrata_metadata(dataset_id, source_name)
        metadata_path = (
            args.output_dir / f"{source_name}_metadata.json"
        )
        write_json(metadata_path, metadata)

        metadata_columns = metadata_column_names(metadata)
        sample_rows: list[dict[str, Any]] = []
        if args.metadata_only:
            raw_path = metadata_path
            columns = metadata_columns
            notes = "Metadata fetched; sample rows skipped by --metadata-only."
        else:
            date_column = (
                None if date_filter_disabled else source["date_column"]
            )
            sample_rows = fetch_socrata_sample(
                dataset_id,
                source_name,
                args.socrata_limit,
                date_column=date_column,
                start_date=(
                    None if date_filter_disabled else buffered_start
                ),
                end_date=None if date_filter_disabled else buffered_end,
                order=None if date_filter_disabled else source["order"],
            )
            sample_path = args.output_dir / f"{source_name}_sample.json"
            write_json(sample_path, sample_rows)
            raw_path = sample_path
            columns = row_column_names(sample_rows) or metadata_columns
            notes = f"Metadata snapshot: {metadata_path.as_posix()}."
            if date_filter_disabled:
                notes += (
                    " Socrata date filter disabled; used limit-only sample "
                    "query."
                )
            else:
                notes += (
                    f" Applied date filter on {source['date_column']}: "
                    f"{buffered_start.isoformat()} through "
                    f"{buffered_end.isoformat()} (7-day buffers)."
                )
            if not sample_rows:
                notes += " Sample response was empty."

        inventory.append(
            inventory_row(
                source_name=source_name,
                source_type="socrata",
                dataset_id_or_endpoint=dataset_id,
                intended_signal_role=source["intended_signal_role"],
                raw_output_path=raw_path,
                rows=sample_rows,
                columns=columns,
                time_range_requested=requested_range,
                date_accessed_utc=accessed_at,
                notes=notes,
            )
        )

    for source in DELPHI_SOURCES:
        source_name = source["source_name"]
        endpoint = source["endpoint"]
        if args.metadata_only:
            inventory.append(
                inventory_row(
                    source_name=source_name,
                    source_type="delphi_epidata",
                    dataset_id_or_endpoint=endpoint,
                    intended_signal_role=source["intended_signal_role"],
                    raw_output_path=None,
                    rows=[],
                    columns=[],
                    time_range_requested=requested_range,
                    date_accessed_utc=accessed_at,
                    notes=(
                        "Data request skipped by --metadata-only; Delphi "
                        "endpoint has no separate metadata request here."
                    ),
                )
            )
            continue

        payload, delphi_rows = fetch_delphi_source(
            endpoint,
            source_name,
            args.start_epiweek,
            args.end_epiweek,
        )
        output_path = (
            args.output_dir
            / f"{source_name}_nat_{args.start_epiweek}_{args.end_epiweek}.json"
        )
        write_json(output_path, payload)
        notes = "National Delphi Epidata response."
        if not delphi_rows:
            notes += " Response contained no rows."
        inventory.append(
            inventory_row(
                source_name=source_name,
                source_type="delphi_epidata",
                dataset_id_or_endpoint=endpoint,
                intended_signal_role=source["intended_signal_role"],
                raw_output_path=output_path,
                rows=delphi_rows,
                columns=row_column_names(delphi_rows),
                time_range_requested=requested_range,
                date_accessed_utc=accessed_at,
                notes=notes,
            )
        )

    flusurv_name = FLUSURV_SOURCE["source_name"]
    flusurv_endpoint = FLUSURV_SOURCE["endpoint"]
    primary_locations = str(
        getattr(
            args,
            "flusurv_locations",
            DEFAULT_FLUSURV_LOCATIONS,
        )
    ).strip()
    fallback_locations = str(
        getattr(
            args,
            "flusurv_fallback_locations",
            DEFAULT_FLUSURV_FALLBACK_LOCATIONS,
        )
    ).strip()
    if args.metadata_only:
        inventory.append(
            inventory_row(
                source_name=flusurv_name,
                source_type="delphi_epidata",
                dataset_id_or_endpoint=flusurv_endpoint,
                intended_signal_role=(
                    FLUSURV_SOURCE["intended_signal_role"]
                ),
                raw_output_path=None,
                rows=[],
                columns=[],
                time_range_requested=requested_range,
                date_accessed_utc=accessed_at,
                notes=(
                    "Data request skipped by --metadata-only. Requested "
                    f"locations would be {primary_locations}."
                ),
            )
        )
    else:
        flusurv_payload, flusurv_rows = fetch_flusurv_source(
            primary_locations,
            args.start_epiweek,
            args.end_epiweek,
        )
        selected_locations = primary_locations
        fallback_used = False
        primary_was_empty = not flusurv_rows
        if primary_was_empty and fallback_locations:
            flusurv_payload, flusurv_rows = fetch_flusurv_source(
                fallback_locations,
                args.start_epiweek,
                args.end_epiweek,
            )
            selected_locations = fallback_locations
            fallback_used = True

        flusurv_path = (
            args.output_dir
            / f"delphi_flusurv_{args.start_epiweek}_{args.end_epiweek}.json"
        )
        write_json(flusurv_path, flusurv_payload)
        notes = (
            f"Requested locations: {primary_locations}. "
            f"Selected locations: {selected_locations}. "
            f"Fallback used: {fallback_used}."
        )
        if primary_was_empty:
            notes += " Primary network_all response was empty."
        if not flusurv_rows:
            notes += " Selected location response contained no rows."
        inventory.append(
            inventory_row(
                source_name=flusurv_name,
                source_type="delphi_epidata",
                dataset_id_or_endpoint=flusurv_endpoint,
                intended_signal_role=(
                    FLUSURV_SOURCE["intended_signal_role"]
                ),
                raw_output_path=flusurv_path,
                rows=flusurv_rows,
                columns=row_column_names(flusurv_rows),
                time_range_requested=requested_range,
                date_accessed_utc=accessed_at,
                notes=notes,
            )
        )

    write_inventory(args.inventory_output, inventory)
    return inventory


def main() -> int:
    args = parse_args()
    try:
        inventory = ingest_sources(args)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Influenza source ingestion failed: {exc}", file=sys.stderr)
        return 1

    print(f"Sources inventoried: {len(inventory)}")
    print(f"Raw output directory: {args.output_dir}")
    print(f"Inventory output: {args.inventory_output}")
    print(f"Metadata-only: {args.metadata_only}")
    print(
        "Socrata date filter enabled: "
        f"{not args.disable_socrata_date_filter}"
    )
    print("No evidence claims were built.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
