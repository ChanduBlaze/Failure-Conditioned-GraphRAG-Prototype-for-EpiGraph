# Current Progress Summary

## Thesis Direction

My thesis direction is graph-structured retrieval for LLM-guided scientific reasoning in epidemiological model revision.

The working hypothesis is that a knowledge graph can improve LLM reasoning by retrieving structured evidence about possible missing drivers in an epidemiological model, helping the LLM produce explanations and model-edit suggestions that are more grounded than LLM-only reasoning.

## Prototype Status

I have built a Neo4j-backed GraphRAG prototype around a U.S. influenza forecast-failure scenario. The failure case is an underpredicted or missed U.S. hospitalization peak.

The prototype stores candidate hidden-driver evidence in Neo4j and retrieves graph support for possible explanations of the forecast failure. The current top candidate is `signal_chile_flu`, representing Chile Influenza Activity.

Chile Influenza Activity is currently supported by three key graph relationships:

| Relationship | Target |
|---|---|
| `LEADING_INDICATOR_FOR` | U.S. hospitalizations |
| `IMPORTATION_LINK` | U.S. flu mechanism |
| `POSSIBLE_DRIVER_OF` | U.S. flu mechanism |

The GraphRAG workflow retrieves this evidence, builds a support subgraph, validates the candidate, and asks the LLM to explain the evidence and propose a testable model edit, such as adding a lagged Chile importation signal to the mechanism.

## Evaluation Methods

I have implemented four evaluation methods:

| Method | Description |
|---|---|
| KG-only | Uses Neo4j retrieval and graph validation without an LLM. |
| LLM-only | Uses only the failure case and candidate list, without retrieval evidence. |
| Text-RAG | Retrieves plain text chunks from a small text corpus, without Neo4j paths or support subgraphs. |
| GraphRAG + LLM | Uses Neo4j retrieval, support subgraph evidence, validation, and LLM reasoning. |

The benchmark has been expanded from 3 starter cases to 10 cases. The newer cases test candidate ranking, candidate contrast, evidence edge retrieval, support-subgraph reasoning, provenance/dataset support, and text-RAG distractors.

## Current 10-Case Results

| Method | Top-1 Accuracy | Evidence Precision | Evidence Recall | Hallucinated Evidence Count |
|---|---:|---:|---:|---:|
| KG-only | 1.000 | 1.000 | 1.000 | 0 |
| LLM-only | 0.200 | 0.000 | 0.000 | 20 |
| Text-RAG | 0.900 | 1.000 | 1.000 | 0 |
| GraphRAG + LLM | 1.000 | 1.000 | 1.000 | 0 |

## Hard Pilot Evaluation

I have also started a separate hard pilot benchmark for cases that go beyond top-candidate selection. This pilot now has 6 cases and uses `evals/eval_cases_hard_pilot.json`, shared metric helpers in `evals/eval_metrics.py`, and separate hard-pilot runners for KG-only, LLM-only, Text-RAG, and GraphRAG.

The hard pilot tests:

- Missing-edge detection.
- Partial-evidence detection.
- Weak-candidate rejection.

The six pilot cases are:

| Case | Purpose |
|---|---|
| Australia missing `IMPORTATION_LINK` | Tests whether the evaluator can identify that Australia has partial evidence but lacks importation support. |
| Travel Pressure missing `LEADING_INDICATOR_FOR` | Tests whether the evaluator can identify that Travel Pressure has importation evidence but lacks leading-indicator evidence. |
| Humidity Drop weak-candidate case | Tests whether the evaluator treats Humidity Drop as weak because it has only `POSSIBLE_DRIVER_OF` evidence. |
| Chile strongest compared with Australia | Tests whether the evaluator identifies Chile as the strongest supported candidate because it has all three expected support edges. |
| Travel Pressure as partial support | Tests whether the evaluator explains why Travel Pressure is partial support rather than the best hidden driver. |
| Humidity Drop should not outrank importation candidates | Tests whether the evaluator avoids promoting Humidity Drop above candidates with importation-related support. |

Current hard pilot results:

| Method | Cases | Candidate Accuracy | Present Edge Precision | Present Edge Recall | Missing Edge Recall | False Claims | Stronger Candidate Accuracy | Weak Candidate Rejection |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| KG-only | 6 | N/A | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| LLM-only | 6 | 0.833 | 0.306 | 0.250 | 0.500 | 1 | 0.500 | 1.000 |
| Text-RAG | 6 | 1.000 | 0.667 | 0.583 | 0.750 | 0 | 0.667 | 0.500 |
| GraphRAG | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |

## Ablation Study

I have started a first hard-pilot ablation study using `evals/run_hard_pilot_ablation_eval.py`. This runner compares Full GraphRAG, No validation, and Ranking only without support-subgraph evidence on the same 6 hard cases.

Current ablation results:

| Variant | Cases | Candidate Accuracy | Present Edge Precision | Present Edge Recall | Missing Edge Recall | False Edge Claims | Stronger Candidate Accuracy | Weak Candidate Rejection |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Full GraphRAG | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| No validation | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| Ranking only, no support subgraph | 6 | 1.000 | 0.333 | 0.167 | 0.667 | 0 | 1.000 | 1.000 |

## Interpretation

The current results suggest that LLM-only reasoning is not reliable for this task. It produced plausible-sounding explanations, but it selected the correct candidate in only 20 percent of the cases and hallucinated evidence relationships that were not part of the expected graph evidence.

KG-only retrieval performed perfectly on this current benchmark, showing that the Neo4j evidence and ranking logic can recover the expected candidate and support edges for the current scenario.

Text-RAG performed strongly, but missed one candidate-selection case. This is useful because it begins to show a separation between flattened text retrieval and structured graph retrieval. However, Text-RAG is still advantaged by the fact that the current text corpus is small and directly states much of the answer.

GraphRAG + LLM also performed perfectly on the 10-case benchmark. It kept the LLM grounded in the support subgraph while still producing natural-language explanations and model-edit proposals. This is the main behavior the thesis is trying to study: using graph-structured retrieval to support evidence-grounded scientific reasoning.

The hard pilot now compares KG-only, LLM-only, Text-RAG, and GraphRAG on 6 missing-edge, partial-evidence, weak-candidate, and candidate-contrast tasks. Stronger-candidate scoring now uses an explicit `stronger_candidate_id` field, making that metric cleaner than the earlier inferred version.

The expanded hard pilot gives a clearer separation across methods. LLM-only becomes weaker on candidate selection, edge grounding, missing-edge recall, false claims, and stronger-candidate identification. This suggests that plausible natural-language reasoning alone is not enough to reliably track the graph evidence distinctions.

Text-RAG retrieval is now fairer because expected labels are excluded from the retrieval query; it uses only the hard-pilot question and failure-case values. The Text-RAG corpus now has 15 chunks, expanded from 7 by adding realistic distractors. Text-RAG keeps candidate accuracy at 1.000, but it has imperfect edge grounding, missing-edge recall, stronger-candidate identification, and weak-candidate rejection.

GraphRAG remains perfect across the current 6-case hard-pilot metrics. This gives a clearer separation between LLM-only reasoning, flattened Text-RAG retrieval, and graph-structured retrieval.

The first ablation result suggests that ranking alone can preserve candidate selection in this 6-case pilot, but ranking alone is not enough for edge-grounded reasoning. Providing graph evidence and support context improves present-edge and missing-edge grounding. Full GraphRAG and No Validation currently perform the same, so this first ablation does not yet isolate validation effects.

## Limitations

These results are promising, but they are not final thesis-level evidence. The benchmark is still small and focused on one Chile hidden-driver scenario. It does not yet include enough variation across diseases, regions, mechanisms, candidate types, or failure modes.

The hard pilot is also still small and remains within one influenza scenario. The added Text-RAG distractors make the setting more realistic, but more diseases, regions, candidate types, and failure modes are needed before making strong claims about method differences.

The ablation study is also small and one-scenario. LLM randomness may affect the results, and the No Validation variant currently receives the same graph evidence context as Full GraphRAG, so the validation ablation needs refinement.

## Next Steps

- Refine the validation ablation.
- Add a clearer support-subgraph-without-validation variant if needed.
- Expand the hard pilot toward 15-30 hard cases.
- Later merge hard-case scoring into the main benchmark.
- Expand the benchmark toward 25-50 diverse evaluation cases.
- Later connect the reasoning layer to a forecasting or surprisal signal so that the system can start from detected forecast failures rather than a manually specified failure case.
