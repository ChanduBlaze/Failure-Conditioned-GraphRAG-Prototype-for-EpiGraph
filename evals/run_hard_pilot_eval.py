import csv
import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_FILE = PROJECT_ROOT / "evals" / "eval_cases_hard_pilot.json"
RESULTS_FILE = PROJECT_ROOT / "evals" / "results" / "hard_pilot_results.csv"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from eval_metrics import (
        compute_evidence_metrics,
        compute_missing_edge_metrics,
        mean,
        normalize_list_of_strings,
    )
    from failure_case import get_failure_case
    from neo4j_retrieval import get_driver, retrieve_failure_candidates_from_neo4j
except ModuleNotFoundError as exc:
    print(f"Hard pilot evaluation failed: missing Python dependency: {exc}", file=sys.stderr)
    raise SystemExit(1) from exc


EDGE_TYPE_RE = re.compile(r"\b[A-Z][A-Z0-9_]*\b")


def load_hard_cases():
    if not EVAL_FILE.exists():
        raise FileNotFoundError(f"Could not find {EVAL_FILE.relative_to(PROJECT_ROOT)}")

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if not isinstance(cases, list):
        raise ValueError("eval_cases_hard_pilot.json must contain a JSON list.")

    return cases


def extract_evidence_edge_types(evidence_items):
    edge_types = []

    for item in evidence_items or []:
        if not isinstance(item, str):
            continue

        match = EDGE_TYPE_RE.search(item)
        if match:
            edge_types.append(match.group(0))

    return edge_types


def build_candidate_lookup(candidates):
    lookup = {}

    for index, candidate in enumerate(candidates):
        candidate_id = candidate.get("candidate_id", "")
        lookup[candidate_id] = {
            "candidate": candidate,
            "rank": index + 1,
        }

    return lookup


def score_case(case, candidate_lookup):
    expected_candidate_id = case.get("expected_candidate_id", "")
    expected_present_edges = normalize_list_of_strings(
        case.get("expected_present_edges", [])
    )
    expected_missing_edges = normalize_list_of_strings(
        case.get("expected_missing_edges", [])
    )

    candidate_info = candidate_lookup.get(expected_candidate_id)
    candidate = candidate_info["candidate"] if candidate_info else None
    candidate_rank = candidate_info["rank"] if candidate_info else None

    present_edges = (
        extract_evidence_edge_types(candidate.get("evidence", []))
        if candidate
        else []
    )

    present_edge_metrics = compute_evidence_metrics(
        present_edges,
        expected_present_edges,
    )

    identified_missing_edges = [
        edge_type
        for edge_type in expected_missing_edges
        if edge_type not in set(present_edges)
    ]
    missing_edge_metrics = compute_missing_edge_metrics(
        identified_missing_edges=identified_missing_edges,
        expected_missing_edges=expected_missing_edges,
        mentioned_edge_types=present_edges,
    )

    expected_stronger_candidate_id = case.get("expected_stronger_candidate_id", "")
    stronger_info = candidate_lookup.get(expected_stronger_candidate_id)
    stronger_rank = stronger_info["rank"] if stronger_info else None
    if expected_stronger_candidate_id == expected_candidate_id:
        stronger_candidate_ranks_above = candidate_rank == 1
    else:
        stronger_candidate_ranks_above = (
            stronger_rank is not None
            and candidate_rank is not None
            and stronger_rank < candidate_rank
        )

    expected_weak_candidate_id = case.get("expected_weak_candidate_id", "")
    weak_info = candidate_lookup.get(expected_weak_candidate_id)
    weak_rank = weak_info["rank"] if weak_info else None
    weak_candidate_not_top = (
        weak_rank != 1
        if expected_weak_candidate_id and weak_rank is not None
        else ""
    )

    return {
        "case_id": case.get("id", ""),
        "task_type": case.get("task_type", ""),
        "expected_answer_type": case.get("expected_answer_type", ""),
        "expected_candidate_id": expected_candidate_id,
        "expected_candidate_found": candidate is not None,
        "expected_candidate_rank": candidate_rank or "",
        "expected_present_edges": ";".join(expected_present_edges),
        "retrieved_present_edges": ";".join(present_edges),
        "present_edge_precision": present_edge_metrics["evidence_precision"],
        "present_edge_recall": present_edge_metrics["evidence_recall"],
        "expected_missing_edges": ";".join(expected_missing_edges),
        "identified_missing_edges": ";".join(identified_missing_edges),
        "missing_edge_correct": missing_edge_metrics["missing_edge_correct"],
        "missing_edge_recall": missing_edge_metrics["missing_edge_recall"],
        "missing_edge_false_claim_count": missing_edge_metrics[
            "missing_edge_false_claim_count"
        ],
        "expected_stronger_candidate_id": expected_stronger_candidate_id,
        "expected_stronger_candidate_rank": stronger_rank or "",
        "stronger_candidate_ranks_above": stronger_candidate_ranks_above,
        "expected_weak_candidate_id": expected_weak_candidate_id,
        "expected_weak_candidate_rank": weak_rank or "",
        "weak_candidate_not_top": weak_candidate_not_top,
    }


def run_eval():
    hard_cases = load_hard_cases()
    failure_case = get_failure_case()
    driver = get_driver()

    try:
        candidates = retrieve_failure_candidates_from_neo4j(driver, failure_case)
    finally:
        driver.close()

    candidate_lookup = build_candidate_lookup(candidates)
    return [score_case(case, candidate_lookup) for case in hard_cases]


def save_results(rows):
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "case_id",
        "task_type",
        "expected_answer_type",
        "expected_candidate_id",
        "expected_candidate_found",
        "expected_candidate_rank",
        "expected_present_edges",
        "retrieved_present_edges",
        "present_edge_precision",
        "present_edge_recall",
        "expected_missing_edges",
        "identified_missing_edges",
        "missing_edge_correct",
        "missing_edge_recall",
        "missing_edge_false_claim_count",
        "expected_stronger_candidate_id",
        "expected_stronger_candidate_rank",
        "stronger_candidate_ranks_above",
        "expected_weak_candidate_id",
        "expected_weak_candidate_rank",
        "weak_candidate_not_top",
    ]

    with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows):
    stronger_values = [
        1.0 if row["stronger_candidate_ranks_above"] else 0.0
        for row in rows
        if row["expected_stronger_candidate_id"]
    ]
    weak_values = [
        1.0 if row["weak_candidate_not_top"] else 0.0
        for row in rows
        if row["expected_weak_candidate_id"]
    ]

    print("Hard pilot evaluation complete.")
    print("-" * 40)
    print(f"Cases: {len(rows)}")
    print(
        "Average present-edge precision: "
        f"{mean([row['present_edge_precision'] for row in rows]):.3f}"
    )
    print(
        "Average present-edge recall: "
        f"{mean([row['present_edge_recall'] for row in rows]):.3f}"
    )
    print(
        "Average missing-edge recall: "
        f"{mean([row['missing_edge_recall'] for row in rows]):.3f}"
    )
    print(
        "Missing-edge false claim count: "
        f"{sum(row['missing_edge_false_claim_count'] for row in rows)}"
    )
    print(
        "Stronger-candidate ranking accuracy: "
        f"{mean(stronger_values):.3f}"
    )
    print(
        "Weak-candidate rejection accuracy: "
        f"{mean(weak_values):.3f}"
    )
    print(f"Results saved to: {RESULTS_FILE.relative_to(PROJECT_ROOT)}")


def main():
    try:
        rows = run_eval()
        save_results(rows)
        print_summary(rows)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Hard pilot evaluation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
