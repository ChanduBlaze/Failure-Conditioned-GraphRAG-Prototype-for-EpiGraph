"""
Summarize scored empirical hard-pilot outputs.

Input:
    evals/empirical_hard_pilot/empirical_hard_pilot_scored.csv

Expected scored columns from score_empirical_hard_pilot_outputs.py:
    case_id, method, case_type, include_score, forbidden_ok, overall_pass,
    missing_required, forbidden_present, grading_focus, answer

Outputs:
    evals/empirical_hard_pilot/empirical_hard_pilot_summary_by_method.csv
    evals/empirical_hard_pilot/empirical_hard_pilot_summary_by_case_type.csv

This script does not call an LLM.
"""
import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Any


DEFAULT_SCORED = Path("evals/empirical_hard_pilot/empirical_hard_pilot_scored.csv")
DEFAULT_OUT_METHOD = Path("evals/empirical_hard_pilot/empirical_hard_pilot_summary_by_method.csv")
DEFAULT_OUT_CASE_TYPE = Path("evals/empirical_hard_pilot/empirical_hard_pilot_summary_by_case_type.csv")


METHOD_COLUMNS = [
    "method",
    "case_count",
    "overall_pass_rate",
    "avg_include_score",
    "forbidden_ok_rate",
    "failed_case_count",
    "forbidden_violation_count",
    "avg_answer_length_chars",
]

CASE_TYPE_COLUMNS = [
    "method",
    "case_type",
    "case_count",
    "overall_pass_rate",
    "avg_include_score",
    "forbidden_ok_rate",
    "failed_case_count",
    "forbidden_violation_count",
]


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def summarize_group(rows: list[dict[str, str]]) -> dict[str, Any]:
    case_count = len(rows)
    if case_count == 0:
        return {
            "case_count": 0,
            "overall_pass_rate": "0.000",
            "avg_include_score": "0.000",
            "forbidden_ok_rate": "0.000",
            "failed_case_count": 0,
            "forbidden_violation_count": 0,
            "avg_answer_length_chars": "0.0",
        }

    pass_count = sum(1 for row in rows if as_bool(row.get("overall_pass", "")))
    include_scores = [as_float(row.get("include_score", "0")) for row in rows]
    forbidden_ok_count = sum(1 for row in rows if as_float(row.get("forbidden_ok", "0")) == 1.0)
    forbidden_violation_count = sum(1 for row in rows if str(row.get("forbidden_present", "")).strip())
    answer_lengths = [len(row.get("answer", "")) for row in rows]

    return {
        "case_count": case_count,
        "overall_pass_rate": f"{pass_count / case_count:.3f}",
        "avg_include_score": f"{sum(include_scores) / case_count:.3f}",
        "forbidden_ok_rate": f"{forbidden_ok_count / case_count:.3f}",
        "failed_case_count": case_count - pass_count,
        "forbidden_violation_count": forbidden_violation_count,
        "avg_answer_length_chars": f"{sum(answer_lengths) / case_count:.1f}",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scored", default=str(DEFAULT_SCORED))
    parser.add_argument("--out-method", default=str(DEFAULT_OUT_METHOD))
    parser.add_argument("--out-case-type", default=str(DEFAULT_OUT_CASE_TYPE))
    args = parser.parse_args()

    scored_path = Path(args.scored)
    rows = read_csv_rows(scored_path)

    if not rows:
        raise ValueError(f"No rows found in scored file: {scored_path}")

    by_method: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_method_case_type: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        method = row.get("method", "")
        case_type = row.get("case_type", "")
        by_method[method].append(row)
        by_method_case_type[(method, case_type)].append(row)

    method_summary = []
    for method in sorted(by_method):
        summary = summarize_group(by_method[method])
        method_summary.append({
            "method": method,
            **{k: v for k, v in summary.items() if k != "avg_answer_length_chars"},
            "avg_answer_length_chars": summary["avg_answer_length_chars"],
        })

    case_type_summary = []
    for method, case_type in sorted(by_method_case_type):
        summary = summarize_group(by_method_case_type[(method, case_type)])
        case_type_summary.append({
            "method": method,
            "case_type": case_type,
            **{k: v for k, v in summary.items() if k != "avg_answer_length_chars"},
        })

    write_csv(Path(args.out_method), METHOD_COLUMNS, method_summary)
    write_csv(Path(args.out_case_type), CASE_TYPE_COLUMNS, case_type_summary)

    print(f"Wrote method summary: {args.out_method}")
    print(f"Wrote case-type summary: {args.out_case_type}")

    print("\nSummary by method:")
    for row in method_summary:
        print(
            f"- {row['method']}: "
            f"pass_rate={row['overall_pass_rate']}, "
            f"avg_include={row['avg_include_score']}, "
            f"forbidden_ok={row['forbidden_ok_rate']}, "
            f"n={row['case_count']}"
        )


if __name__ == "__main__":
    main()
