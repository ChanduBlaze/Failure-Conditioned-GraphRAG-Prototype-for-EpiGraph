
"""
Score real respiratory retrieval-stress outputs.

This scorer uses the original respiratory expansion cases, but scores outputs from:
- resp_exp_text_rag_top1
- resp_exp_text_rag_top2
- resp_exp_graphrag_target_neighborhood

It also joins retrieval coverage diagnostics so answer failures can be interpreted
against retrieved-context coverage.

This script does not call an LLM.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path


DEFAULT_CASES = Path("evals/respiratory_expansion/respiratory_expansion_cases.csv")
DEFAULT_OUTPUTS = Path("evals/respiratory_expansion/retrieval_stress/model_outputs/respiratory_retrieval_stress_model_outputs.csv")
DEFAULT_RETRIEVAL_LOG = Path("evals/respiratory_expansion/retrieval_stress/respiratory_retrieval_stress_retrieval_log.csv")

DEFAULT_SCORED = Path("evals/respiratory_expansion/retrieval_stress/respiratory_retrieval_stress_scored.csv")
DEFAULT_METHOD_SUMMARY = Path("evals/respiratory_expansion/retrieval_stress/respiratory_retrieval_stress_summary_by_method.csv")
DEFAULT_CASE_TYPE_SUMMARY = Path("evals/respiratory_expansion/retrieval_stress/respiratory_retrieval_stress_summary_by_case_type.csv")
DEFAULT_COVERAGE_SUMMARY = Path("evals/respiratory_expansion/retrieval_stress/respiratory_retrieval_stress_summary_by_retrieval_coverage.csv")


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

        window_start = max(0, index - 45)
        prefix = answer_norm[window_start:index]

        negation_markers = [
            "not ",
            "not a ",
            "not an ",
            "no ",
            "does not ",
            "do not ",
            "did not ",
            "cannot ",
            "can't ",
            "without ",
            "unvalidated ",
            "not validated ",
            "not proof of ",
            "does not prove ",
            "do not prove ",
        ]

        if any(marker in prefix for marker in negation_markers):
            start = index + len(forbidden_norm)
            continue

        return True


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def score_row(case: dict[str, str], output: dict[str, str], retrieval: dict[str, str] | None) -> dict[str, str]:
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

    retrieval = retrieval or {}

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
        "retrieval_coverage": retrieval.get("coverage", ""),
        "retrieval_all_required_terms_present": retrieval.get("all_required_terms_present", ""),
        "retrieval_missing_terms_json": retrieval.get("missing_terms_json", ""),
        "retrieved_chunk_ids": retrieval.get("retrieved_chunk_ids", ""),
        "retrieved_chunk_titles": retrieval.get("retrieved_chunk_titles", ""),
        "question": case["question"],
        "expected_answer": case["expected_answer"],
        "answer": answer,
    }


def summarize(rows: list[dict[str, str]], group_fields: list[str]) -> list[dict[str, str]]:
    groups = defaultdict(list)
    for row in rows:
        key = tuple(row[field] for field in group_fields)
        groups[key].append(row)

    summary = []
    for key in sorted(groups):
        group = groups[key]
        n = len(group)

        pass_count = sum(1 for r in group if r["overall_pass"] == "True")
        forbidden_ok_count = sum(1 for r in group if r["forbidden_ok"] == "True")
        avg_include = sum(float(r["include_score"]) for r in group) / n

        coverage_values = [
            float(r["retrieval_coverage"])
            for r in group
            if str(r.get("retrieval_coverage", "")).strip() != ""
        ]

        retrieval_full_count = sum(
            1 for r in group
            if r.get("retrieval_all_required_terms_present") == "True"
        )

        row = {
            field: key[i]
            for i, field in enumerate(group_fields)
        }

        row.update({
            "case_count": str(n),
            "overall_pass_rate": f"{pass_count / n:.3f}",
            "avg_include_score": f"{avg_include:.3f}",
            "forbidden_ok_rate": f"{forbidden_ok_count / n:.3f}",
            "failed_case_count": str(n - pass_count),
            "avg_retrieval_coverage": f"{(sum(coverage_values) / len(coverage_values)):.3f}" if coverage_values else "",
            "retrieval_full_coverage_rate": f"{retrieval_full_count / n:.3f}",
        })

        summary.append(row)

    return summary


def coverage_bucket(row: dict[str, str]) -> str:
    if row.get("retrieval_all_required_terms_present") == "True":
        return "retrieval_full_coverage"

    coverage = row.get("retrieval_coverage", "")
    if coverage == "":
        return "retrieval_unknown"

    value = float(coverage)
    if value >= 0.90:
        return "retrieval_partial_ge_0.90"
    if value >= 0.75:
        return "retrieval_partial_0.75_to_0.89"
    return "retrieval_partial_lt_0.75"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--outputs", type=Path, default=DEFAULT_OUTPUTS)
    parser.add_argument("--retrieval-log", type=Path, default=DEFAULT_RETRIEVAL_LOG)
    parser.add_argument("--out", type=Path, default=DEFAULT_SCORED)
    parser.add_argument("--method-summary", type=Path, default=DEFAULT_METHOD_SUMMARY)
    parser.add_argument("--case-type-summary", type=Path, default=DEFAULT_CASE_TYPE_SUMMARY)
    parser.add_argument("--coverage-summary", type=Path, default=DEFAULT_COVERAGE_SUMMARY)
    args = parser.parse_args()

    cases = {row["case_id"]: row for row in load_csv(args.cases)}
    outputs = load_csv(args.outputs)
    retrieval_rows = load_csv(args.retrieval_log)

    retrieval_by_key = {
        (row["case_id"], row["method"]): row
        for row in retrieval_rows
    }

    expected_columns = ["case_id", "method", "answer"]
    if outputs:
        actual_columns = list(outputs[0].keys())
        if actual_columns != expected_columns:
            raise ValueError(
                f"Expected output columns {expected_columns}, got {actual_columns}"
            )

    scored = []
    missing_case_ids = []

    for output in outputs:
        case_id = output["case_id"]
        method = output["method"]

        if case_id not in cases:
            missing_case_ids.append(case_id)
            continue

        retrieval = retrieval_by_key.get((case_id, method))
        scored.append(score_row(cases[case_id], output, retrieval))

    for row in scored:
        row["retrieval_coverage_bucket"] = coverage_bucket(row)

    write_csv(args.out, scored)
    write_csv(args.method_summary, summarize(scored, ["method"]))
    write_csv(args.case_type_summary, summarize(scored, ["method", "case_type"]))
    write_csv(args.coverage_summary, summarize(scored, ["method", "retrieval_coverage_bucket"]))

    print(f"Wrote scored outputs to {args.out}")
    print(f"Wrote method summary to {args.method_summary}")
    print(f"Wrote case-type summary to {args.case_type_summary}")
    print(f"Wrote retrieval coverage summary to {args.coverage_summary}")

    print("\nSummary by method:")
    for row in summarize(scored, ["method"]):
        print(
            f"- {row['method']}: "
            f"pass_rate={row['overall_pass_rate']}, "
            f"avg_include={row['avg_include_score']}, "
            f"forbidden_ok={row['forbidden_ok_rate']}, "
            f"avg_retrieval_coverage={row['avg_retrieval_coverage']}, "
            f"retrieval_full_coverage={row['retrieval_full_coverage_rate']}, "
            f"n={row['case_count']}"
        )

    if missing_case_ids:
        print("\nWARNING: outputs had unknown case_ids:")
        for case_id in missing_case_ids:
            print(f"- {case_id}")


if __name__ == "__main__":
    main()
