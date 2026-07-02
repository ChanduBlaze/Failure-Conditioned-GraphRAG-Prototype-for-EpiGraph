"""
Build information-matched respiratory expansion evaluation cases and prompts.

Methods:
    resp_exp_text_rag_unstructured_full
    resp_exp_graphrag_context

Both methods receive the same 21 evidence claims. Text-RAG receives them as
unstructured memo text. GraphRAG receives them as structured claim/edge JSON.

This script does not call an LLM.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


CLAIMS = Path("data/real_processed/respiratory_expansion/respiratory_expansion_evidence_claims.csv")
TEXT_CONTEXT = Path("data/real_processed/respiratory_expansion/respiratory_expansion_text_context.txt")
GRAPH_CONTEXT = Path("data/real_processed/respiratory_expansion/respiratory_expansion_graph_context.json")

EVAL_DIR = Path("evals/respiratory_expansion")
PROMPT_DIR = EVAL_DIR / "prompts"
OUTPUT_DIR = EVAL_DIR / "model_outputs"

CASES_CSV = EVAL_DIR / "respiratory_expansion_cases.csv"
CASES_JSON = EVAL_DIR / "respiratory_expansion_cases.json"

TEXT_PROMPTS = PROMPT_DIR / "resp_exp_text_rag_unstructured_full_prompts.json"
GRAPH_PROMPTS = PROMPT_DIR / "resp_exp_graphrag_context_prompts.json"
ALL_PROMPTS = PROMPT_DIR / "respiratory_expansion_all_prompts.json"
PROMPT_INDEX = PROMPT_DIR / "respiratory_expansion_prompt_index.csv"

TEXT_JSONL = OUTPUT_DIR / "resp_exp_text_rag_unstructured_full_prompts_for_filling.jsonl"
GRAPH_JSONL = OUTPUT_DIR / "resp_exp_graphrag_context_prompts_for_filling.jsonl"


def read_claims() -> list[dict[str, str]]:
    with CLAIMS.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def required_exact_binding_terms(row: dict[str, str]) -> list[str]:
    return [
        row["candidate_label"],
        row["target_label"],
        f"lag={row['best_lag_weeks']}",
        f"r={row['pearson_r']}",
        f"paired_weeks={row['paired_weeks']}",
        f"evidence_status={row['evidence_status']}",
        f"edge_type={row['promoted_edge_type']}",
    ]


def expected_binding_answer(row: dict[str, str]) -> str:
    return (
        f"{row['candidate_label']} -> {row['target_label']}: "
        f"lag={row['best_lag_weeks']}, r={row['pearson_r']}, "
        f"paired_weeks={row['paired_weeks']}, "
        f"evidence_status={row['evidence_status']}, "
        f"edge_type={row['promoted_edge_type']}. "
        f"This is screening evidence only, not causal proof or validated forecast improvement."
    )


def make_case(
    case_id: str,
    case_type: str,
    question: str,
    expected_answer: str,
    must_include_terms: list[str],
    must_not_include_terms: list[str] | None = None,
) -> dict[str, str]:
    return {
        "case_id": case_id,
        "case_type": case_type,
        "question": question,
        "expected_answer": expected_answer,
        "must_include_terms_json": json.dumps(must_include_terms),
        "must_not_include_terms_json": json.dumps(
            must_not_include_terms or [
                "causal proof",
                "validated forecast improvement",
                "causal discovery",
            ]
        ),
    }


def build_cases(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    cases = []
    idx = 1

    promoted = [r for r in rows if r["promoted_edge_type"] != "NO_TYPED_EDGE"]
    missing = [r for r in rows if r["promoted_edge_type"] == "NO_TYPED_EDGE"]

    # 1. Exact binding cases for all promoted edges.
    for row in promoted:
        cases.append(
            make_case(
                f"resp_exp_{idx:03d}",
                "promoted_exact_binding",
                (
                    f"Give the exact evidence binding for candidate '{row['candidate_label']}' "
                    f"and target '{row['target_label']}'. Use the format "
                    f"candidate -> target: lag=..., r=..., paired_weeks=..., "
                    f"evidence_status=..., edge_type=...."
                ),
                expected_binding_answer(row),
                required_exact_binding_terms(row),
            )
        )
        idx += 1

    # 2. Exact binding cases for representative missing/unpromoted claims.
    representative_missing = []
    for target in ["influenza", "covid", "rsv"]:
        target_missing = [r for r in missing if r["target_disease"] == target]
        negative = [
            r for r in target_missing
            if r["candidate_family"] == "negative_control"
        ]
        cross_disease = [
            r for r in target_missing
            if r["candidate_disease"] not in (target, "none")
        ]
        same_family_missing = [
            r for r in target_missing
            if r["candidate_disease"] == target
        ]

        representative_missing.extend(negative[:1])
        representative_missing.extend(cross_disease[:2])
        representative_missing.extend(same_family_missing[:1])

    # Keep deterministic unique order.
    seen_claims = set()
    representative_missing_unique = []
    for row in representative_missing:
        if row["claim_id"] not in seen_claims:
            representative_missing_unique.append(row)
            seen_claims.add(row["claim_id"])

    for row in representative_missing_unique:
        cases.append(
            make_case(
                f"resp_exp_{idx:03d}",
                "missing_exact_binding",
                (
                    f"Give the exact evidence binding for the unpromoted claim involving "
                    f"candidate '{row['candidate_label']}' and target '{row['target_label']}'. "
                    f"Use the format candidate -> target: lag=..., r=..., paired_weeks=..., "
                    f"evidence_status=..., edge_type=...."
                ),
                expected_binding_answer(row),
                required_exact_binding_terms(row),
            )
        )
        idx += 1

    # 3. Strongest promoted edge by target.
    for target in ["influenza", "covid", "rsv"]:
        target_promoted = [r for r in promoted if r["target_disease"] == target]
        strongest = max(target_promoted, key=lambda r: float(r["pearson_r"]))

        cases.append(
            make_case(
                f"resp_exp_{idx:03d}",
                "strongest_promoted_by_target",
                (
                    f"Among promoted typed edges for the {target} hospitalization target, "
                    f"which candidate has the strongest Pearson correlation? Return the exact "
                    f"candidate, target, lag, r, paired_weeks, evidence_status, and edge_type."
                ),
                expected_binding_answer(strongest),
                required_exact_binding_terms(strongest),
            )
        )
        idx += 1

    # 4. Leading-indicator edge by target.
    for target in ["influenza", "covid", "rsv"]:
        target_leading = [
            r for r in promoted
            if r["target_disease"] == target
            and r["promoted_edge_type"] == "LEADING_INDICATOR_FOR"
        ]

        for row in target_leading:
            cases.append(
                make_case(
                    f"resp_exp_{idx:03d}",
                    "leading_indicator_by_target",
                    (
                        f"Which promoted candidate is a LEADING_INDICATOR_FOR the {target} "
                        f"hospitalization target? Return the exact binding."
                    ),
                    expected_binding_answer(row),
                    required_exact_binding_terms(row),
                )
            )
            idx += 1

    # 5. Concurrent edge discrimination.
    for row in promoted:
        if row["promoted_edge_type"] != "CONCURRENT_INDICATOR_FOR":
            continue

        cases.append(
            make_case(
                f"resp_exp_{idx:03d}",
                "concurrent_indicator_discrimination",
                (
                    f"For target '{row['target_label']}', identify the promoted concurrent "
                    f"indicator involving '{row['candidate_label']}'. Return the exact binding."
                ),
                expected_binding_answer(row),
                required_exact_binding_terms(row),
            )
        )
        idx += 1

    # 6. Negative-control guard cases.
    for row in missing:
        if row["candidate_family"] != "negative_control":
            continue

        cases.append(
            make_case(
                f"resp_exp_{idx:03d}",
                "negative_control_guard",
                (
                    f"What happened to the deterministic negative-control surveillance signal "
                    f"for target '{row['target_label']}'? Return the exact binding and edge status."
                ),
                expected_binding_answer(row),
                required_exact_binding_terms(row),
            )
        )
        idx += 1

    # 7. Model revision guard: choose promoted edges only, avoid unsupported edits.
    for target in ["influenza", "covid", "rsv"]:
        target_promoted = [r for r in promoted if r["target_disease"] == target]
        target_missing = [r for r in missing if r["target_disease"] == target]
        strongest = max(target_promoted, key=lambda r: float(r["pearson_r"]))
        weakest_missing = min(target_missing, key=lambda r: float(r["pearson_r"]))

        required = required_exact_binding_terms(strongest) + [
            "screening evidence only",
            weakest_missing["candidate_label"],
            "should not be promoted",
        ]

        expected = (
            f"For a candidate model revision for {target}, use the promoted binding "
            f"{expected_binding_answer(strongest)} "
            f"The unsupported candidate {weakest_missing['candidate_label']} should not be promoted."
        )

        cases.append(
            make_case(
                f"resp_exp_{idx:03d}",
                "model_revision_guard",
                (
                    f"For the {target} hospitalization target, recommend one candidate signal "
                    f"that could be considered for a model-revision hypothesis, and name one "
                    f"unsupported candidate that should not be promoted. Preserve the exact binding."
                ),
                expected,
                required,
            )
        )
        idx += 1

    return cases


def system_instruction() -> str:
    return (
        "You are evaluating evidence preservation after epidemiological forecast failure. "
        "Use only the provided context. Preserve exact candidate-target bindings. "
        "Do not claim causal discovery. Do not claim validated forecast improvement. "
        "Return concise answers with exact lag, r, paired_weeks, evidence_status, and edge_type."
    )


def build_prompt(case: dict[str, str], method: str, context: str) -> dict[str, str]:
    prompt = (
        f"{system_instruction()}\n\n"
        f"METHOD: {method}\n\n"
        f"CONTEXT:\n{context}\n\n"
        f"QUESTION:\n{case['question']}\n\n"
        f"ANSWER:"
    )

    return {
        "case_id": case["case_id"],
        "method": method,
        "case_type": case["case_type"],
        "question": case["question"],
        "prompt": prompt,
    }


def write_cases(cases: list[dict[str, str]]) -> None:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "case_id",
        "case_type",
        "question",
        "expected_answer",
        "must_include_terms_json",
        "must_not_include_terms_json",
    ]

    with CASES_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(cases)

    CASES_JSON.write_text(json.dumps(cases, indent=2), encoding="utf-8")


def write_prompts(prompts: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(prompts, indent=2), encoding="utf-8")


def write_jsonl(prompts: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        for prompt in prompts:
            f.write(json.dumps(prompt, ensure_ascii=False) + "\n")


def main() -> None:
    rows = read_claims()
    cases = build_cases(rows)

    text_context = TEXT_CONTEXT.read_text(encoding="utf-8")
    graph_context = GRAPH_CONTEXT.read_text(encoding="utf-8")

    text_prompts = [
        build_prompt(case, "resp_exp_text_rag_unstructured_full", text_context)
        for case in cases
    ]

    graph_prompts = [
        build_prompt(case, "resp_exp_graphrag_context", graph_context)
        for case in cases
    ]

    all_prompts = text_prompts + graph_prompts

    write_cases(cases)
    write_prompts(text_prompts, TEXT_PROMPTS)
    write_prompts(graph_prompts, GRAPH_PROMPTS)
    write_prompts(all_prompts, ALL_PROMPTS)
    write_jsonl(text_prompts, TEXT_JSONL)
    write_jsonl(graph_prompts, GRAPH_JSONL)

    with PROMPT_INDEX.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["case_id", "method", "case_type", "question"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for prompt in all_prompts:
            writer.writerow({k: prompt[k] for k in fieldnames})

    print(f"Wrote {len(cases)} cases")
    print(f"Wrote {len(text_prompts)} Text-RAG prompts")
    print(f"Wrote {len(graph_prompts)} GraphRAG prompts")
    print(f"Wrote {len(all_prompts)} total prompts")
    print(f"Cases: {CASES_CSV}")
    print(f"Text JSONL: {TEXT_JSONL}")
    print(f"Graph JSONL: {GRAPH_JSONL}")


if __name__ == "__main__":
    main()
