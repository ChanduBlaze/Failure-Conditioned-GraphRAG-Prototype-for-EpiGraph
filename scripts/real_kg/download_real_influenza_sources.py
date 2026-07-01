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
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_OUTPUT_DIR = Path("data/real_raw/influenza")
DEFAULT_INVENTORY_OUTPUT = Path(
    "data/real_processed/real_influenza_source_inventory.csv"
)
DEFAULT_START_EPIWEEK = 202440
DEFAULT_END_EPIWEEK = 202520
DEFAULT_SOCRATA_LIMIT = 5000
HTTP_TIMEOUT_SECONDS = 60

SOCRATA_SOURCES = [
    {
        "source_name": "cdc_hospital_respiratory_admissions",
        "dataset_id": "vdzy-6i9v",
        "intended_signal_role": (
            "target signal candidate for U.S. influenza hospital "
            "admission/hospitalization burden"
        ),
    },
    {
        "source_name": "cdc_influenza_a_wastewater",
        "dataset_id": "ymmh-divb",
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
    return parser.parse_args()


def validate_epiweek(value: int, option_name: str) -> None:
    year, week = divmod(value, 100)
    if year < 2000 or not 1 <= week <= 53:
        raise ValueError(
            f"{option_name} must be a six-digit epiweek YYYYWW; got {value}."
        )


def validate_args(args: argparse.Namespace) -> None:
    validate_epiweek(args.start_epiweek, "--start-epiweek")
    validate_epiweek(args.end_epiweek, "--end-epiweek")
    if args.start_epiweek > args.end_epiweek:
        raise ValueError("--start-epiweek must not exceed --end-epiweek.")
    if args.socrata_limit < 1:
        raise ValueError("--socrata-limit must be at least 1.")


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
) -> list[dict[str, Any]]:
    url = (
        f"https://data.cdc.gov/resource/{dataset_id}.json"
        f"?$limit={limit}"
    )
    return parse_socrata_sample(fetch_json(url, source_name), source_name)


def parse_delphi_response(
    payload: Any,
    source_name: str,
) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError(
            f"Delphi response for {source_name} must be a JSON object."
        )
    result_code = payload.get("result")
    message = str(payload.get("message", "")).strip()
    if result_code != 1:
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
            sample_rows = fetch_socrata_sample(
                dataset_id,
                source_name,
                args.socrata_limit,
            )
            sample_path = args.output_dir / f"{source_name}_sample.json"
            write_json(sample_path, sample_rows)
            raw_path = sample_path
            columns = row_column_names(sample_rows) or metadata_columns
            notes = f"Metadata snapshot: {metadata_path.as_posix()}."
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
                time_range_requested="",
                date_accessed_utc=accessed_at,
                notes=notes,
            )
        )

    requested_range = f"{args.start_epiweek}-{args.end_epiweek}"
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
    print("No evidence claims were built.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
