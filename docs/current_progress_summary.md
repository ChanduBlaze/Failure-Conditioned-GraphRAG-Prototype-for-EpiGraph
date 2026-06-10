# Current Progress Summary

## Thesis Direction

My thesis direction is graph-structured retrieval for LLM-guided scientific reasoning in epidemiological model revision.

The working hypothesis is that a knowledge graph can improve LLM reasoning by retrieving structured evidence about possible missing drivers in an epidemiological model, helping the LLM produce explanations and model-edit suggestions that are more grounded than LLM-only reasoning.

## Prototype Status

I have built a Neo4j-backed GraphRAG prototype for forecast-failure analysis in epidemiological model revision.

The prototype now supports two prototype failure scenarios:

| Scenario | Disease | Region | Failure Pattern | Target Signal |
|---|---|---|---|---|
| U.S. influenza missed hospitalization peak | Influenza | United States | Underpredicted / missed peak | `signal_us_hosp` |
| Puerto Rico dengue regional outbreak underprediction | Dengue | Puerto Rico | Underpredicted / missed peak | `signal_pr_dengue_cases` |

The original influenza scenario uses `signal_chile_flu` / Chile Influenza Activity as the strongest current candidate. The second dengue scenario uses `signal_vector_index` / Mosquito Vector Index as the strongest current candidate.

The dengue scenario is prototype evidence for testing the evaluation pipeline. It should not be presented as a final scientific claim about dengue causality.

## Evaluation Methods

I compare four evaluation methods:

| Method | Description |
|---|---|
| KG-only | Uses Neo4j retrieval and graph validation without an LLM. |
| LLM-only | Gives the LLM only the failure case and candidate list, without retrieval evidence. |
| Text-RAG | Retrieves plain text chunks from a small text corpus, without Neo4j paths or support subgraphs. |
| GraphRAG | Uses Neo4j retrieval, support-subgraph evidence, validation context, and LLM reasoning. |

## Hard Pilot Evaluation

The hard pilot now has 14 cases across two prototype scenarios.

| Case Range | Scenario | Purpose |
|---|---|---|
| `hard_case_001`-`hard_case_010` | U.S. influenza missed hospitalization peak | Missing edges, partial evidence, weak-candidate rejection, candidate contrast, and strongest-candidate completeness. |
| `hard_case_011`-`hard_case_014` | Puerto Rico dengue regional outbreak underprediction | Tests the same evaluation pipeline on a second disease, region, mechanism, target signal, and candidate set. |

The hard pilot tests missing-edge detection, partial-evidence detection, weak-candidate rejection, stronger-candidate identification, and candidate-specific edge grounding.

## Current 14-Case Hard Pilot Results

| Method | Cases | Candidate Accuracy | Present Edge Precision | Present Edge Recall | Missing Edge Recall | False Claims | Stronger Candidate Accuracy | Weak Candidate Rejection |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| KG-only | 14 | N/A | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| LLM-only | 14 | 1.000 | 1.000 | 0.726 | 0.929 | 0 | 0.929 | 1.000 |
| Text-RAG | 14 | 0.929 | 0.845 | 0.857 | 0.821 | 3 | 0.643 | 1.000 |
| GraphRAG | 14 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |

## Repeated Hard Pilot Method Check

I also ran a 3-run repeated check for the LLM-based methods.

| Method | Runs | Cases/Run | Candidate Accuracy Mean/Std | Present Edge Precision Mean/Std | Present Edge Recall Mean/Std | Missing Edge Recall Mean/Std | False Claims Mean/Std | Stronger Candidate Accuracy Mean/Std | Weak Candidate Rejection Mean/Std |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LLM-only | 3 | 14 | 0.976 / 0.041 | 0.988 / 0.021 | 0.706 / 0.025 | 0.905 / 0.041 | 0.333 / 0.577 | 0.905 / 0.041 | 1.000 / 0.000 |
| Text-RAG | 3 | 14 | 0.976 / 0.041 | 0.817 / 0.055 | 0.786 / 0.062 | 0.964 / 0.036 | 0.667 / 1.155 | 0.643 / 0.071 | 1.000 / 0.000 |
| GraphRAG | 3 | 14 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 0.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 |

## Ablation Study

The hard-pilot ablation compares three variants:

| Variant | Description |
|---|---|
| Full GraphRAG | Uses candidate ranking, graph evidence lists, support-subgraph-style nodes and edges, and an explicit `validation_summary` derived from retrieved graph evidence. |
| No validation | Uses graph evidence and support context, but does not receive the explicit `validation_summary`. |
| Ranking only, no support subgraph | Provides only candidate IDs, names, scores, and ranks. It does not provide support-subgraph edges or detailed evidence edge lists. |

## Current 14-Case Ablation Results

| Variant | Cases | Candidate Accuracy | Present Edge Precision | Present Edge Recall | Missing Edge Recall | False Edge Claims | Stronger Candidate Accuracy | Weak Candidate Rejection |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Full GraphRAG | 14 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| No validation | 14 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| Ranking only, no support subgraph | 14 | 0.929 | 0.000 | 0.000 | 0.286 | 0 | 1.000 | 1.000 |

## Repeated Ablation Check

I also ran a 3-run repeated ablation check.

| Variant | Runs | Cases/Run | Candidate Accuracy Mean/Std | Present Edge Precision Mean/Std | Present Edge Recall Mean/Std | Missing Edge Recall Mean/Std | False Edge Claims Mean/Std | Stronger Candidate Accuracy Mean/Std | Weak Candidate Rejection Mean/Std |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Full GraphRAG | 3 | 14 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 0.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 |
| No validation | 3 | 14 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 0.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 |
| Ranking only, no support subgraph | 3 | 14 | 0.929 / 0.000 | 0.024 / 0.041 | 0.012 / 0.021 | 0.286 / 0.071 | 0.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 |

## Interpretation

The hard pilot is no longer limited to one scenario. It now tests the evaluation pipeline across both the original U.S. influenza missed-hospitalization-peak scenario and a second Puerto Rico dengue regional outbreak underprediction scenario.

GraphRAG remains stable across both prototype scenarios. In both the single-run and repeated-run hard-pilot checks, GraphRAG recovers the expected candidate, present evidence edges, missing evidence edges, stronger candidate, and weak-candidate rejection decisions.

LLM-only is strong on candidate selection, but it remains weaker than GraphRAG on edge recall and stronger-candidate identification. This suggests that plausible language reasoning can often select the right candidate, but it is less reliable at preserving exact graph evidence distinctions.

Text-RAG retrieves useful information, but it can blur candidate-specific evidence and comparison evidence. This is especially visible in stronger-candidate identification, where Text-RAG is weaker than GraphRAG in both the single-run and repeated-run results.

The ablation results show that ranking alone can often preserve candidate selection, but it fails on edge-grounded reasoning. The ranking-only variant has very low present-edge and missing-edge grounding compared with variants that receive graph evidence and support context.

Full GraphRAG and No validation still perform the same in the current ablation. Therefore, this ablation mainly isolates the importance of graph evidence/support context rather than the independent value of validation.

## Limitations

These are still prototype results, not final thesis-level evidence. The benchmark has 14 hard cases and 2 prototype scenarios, which is stronger than the earlier single-scenario setup but still small.

The dengue scenario is prototype evidence designed to test the evaluation pipeline. It should not be presented as a final scientific claim about dengue causality.

The current graph and text corpus are still manually constructed. More real-data grounding, more diseases, more regions, and more diverse failure modes would be needed before making broad claims about general epidemiological discovery.

LLM stochasticity can still affect LLM-only, Text-RAG, and GraphRAG outputs, although the repeated checks show GraphRAG is stable on the current benchmark.

## Next Steps

- Stabilize the current 14-case two-scenario results.
- Avoid major new feature work unless it is necessary for the thesis.
- Prepare thesis and presentation interpretation around the current hard-pilot and ablation findings.
- Add real-data grounding only if time allows.
