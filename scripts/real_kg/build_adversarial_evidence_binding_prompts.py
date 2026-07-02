"""
Build prompts for the adversarial evidence-binding evaluation.

Methods:
- adversarial_text_rag_overloaded
- adversarial_graphrag_context

This script does not call an LLM.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


EVAL_DIR = Path("evals/adversarial_evidence_binding")
DATA_DIR = Path("data/real_processed/adversarial_evidence_binding")
PROMPT_DIR = EVAL_DIR / "prompts"

CASES_CSV = EVAL_DIR / "adversarial_evidence_binding_cases.csv"
TEXT_CHUNKS = DATA_DIR / "adversarial_text_rag_chunks.json"
GRAPH_CONTEXT = DATA_DIR / "adversarial_graph_context.json"


def read_cases() -> list[dict[str, str]]:
    with CASES_CSV.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def build_text_context(chunks: list[dict[str, str]]) -> str:
    parts = []
    for chunk in chunks:
        parts.append(
            f"[{chunk['chunk_id']}] {chunk['title']}\n{chunk['text']}"
        )
    return "\n\n".join(parts)


def build_graph_context_text(graph_context: dict) -> str:
    return json.dumps(graph_context, indent=2, ensure_ascii=False)


def build_prompt(row: dict[str, str], method: str, context: str) -> dict[str, str]:
    prompt = f"""You are answering an adversarial evidence-binding evaluation case.

Method: {method}
Target signal: {row["target_signal"]}
Case type: {row["case_type"]}

Question:
{row["query"]}

Context:
{context}

Instructions:
- Answer using only the supplied context.
- Preserve candidate-specific score, lag, paired-week count, evidence status, and edge status.
- Do not mix scores across candidates.
- Do not promote missing evidence into a typed edge.
- Do not import controlled-fixture distractors into empirical_influenza.
- Do not claim causal discovery.
- Do not claim forecast improvement has already been validated.
- Keep the answer concise, usually 2-4 sentences.
"""
    return {
        "case_id": row["case_id"],
        "method": method,
        "case_type": row["case_type"],
        "target_signal": row["target_signal"],
        "query": row["query"],
        "prompt": prompt,
    }


def write_json(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def write_index(path: Path, rows: list[dict[str, str]]) -> None:
    fieldnames = ["case_id", "method", "case_type", "target_signal", "query"]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in fieldnames})


def main() -> None:
    cases = read_cases()
    text_chunks = read_json(TEXT_CHUNKS)
    graph_context = read_json(GRAPH_CONTEXT)

    text_context = build_text_context(text_chunks)
    graph_context_text = build_graph_context_text(graph_context)

    text_prompts = [
        build_prompt(row, "adversarial_text_rag_overloaded", text_context)
        for row in cases
    ]
    graph_prompts = [
        build_prompt(row, "adversarial_graphrag_context", graph_context_text)
        for row in cases
    ]

    all_prompts = [*text_prompts, *graph_prompts]

    write_json(PROMPT_DIR / "adversarial_text_rag_overloaded_prompts.json", text_prompts)
    write_json(PROMPT_DIR / "adversarial_graphrag_context_prompts.json", graph_prompts)
    write_json(PROMPT_DIR / "adversarial_evidence_binding_all_prompts.json", all_prompts)
    write_index(PROMPT_DIR / "adversarial_evidence_binding_prompt_index.csv", all_prompts)

    print(f"Wrote {len(text_prompts)} Text-RAG prompts")
    print(f"Wrote {len(graph_prompts)} GraphRAG prompts")
    print(f"Wrote {len(all_prompts)} total prompts")


if __name__ == "__main__":
    main()
