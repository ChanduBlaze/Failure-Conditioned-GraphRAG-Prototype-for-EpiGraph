"""
Build prompts for the empirical influenza hard-pilot stress evaluation.

This script creates reproducible prompt files for four method conditions:

1. empirical_llm_only
   - Receives the case question but no empirical lag/score/pair-week/KG evidence.

2. empirical_text_rag_clean
   - Receives clean candidate-specific evidence chunks.

3. empirical_text_rag_blended
   - Receives blended multi-candidate chunks designed to stress evidence blurring.

4. empirical_graphrag_context
   - Receives graph-style empirical context.
   - Uses existing real_empirical_influenza_graph_context.json if available.
   - Falls back to a graph-style context built from candidate facts.

The prompts preserve the thesis framing:
Evidence preservation after forecast failure, not automatic causal discovery.
"""
import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Any


DEFAULT_CASES = Path("evals/empirical_hard_pilot/real_empirical_hard_pilot_cases.csv")
DEFAULT_CANDIDATE_FACTS = Path("data/real_processed/empirical_hard_pilot/real_empirical_candidate_facts.csv")
DEFAULT_CLEAN_CHUNKS = Path("data/real_processed/empirical_hard_pilot/real_empirical_text_rag_clean_chunks.json")
DEFAULT_BLENDED_CHUNKS = Path("data/real_processed/empirical_hard_pilot/real_empirical_text_rag_blended_chunks.json")
DEFAULT_EXISTING_GRAPH_CONTEXT = Path("data/real_processed/real_empirical_influenza_graph_context.json")
DEFAULT_OUT_DIR = Path("evals/empirical_hard_pilot/prompts")


METHODS = [
    "empirical_llm_only",
    "empirical_text_rag_clean",
    "empirical_text_rag_blended",
    "empirical_graphrag_context",
]


SYSTEM_INSTRUCTIONS = """You are evaluating empirical influenza evidence claims for a thesis on Failure-Conditioned GraphRAG.

Use only the supplied context for empirical details.
Preserve exact candidate names, evidence status, lag, correlation score, paired-week count, and KG edge status when available.
Do not import controlled fixture candidates such as Chile Influenza Activity, Australia Influenza Activity, Travel Importation Pressure, or Humidity Drop.
Do not claim causal discovery.
Do not claim that forecast improvement has already been validated.
Frame lagged correlations as screening evidence for possible model-revision testing, not causal proof.
Return a concise answer.
"""


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def clean_chunk_context(chunks: List[Dict[str, Any]]) -> str:
    lines = []
    for chunk in chunks:
        lines.append(f"[{chunk.get('chunk_id', 'chunk')}]")
        lines.append(str(chunk.get("text", "")).strip())
        lines.append("")
    return "\n".join(lines).strip()


def blended_chunk_context(chunks: List[Dict[str, Any]]) -> str:
    lines = []
    for chunk in chunks:
        lines.append(f"[{chunk.get('chunk_id', 'chunk')}]")
        lines.append(str(chunk.get("text", "")).strip())
        lines.append("")
    return "\n".join(lines).strip()


def build_fallback_graph_context(candidate_facts: List[Dict[str, str]]) -> str:
    """
    Builds a graph-style context from candidate facts when the full Neo4j context JSON
    is not present locally.
    """
    lines = []
    lines.append("Pipeline: empirical_influenza")
    lines.append("Target node: FluSurv-NET influenza hospitalization rate")
    lines.append("EvidenceClaim nodes and promoted KG edge behavior:")
    lines.append("")

    promoted_count = 0
    for row in candidate_facts:
        candidate = row.get("candidate_name", "")
        status = row.get("status", "")
        lag = row.get("best_lag_weeks", "")
        score = row.get("score", "")
        paired = row.get("paired_weeks", "")
        edge_type = row.get("edge_type_if_promoted", "")
        kg_behavior = row.get("kg_behavior", "")
        pipeline = row.get("pipeline", "")

        if edge_type:
            promoted_count += 1

        lines.append(f"- Candidate node: {candidate}")
        lines.append(f"  EvidenceClaim status: {status}")
        lines.append(f"  Best lag weeks: {lag}")
        lines.append(f"  Correlation score: r={score}")
        lines.append(f"  Paired weeks: {paired}")
        lines.append(f"  Pipeline: {pipeline}")
        if edge_type:
            lines.append(f"  Typed KG edge: {candidate} -[{edge_type}]-> FluSurv-NET influenza hospitalization rate")
        else:
            lines.append("  Typed KG edge: none")
        lines.append(f"  KG behavior: {kg_behavior}")
        lines.append("")

    lines.append(f"Total EvidenceClaims: {len(candidate_facts)}")
    lines.append(f"Typed LEADING_INDICATOR_FOR edges created: {promoted_count}")
    lines.append("Negative-control missing evidence must not be promoted into a typed KG edge.")
    return "\n".join(lines).strip()


def existing_graph_context_to_text(path: Path, fallback_text: str) -> str:
    """
    Converts the existing graph context JSON to readable prompt context.
    If parsing or structure is unexpected, returns JSON text or fallback text.
    """
    if not path.exists():
        return fallback_text

    try:
        data = read_json(path)
    except Exception:
        return fallback_text

    try:
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception:
        return fallback_text


def build_prompt(case: Dict[str, str], method: str, context: str) -> Dict[str, Any]:
    query = case.get("query", "")
    case_id = case.get("case_id", "")
    case_type = case.get("case_type", "")
    target_signal = case.get("target_signal", "")
    pipeline = case.get("pipeline", "")

    prompt = f"""{SYSTEM_INSTRUCTIONS}

Case ID: {case_id}
Case type: {case_type}
Pipeline: {pipeline}
Target signal: {target_signal}

Question:
{query}

Supplied context:
{context}

Answer:"""

    return {
        "case_id": case_id,
        "method": method,
        "case_type": case_type,
        "target_signal": target_signal,
        "query": query,
        "prompt": prompt,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--candidate-facts", default=str(DEFAULT_CANDIDATE_FACTS))
    parser.add_argument("--clean-chunks", default=str(DEFAULT_CLEAN_CHUNKS))
    parser.add_argument("--blended-chunks", default=str(DEFAULT_BLENDED_CHUNKS))
    parser.add_argument("--graph-context", default=str(DEFAULT_EXISTING_GRAPH_CONTEXT))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    cases_path = Path(args.cases)
    candidate_facts_path = Path(args.candidate_facts)
    clean_chunks_path = Path(args.clean_chunks)
    blended_chunks_path = Path(args.blended_chunks)
    graph_context_path = Path(args.graph_context)
    out_dir = Path(args.out_dir)

    cases = read_csv_rows(cases_path)
    candidate_facts = read_csv_rows(candidate_facts_path)
    clean_chunks = read_json(clean_chunks_path)
    blended_chunks = read_json(blended_chunks_path)

    fallback_graph_context = build_fallback_graph_context(candidate_facts)
    graph_context = existing_graph_context_to_text(graph_context_path, fallback_graph_context)

    contexts = {
        "empirical_llm_only": (
            "No empirical lag, correlation score, threshold, paired-week count, or KG edge evidence is supplied. "
            "Use only broad epidemiological reasoning and explicitly state when exact empirical details are unavailable."
        ),
        "empirical_text_rag_clean": clean_chunk_context(clean_chunks),
        "empirical_text_rag_blended": blended_chunk_context(blended_chunks),
        "empirical_graphrag_context": graph_context,
    }

    all_prompts = []

    for method in METHODS:
        prompts = [build_prompt(case, method, contexts[method]) for case in cases]
        all_prompts.extend(prompts)

        out_path = out_dir / f"{method}_prompts.json"
        write_json(out_path, prompts)
        print(f"Wrote {len(prompts)} prompts: {out_path}")

    combined_path = out_dir / "empirical_hard_pilot_all_prompts.json"
    write_json(combined_path, all_prompts)
    print(f"Wrote {len(all_prompts)} combined prompts: {combined_path}")

    index_path = out_dir / "empirical_hard_pilot_prompt_index.csv"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["case_id", "method", "case_type", "target_signal", "query"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in all_prompts:
            writer.writerow({k: row[k] for k in fieldnames})
    print(f"Wrote prompt index: {index_path}")


if __name__ == "__main__":
    main()
