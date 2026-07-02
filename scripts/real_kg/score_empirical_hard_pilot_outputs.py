"""
Simple keyword/guardrail scorer for empirical influenza hard-pilot outputs.

Usage from repo root:
    python scripts/real_kg/score_empirical_hard_pilot_outputs.py \
        --cases evals/empirical_hard_pilot/real_empirical_hard_pilot_cases.csv \
        --outputs evals/empirical_hard_pilot/model_outputs.csv \
        --out evals/empirical_hard_pilot/empirical_hard_pilot_scored.csv

Expected outputs CSV columns:
    case_id, method, answer

This scorer is intentionally simple. It checks required and forbidden strings.
Use it as a first pass, then manually inspect borderline answers.

Updates:
- Reads CSV files with utf-8-sig so BOM headers do not break field names.
- Treats negated forbidden phrases like "not causal proof" as non-violations.
"""
import argparse
import csv
import re
from pathlib import Path


NEGATION_MARKERS = [
    "not",
    "no",
    "without",
    "does not",
    "do not",
    "did not",
    "doesn't",
    "don't",
    "didn't",
    "cannot",
    "can't",
    "is not",
    "are not",
    "was not",
    "were not",
    "not a",
    "not an",
    "not automatic",
    "not claiming",
    "does not claim",
    "do not claim",
    "doesn't claim",
]


def split_terms(value):
    if value is None:
        return []
    return [x.strip() for x in str(value).split(";") if x.strip()]


def normalize(s):
    return re.sub(r"\s+", " ", str(s).lower()).strip()


def contains_term(answer_norm, term):
    term_norm = normalize(term)
    if not term_norm:
        return False
    return term_norm in answer_norm


def is_negated_forbidden_occurrence(answer_norm, start_index):
    """
    Checks whether a forbidden phrase occurrence appears inside a local negation context.

    Example:
        "not causal proof" should not count as a causal-overclaim violation.
        "not a confirmed driver" should not count as a confirmed-driver violation.
    """
    prefix_window = answer_norm[max(0, start_index - 50):start_index].strip()

    for marker in NEGATION_MARKERS:
        marker_norm = normalize(marker)
        if re.search(rf"(^|\W){re.escape(marker_norm)}(\W|$)", prefix_window):
            return True

    return False


def forbidden_term_present(answer_norm, term):
    """
    Returns True only if the forbidden term appears in a non-negated context.
    """
    term_norm = normalize(term)
    if not term_norm:
        return False

    pattern = re.escape(term_norm)

    for match in re.finditer(pattern, answer_norm):
        if not is_negated_forbidden_occurrence(answer_norm, match.start()):
            return True

    return False


def read_csv_dicts(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--outputs", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    case_rows = read_csv_dicts(args.cases)
    output_rows = read_csv_dicts(args.outputs)

    cases = {}
    for row in case_rows:
        if "case_id" not in row:
            raise KeyError(f"Cases CSV is missing case_id column. Found columns: {list(row.keys())}")
        cases[row["case_id"]] = row

    rows = []
    for out in output_rows:
        if "case_id" not in out:
            raise KeyError(f"Outputs CSV is missing case_id column. Found columns: {list(out.keys())}")

        case_id = out["case_id"]
        if case_id not in cases:
            raise KeyError(f"Output case_id {case_id!r} was not found in cases file.")

        case = cases[case_id]
        answer = out.get("answer", "")
        ans_norm = normalize(answer)

        must_include = split_terms(case.get("must_include", ""))
        must_not_include = split_terms(case.get("must_not_include", ""))

        missing_required = [t for t in must_include if not contains_term(ans_norm, t)]
        forbidden_present = [t for t in must_not_include if forbidden_term_present(ans_norm, t)]

        required_hits = len(must_include) - len(missing_required)
        required_total = len(must_include)
        include_score = required_hits / required_total if required_total else 1.0
        forbidden_ok = 1.0 if not forbidden_present else 0.0
        overall_pass = include_score == 1.0 and forbidden_ok == 1.0

        rows.append({
            "case_id": case_id,
            "method": out.get("method", ""),
            "case_type": case.get("case_type", ""),
            "include_score": f"{include_score:.3f}",
            "forbidden_ok": f"{forbidden_ok:.0f}",
            "overall_pass": str(overall_pass),
            "missing_required": "; ".join(missing_required),
            "forbidden_present": "; ".join(forbidden_present),
            "grading_focus": case.get("grading_focus", ""),
            "answer": answer,
        })

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "case_id",
        "method",
        "case_type",
        "include_score",
        "forbidden_ok",
        "overall_pass",
        "missing_required",
        "forbidden_present",
        "grading_focus",
        "answer",
    ]

    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote scored outputs to {args.out}")


if __name__ == "__main__":
    main()
