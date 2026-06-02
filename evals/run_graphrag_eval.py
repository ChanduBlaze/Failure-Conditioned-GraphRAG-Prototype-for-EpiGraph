import csv
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_FILE = PROJECT_ROOT / "evals" / "eval_cases.json"
RESULTS_FILE = PROJECT_ROOT / "evals" / "results" / "graphrag_results.csv"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from eval_metrics import (
        compute_evidence_metrics,
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
    from neo4j_validator import validate_candidate_neo4j
except ModuleNotFoundError as exc:
    print(f"Evaluation failed: missing Python dependency: {exc}", file=sys.stderr)
    raise SystemExit(1) from exc


REQUIRED_LLM_KEYS = {
    "predicted_candidate_id",
    "predicted_candidate_name",
    "explanation",
    "proposed_edit_type",
    "mentioned_evidence_edges",
}


def load_eval_cases():
    if not EVAL_FILE.exists():
        raise FileNotFoundError(f"Could not find {EVAL_FILE.relative_to(PROJECT_ROOT)}")

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if not isinstance(cases, list):
        raise ValueError("eval_cases.json must contain a JSON list.")

    return cases


def build_prompt(eval_case, failure_case, candidates, top_candidate, validation_result):
    support_subgraph = top_candidate.get("support_subgraph", {"nodes": [], "edges": []})

    prompt_payload = {
        "failure_case": failure_case,
        "question": eval_case["question"],
        "top_3_candidate_rankings": [
            {
                "rank": index + 1,
                "candidate_id": candidate.get("candidate_id", ""),
                "candidate_name": candidate.get("candidate_name", ""),
                "score": candidate.get("score"),
                "ranking_evidence": candidate.get("evidence", []),
            }
            for index, candidate in enumerate(candidates[:3])
        ],
        "top_candidate_support_subgraph": {
            "nodes": support_subgraph.get("nodes", []),
            "edges": support_subgraph.get("edges", []),
        },
        "top_candidate_validation": validation_result,
    }

    return f"""
You are evaluating a Neo4j-backed GraphRAG method for epidemiological model revision.

Use only the retrieved graph evidence in the input:
- failure case
- eval question
- top 3 candidate rankings
- top candidate support subgraph nodes
- top candidate support subgraph edges
- top candidate validation result

Do not use outside knowledge.
Do not invent datasets, nodes, edges, or mechanisms.
If the retrieved evidence is insufficient, say so in the explanation while still
returning the best supported candidate from the provided ranking.

Input:
{json.dumps(prompt_payload, indent=2)}

Return valid JSON only.
Do not use markdown fences.
Do not add text before or after the JSON.

Use exactly this schema:
{{
  "predicted_candidate_id": "...",
  "predicted_candidate_name": "...",
  "explanation": "...",
  "proposed_edit_type": "...",
  "mentioned_evidence_edges": []
}}

For mentioned_evidence_edges, return only relationship type names that are explicitly
used in your explanation, such as "LEADING_INDICATOR_FOR".
""".strip()


def validate_llm_output(data):
    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object.")

    missing = REQUIRED_LLM_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"LLM JSON is missing required keys: {sorted(missing)}")

    for key in REQUIRED_LLM_KEYS - {"mentioned_evidence_edges"}:
        value = data.get(key)
        if not isinstance(value, str):
            raise ValueError(f"LLM JSON key '{key}' must be a string.")

    if not isinstance(data["mentioned_evidence_edges"], list):
        raise ValueError("LLM JSON key 'mentioned_evidence_edges' must be a list.")

    return True


def run_llm_case(client, eval_case, failure_case, candidates, top_candidate, validation_result):
    prompt = build_prompt(
        eval_case,
        failure_case,
        candidates,
        top_candidate,
        validation_result,
    )

    response = client.responses.create(
        model=MODEL_NAME,
        instructions=(
            "You are a careful epidemiological reasoning assistant. "
            "Use only the retrieved Neo4j graph evidence provided. "
            "Return valid JSON only."
        ),
        input=prompt,
        reasoning={"effort": "low"},
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    raw_text = response.output_text
    if not raw_text or not raw_text.strip():
        raise ValueError(f"Model returned no visible text for case {eval_case['id']}.")

    parsed = json.loads(extract_json_text(raw_text))
    validate_llm_output(parsed)

    return parsed, raw_text


def prepare_graph_context(driver, failure_case):
    candidates = retrieve_failure_candidates_from_neo4j(driver, failure_case)

    if not candidates:
        raise ValueError("No Neo4j candidates found. Cannot run GraphRAG evaluation.")

    top_candidate = candidates[0]
    support_subgraph = get_top_candidate_support_subgraph(
        driver,
        top_candidate["candidate_id"],
        failure_case,
    )
    top_candidate["support_subgraph"] = support_subgraph or {"nodes": [], "edges": []}

    validation_result = validate_candidate_neo4j(driver, top_candidate)

    return candidates, top_candidate, validation_result


def run_eval():
    eval_cases = load_eval_cases()
    failure_case = get_failure_case()
    driver = get_driver()
    client = get_client()
    rows = []

    try:
        candidates, top_candidate, validation_result = prepare_graph_context(
            driver,
            failure_case,
        )

        support_edges = [
            edge.get("type", "")
            for edge in top_candidate["support_subgraph"].get("edges", [])
            if edge.get("type")
        ]

        for eval_case in eval_cases:
            llm_output, raw_text = run_llm_case(
                client,
                eval_case,
                failure_case,
                candidates,
                top_candidate,
                validation_result,
            )

            expected_candidate_id = eval_case.get("expected_candidate_id", "")
            predicted_candidate_id = llm_output["predicted_candidate_id"]
            expected_edge_types = eval_case.get("expected_evidence_edges", [])
            mentioned_edge_types = normalize_list_of_strings(
                llm_output["mentioned_evidence_edges"]
            )

            evidence_metrics = compute_evidence_metrics(
                mentioned_edge_types,
                expected_edge_types,
            )

            rows.append(
                {
                    "case_id": eval_case.get("id", ""),
                    "task_type": eval_case.get("task_type", ""),
                    "expected_candidate_id": expected_candidate_id,
                    "retrieved_top_candidate_id": top_candidate["candidate_id"],
                    "predicted_candidate_id": predicted_candidate_id,
                    "predicted_candidate_name": llm_output["predicted_candidate_name"],
                    "top1_correct": predicted_candidate_id == expected_candidate_id,
                    "top3_candidate_ids": ";".join(
                        candidate["candidate_id"] for candidate in candidates[:3]
                    ),
                    "expected_evidence_edges": ";".join(
                        normalize_list_of_strings(expected_edge_types)
                    ),
                    "support_subgraph_edges": ";".join(support_edges),
                    "mentioned_evidence_edges": ";".join(mentioned_edge_types),
                    "evidence_precision": evidence_metrics["evidence_precision"],
                    "evidence_recall": evidence_metrics["evidence_recall"],
                    "hallucinated_evidence_count": evidence_metrics[
                        "hallucinated_evidence_count"
                    ],
                    "kg_validation_passed": validation_result["passed"],
                    "kg_validation_reasons": "; ".join(validation_result["reasons"]),
                    "proposed_edit_type": llm_output["proposed_edit_type"],
                    "explanation": llm_output["explanation"],
                    "raw_response": raw_text,
                }
            )
    finally:
        driver.close()

    return rows


def save_results(rows):
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "case_id",
        "task_type",
        "expected_candidate_id",
        "retrieved_top_candidate_id",
        "predicted_candidate_id",
        "predicted_candidate_name",
        "top1_correct",
        "top3_candidate_ids",
        "expected_evidence_edges",
        "support_subgraph_edges",
        "mentioned_evidence_edges",
        "evidence_precision",
        "evidence_recall",
        "hallucinated_evidence_count",
        "kg_validation_passed",
        "kg_validation_reasons",
        "proposed_edit_type",
        "explanation",
        "raw_response",
    ]

    with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(rows):
    case_count = len(rows)
    top1_accuracy = mean([1.0 if row["top1_correct"] else 0.0 for row in rows])
    avg_evidence_precision = mean([row["evidence_precision"] for row in rows])
    avg_evidence_recall = mean([row["evidence_recall"] for row in rows])
    total_hallucinated_evidence_count = sum(
        row["hallucinated_evidence_count"] for row in rows
    )

    print("GraphRAG evaluation complete.")
    print("-" * 40)
    print(f"Cases: {case_count}")
    print(f"Top-1 accuracy: {top1_accuracy:.3f}")
    print(f"Average evidence precision: {avg_evidence_precision:.3f}")
    print(f"Average evidence recall: {avg_evidence_recall:.3f}")
    print(f"Total hallucinated evidence count: {total_hallucinated_evidence_count}")
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
