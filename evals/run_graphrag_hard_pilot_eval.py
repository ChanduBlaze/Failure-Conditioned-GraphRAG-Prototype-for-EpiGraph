import csv
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_FILE = PROJECT_ROOT / "evals" / "eval_cases_hard_pilot.json"
RESULTS_FILE = PROJECT_ROOT / "evals" / "results" / "graphrag_hard_pilot_results.csv"

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
    from llm_reasoner import (
        MAX_OUTPUT_TOKENS,
        MODEL_NAME,
        extract_json_text,
        get_client,
    )
    from neo4j_retrieval import (
        get_driver,
        get_top_candidate_support_subgraph,
        retrieve_failure_candidates_from_neo4j,
    )
except ModuleNotFoundError as exc:
    print(
        f"GraphRAG hard pilot evaluation failed: missing dependency: {exc}",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


REQUIRED_LLM_KEYS = {
    "predicted_candidate_id",
    "predicted_candidate_name",
    "explanation",
    "mentioned_evidence_edges",
    "identified_missing_edges",
    "rejected_candidate_ids",
    "weak_candidate_ids",
}


def load_hard_cases():
    if not EVAL_FILE.exists():
        raise FileNotFoundError(f"Could not find {EVAL_FILE.relative_to(PROJECT_ROOT)}")

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if not isinstance(cases, list):
        raise ValueError("eval_cases_hard_pilot.json must contain a JSON list.")

    return cases


def fetch_candidate_context(driver, failure_case):
    candidates = retrieve_failure_candidates_from_neo4j(driver, failure_case)

    if not candidates:
        raise ValueError("No Neo4j candidates found. Cannot run hard pilot eval.")

    candidate_context = []

    for rank, candidate in enumerate(candidates, start=1):
        support_subgraph = get_top_candidate_support_subgraph(
            driver,
            candidate["candidate_id"],
            failure_case,
        )
        support_subgraph = support_subgraph or {"nodes": [], "edges": []}

        candidate_context.append(
            {
                "rank": rank,
                "candidate_id": candidate.get("candidate_id", ""),
                "candidate_name": candidate.get("candidate_name", ""),
                "score": candidate.get("score"),
                "ranking_evidence": candidate.get("evidence", []),
                "support_subgraph_nodes": support_subgraph.get("nodes", []),
                "support_subgraph_edges": support_subgraph.get("edges", []),
            }
        )

    return candidate_context


def build_prompt(failure_case, hard_case, candidate_context):
    payload = {
        "failure_case": failure_case,
        "question": hard_case["question"],
        "retrieved_candidate_rankings": candidate_context,
    }

    return f"""
You are evaluating a Neo4j-backed GraphRAG method for epidemiological model revision.

Use only the retrieved graph evidence in the input:
- failure case
- hard pilot question
- candidate rankings
- candidate evidence lists
- support-subgraph-style nodes and edges when available

These hard pilot cases may ask about candidates that are not ranked first. Reason
about the specific candidate in the question, identify which evidence is present,
and identify which expected graph relationships are missing.

Do not use outside knowledge.
Do not invent datasets, nodes, edges, mechanisms, or candidate IDs.

Input:
{json.dumps(payload, indent=2)}

Return valid JSON only.
Do not use markdown fences.
Do not add text before or after the JSON.

Use exactly this schema:
{{
  "predicted_candidate_id": "...",
  "predicted_candidate_name": "...",
  "explanation": "...",
  "mentioned_evidence_edges": [],
  "identified_missing_edges": [],
  "rejected_candidate_ids": [],
  "weak_candidate_ids": []
}}

For mentioned_evidence_edges and identified_missing_edges, use relationship type
names such as "LEADING_INDICATOR_FOR" or "IMPORTATION_LINK".
""".strip()


def validate_llm_output(data):
    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object.")

    missing = REQUIRED_LLM_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"LLM JSON is missing required keys: {sorted(missing)}")

    for key in ["predicted_candidate_id", "predicted_candidate_name", "explanation"]:
        if not isinstance(data.get(key), str):
            raise ValueError(f"LLM JSON key '{key}' must be a string.")

    for key in [
        "mentioned_evidence_edges",
        "identified_missing_edges",
        "rejected_candidate_ids",
        "weak_candidate_ids",
    ]:
        if not isinstance(data.get(key), list):
            raise ValueError(f"LLM JSON key '{key}' must be a list.")

    return True


def run_llm_case(client, failure_case, hard_case, candidate_context):
    response = client.responses.create(
        model=MODEL_NAME,
        instructions=(
            "You are a careful epidemiological reasoning assistant. "
            "Use only the retrieved Neo4j graph evidence provided. "
            "Return valid JSON only."
        ),
        input=build_prompt(failure_case, hard_case, candidate_context),
        reasoning={"effort": "low"},
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    raw_text = response.output_text
    if not raw_text or not raw_text.strip():
        raise ValueError(f"Model returned no visible text for case {hard_case['id']}.")

    parsed = json.loads(extract_json_text(raw_text))
    validate_llm_output(parsed)

    return parsed, raw_text


def score_case(hard_case, llm_output, raw_text, candidate_context):
    expected_candidate_id = hard_case.get("expected_candidate_id", "")
    expected_present_edges = normalize_list_of_strings(
        hard_case.get("expected_present_edges", [])
    )
    expected_missing_edges = normalize_list_of_strings(
        hard_case.get("expected_missing_edges", [])
    )
    mentioned_edges = normalize_list_of_strings(
        llm_output.get("mentioned_evidence_edges", [])
    )
    identified_missing_edges = normalize_list_of_strings(
        llm_output.get("identified_missing_edges", [])
    )
    rejected_candidate_ids = normalize_list_of_strings(
        llm_output.get("rejected_candidate_ids", [])
    )
    weak_candidate_ids = normalize_list_of_strings(
        llm_output.get("weak_candidate_ids", [])
    )

    evidence_metrics = compute_evidence_metrics(
        mentioned_edges,
        expected_present_edges,
    )
    missing_edge_metrics = compute_missing_edge_metrics(
        identified_missing_edges,
        expected_missing_edges,
        mentioned_edge_types=mentioned_edges,
    )

    expected_stronger_candidate_id = hard_case.get("expected_stronger_candidate_id", "")
    stronger_candidate_identified = (
        expected_stronger_candidate_id == llm_output["predicted_candidate_id"]
        or expected_stronger_candidate_id in raw_text
    )

    expected_weak_candidate_id = hard_case.get("expected_weak_candidate_id", "")
    weak_candidate_rejected = (
        expected_weak_candidate_id in rejected_candidate_ids
        or expected_weak_candidate_id in weak_candidate_ids
        if expected_weak_candidate_id
        else ""
    )

    return {
        "case_id": hard_case.get("id", ""),
        "task_type": hard_case.get("task_type", ""),
        "expected_answer_type": hard_case.get("expected_answer_type", ""),
        "expected_candidate_id": expected_candidate_id,
        "predicted_candidate_id": llm_output["predicted_candidate_id"],
        "predicted_candidate_name": llm_output["predicted_candidate_name"],
        "candidate_correct": llm_output["predicted_candidate_id"]
        == expected_candidate_id,
        "retrieved_candidate_ids": ";".join(
            candidate["candidate_id"] for candidate in candidate_context
        ),
        "expected_present_edges": ";".join(expected_present_edges),
        "mentioned_evidence_edges": ";".join(mentioned_edges),
        "present_edge_precision": evidence_metrics["evidence_precision"],
        "present_edge_recall": evidence_metrics["evidence_recall"],
        "expected_missing_edges": ";".join(expected_missing_edges),
        "identified_missing_edges": ";".join(identified_missing_edges),
        "missing_edge_recall": missing_edge_metrics["missing_edge_recall"],
        "missing_edge_false_claim_count": missing_edge_metrics[
            "missing_edge_false_claim_count"
        ],
        "expected_stronger_candidate_id": expected_stronger_candidate_id,
        "stronger_candidate_identified": stronger_candidate_identified,
        "expected_weak_candidate_id": expected_weak_candidate_id,
        "rejected_candidate_ids": ";".join(rejected_candidate_ids),
        "weak_candidate_ids": ";".join(weak_candidate_ids),
        "weak_candidate_rejected": weak_candidate_rejected,
        "explanation": llm_output["explanation"],
        "raw_response": raw_text,
    }


def run_eval():
    hard_cases = load_hard_cases()
    failure_case = get_failure_case()
    driver = get_driver()
    client = get_client()
    rows = []

    try:
        candidate_context = fetch_candidate_context(driver, failure_case)

        for hard_case in hard_cases:
            llm_output, raw_text = run_llm_case(
                client,
                failure_case,
                hard_case,
                candidate_context,
            )
            rows.append(score_case(hard_case, llm_output, raw_text, candidate_context))
    finally:
        driver.close()

    return rows


def save_results(rows):
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "case_id",
        "task_type",
        "expected_answer_type",
        "expected_candidate_id",
        "predicted_candidate_id",
        "predicted_candidate_name",
        "candidate_correct",
        "retrieved_candidate_ids",
        "expected_present_edges",
        "mentioned_evidence_edges",
        "present_edge_precision",
        "present_edge_recall",
        "expected_missing_edges",
        "identified_missing_edges",
        "missing_edge_recall",
        "missing_edge_false_claim_count",
        "expected_stronger_candidate_id",
        "stronger_candidate_identified",
        "expected_weak_candidate_id",
        "rejected_candidate_ids",
        "weak_candidate_ids",
        "weak_candidate_rejected",
        "explanation",
        "raw_response",
    ]

    with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows):
    stronger_values = [
        1.0 if row["stronger_candidate_identified"] else 0.0
        for row in rows
        if row["expected_stronger_candidate_id"]
    ]
    weak_values = [
        1.0 if row["weak_candidate_rejected"] else 0.0
        for row in rows
        if row["expected_weak_candidate_id"]
    ]

    print("GraphRAG hard pilot evaluation complete.")
    print("-" * 40)
    print(f"Cases: {len(rows)}")
    print(
        "Candidate accuracy: "
        f"{mean([1.0 if row['candidate_correct'] else 0.0 for row in rows]):.3f}"
    )
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
        "Stronger-candidate identification accuracy: "
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
        print(f"GraphRAG hard pilot evaluation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
