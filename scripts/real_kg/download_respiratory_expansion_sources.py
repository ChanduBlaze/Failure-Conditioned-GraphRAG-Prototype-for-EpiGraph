"""
Download and inspect respiratory expansion source CSVs.

Inputs:
    data/real_processed/respiratory_expansion/respiratory_expansion_source_manifest.csv

Outputs:
    data/raw/respiratory_expansion/*.csv
    data/real_processed/respiratory_expansion/respiratory_expansion_schema_summary.csv

This script does not call an LLM.
"""

from __future__ import annotations

import csv
import json
import re
import sys
import urllib.request
from pathlib import Path


MANIFEST = Path(
    "data/real_processed/respiratory_expansion/"
    "respiratory_expansion_source_manifest.csv"
)
RAW_DIR = Path("data/raw/respiratory_expansion")
OUT_SUMMARY = Path(
    "data/real_processed/respiratory_expansion/"
    "respiratory_expansion_schema_summary.csv"
)


def slugify(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def download_csv(url: str, out_path: Path) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "KG-LLM-GraphRAG-thesis-data-script/1.0"
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            content = response.read()
        out_path.write_bytes(content)
        return "ok"
    except Exception as exc:
        return f"failed: {type(exc).__name__}: {exc}"


def inspect_csv(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size == 0:
        return {
            "row_count": 0,
            "column_count": 0,
            "columns": [],
            "sample_rows": [],
        }

    with path.open("r", newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        sample_rows = []
        row_count = 0

        for row in reader:
            row_count += 1
            if len(sample_rows) < 3:
                sample_rows.append(row)

    return {
        "row_count": row_count,
        "column_count": len(columns),
        "columns": columns,
        "sample_rows": sample_rows,
    }


def read_manifest() -> list[dict[str, str]]:
    if not MANIFEST.is_file():
        raise FileNotFoundError(f"Missing manifest: {MANIFEST}")

    with MANIFEST.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_SUMMARY.parent.mkdir(parents=True, exist_ok=True)

    manifest_rows = read_manifest()
    summary_rows = []

    for row in manifest_rows:
        source_name = row["source_name"]
        url = row["api_csv_url"]
        raw_path = RAW_DIR / f"{slugify(source_name)}.csv"

        print(f"Downloading: {source_name}")
        print(f"  URL: {url}")
        print(f"  Raw path: {raw_path}")

        status = download_csv(url, raw_path)
        print(f"  Status: {status}")

        info = inspect_csv(raw_path) if status == "ok" else {
            "row_count": 0,
            "column_count": 0,
            "columns": [],
            "sample_rows": [],
        }

        print(f"  Rows: {info['row_count']}")
        print(f"  Columns: {info['column_count']}")

        summary_rows.append(
            {
                "source_name": source_name,
                "disease_coverage": row.get("disease_coverage", ""),
                "role": row.get("role", ""),
                "api_csv_url": url,
                "raw_path": str(raw_path),
                "download_status": status,
                "row_count": str(info["row_count"]),
                "column_count": str(info["column_count"]),
                "columns_json": json.dumps(info["columns"], ensure_ascii=False),
                "sample_rows_json": json.dumps(info["sample_rows"], ensure_ascii=False),
                "notes": row.get("notes", ""),
            }
        )

    fieldnames = [
        "source_name",
        "disease_coverage",
        "role",
        "api_csv_url",
        "raw_path",
        "download_status",
        "row_count",
        "column_count",
        "columns_json",
        "sample_rows_json",
        "notes",
    ]

    with OUT_SUMMARY.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary_rows)

    print(f"\nWrote schema summary: {OUT_SUMMARY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
