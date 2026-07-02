"""
Build adversarial evidence-binding evaluation files.

This evaluation tests whether a method preserves candidate-specific evidence
bindings under noisy, overloaded retrieval context.

It does not call an LLM.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


EVAL_DIR = Path("evals/adversarial_evidence_binding")
DATA_DIR = Path("data/real_processed/adversarial_evidence_binding")

CASES_CSV = EVAL_DIR / "adversarial_evidence_binding_cases.csv"
CASES_JSON = EVAL_DIR / "adversarial_evidence_binding_cases.json"
README = EVAL_DIR / "README_adversarial_evidence_binding.md"

TEXT_CHUNKS = DATA_DIR / "adversarial_text_rag_chunks.json"
GRAPH_CONTEXT = DATA_DIR / "adversarial_graph_context.json"


FACTS = {
    "ili": {
        "candidate": "Outpatient ILI activity",
        "status": "present",
        "lag": "lag 1 week",
        "score": "r=0.958037",
        "paired_weeks": "29 paired weeks",
        "edge": "typed LEADING_INDICATOR_FOR edge",
    },
    "wastewater": {
        "candidate": "Influenza A wastewater concentration",
        "status": "present",
        "lag": "lag 1 week",
        "score": "r=0.947016",
        "paired_weeks": "26 paired weeks",
        "edge": "typed LEADING_INDICATOR_FOR edge",
    },
    "positivity": {
        "candidate": "Influenza test positivity",
        "status": "present",
        "lag": "lag 1 week",
        "score": "r=0.925810",
        "paired_weeks": "29 paired weeks",
        "edge": "typed LEADING_INDICATOR_FOR edge",
    },
    "negative": {
        "candidate": "Negative-control permuted surveillance signal",
        "status": "missing",
        "lag": "lag 4 weeks",
        "score": "r=-0.048027",
        "paired_weeks": "26 paired weeks",
        "edge": "no typed LEADING_INDICATOR_FOR edge",
    },
}

CONTROLLED_DISTRACTORS = [
    "Chile Influenza Activity",
    "Australia Influenza Activity",
    "Travel Importation Pressure",
    "Humidity Drop",
]


def terms(*values: str) -> str:
    return json.dumps(list(values), ensure_ascii=False)


def case(
    case_id: str,
    case_type: str,
    query: str,
    expected_answer: str,
    must_include: list[str],
    must_not_include: list[str],
    notes: str,
) -> dict[str, str]:
    return {
        "case_id": case_id,
        "case_type": case_type,
        "target_signal": "FluSurv-NET influenza hospitalization rate",
        "query": query,
        "expected_answer": expected_answer,
        "must_include_terms": json.dumps(must_include, ensure_ascii=False),
        "must_not_include_terms": json.dumps(must_not_include, ensure_ascii=False),
        "notes": notes,
    }


def build_cases() -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []

    cases.extend(
        [
            case(
                "adv_bind_001",
                "score_binding",
                "Which empirical candidate has r=0.958037, and what lag and edge status belong to it?",
                "Outpatient ILI activity has r=0.958037 at lag 1 week and has a typed LEADING_INDICATOR_FOR edge.",
                [
                    "Outpatient ILI activity",
                    "r=0.958037",
                    "lag 1 week",
                    "typed LEADING_INDICATOR_FOR edge",
                ],
                [
                    "Influenza A wastewater concentration has r=0.958037",
                    "Influenza test positivity has r=0.958037",
                    "Negative-control permuted surveillance signal has r=0.958037",
                    "causal proof",
                ],
                "Tests exact score-to-candidate binding.",
            ),
            case(
                "adv_bind_002",
                "score_binding",
                "Which empirical candidate has r=0.947016, and what paired-week count belongs to it?",
                "Influenza A wastewater concentration has r=0.947016 with 26 paired weeks.",
                [
                    "Influenza A wastewater concentration",
                    "r=0.947016",
                    "26 paired weeks",
                ],
                [
                    "Outpatient ILI activity has r=0.947016",
                    "Influenza test positivity has r=0.947016",
                    "29 paired weeks for wastewater",
                    "causal proof",
                ],
                "Tests score and paired-week binding.",
            ),
            case(
                "adv_bind_003",
                "score_binding",
                "Which empirical candidate has r=0.925810, and what edge status belongs to it?",
                "Influenza test positivity has r=0.925810 and has a typed LEADING_INDICATOR_FOR edge.",
                [
                    "Influenza test positivity",
                    "r=0.925810",
                    "typed LEADING_INDICATOR_FOR edge",
                ],
                [
                    "Outpatient ILI activity has r=0.925810",
                    "Influenza A wastewater concentration has r=0.925810",
                    "no typed LEADING_INDICATOR_FOR edge for test positivity",
                    "causal proof",
                ],
                "Tests score-to-edge binding.",
            ),
            case(
                "adv_bind_004",
                "negative_control_guard",
                "Which candidate has r=-0.048027, and should it be promoted into a typed edge?",
                "The negative-control permuted surveillance signal has r=-0.048027 and should not be promoted into a typed LEADING_INDICATOR_FOR edge.",
                [
                    "Negative-control permuted surveillance signal",
                    "r=-0.048027",
                    "not promoted",
                    "no typed LEADING_INDICATOR_FOR edge",
                ],
                [
                    "typed LEADING_INDICATOR_FOR edge for the negative control",
                    "negative control is present",
                    "causal proof",
                ],
                "Tests negative-control preservation.",
            ),
            case(
                "adv_bind_005",
                "ranking_binding",
                "Rank the three supported empirical candidates by score without mixing their scores.",
                "Outpatient ILI activity ranks first at r=0.958037, Influenza A wastewater concentration second at r=0.947016, and Influenza test positivity third at r=0.925810.",
                [
                    "Outpatient ILI activity",
                    "r=0.958037",
                    "Influenza A wastewater concentration",
                    "r=0.947016",
                    "Influenza test positivity",
                    "r=0.925810",
                ],
                [
                    "Negative-control permuted surveillance signal ranks first",
                    "Chile Influenza Activity",
                    "Australia Influenza Activity",
                    "causal proof",
                ],
                "Tests multi-candidate score ordering.",
            ),
            case(
                "adv_bind_006",
                "claim_vs_edge_count",
                "How many EvidenceClaims exist, and how many typed LEADING_INDICATOR_FOR edges exist?",
                "There are 4 EvidenceClaims but only 3 typed LEADING_INDICATOR_FOR edges.",
                [
                    "4 EvidenceClaims",
                    "3 typed LEADING_INDICATOR_FOR edges",
                ],
                [
                    "4 typed LEADING_INDICATOR_FOR edges",
                    "3 EvidenceClaims",
                    "all EvidenceClaims become typed edges",
                ],
                "Tests distinction between evidence claims and promoted KG edges.",
            ),
            case(
                "adv_bind_007",
                "claim_vs_edge_count",
                "Why does the number of EvidenceClaims differ from the number of typed edges?",
                "The negative-control claim exists as an EvidenceClaim with missing evidence but was not promoted into a typed LEADING_INDICATOR_FOR edge.",
                [
                    "Negative-control permuted surveillance signal",
                    "EvidenceClaim",
                    "missing",
                    "not promoted",
                ],
                [
                    "all EvidenceClaims become typed edges",
                    "negative control was promoted",
                    "causal proof",
                ],
                "Tests promotion logic.",
            ),
            case(
                "adv_bind_008",
                "pipeline_isolation",
                "Should Chile Influenza Activity be included in the empirical_influenza answer?",
                "No. Chile Influenza Activity is a controlled-fixture distractor and should not be included in the empirical_influenza answer.",
                [
                    "No",
                    "Chile Influenza Activity",
                    "controlled-fixture distractor",
                    "empirical_influenza",
                ],
                [
                    "Chile Influenza Activity has empirical_influenza evidence",
                    "Chile Influenza Activity should be included",
                    "r=0.958037 for Chile",
                ],
                "Tests pipeline isolation.",
            ),
            case(
                "adv_bind_009",
                "pipeline_isolation",
                "List only the empirical_influenza candidates and exclude controlled-fixture distractors.",
                "The empirical candidates are Outpatient ILI activity, Influenza A wastewater concentration, Influenza test positivity, and Negative-control permuted surveillance signal.",
                [
                    "Outpatient ILI activity",
                    "Influenza A wastewater concentration",
                    "Influenza test positivity",
                    "Negative-control permuted surveillance signal",
                ],
                [
                    "Chile Influenza Activity",
                    "Australia Influenza Activity",
                    "Travel Importation Pressure",
                    "Humidity Drop",
                ],
                "Tests whether distractor candidates are imported.",
            ),
            case(
                "adv_bind_010",
                "model_revision_guard",
                "Recommend one empirical model-revision candidate and explain the evidence without causal overclaiming.",
                "Outpatient ILI activity is the strongest screening candidate, with present evidence, lag 1 week, r=0.958037, 29 paired weeks, and a typed LEADING_INDICATOR_FOR edge; this is not causal proof and needs downstream validation.",
                [
                    "Outpatient ILI activity",
                    "present",
                    "lag 1 week",
                    "r=0.958037",
                    "29 paired weeks",
                    "typed LEADING_INDICATOR_FOR edge",
                    "not causal proof",
                    "downstream validation",
                ],
                [
                    "forecast improvement is validated",
                    "causal proof",
                    "Negative-control permuted surveillance signal should be added",
                ],
                "Tests evidence-grounded model-edit recommendation.",
            ),
            case(
                "adv_bind_011",
                "model_revision_guard",
                "Which candidate should be excluded from a model revision despite having a listed best lag?",
                "The Negative-control permuted surveillance signal should be excluded because its evidence status is missing, r=-0.048027 at lag 4 weeks, and it has no typed LEADING_INDICATOR_FOR edge.",
                [
                    "Negative-control permuted surveillance signal",
                    "excluded",
                    "missing",
                    "r=-0.048027",
                    "lag 4 weeks",
                    "no typed LEADING_INDICATOR_FOR edge",
                ],
                [
                    "negative control should be added",
                    "negative control is present",
                    "causal proof",
                ],
                "Tests lag without support.",
            ),
            case(
                "adv_bind_012",
                "edge_status_binding",
                "Which three candidates received typed LEADING_INDICATOR_FOR edges?",
                "Outpatient ILI activity, Influenza A wastewater concentration, and Influenza test positivity received typed LEADING_INDICATOR_FOR edges.",
                [
                    "Outpatient ILI activity",
                    "Influenza A wastewater concentration",
                    "Influenza test positivity",
                    "typed LEADING_INDICATOR_FOR edge",
                ],
                [
                    "Negative-control permuted surveillance signal received a typed LEADING_INDICATOR_FOR edge",
                    "Chile Influenza Activity",
                    "Australia Influenza Activity",
                ],
                "Tests promoted edge membership.",
            ),
        ]
    )

    # Add paired comparison cases.
    comparisons = [
        (
            "adv_bind_013",
            "Outpatient ILI activity",
            "r=0.958037",
            "Influenza A wastewater concentration",
            "r=0.947016",
            "Outpatient ILI activity",
        ),
        (
            "adv_bind_014",
            "Influenza A wastewater concentration",
            "r=0.947016",
            "Influenza test positivity",
            "r=0.925810",
            "Influenza A wastewater concentration",
        ),
        (
            "adv_bind_015",
            "Outpatient ILI activity",
            "r=0.958037",
            "Influenza test positivity",
            "r=0.925810",
            "Outpatient ILI activity",
        ),
    ]

    for case_id, a, a_score, b, b_score, stronger in comparisons:
        cases.append(
            case(
                case_id,
                "pairwise_score_binding",
                f"Which candidate is stronger by score: {a} or {b}?",
                f"{stronger} is stronger by score. {a} has {a_score}; {b} has {b_score}.",
                [
                    stronger,
                    a,
                    a_score,
                    b,
                    b_score,
                ],
                [
                    "causal proof",
                    "forecast improvement is validated",
                ],
                "Tests pairwise score comparison without score swapping.",
            )
        )

    cases.extend(
        [
            case(
                "adv_bind_016",
                "paired_week_binding",
                "Which candidates have 29 paired weeks?",
                "Outpatient ILI activity and Influenza test positivity have 29 paired weeks.",
                [
                    "Outpatient ILI activity",
                    "Influenza test positivity",
                    "29 paired weeks",
                ],
                [
                    "Influenza A wastewater concentration has 29 paired weeks",
                    "Negative-control permuted surveillance signal has 29 paired weeks",
                ],
                "Tests paired-week count binding.",
            ),
            case(
                "adv_bind_017",
                "paired_week_binding",
                "Which candidates have 26 paired weeks?",
                "Influenza A wastewater concentration and the Negative-control permuted surveillance signal have 26 paired weeks.",
                [
                    "Influenza A wastewater concentration",
                    "Negative-control permuted surveillance signal",
                    "26 paired weeks",
                ],
                [
                    "Outpatient ILI activity has 26 paired weeks",
                    "Influenza test positivity has 26 paired weeks",
                ],
                "Tests paired-week count binding with one positive and one negative-control claim.",
            ),
            case(
                "adv_bind_018",
                "lag_binding",
                "Which supported empirical candidates have lag 1 week?",
                "Outpatient ILI activity, Influenza A wastewater concentration, and Influenza test positivity are supported candidates at lag 1 week.",
                [
                    "Outpatient ILI activity",
                    "Influenza A wastewater concentration",
                    "Influenza test positivity",
                    "lag 1 week",
                ],
                [
                    "Negative-control permuted surveillance signal is supported at lag 1 week",
                    "Chile Influenza Activity",
                ],
                "Tests lag binding for supported candidates.",
            ),
            case(
                "adv_bind_019",
                "lag_binding",
                "Which candidate has lag 4 weeks, and why is that not enough to support an edge?",
                "The Negative-control permuted surveillance signal has lag 4 weeks, but its evidence status is missing and its score is r=-0.048027, so it has no typed LEADING_INDICATOR_FOR edge.",
                [
                    "Negative-control permuted surveillance signal",
                    "lag 4 weeks",
                    "missing",
                    "r=-0.048027",
                    "no typed LEADING_INDICATOR_FOR edge",
                ],
                [
                    "negative control is supported",
                    "negative control has a typed LEADING_INDICATOR_FOR edge",
                    "causal proof",
                ],
                "Tests lag vs support distinction.",
            ),
            case(
                "adv_bind_020",
                "causal_overclaim_guard",
                "Do these lagged correlations prove that the candidates caused hospitalizations to rise?",
                "No. The lagged correlations are screening evidence for possible model-revision testing, not causal proof.",
                [
                    "No",
                    "screening evidence",
                    "not causal proof",
                ],
                [
                    "prove causality",
                    "caused hospitalizations",
                    "forecast improvement is validated",
                ],
                "Tests causal-overclaim guard.",
            ),
        ]
    )

    return cases


def build_text_chunks() -> list[dict[str, str]]:
    return [
        {
            "chunk_id": "adv_text_mixed_001",
            "title": "Overloaded empirical influenza memo with distractors",
            "text": (
                "Pipeline: empirical_influenza. Target: FluSurv-NET influenza hospitalization rate. "
                "Real empirical candidates: Outpatient ILI activity, Influenza A wastewater concentration, "
                "Influenza test positivity, and Negative-control permuted surveillance signal. "
                "Outpatient ILI activity: status present; lag 1 week; r=0.958037; 29 paired weeks; "
                "promoted to typed LEADING_INDICATOR_FOR edge. Influenza A wastewater concentration: "
                "status present; lag 1 week; r=0.947016; 26 paired weeks; promoted to typed "
                "LEADING_INDICATOR_FOR edge. Influenza test positivity: status present; lag 1 week; "
                "r=0.925810; 29 paired weeks; promoted to typed LEADING_INDICATOR_FOR edge. "
                "Negative-control permuted surveillance signal: status missing; lag 4 weeks; "
                "r=-0.048027; 26 paired weeks; retained as EvidenceClaim only; no typed "
                "LEADING_INDICATOR_FOR edge. Distractors from a different controlled fixture: "
                "Chile Influenza Activity, Australia Influenza Activity, Travel Importation Pressure, "
                "Humidity Drop. Do not import those into empirical_influenza."
            ),
        },
        {
            "chunk_id": "adv_text_mixed_002",
            "title": "Noisy notes with explicit traps",
            "text": (
                "Draft note: a sloppy summary might say there are four leading-indicator edges because "
                "there are four EvidenceClaims, but that is wrong. Correct record: there are four "
                "EvidenceClaims and only three typed LEADING_INDICATOR_FOR edges. The negative control "
                "has a listed best lag but missing evidence, so best lag alone does not imply support. "
                "Do not treat lagged correlation as causal proof. Do not say forecast improvement has "
                "already been validated. Do not assign r=0.958037 to wastewater or test positivity; "
                "that score belongs to Outpatient ILI activity. Do not assign r=0.947016 to ILI; "
                "that score belongs to wastewater. Do not assign r=0.925810 to ILI or wastewater; "
                "that score belongs to test positivity."
            ),
        },
        {
            "chunk_id": "adv_text_mixed_003",
            "title": "Model revision constraints",
            "text": (
                "For a cautious model-revision test, the strongest empirical screening candidate is "
                "Outpatient ILI activity because it has status present, lag 1 week, r=0.958037, "
                "29 paired weeks, and a typed LEADING_INDICATOR_FOR edge. Wastewater and test positivity "
                "are also supported screening candidates, but lower by score. The negative-control "
                "permuted surveillance signal should be excluded from model revision because it has "
                "status missing and no typed edge. All model edits require downstream validation before "
                "claiming forecast improvement."
            ),
        },
        {
            "chunk_id": "adv_text_mixed_004",
            "title": "Pipeline isolation warning",
            "text": (
                "This adversarial text chunk intentionally mentions controlled-fixture candidates: "
                "Chile Influenza Activity, Australia Influenza Activity, Travel Importation Pressure, "
                "and Humidity Drop. They are not part of empirical_influenza. They must not be mixed "
                "with the real empirical candidates. The empirical_influenza candidates are only "
                "Outpatient ILI activity, Influenza A wastewater concentration, Influenza test positivity, "
                "and Negative-control permuted surveillance signal."
            ),
        },
    ]


def build_graph_context() -> dict[str, object]:
    claims = []
    edges = []

    for key, fact in FACTS.items():
        claims.append(
            {
                "candidate": fact["candidate"],
                "target": "FluSurv-NET influenza hospitalization rate",
                "evidence_status": fact["status"],
                "lag": fact["lag"],
                "score": fact["score"],
                "paired_weeks": fact["paired_weeks"],
                "pipeline": "empirical_influenza",
            }
        )

        if fact["status"] == "present":
            edges.append(
                {
                    "source": fact["candidate"],
                    "target": "FluSurv-NET influenza hospitalization rate",
                    "edge_type": "LEADING_INDICATOR_FOR",
                    "evidence_status": fact["status"],
                    "lag": fact["lag"],
                    "score": fact["score"],
                    "paired_weeks": fact["paired_weeks"],
                    "pipeline": "empirical_influenza",
                }
            )

    return {
        "pipeline": "empirical_influenza",
        "target": "FluSurv-NET influenza hospitalization rate",
        "claims": claims,
        "typed_edges": edges,
        "controlled_fixture_distractors_to_exclude": CONTROLLED_DISTRACTORS,
        "interpretation_constraints": [
            "Lagged correlation is screening evidence, not causal proof.",
            "Forecast improvement requires downstream validation.",
            "EvidenceClaim existence does not imply typed edge promotion.",
            "The negative control is missing evidence and must not be promoted.",
        ],
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "case_id",
        "case_type",
        "target_signal",
        "query",
        "expected_answer",
        "must_include_terms",
        "must_not_include_terms",
        "notes",
    ]

    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    cases = build_cases()

    write_csv(CASES_CSV, cases)
    CASES_JSON.write_text(json.dumps(cases, indent=2), encoding="utf-8")

    TEXT_CHUNKS.write_text(
        json.dumps(build_text_chunks(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    GRAPH_CONTEXT.write_text(
        json.dumps(build_graph_context(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    README.write_text(
        """# Adversarial Evidence-Binding Evaluation

This evaluation tests whether a method preserves candidate-specific evidence
bindings under overloaded retrieval context.

It is designed to stress these failure modes:

1. Score-to-candidate binding.
2. Lag-to-candidate binding.
3. EvidenceClaim versus promoted typed edge.
4. Missing negative-control preservation.
5. Pipeline isolation from controlled-fixture distractors.
6. Model-revision recommendations without causal overclaiming.

This is not an independent outbreak evaluation. It is an adversarial
evidence-preservation benchmark derived from the empirical influenza KG claims.

The expected thesis interpretation is conditional: GraphRAG should only be
claimed better than Text-RAG if it preserves these bindings more reliably under
the adversarial text condition.
""",
        encoding="utf-8",
    )

    case_types: dict[str, int] = {}
    for row in cases:
        case_types[row["case_type"]] = case_types.get(row["case_type"], 0) + 1

    print(f"Wrote {len(cases)} cases to {CASES_CSV}")
    print(f"Wrote text chunks to {TEXT_CHUNKS}")
    print(f"Wrote graph context to {GRAPH_CONTEXT}")
    print("Case types:")
    for key, value in sorted(case_types.items()):
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
