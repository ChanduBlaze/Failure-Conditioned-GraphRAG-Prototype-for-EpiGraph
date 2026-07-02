"""
Score respiratory expansion model outputs.

Inputs:
    evals/respiratory_expansion/respiratory_expansion_cases.csv
    evals/respiratory_expansion/model_outputs/respiratory_expansion_model_outputs.csv

Expected output columns:
    case_id,method,answer

Outputs:
    evals/respiratory_expansion/respiratory_expansion_scored.csv
    evals/respiratory_expansion/respiratory_expansion_summary_by_method.csv
    evals/respiratory_expansion/respiratory_expansion_summary_by_case_type.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path


DEFAULT_CASES = Path("evals/respiratory_expansion/respiratory_expansion_cases.csv")
DEFAULT_OUTPUTS = Path("evals/respiratory_expansion/model_outputs/respiratory_expansion_model_outputs.csv")
DEFAULT_SCORED = Path("evals/respiratory_expansion/respiratory_expansion_scored.csv")
DEFAULT_METHOD_SUMMARY = Path("evals/respiratory_expansion/respiratory_expansion_summary_by_method.csv")
DEFAULT_CASE_TYPE_SUMMARY = Path("evals/respiratory_expansion/respiratory_expansion_summary_by_case_type.csv")


def normalize(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("?", "-")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def term_present(answer: str, term: str) -> bool:
    return normalize(term) in normalize(answer)


def forbidden_present_unnegated(answer: str, forbidden: str) -> bool:
    answer_norm = normalize(answer)
    forbidden_norm = normalize(forbidden)

    start = 0
    while True:
        index = answer_norm.find(forbidden_norm, start)
        if index == -1:
            return False

        window_start = max(0, index - 40)
        prefix = answer_norm[window_start:index]

        negation_markers = [
            "not ",
            "no ",
            "without ",
            "does not ",
            "doesn't ",
            "do not ",
            "cannot ",
            "should not ",
            "is not ",
            "are not ",
            "not a ",
            "not an ",
        ]

        if any(marker in prefix for marker in negation_markers):
            start = index + len(forbidden_norm)
            continue

        return True


def read_cases(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return {row["case_id"]: row for row in csv.DictReader(f)}


def read_outputs(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def score_row(case: dict[str, str], output: dict[str, str]) -> dict[str, str]:
    answer = output.get("answer", "")

    must_include = json.loads(case["must_include_terms_json"])
    must_not_include = json.loads(case["must_not_include_terms_json"])

    missing_required = [
        term for term in must_include
        if not term_present(answer, term)
    ]

    forbidden_terms_present = [
        term for term in must_not_include
        if forbidden_present_unnegated(answer, term)
    ]

    include_score = (
        (len(must_include) - len(missing_required)) / len(must_include)
        if must_include else 1.0
    )

    forbidden_ok = len(forbidden_terms_present) == 0
    overall_pass = include_score == 1.0 and forbidden_ok

    return {
        "case_id": output["case_id"],
        "method": output["method"],
        "case_type": case["case_type"],
        "include_score": f"{include_score:.3f}",
        "forbidden_ok": str(forbidden_ok),
        "overall_pass": str(overall_pass),
        "missing_required_terms_json": json.dumps(missing_required),
        "forbidden_terms_present_json": json.dumps(forbidden_terms_present),
        "answer_length_chars": str(len(answer)),
        "question": case["question"],
        "expected_answer": case["expected_answer"],
        "answer": answer,
    }


def summarize(rows: list[dict[str, str]], group_field: str) -> list[dict[str, str]]:
    groups = defaultdict(list)
    for row in rows:
        groups[row[group_field]].append(row)

    summary = []

    for key in sorted(groups):
        group = groups[key]
        n = len(group)

        pass_count = sum(1 for r in group if r["overall_pass"] == "True")
        forbidden_ok_count = sum(1 for r in group if r["forbidden_ok"] == "True")
        avg_include = sum(float(r["include_score"]) for r in group) / n

        summary.append(
            {
                group_field: key,
                "case_count": str(n),
                "overall_pass_rate": f"{pass_count / n:.3f}",
                "avg_include_score": f"{avg_include:.3f}",
                "forbidden_ok_rate": f"{forbidden_ok_count / n:.3f}",
                "failed_case_count": str(n - pass_count),
            }
        )

    return summary


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--outputs", type=Path, default=DEFAULT_OUTPUTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_SCORED)
    parser.add_argument("--method-summary", type=Path, default=DEFAULT_METHOD_SUMMARY)
    parser.add_argument("--case-type-summary", type=Path, default=DEFAULT_CASE_TYPE_SUMMARY)
    args = parser.parse_args()

    cases = read_cases(args.cases)
    outputs = read_outputs(args.outputs)

    scored = []
    missing_case_ids = []

    for output in outputs:
        case_id = output["case_id"]
        if case_id not in cases:
            missing_case_ids.append(case_id)
            continue
        scored.append(score_row(cases[case_id], output))

    write_csv(args.out, scored)
    write_csv(args.method_summary, summarize(scored, "method"))
    write_csv(args.case_type_summary, summarize(scored, "case_type"))

    print(f"Wrote scored outputs to {args.out}")
    print(f"Wrote method summary to {args.method_summary}")
    print(f"Wrote case-type summary to {args.case_type_summary}")

    print("\nSummary by method:")
    for row in summarize(scored, "method"):
        print(
            f"- {row['method']}: "
            f"pass_rate={row['overall_pass_rate']}, "
            f"avg_include={row['avg_include_score']}, "
            f"forbidden_ok={row['forbidden_ok_rate']}, "
            f"n={row['case_count']}"
        )

    if missing_case_ids:
        print("\nWARNING: outputs had unknown case_ids:")
        for case_id in missing_case_ids:
            print("-", case_id)


if __name__ == "__main__":
    main()
