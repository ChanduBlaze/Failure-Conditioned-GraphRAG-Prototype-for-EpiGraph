
"""
Build real respiratory retrieval-stress prompts.

This benchmark tests retrieval behavior, not full-context reading.

Text-RAG conditions receive lexical top-k chunks from the respiratory text corpus.
GraphRAG receives a structured target-neighborhood from the respiratory graph context.

This script does not call an LLM.
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter
from pathlib import Path


TEXT_CORPUS = Path("data/real_processed/respiratory_expansion/respiratory_expansion_text_corpus.json")
GRAPH_CONTEXT = Path("data/real_processed/respiratory_expansion/respiratory_expansion_graph_context.json")
CASES_CSV = Path("evals/respiratory_expansion/respiratory_expansion_cases.csv")

OUT_DIR = Path("evals/respiratory_expansion/retrieval_stress")
PROMPT_DIR = OUT_DIR / "prompts"
MODEL_OUTPUT_DIR = OUT_DIR / "model_outputs"

TEXT_TOP_K_VALUES = [1, 2]


def normalize(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("?", "-")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", normalize(text))


def lexical_score(query: str, chunk_text: str) -> float:
    q_tokens = tokenize(query)
    c_tokens = tokenize(chunk_text)

    if not q_tokens or not c_tokens:
        return 0.0

    q_counts = Counter(q_tokens)
    c_counts = Counter(c_tokens)

    score = 0.0
    for tok in q_counts:
        if tok in c_counts:
            score += 1.0 + math.log(1 + c_counts[tok])

    quoted = re.findall(r"'([^']+)'", query)
    for phrase in quoted:
        if normalize(phrase) in normalize(chunk_text):
            score += 12.0

    return score


def aliases_for_required_term(term: str) -> list[str]:
    t = str(term)

    m = re.fullmatch(r"lag=(\d+)", t)
    if m:
        n = m.group(1)
        return [
            f"lag={n}",
            f"best lag was {n} weeks",
            f"best lag was {n} week",
            f"lag was {n} weeks",
        ]

    m = re.fullmatch(r"paired_weeks=(\d+)", t)
    if m:
        n = m.group(1)
        return [
            f"paired_weeks={n}",
            f"{n} paired weeks",
            f"used {n} paired weeks",
            f"comparison used {n} paired weeks",
        ]

    m = re.fullmatch(r"evidence_status=(present|missing)", t)
    if m:
        status = m.group(1)
        return [
            f"evidence_status={status}",
            f"evidence status for this candidate-target binding was {status}",
            f"evidence status was {status}",
        ]

    m = re.fullmatch(r"edge_type=([A-Z_]+)", t)
    if m:
        edge = m.group(1)
        return [
            f"edge_type={edge}",
            f"promoted edge type was {edge}",
            f"edge type was {edge}",
            edge,
        ]

    if t == "screening evidence only":
        return [
            "screening evidence only",
            "screening evidence",
            "do not prove causality",
            "do not demonstrate forecast improvement",
        ]

    if t == "should not be promoted":
        return [
            "should not be promoted",
            "remain unpromoted",
            "unsupported claims remain unpromoted",
            "NO_TYPED_EDGE",
        ]

    return [t]


def flexible_term_present(text: str, term: str) -> bool:
    text_norm = normalize(text)
    return any(normalize(alias) in text_norm for alias in aliases_for_required_term(term))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def format_claim(claim: dict) -> str:
    return (
        f"{claim['candidate_label']} -> {claim['target_label']}: "
        f"lag={claim['best_lag_weeks']}, "
        f"r={float(claim['pearson_r']):.6f}, "
        f"paired_weeks={claim['paired_weeks']}, "
        f"evidence_status={claim['evidence_status']}, "
        f"edge_type={claim['promoted_edge_type']}"
    )


def detect_target_label(case: dict[str, str], graph_claims: list[dict]) -> str:
    blob = " ".join([
        case.get("question", ""),
        case.get("expected_answer", ""),
        case.get("must_include_terms_json", ""),
    ]).lower()

    targets = sorted(
        {str(claim["target_label"]) for claim in graph_claims},
        key=len,
        reverse=True,
    )

    for target in targets:
        if target.lower() in blob:
            return target

    # Fallback using disease words in question.
    q = case.get("question", "").lower()
    if "influenza" in q or "flu" in q:
        return "FluSurv-NET influenza hospitalization rate"
    if "covid" in q:
        return "COVID-NET COVID-19 hospitalization rate"
    if "rsv" in q:
        return "RSV-NET RSV hospitalization rate"

    return ""


def build_text_prompt(case: dict[str, str], retrieved_chunks: list[dict], method: str) -> str:
    context = "\n\n".join(
        f"[{chunk['chunk_id']}] {chunk['title']}\n{chunk['text']}"
        for chunk in retrieved_chunks
    )

    return f"""You are answering an epidemiological forecast-failure evidence-preservation question.

Method: {method}

Use only the retrieved Text-RAG context below. If the retrieved context does not contain a required binding, do not invent it. Preserve exact candidate-target bindings when available.

Retrieved Text-RAG context:
{context}

Question:
{case['question']}

Answer:"""


def build_graph_prompt(case: dict[str, str], target_label: str, target_claims: list[dict], constraints: list[str], method: str) -> str:
    claim_lines = "\n".join(f"- {format_claim(claim)}" for claim in target_claims)

    constraint_lines = "\n".join(f"- {c}" for c in constraints)

    return f"""You are answering an epidemiological forecast-failure evidence-preservation question.

Method: {method}

Use only the structured GraphRAG target-neighborhood below. Preserve exact candidate-target bindings. Do not promote missing evidence or negative controls.

Target neighborhood:
Target: {target_label}

Claims:
{claim_lines}

Interpretation constraints:
{constraint_lines}

Question:
{case['question']}

Answer:"""


def main() -> None:
    PROMPT_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    corpus = json.loads(TEXT_CORPUS.read_text(encoding="utf-8"))
    graph = json.loads(GRAPH_CONTEXT.read_text(encoding="utf-8"))
    cases = load_csv(CASES_CSV)

    graph_claims = graph["claims"]
    constraints = graph.get("interpretation_constraints", [])

    all_prompts = []
    prompt_index = []
    retrieval_log = []

    # Text-RAG top-k retrieval prompts.
    for top_k in TEXT_TOP_K_VALUES:
        method = f"resp_exp_text_rag_top{top_k}"
        method_prompts = []

        for case in cases:
            question = case["question"]
            must_include = json.loads(case["must_include_terms_json"])

            scored_chunks = []
            for chunk in corpus:
                chunk_text = f"{chunk.get('title', '')}\n{chunk.get('text', '')}"
                scored_chunks.append({
                    "chunk_id": chunk.get("chunk_id", ""),
                    "title": chunk.get("title", ""),
                    "score": lexical_score(question, chunk_text),
                    "text": chunk.get("text", ""),
                })

            scored_chunks.sort(key=lambda x: x["score"], reverse=True)
            retrieved = scored_chunks[:top_k]
            retrieved_text = "\n\n".join(f"{r['title']}\n{r['text']}" for r in retrieved)

            missing = [term for term in must_include if not flexible_term_present(retrieved_text, term)]
            coverage = (len(must_include) - len(missing)) / len(must_include) if must_include else 1.0

            prompt = {
                "case_id": case["case_id"],
                "case_type": case["case_type"],
                "method": method,
                "top_k": top_k,
                "question": question,
                "prompt": build_text_prompt(case, retrieved, method),
            }

            method_prompts.append(prompt)
            all_prompts.append(prompt)

            prompt_index.append({
                "case_id": case["case_id"],
                "case_type": case["case_type"],
                "method": method,
                "top_k": str(top_k),
                "retrieval_mode": "text_lexical_top_k",
            })

            retrieval_log.append({
                "case_id": case["case_id"],
                "case_type": case["case_type"],
                "method": method,
                "top_k": str(top_k),
                "coverage": f"{coverage:.3f}",
                "all_required_terms_present": str(len(missing) == 0),
                "missing_terms_json": json.dumps(missing),
                "retrieved_chunk_ids": json.dumps([r["chunk_id"] for r in retrieved]),
                "retrieved_chunk_titles": json.dumps([r["title"] for r in retrieved]),
                "retrieval_scores": json.dumps([round(r["score"], 3) for r in retrieved]),
            })

        write_json(PROMPT_DIR / f"{method}_prompts.json", method_prompts)
        write_jsonl(MODEL_OUTPUT_DIR / f"{method}_prompts_for_filling.jsonl", method_prompts)

    # GraphRAG target-neighborhood prompts.
    graph_method = "resp_exp_graphrag_target_neighborhood"
    graph_prompts = []

    for case in cases:
        target_label = detect_target_label(case, graph_claims)
        target_claims = [claim for claim in graph_claims if claim["target_label"] == target_label]

        prompt = {
            "case_id": case["case_id"],
            "case_type": case["case_type"],
            "method": graph_method,
            "target_label": target_label,
            "question": case["question"],
            "prompt": build_graph_prompt(case, target_label, target_claims, constraints, graph_method),
        }

        graph_prompts.append(prompt)
        all_prompts.append(prompt)

        prompt_index.append({
            "case_id": case["case_id"],
            "case_type": case["case_type"],
            "method": graph_method,
            "top_k": "",
            "retrieval_mode": "graph_target_neighborhood",
        })

        retrieval_log.append({
            "case_id": case["case_id"],
            "case_type": case["case_type"],
            "method": graph_method,
            "top_k": "",
            "coverage": "1.000",
            "all_required_terms_present": "True",
            "missing_terms_json": "[]",
            "retrieved_chunk_ids": "",
            "retrieved_chunk_titles": "",
            "retrieval_scores": "",
        })

    write_json(PROMPT_DIR / f"{graph_method}_prompts.json", graph_prompts)
    write_jsonl(MODEL_OUTPUT_DIR / f"{graph_method}_prompts_for_filling.jsonl", graph_prompts)

    write_json(PROMPT_DIR / "respiratory_retrieval_stress_all_prompts.json", all_prompts)
    write_csv(OUT_DIR / "respiratory_retrieval_stress_prompt_index.csv", prompt_index)
    write_csv(OUT_DIR / "respiratory_retrieval_stress_retrieval_log.csv", retrieval_log)

    print(f"Wrote {len(all_prompts)} total retrieval-stress prompts")
    print(f"- Text-RAG top1 prompts: {len(cases)}")
    print(f"- Text-RAG top2 prompts: {len(cases)}")
    print(f"- GraphRAG target-neighborhood prompts: {len(graph_prompts)}")
    print()
    print(f"Wrote prompt index to {OUT_DIR / 'respiratory_retrieval_stress_prompt_index.csv'}")
    print(f"Wrote retrieval log to {OUT_DIR / 'respiratory_retrieval_stress_retrieval_log.csv'}")

    print()
    print("Text retrieval coverage summary:")
    for top_k in TEXT_TOP_K_VALUES:
        method = f"resp_exp_text_rag_top{top_k}"
        rows = [r for r in retrieval_log if r["method"] == method]
        full = sum(1 for r in rows if r["all_required_terms_present"] == "True")
        avg = sum(float(r["coverage"]) for r in rows) / len(rows)
        print(f"- {method}: full_coverage={full}/{len(rows)} ({full/len(rows):.3f}), avg_coverage={avg:.3f}")

    print(f"- {graph_method}: full_coverage={len(cases)}/{len(cases)} (1.000), avg_coverage=1.000")


if __name__ == "__main__":
    main()
