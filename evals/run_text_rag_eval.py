import csv
import json
import re
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_FILE = PROJECT_ROOT / "evals" / "eval_cases.json"
CORPUS_FILE = PROJECT_ROOT / "evals" / "text_rag_corpus.json"
RESULTS_FILE = PROJECT_ROOT / "evals" / "results" / "text_rag_results.csv"
DEFAULT_TOP_K = 3

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from failure_case import get_failure_case
    from llm_reasoner import (
        MAX_OUTPUT_TOKENS,
        MODEL_NAME,
        extract_json_text,
        get_client,
    )
except ModuleNotFoundError as exc:
    print(f"Evaluation failed: missing Python dependency: {exc}", file=sys.stderr)
    raise SystemExit(1) from exc


CANDIDATES = [
    {
        "candidate_id": "signal_chile_flu",
        "candidate_name": "Chile Influenza Activity",
    },
    {
        "candidate_id": "signal_australia_flu",
        "candidate_name": "Australia Influenza Activity",
    },
    {
        "candidate_id": "signal_travel_pressure",
        "candidate_name": "Travel Importation Pressure",
    },
    {
        "candidate_id": "signal_humidity_drop",
        "candidate_name": "Humidity Drop Anomaly",
    },
]

REQUIRED_LLM_KEYS = {
    "predicted_candidate_id",
    "predicted_candidate_name",
    "explanation",
    "proposed_edit_type",
    "mentioned_evidence_edges",
}

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "case",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "what",
    "which",
    "with",
}


def load_json_list(path, label):
    if not path.exists():
        raise FileNotFoundError(f"Could not find {path.relative_to(PROJECT_ROOT)}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"{label} must contain a JSON list.")

    return data


def tokenize(text):
    return [
        token
        for token in re.findall(r"[a-z0-9]+", str(text).lower())
        if token not in STOPWORDS and len(token) > 1
    ]


def build_query_text(eval_case, failure_case):
    failure_values = [
        value
        for value in failure_case.values()
        if isinstance(value, (str, int, float))
    ]

    return " ".join([eval_case.get("question", ""), *map(str, failure_values)])


def score_chunk(query_tokens, chunk):
    chunk_text = f"{chunk.get('title', '')} {chunk.get('text', '')}"
    chunk_tokens = tokenize(chunk_text)
    chunk_token_set = set(chunk_tokens)

    overlap_score = sum(1 for token in query_tokens if token in chunk_token_set)
    title_tokens = set(tokenize(chunk.get("title", "")))
    title_bonus = sum(1 for token in query_tokens if token in title_tokens)

    return overlap_score + title_bonus


def retrieve_text_chunks(eval_case, failure_case, corpus, top_k=DEFAULT_TOP_K):
    query_tokens = tokenize(build_query_text(eval_case, failure_case))

    scored_chunks = [
        (score_chunk(query_tokens, chunk), chunk.get("chunk_id", ""), chunk)
        for chunk in corpus
    ]
    scored_chunks.sort(key=lambda item: (-item[0], item[1]))

    return [
        {
            **chunk,
            "retrieval_score": score,
        }
        for score, _chunk_id, chunk in scored_chunks[:top_k]
    ]


def build_prompt(failure_case, eval_case, retrieved_chunks):
    prompt_payload = {
        "failure_case": failure_case,
        "question": eval_case["question"],
        "retrieved_text_chunks": retrieved_chunks,
        "possible_candidates": CANDIDATES,
    }

    return f"""
You are evaluating a text-based RAG baseline for epidemiological model revision.

Use only the retrieved text chunks, the failure case, and the candidate list.
Do not use Neo4j retrieval.
Do not assume access to graph paths or support subgraphs.
Do not invent datasets, edges, mechanisms, or candidate IDs that are not present in
the input.

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

For mentioned_evidence_edges, return only relationship type names explicitly used
in your explanation, such as "LEADING_INDICATOR_FOR".
""".strip()


def validate_llm_output(data):
    if not isinstance(data, dict):
        raise ValueError("LLM response must be a JSON object.")

    missing = REQUIRED_LLM_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"LLM JSON is missing required keys: {sorted(missing)}")

    for key in REQUIRED_LLM_KEYS - {"mentioned_evidence_edges"}:
        if not isinstance(data.get(key), str):
            raise ValueError(f"LLM JSON key '{key}' must be a string.")

    if not isinstance(data["mentioned_evidence_edges"], list):
        raise ValueError("LLM JSON key 'mentioned_evidence_edges' must be a list.")

    return True


def run_llm_case(client, failure_case, eval_case, retrieved_chunks):
    prompt = build_prompt(failure_case, eval_case, retrieved_chunks)

    response = client.responses.create(
        model=MODEL_NAME,
        instructions=(
            "You are a careful epidemiological reasoning assistant. "
            "Use only the retrieved text chunks provided. "
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


def normalize_edge_types(edge_types):
    normalized = []

    for edge_type in edge_types or []:
        if isinstance(edge_type, str) and edge_type.strip():
            normalized.append(edge_type.strip())

    return normalized


def compute_evidence_metrics(mentioned_edge_types, expected_edge_types):
    mentioned = set(normalize_edge_types(mentioned_edge_types))
    expected = set(normalize_edge_types(expected_edge_types))

    if mentioned:
        precision = len(mentioned & expected) / len(mentioned)
    else:
        precision = 1.0 if not expected else 0.0

    if expected:
        recall = len(mentioned & expected) / len(expected)
    else:
        recall = 1.0

    hallucinated_count = len(mentioned - expected)

    return precision, recall, hallucinated_count


def mean(values):
    return sum(values) / len(values) if values else 0.0


def run_eval():
    eval_cases = load_json_list(EVAL_FILE, "eval_cases.json")
    corpus = load_json_list(CORPUS_FILE, "text_rag_corpus.json")
    failure_case = get_failure_case()
    client = get_client()
    rows = []

    for eval_case in eval_cases:
        retrieved_chunks = retrieve_text_chunks(eval_case, failure_case, corpus)
        llm_output, raw_text = run_llm_case(
            client,
            failure_case,
            eval_case,
            retrieved_chunks,
        )

        expected_candidate_id = eval_case.get("expected_candidate_id", "")
        predicted_candidate_id = llm_output["predicted_candidate_id"]
        expected_edge_types = eval_case.get("expected_evidence_edges", [])
        mentioned_edge_types = normalize_edge_types(
            llm_output["mentioned_evidence_edges"]
        )

        evidence_precision, evidence_recall, hallucinated_evidence_count = (
            compute_evidence_metrics(mentioned_edge_types, expected_edge_types)
        )

        rows.append(
            {
                "case_id": eval_case.get("id", ""),
                "task_type": eval_case.get("task_type", ""),
                "expected_candidate_id": expected_candidate_id,
                "predicted_candidate_id": predicted_candidate_id,
                "predicted_candidate_name": llm_output["predicted_candidate_name"],
                "top1_correct": predicted_candidate_id == expected_candidate_id,
                "retrieved_chunk_ids": ";".join(
                    chunk.get("chunk_id", "") for chunk in retrieved_chunks
                ),
                "retrieved_chunk_scores": ";".join(
                    str(chunk.get("retrieval_score", 0))
                    for chunk in retrieved_chunks
                ),
                "expected_evidence_edges": ";".join(
                    normalize_edge_types(expected_edge_types)
                ),
                "mentioned_evidence_edges": ";".join(mentioned_edge_types),
                "evidence_precision": evidence_precision,
                "evidence_recall": evidence_recall,
                "hallucinated_evidence_count": hallucinated_evidence_count,
                "proposed_edit_type": llm_output["proposed_edit_type"],
                "explanation": llm_output["explanation"],
                "raw_response": raw_text,
            }
        )

    return rows


def save_results(rows):
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "case_id",
        "task_type",
        "expected_candidate_id",
        "predicted_candidate_id",
        "predicted_candidate_name",
        "top1_correct",
        "retrieved_chunk_ids",
        "retrieved_chunk_scores",
        "expected_evidence_edges",
        "mentioned_evidence_edges",
        "evidence_precision",
        "evidence_recall",
        "hallucinated_evidence_count",
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

    print("Text-RAG evaluation complete.")
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
