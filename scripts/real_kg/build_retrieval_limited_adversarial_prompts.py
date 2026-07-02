"""
Build retrieval-limited Text-RAG prompts for adversarial evidence binding.

This simulates a realistic retrieval failure mode: Text-RAG receives only a
partial or noisy top-k text context, while GraphRAG keeps structured
candidate-edge context.

This script does not call an LLM.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


EVAL_DIR = Path("evals/adversarial_evidence_binding")
PROMPT_DIR = EVAL_DIR / "prompts"

CASES_CSV = EVAL_DIR / "adversarial_evidence_binding_cases.csv"
OUT_PROMPTS = PROMPT_DIR / "adversarial_text_rag_retrieval_limited_prompts.json"


LIMITED_CONTEXT_BY_CASE_TYPE = {
    "score_binding": (
        "Retrieved text snippet: The empirical influenza extension evaluated outpatient ILI, "
        "wastewater, test positivity, and a negative-control surveillance signal. Several lagged "
        "correlations were reported, but this retrieved snippet does not preserve all score-to-candidate "
        "bindings. Do not infer missing numeric bindings from memory."
    ),
    "ranking_binding": (
        "Retrieved text snippet: Three empirical candidates were supported and one negative control was not. "
        "The retrieved text says there was a strongest candidate, but it does not include the full "
        "ordered score table. Do not invent the ranking."
    ),
    "pairwise_score_binding": (
        "Retrieved text snippet: Two candidate scores were compared in the full report, but this top-k text "
        "retrieval only says both candidates were plausible influenza surveillance signals. Exact "
        "scores are not included in this snippet."
    ),
    "paired_week_binding": (
        "Retrieved text snippet: The empirical analysis used paired weekly observations after alignment. "
        "Some candidates had different paired-week counts, but this retrieved snippet does not say "
        "which candidate had which count."
    ),
    "lag_binding": (
        "Retrieved text snippet: Several surveillance signals had lagged relationships to the hospitalization "
        "target. This retrieved snippet mentions lagged evidence, but it does not preserve every "
        "candidate-specific lag and support status."
    ),
    "negative_control_guard": (
        "Retrieved text snippet: A negative control was included to test whether missing evidence would be "
        "preserved. The snippet does not include its exact score, lag, paired-week count, or edge status."
    ),
    "claim_vs_edge_count": (
        "Retrieved text snippet: EvidenceClaims and typed KG edges are different objects. Some claims may not "
        "be promoted into edges. This snippet does not include the exact claim count or edge count."
    ),
    "edge_status_binding": (
        "Retrieved text snippet: Some empirical candidates were promoted into typed leading-indicator edges, "
        "while another candidate was not. This snippet does not list the exact promoted-edge members."
    ),
    "pipeline_isolation": (
        "Retrieved text snippet: The empirical_influenza pipeline should be kept separate from controlled "
        "fixture scenarios. Controlled-fixture names may appear elsewhere, but this snippet does not "
        "provide the full empirical candidate table."
    ),
    "model_revision_guard": (
        "Retrieved text snippet: Model revision should be based on supported screening evidence and should "
        "avoid causal claims. This snippet does not provide exact candidate score, lag, paired-week "
        "count, or edge status."
    ),
    "causal_overclaim_guard": (
        "Retrieved text snippet: Lagged correlations are screening evidence and should not be interpreted as "
        "causal proof or validated forecast improvement."
    ),
}


def read_cases() -> list[dict[str, str]]:
    with CASES_CSV.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def build_prompt(row: dict[str, str]) -> dict[str, str]:
    case_type = row["case_type"]
    context = LIMITED_CONTEXT_BY_CASE_TYPE.get(
        case_type,
        "Retrieved text snippet: The retrieved context is incomplete.",
    )

    prompt = f"""You are answering a retrieval-limited Text-RAG adversarial evidence-binding case.

Method: adversarial_text_rag_retrieval_limited
Target signal: {row["target_signal"]}
Case type: {row["case_type"]}

Question:
{row["query"]}

Retrieved Text-RAG context:
{context}

Instructions:
- Answer using only the retrieved Text-RAG context above.
- Do not use graph context.
- Do not use any other repo files.
- Do not invent exact candidate-specific score, lag, paired-week count, evidence status, or edge status.
- If the retrieved context does not provide the exact binding, say that the exact binding is not available from the retrieved text.
- Do not import controlled-fixture distractors into empirical_influenza.
- Do not claim causal discovery.
- Do not claim forecast improvement has already been validated.
- Keep the answer concise, usually 2-4 sentences.
"""

    return {
        "case_id": row["case_id"],
        "method": "adversarial_text_rag_retrieval_limited",
        "case_type": row["case_type"],
        "target_signal": row["target_signal"],
        "query": row["query"],
        "prompt": prompt,
    }


def main() -> None:
    rows = [build_prompt(row) for row in read_cases()]
    OUT_PROMPTS.parent.mkdir(parents=True, exist_ok=True)
    OUT_PROMPTS.write_text(
        json.dumps(rows, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {len(rows)} retrieval-limited Text-RAG prompts to {OUT_PROMPTS}")


if __name__ == "__main__":
    main()
