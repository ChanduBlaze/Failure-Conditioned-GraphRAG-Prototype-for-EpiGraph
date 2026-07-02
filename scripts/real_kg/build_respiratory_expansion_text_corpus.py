"""
Build an information-matched unstructured Text-RAG corpus from the respiratory
expansion evidence claims.

The Text-RAG corpus contains the same factual evidence bindings as the graph
context, but represents them as noisy prose rather than structured edges.

Inputs:
    data/real_processed/respiratory_expansion/respiratory_expansion_evidence_claims.csv
    data/real_processed/respiratory_expansion/respiratory_expansion_graph_context.json

Outputs:
    data/real_processed/respiratory_expansion/respiratory_expansion_text_corpus.json
    data/real_processed/respiratory_expansion/respiratory_expansion_text_context.txt
    evals/respiratory_expansion/respiratory_expansion_information_parity_check.csv
    evals/respiratory_expansion/respiratory_expansion_information_parity_summary.json

This script does not call an LLM.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


CLAIMS = Path("data/real_processed/respiratory_expansion/respiratory_expansion_evidence_claims.csv")
GRAPH_CONTEXT = Path("data/real_processed/respiratory_expansion/respiratory_expansion_graph_context.json")

TEXT_CORPUS = Path("data/real_processed/respiratory_expansion/respiratory_expansion_text_corpus.json")
TEXT_CONTEXT = Path("data/real_processed/respiratory_expansion/respiratory_expansion_text_context.txt")

PARITY_CHECK = Path("evals/respiratory_expansion/respiratory_expansion_information_parity_check.csv")
PARITY_SUMMARY = Path("evals/respiratory_expansion/respiratory_expansion_information_parity_summary.json")


def read_claims() -> list[dict[str, str]]:
    with CLAIMS.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def claim_sentence(row: dict[str, str]) -> str:
    return (
        f"In the respiratory expansion screening run, the candidate signal "
        f"{row['candidate_label']} was compared with the target "
        f"{row['target_label']}. The best lag was {row['best_lag_weeks']} weeks, "
        f"the Pearson correlation was r={row['pearson_r']}, and the comparison used "
        f"{row['paired_weeks']} paired weeks. The evidence status for this candidate-target "
        f"binding was {row['evidence_status']}. The promoted edge type was "
        f"{row['promoted_edge_type']}."
    )


def build_chunks(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    promoted = [r for r in rows if r["promoted_edge_type"] != "NO_TYPED_EDGE"]
    missing = [r for r in rows if r["promoted_edge_type"] == "NO_TYPED_EDGE"]

    chunks = []

    chunks.append(
        {
            "chunk_id": "resp_exp_text_chunk_001_methods",
            "title": "Respiratory expansion screening method notes",
            "text": (
                "This memo describes a respiratory surveillance screening run for influenza, "
                "COVID-19, and RSV hospitalization targets. Candidate signals include wastewater "
                "viral activity, pathogen test positivity, and a deterministic negative-control "
                "signal. The screening rule uses lagged or concurrent Pearson correlation as "
                "evidence. A claim is promoted only when it has enough paired weeks and reaches "
                "the correlation threshold. These relationships are screening evidence only. "
                "They do not prove causality and they do not demonstrate forecast improvement."
            ),
        }
    )

    # Deterministic but intentionally mixed order: interleave promoted and missing claims.
    mixed_rows = []
    max_len = max(len(promoted), len(missing))
    for i in range(max_len):
        if i < len(missing):
            mixed_rows.append(missing[i])
        if i < len(promoted):
            mixed_rows.append(promoted[i])

    group_size = 5
    for idx in range(0, len(mixed_rows), group_size):
        group = mixed_rows[idx : idx + group_size]
        sentences = []

        sentences.append(
            "The following notes are copied from analyst memo fragments rather than from a clean table. "
            "Several diseases and signal families are discussed together, so candidate-target bindings "
            "must be read carefully."
        )

        for row in group:
            sentences.append(claim_sentence(row))

            if row["candidate_family"] == "wastewater":
                sentences.append(
                    "This wastewater note should be interpreted as a surveillance signal comparison, "
                    "not as proof that wastewater caused the hospitalization pattern."
                )
            elif row["candidate_family"] == "test_positivity":
                sentences.append(
                    "This laboratory positivity note may overlap seasonally with other respiratory "
                    "viruses, so the candidate name and target name should not be merged."
                )
            elif row["candidate_family"] == "negative_control":
                sentences.append(
                    "The negative-control signal is included to test whether unsupported claims remain "
                    "unpromoted."
                )

        chunks.append(
            {
                "chunk_id": f"resp_exp_text_chunk_{len(chunks)+1:03d}_memo",
                "title": f"Mixed respiratory evidence memo fragment {len(chunks)}",
                "text": " ".join(sentences),
            }
        )

    chunks.append(
        {
            "chunk_id": "resp_exp_text_chunk_final_constraints",
            "title": "Interpretation constraints",
            "text": (
                "EvidenceClaim existence is not the same as a promoted typed edge. Claims with "
                "NO_TYPED_EDGE should not be treated as leading indicators. Negative-control claims "
                "should remain unpromoted. Concurrent indicators and leading indicators should not be "
                "collapsed into one category. The result should preserve the exact candidate, target, "
                "lag, score, paired-week count, evidence status, and promoted edge type."
            ),
        }
    )

    return chunks


def write_text_outputs(chunks: list[dict[str, str]]) -> None:
    TEXT_CORPUS.parent.mkdir(parents=True, exist_ok=True)
    TEXT_CORPUS.write_text(json.dumps(chunks, indent=2), encoding="utf-8")

    context = []
    for chunk in chunks:
        context.append(f"### {chunk['title']}\n{chunk['text']}")

    TEXT_CONTEXT.write_text("\n\n".join(context), encoding="utf-8")


def graph_has_claim(graph: dict, row: dict[str, str]) -> bool:
    claims = graph.get("claims", [])
    for claim in claims:
        if claim.get("claim_id") != row["claim_id"]:
            continue

        fields = [
            "target_label",
            "candidate_label",
            "best_lag_weeks",
            "pearson_r",
            "paired_weeks",
            "evidence_status",
            "promoted_edge_type",
        ]

        return all(str(claim.get(field, "")) == str(row.get(field, "")) for field in fields)

    return False


def text_has_claim(text: str, row: dict[str, str]) -> bool:
    required_terms = [
        row["candidate_label"],
        row["target_label"],
        f"best lag was {row['best_lag_weeks']} weeks",
        f"r={row['pearson_r']}",
        f"{row['paired_weeks']} paired weeks",
        f"evidence status for this candidate-target binding was {row['evidence_status']}",
        f"promoted edge type was {row['promoted_edge_type']}",
    ]

    return all(term in text for term in required_terms)


def run_parity_check(rows: list[dict[str, str]]) -> None:
    graph = json.loads(GRAPH_CONTEXT.read_text(encoding="utf-8"))
    text = TEXT_CONTEXT.read_text(encoding="utf-8")

    forbidden_hint_phrases = [
        "correct answer",
        "answer key",
        "gold answer",
        "do not assign r=",
        "that score belongs to",
    ]

    hint_phrase_hits = [phrase for phrase in forbidden_hint_phrases if phrase in text.lower()]

    out_rows = []
    for row in rows:
        text_ok = text_has_claim(text, row)
        graph_ok = graph_has_claim(graph, row)

        out_rows.append(
            {
                "claim_id": row["claim_id"],
                "target_label": row["target_label"],
                "candidate_label": row["candidate_label"],
                "text_context_has_full_binding": str(text_ok),
                "graph_context_has_full_binding": str(graph_ok),
                "information_parity_pass": str(text_ok and graph_ok),
                "promoted_edge_type": row["promoted_edge_type"],
                "evidence_status": row["evidence_status"],
            }
        )

    PARITY_CHECK.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "claim_id",
        "target_label",
        "candidate_label",
        "text_context_has_full_binding",
        "graph_context_has_full_binding",
        "information_parity_pass",
        "promoted_edge_type",
        "evidence_status",
    ]

    with PARITY_CHECK.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)

    summary = {
        "claim_count": len(out_rows),
        "text_context_full_binding_count": sum(
            1 for r in out_rows if r["text_context_has_full_binding"] == "True"
        ),
        "graph_context_full_binding_count": sum(
            1 for r in out_rows if r["graph_context_has_full_binding"] == "True"
        ),
        "information_parity_pass_count": sum(
            1 for r in out_rows if r["information_parity_pass"] == "True"
        ),
        "information_parity_pass_rate": (
            sum(1 for r in out_rows if r["information_parity_pass"] == "True") / len(out_rows)
            if out_rows else 0.0
        ),
        "forbidden_answer_hint_phrases_found": hint_phrase_hits,
        "outputs": {
            "text_corpus": str(TEXT_CORPUS),
            "text_context": str(TEXT_CONTEXT),
            "parity_check": str(PARITY_CHECK),
        },
    }

    PARITY_SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main() -> None:
    rows = read_claims()
    chunks = build_chunks(rows)
    write_text_outputs(chunks)
    run_parity_check(rows)


if __name__ == "__main__":
    main()
