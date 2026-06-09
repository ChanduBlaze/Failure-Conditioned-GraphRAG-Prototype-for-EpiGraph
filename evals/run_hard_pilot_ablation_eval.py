import csv
import json
import sys
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_FILE = PROJECT_ROOT / "evals" / "eval_cases_hard_pilot.json"
RESULTS_FILE = PROJECT_ROOT / "evals" / "results" / "hard_pilot_ablation_results.csv"

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
        f"Hard pilot ablation evaluation failed: missing dependency: {exc}",
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
    "stronger_candidate_id",
}

EDGE_TYPES = [
    "LEADING_INDICATOR_FOR",
    "IMPORTATION_LINK",
    "POSSIBLE_DRIVER_OF",
]

VARIANTS = [
    {
        "variant_name": "Full GraphRAG",
        "validation_enabled": True,
        "support_subgraph_enabled": True,
        "ranking_only": False,
    },
    {
        "variant_name": "No validation",
        "validation_enabled": False,
        "support_subgraph_enabled": True,
        "ranking_only": False,
    },
    {
        "variant_name": "Ranking only, no support subgraph",
        "validation_enabled": False,
        "support_subgraph_enabled": False,
        "ranking_only": True,
    },
]


def load_hard_cases():
    if not EVAL_FILE.exists():
        raise FileNotFoundError(f"Could not find {EVAL_FILE.relative_to(PROJECT_ROOT)}")

    with open(EVAL_FILE, "r", encoding="utf-8") as f:
        cases = json.load(f)

    if not isinstance(cases, list):
        raise ValueError("eval_cases_hard_pilot.json must contain a JSON list.")

    return cases


def fetch_full_candidate_context(driver, failure_case):
    candidates = retrieve_failure_candidates_from_neo4j(driver, failure_case)

    if not candidates:
        raise ValueError("No Neo4j candidates found. Cannot run ablation eval.")

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


def build_variant_context(full_candidate_context, variant):
    if not variant["ranking_only"]:
        return full_candidate_context

    return [
        {
            "rank": candidate["rank"],
            "candidate_id": candidate["candidate_id"],
            "candidate_name": candidate["candidate_name"],
            "score": candidate["score"],
        }
        for candidate in full_candidate_context
    ]


def extract_present_edge_types(candidate):
    present_edge_types = set()

    for item in candidate.get("ranking_evidence", []):
        if not isinstance(item, str):
            continue

        for edge_type in EDGE_TYPES:
            if edge_type in item:
                present_edge_types.add(edge_type)

    for edge in candidate.get("support_subgraph_edges", []):
        if isinstance(edge, dict) and edge.get("type"):
            present_edge_types.add(edge["type"])

    return sorted(present_edge_types)


def determine_support_level(present_edge_types):
    present_edges = set(present_edge_types)

    if all(edge_type in present_edges for edge_type in EDGE_TYPES):
        return "full"

    if len(present_edges) <= 1:
        return "weak"

    return "partial"


def build_validation_summary(full_candidate_context):
    validation_summary = []

    for candidate in full_candidate_context:
        present_edge_types = extract_present_edge_types(candidate)
        present_edges = set(present_edge_types)

        validation_summary.append(
            {
                "candidate_id": candidate["candidate_id"],
                "present_edge_types": present_edge_types,
                "evidence_edge_count": len(present_edge_types),
                "has_leading_indicator": "LEADING_INDICATOR_FOR" in present_edges,
                "has_importation_link": "IMPORTATION_LINK" in present_edges,
                "has_possible_driver": "POSSIBLE_DRIVER_OF" in present_edges,
                "support_level": determine_support_level(present_edge_types),
            }
        )

    return validation_summary


def build_prompt(failure_case, hard_case, candidate_context, variant):
    if variant["ranking_only"]:
        evidence_instructions = """
Use only the ranking context in the input:
- failure case
- hard pilot question
- candidate IDs, names, scores, and ranks

Do not assume support-subgraph edges or detailed evidence edge lists are available.
If support-subgraph evidence and detailed evidence edge lists are not provided,
do not invent edge types.
In ranking-only mode, leave mentioned_evidence_edges empty unless an exact valid
relationship type is explicitly present in the provided ranking context.
In ranking-only mode, leave identified_missing_edges empty unless the provided
context explicitly supports a missing valid relationship type.
""".strip()
    else:
        evidence_instructions = """
Use only the retrieved graph evidence in the input:
- failure case
- hard pilot question
- candidate rankings
- candidate evidence lists
- support-subgraph-style nodes and edges

Do not use outside knowledge.
Do not invent datasets, nodes, edges, mechanisms, or candidate IDs.
""".strip()

    payload = {
        "ablation_variant": {
            "variant_name": variant["variant_name"],
            "validation_enabled": variant["validation_enabled"],
            "support_subgraph_enabled": variant["support_subgraph_enabled"],
            "ranking_only": variant["ranking_only"],
        },
        "failure_case": failure_case,
        "question": hard_case["question"],
        "retrieved_candidate_rankings": candidate_context,
    }
    if variant["validation_enabled"]:
        payload["validation_summary"] = build_validation_summary(candidate_context)

    return f"""
You are evaluating an ablation variant of a Neo4j-backed GraphRAG method for
epidemiological model revision.

{evidence_instructions}

These hard pilot cases may ask about candidates that are not ranked first. Reason
about the specific candidate in the question, identify which evidence is present,
and identify which expected graph relationships are missing when the input
supports that distinction.

Keep candidate-specific evidence separate from comparison evidence, especially
for weak-candidate or contrast questions.

If validation_summary is present, use it to keep present and missing edge claims
consistent with the retrieved graph evidence. If validation_summary is absent,
rely only on the retrieved evidence provided in the prompt.

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
Do not include comparison-candidate edges in mentioned_evidence_edges.
Do not include explanatory text, node names, arrows, parentheses, phrases, or
invented edge names in either edge list.

If this is the ranking-only variant, leave mentioned_evidence_edges empty unless
an exact valid relationship type is explicitly present in the provided ranking
context. Leave identified_missing_edges empty unless the provided context
explicitly supports a missing valid relationship type.

Use stronger_candidate_id for the candidate that is best supported overall. If
the predicted/evaluated candidate is itself the strongest or most complete
candidate, return that same candidate ID. Only return an empty string if the
provided input truly does not support identifying any strongest candidate.
""".strip()


def validate_llm_output(data):
    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object.")

    missing = REQUIRED_LLM_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"LLM JSON is missing required keys: {sorted(missing)}")

    for key in [
        "predicted_candidate_id",
        "predicted_candidate_name",
        "explanation",
        "stronger_candidate_id",
    ]:
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


def run_llm_case(client, failure_case, hard_case, candidate_context, variant):
    response = client.responses.create(
        model=MODEL_NAME,
        instructions=(
            "You are a careful epidemiological reasoning assistant. "
            "Use only the evidence provided for the ablation variant. "
            "Return valid JSON only."
        ),
        input=build_prompt(failure_case, hard_case, candidate_context, variant),
        reasoning={"effort": "low"},
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    raw_text = response.output_text
    if not raw_text or not raw_text.strip():
        raise ValueError(
            f"Model returned no visible text for variant {variant['variant_name']} "
            f"case {hard_case['id']}."
        )

    parsed = json.loads(extract_json_text(raw_text))
    validate_llm_output(parsed)

    return parsed, raw_text


def score_case(variant, hard_case, llm_output, raw_text):
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
        identified_missing_edges=identified_missing_edges,
        expected_missing_edges=expected_missing_edges,
        mentioned_edge_types=mentioned_edges,
    )

    expected_stronger_candidate_id = hard_case.get("expected_stronger_candidate_id", "")
    stronger_candidate_identified = (
        llm_output["stronger_candidate_id"] == expected_stronger_candidate_id
        if expected_stronger_candidate_id
        else ""
    )

    expected_weak_candidate_id = hard_case.get("expected_weak_candidate_id", "")
    weak_candidate_rejected = (
        expected_weak_candidate_id in rejected_candidate_ids
        or expected_weak_candidate_id in weak_candidate_ids
        if expected_weak_candidate_id
        else ""
    )

    return {
        "variant_name": variant["variant_name"],
        "case_id": hard_case.get("id", ""),
        "task_type": hard_case.get("task_type", ""),
        "expected_candidate_id": expected_candidate_id,
        "predicted_candidate_id": llm_output["predicted_candidate_id"],
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
        "weak_candidate_rejected": weak_candidate_rejected,
        "validation_enabled": variant["validation_enabled"],
        "support_subgraph_enabled": variant["support_subgraph_enabled"],
        "ranking_only": variant["ranking_only"],
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
        full_candidate_context = fetch_full_candidate_context(driver, failure_case)

        for variant in VARIANTS:
            candidate_context = build_variant_context(full_candidate_context, variant)

            for hard_case in hard_cases:
                llm_output, raw_text = run_llm_case(
                    client,
                    failure_case,
                    hard_case,
                    candidate_context,
                    variant,
                )
                rows.append(score_case(variant, hard_case, llm_output, raw_text))
    finally:
        driver.close()

    return rows


def save_results(rows):
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "variant_name",
        "case_id",
        "task_type",
        "expected_candidate_id",
        "predicted_candidate_id",
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
        "weak_candidate_rejected",
        "validation_enabled",
        "support_subgraph_enabled",
        "ranking_only",
        "explanation",
        "raw_response",
    ]

    with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def print_variant_summary(variant_name, rows):
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

    print(variant_name)
    print("-" * len(variant_name))
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
        "False edge claims: "
        f"{sum(row['missing_edge_false_claim_count'] for row in rows)}"
    )
    print(
        "Stronger-candidate accuracy: "
        f"{mean(stronger_values):.3f}"
    )
    print(
        "Weak-candidate rejection accuracy: "
        f"{mean(weak_values):.3f}"
    )
    print()


def print_summary(rows):
    rows_by_variant = defaultdict(list)

    for row in rows:
        rows_by_variant[row["variant_name"]].append(row)

    print("Hard pilot ablation evaluation complete.")
    print("=" * 40)

    for variant in VARIANTS:
        print_variant_summary(
            variant["variant_name"],
            rows_by_variant[variant["variant_name"]],
        )

    print(f"Results saved to: {RESULTS_FILE.relative_to(PROJECT_ROOT)}")


def main():
    try:
        rows = run_eval()
        save_results(rows)
        print_summary(rows)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        print(f"Hard pilot ablation evaluation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
