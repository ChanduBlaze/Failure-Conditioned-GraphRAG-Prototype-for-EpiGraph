import csv
import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_FILE = PROJECT_ROOT / "evals" / "eval_cases.json"
RESULTS_FILE = PROJECT_ROOT / "evals" / "results" / "kg_only_results.csv"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from eval_metrics import (
        compute_evidence_metrics,
        mean,
        normalize_list_of_strings,
    )
    from failure_case import get_failure_case
    from neo4j_retrieval import get_driver, retrieve_failure_candidates_from_neo4j
    from neo4j_validator import validate_candidate_neo4j
except ModuleNotFoundError as exc:
    print(f"Evaluation failed: missing Python dependency: {exc}", file=sys.stderr)
    raise SystemExit(1) from exc


EDGE_TYPE_RE = re.compile(r"\b[A-Z][A-Z0-9_]*\b")


def load_eval_cases():
    if not EVAL_FILE.exists():
        raise FileNotFoundError(f"Could not find {EVAL_FILE.relative_to(PROJECT_ROOT)}")

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if not isinstance(cases, list):
        raise ValueError("eval_cases.json must contain a JSON list.")

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


def make_support_subgraph_from_evidence(edge_types):
    return {
        "nodes": [],
        "edges": [{"type": edge_type} for edge_type in edge_types],
    }


def run_eval():
    eval_cases = load_eval_cases()
    failure_case = get_failure_case()
    driver = get_driver()

    try:
        candidates = retrieve_failure_candidates_from_neo4j(driver, failure_case)

        top_candidate = candidates[0] if candidates else None
        top_candidate_id = top_candidate["candidate_id"] if top_candidate else ""
        top3_candidate_ids = [candidate["candidate_id"] for candidate in candidates[:3]]

        top_candidate_validation = None
        top_predicted_edge_types = []

        if top_candidate:
            top_predicted_edge_types = extract_evidence_edge_types(
                top_candidate.get("evidence", [])
            )
            top_candidate["support_subgraph"] = make_support_subgraph_from_evidence(
                top_predicted_edge_types
            )
            top_candidate_validation = validate_candidate_neo4j(driver, top_candidate)

        rows = []

        for case in eval_cases:
            expected_candidate_id = case.get("expected_candidate_id", "")
            expected_edge_types = case.get("expected_evidence_edges", [])

            evidence_metrics = compute_evidence_metrics(
                top_predicted_edge_types,
                expected_edge_types,
            )

            rows.append(
                {
                    "case_id": case.get("id", ""),
                    "task_type": case.get("task_type", ""),
                    "expected_candidate_id": expected_candidate_id,
                    "predicted_top_candidate_id": top_candidate_id,
                    "top3_candidate_ids": ";".join(top3_candidate_ids),
                    "top1_correct": top_candidate_id == expected_candidate_id,
                    "top3_contains_expected": expected_candidate_id in top3_candidate_ids,
                    "expected_evidence_edges": ";".join(
                        normalize_list_of_strings(expected_edge_types)
                    ),
                    "predicted_evidence_edges": ";".join(top_predicted_edge_types),
                    "evidence_precision": evidence_metrics["evidence_precision"],
                    "evidence_recall": evidence_metrics["evidence_recall"],
                    "kg_validation_passed": (
                        top_candidate_validation["passed"]
                        if top_candidate_validation
                        else False
                    ),
                    "kg_validation_reasons": (
                        "; ".join(top_candidate_validation["reasons"])
                        if top_candidate_validation
                        else "no candidates retrieved"
                    ),
                }
            )

        return rows
    finally:
        driver.close()


def save_results(rows):
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "case_id",
        "task_type",
        "expected_candidate_id",
        "predicted_top_candidate_id",
        "top3_candidate_ids",
        "top1_correct",
        "top3_contains_expected",
        "expected_evidence_edges",
        "predicted_evidence_edges",
        "evidence_precision",
        "evidence_recall",
        "kg_validation_passed",
        "kg_validation_reasons",
    ]

    with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows):
    case_count = len(rows)
    top1_accuracy = mean([1.0 if row["top1_correct"] else 0.0 for row in rows])
    recall_at_3 = mean(
        [1.0 if row["top3_contains_expected"] else 0.0 for row in rows]
    )
    avg_evidence_precision = mean([row["evidence_precision"] for row in rows])
    avg_evidence_recall = mean([row["evidence_recall"] for row in rows])

    print("KG-only evaluation complete.")
    print("-" * 40)
    print(f"Cases: {case_count}")
    print(f"Top-1 accuracy: {top1_accuracy:.3f}")
    print(f"Recall@3: {recall_at_3:.3f}")
    print(f"Average evidence precision: {avg_evidence_precision:.3f}")
    print(f"Average evidence recall: {avg_evidence_recall:.3f}")
    print(f"Results saved to: {RESULTS_FILE.relative_to(PROJECT_ROOT)}")


def main():
    try:
        rows = run_eval()
        save_results(rows)
        print_summary(rows)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Evaluation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
