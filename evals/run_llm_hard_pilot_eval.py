import csv
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_FILE = PROJECT_ROOT / "evals" / "eval_cases_hard_pilot.json"
RESULTS_FILE = PROJECT_ROOT / "evals" / "results" / "llm_hard_pilot_results.csv"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from eval_metrics import (
        compute_evidence_metrics,
        compute_missing_edge_metrics,
        mean,
        normalize_list_of_strings,
    )
    from failure_case import (
        get_candidates_for_failure_case,
        get_failure_case,
        get_failure_case_by_id,
    )
    from llm_reasoner import (
        MAX_OUTPUT_TOKENS,
        MODEL_NAME,
        extract_json_text,
        get_client,
    )
except ModuleNotFoundError as exc:
    print(f"LLM hard pilot evaluation failed: missing dependency: {exc}", file=sys.stderr)
    raise SystemExit(1) from exc


REQUIRED_LLM_KEYS = {
    "predicted_candidate_id",
    "predicted_candidate_name",
    "explanation",
    "mentioned_evidence_edges",
    "identified_missing_edges",
    "rejected_candidate_ids",
    "weak_candidate_ids",
    "stronger_candidate_id",
}


def load_hard_cases():
    if not EVAL_FILE.exists():
        raise FileNotFoundError(f"Could not find {EVAL_FILE.relative_to(PROJECT_ROOT)}")

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if not isinstance(cases, list):
        raise ValueError("eval_cases_hard_pilot.json must contain a JSON list.")

    return cases


def build_prompt(failure_case, hard_case, candidates):
    payload = {
        "failure_case": failure_case,
        "question": hard_case["question"],
        "possible_candidates": candidates,
    }

    return f"""
You are evaluating an LLM-only baseline for epidemiological model revision.

Use only the failure case, the hard pilot question, and the possible candidate list.
Do not use Neo4j retrieval.
Do not use text-RAG retrieval.
Do not assume access to support subgraphs or graph paths.

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
  "weak_candidate_ids": [],
  "stronger_candidate_id": "..."
}}

For mentioned_evidence_edges and identified_missing_edges, use only exact
relationship type names. Valid edge-list values are only:
- "LEADING_INDICATOR_FOR"
- "IMPORTATION_LINK"
- "POSSIBLE_DRIVER_OF"

mentioned_evidence_edges must contain only exact relationship type names that
are present for the predicted/evaluated candidate.
identified_missing_edges must contain only exact relationship type names that
are missing for the predicted/evaluated candidate.
Do not include edges belonging only to comparison candidates in
mentioned_evidence_edges.
Do not include explanatory text, node names, arrows, parentheses, or phrases in
either edge list.

weak_candidate_ids are candidate IDs that are weak, partial, insufficiently
supported, or should not be promoted as the main explanation.
rejected_candidate_ids are candidate IDs that the answer rejects, demotes, or
says should not be selected as the best explanation.
If the evaluated/predicted candidate is described as weak, partial, or should
not be promoted, include that candidate ID in weak_candidate_ids.
Do not put stronger comparison candidates in rejected_candidate_ids just because
they are being compared.
For weak-candidate rejection questions, the weak evaluated candidate should
usually appear in weak_candidate_ids.

Use stronger_candidate_id for the candidate that is best supported overall. If
the predicted/evaluated candidate is itself the strongest or most complete
candidate, return that same candidate ID. Only return an empty string if the
provided input does not support identifying any strongest candidate.
""".strip()


def get_hard_case_failure_case(hard_case):
    failure_case_id = hard_case.get("failure_case_id", "")

    if failure_case_id:
        return get_failure_case_by_id(failure_case_id)

    return get_failure_case()


def get_hard_case_candidates(failure_case):
    return get_candidates_for_failure_case(failure_case.get("id", ""))


def validate_llm_output(data):
    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object.")

    missing = REQUIRED_LLM_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"LLM JSON is missing required keys: {sorted(missing)}")

    for key in ["predicted_candidate_id", "predicted_candidate_name", "explanation"]:
        if not isinstance(data.get(key), str):
            raise ValueError(f"LLM JSON key '{key}' must be a string.")

    if not isinstance(data.get("stronger_candidate_id"), str):
        raise ValueError("LLM JSON key 'stronger_candidate_id' must be a string.")

    for key in [
        "mentioned_evidence_edges",
        "identified_missing_edges",
        "rejected_candidate_ids",
        "weak_candidate_ids",
    ]:
        if not isinstance(data.get(key), list):
            raise ValueError(f"LLM JSON key '{key}' must be a list.")

    return True


def run_llm_case(client, failure_case, hard_case, candidates):
    response = client.responses.create(
        model=MODEL_NAME,
        instructions=(
            "You are a careful epidemiological reasoning assistant. "
            "This is an LLM-only hard pilot: use no retrieved evidence. "
            "Return valid JSON only."
        ),
        input=build_prompt(failure_case, hard_case, candidates),
        reasoning={"effort": "low"},
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    raw_text = response.output_text
    if not raw_text or not raw_text.strip():
        raise ValueError(f"Model returned no visible text for case {hard_case['id']}.")

    parsed = json.loads(extract_json_text(raw_text))
    validate_llm_output(parsed)

    return parsed, raw_text


def score_case(hard_case, llm_output, raw_text):
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
        llm_output["stronger_candidate_id"] == expected_stronger_candidate_id
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
        "stronger_candidate_id": llm_output["stronger_candidate_id"],
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
    client = get_client()
    rows = []

    for hard_case in hard_cases:
        failure_case = get_hard_case_failure_case(hard_case)
        candidates = get_hard_case_candidates(failure_case)
        llm_output, raw_text = run_llm_case(
            client,
            failure_case,
            hard_case,
            candidates,
        )
        rows.append(score_case(hard_case, llm_output, raw_text))

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
        "expected_present_edges",
        "mentioned_evidence_edges",
        "present_edge_precision",
        "present_edge_recall",
        "expected_missing_edges",
        "identified_missing_edges",
        "missing_edge_recall",
        "missing_edge_false_claim_count",
        "expected_stronger_candidate_id",
        "stronger_candidate_id",
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

    print("LLM hard pilot evaluation complete.")
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
        print(f"LLM hard pilot evaluation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
