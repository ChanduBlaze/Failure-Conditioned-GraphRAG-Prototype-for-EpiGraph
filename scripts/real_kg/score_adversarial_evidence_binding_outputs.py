"""
Score adversarial evidence-binding outputs.

Input output CSV columns:
    case_id,method,answer

This script does not call an LLM.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


DEFAULT_CASES = Path("evals/adversarial_evidence_binding/adversarial_evidence_binding_cases.csv")
DEFAULT_OUTPUTS = Path("evals/adversarial_evidence_binding/model_outputs/adversarial_evidence_binding_model_outputs.csv")
DEFAULT_OUT = Path("evals/adversarial_evidence_binding/adversarial_evidence_binding_scored.csv")


NEGATION_PATTERNS = [
    "not {term}",
    "no {term}",
    "not a {term}",
    "not an {term}",
    "does not {term}",
    "should not {term}",
    "must not {term}",
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def parse_terms(raw: str) -> list[str]:
    if not raw:
        return []
    return [str(term) for term in json.loads(raw)]


def contains_term(answer_norm: str, term: str) -> bool:
    return normalize(term) in answer_norm


def forbidden_present(answer_norm: str, term: str) -> bool:
    term_norm = normalize(term)

    if term_norm not in answer_norm:
        return False

    for pattern in NEGATION_PATTERNS:
        negated = pattern.format(term=term_norm)
        if negated in answer_norm:
            return False

    return True


def read_cases(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return {row["case_id"]: row for row in csv.DictReader(f)}


def read_outputs(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def score_row(case_row: dict[str, str], output_row: dict[str, str]) -> dict[str, str]:
    answer = output_row.get("answer", "")
    answer_norm = normalize(answer)

    include_terms = parse_terms(case_row["must_include_terms"])
    forbidden_terms = parse_terms(case_row["must_not_include_terms"])

    include_hits = [
        term for term in include_terms if contains_term(answer_norm, term)
    ]
    include_missing = [
        term for term in include_terms if not contains_term(answer_norm, term)
    ]
    forbidden_hits = [
        term for term in forbidden_terms if forbidden_present(answer_norm, term)
    ]

    include_score = (
        len(include_hits) / len(include_terms)
        if include_terms
        else 1.0
    )
    forbidden_ok = len(forbidden_hits) == 0
    overall_pass = include_score == 1.0 and forbidden_ok

    return {
        "case_id": output_row["case_id"],
        "method": output_row["method"],
        "case_type": case_row["case_type"],
        "include_score": f"{include_score:.3f}",
        "forbidden_ok": "1" if forbidden_ok else "0",
        "overall_pass": "1" if overall_pass else "0",
        "missing_required_terms": json.dumps(include_missing, ensure_ascii=False),
        "forbidden_terms_present": json.dumps(forbidden_hits, ensure_ascii=False),
        "answer_length_chars": str(len(answer)),
        "answer": answer,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--outputs", type=Path, default=DEFAULT_OUTPUTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    cases = read_cases(args.cases)
    outputs = read_outputs(args.outputs)

    scored = []
    for output_row in outputs:
        case_id = output_row["case_id"]
        if case_id not in cases:
            raise KeyError(f"Unknown case_id in outputs: {case_id}")
        scored.append(score_row(cases[case_id], output_row))

    args.out.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "case_id",
        "method",
        "case_type",
        "include_score",
        "forbidden_ok",
        "overall_pass",
        "missing_required_terms",
        "forbidden_terms_present",
        "answer_length_chars",
        "answer",
    ]

    with args.out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(scored)

    by_method: dict[str, list[dict[str, str]]] = {}
    for row in scored:
        by_method.setdefault(row["method"], []).append(row)

    print(f"Wrote scored outputs to {args.out}")
    print("Summary by method:")
    for method, rows in sorted(by_method.items()):
        n = len(rows)
        pass_rate = sum(float(row["overall_pass"]) for row in rows) / n
        include_avg = sum(float(row["include_score"]) for row in rows) / n
        forbidden_ok = sum(float(row["forbidden_ok"]) for row in rows) / n
        print(
            f"- {method}: pass_rate={pass_rate:.3f}, "
            f"avg_include={include_avg:.3f}, forbidden_ok={forbidden_ok:.3f}, n={n}"
        )


if __name__ == "__main__":
    main()
