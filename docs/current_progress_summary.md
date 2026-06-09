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

I have also started a separate hard pilot benchmark for cases that go beyond top-candidate selection. This pilot now has 10 cases and uses `evals/eval_cases_hard_pilot.json`, shared metric helpers in `evals/eval_metrics.py`, and separate hard-pilot runners for KG-only, LLM-only, Text-RAG, and GraphRAG.

The hard pilot tests:

- Missing-edge detection.
- Partial-evidence detection.
- Weak-candidate rejection.

The 10 pilot cases are:

| Case | Purpose |
|---|---|
| `hard_case_001` | Australia missing `IMPORTATION_LINK`; tests whether the evaluator can identify partial evidence but missing importation support. |
| `hard_case_002` | Travel Pressure missing `LEADING_INDICATOR_FOR`; tests whether the evaluator can identify importation support but missing leading-indicator evidence. |
| `hard_case_003` | Humidity Drop weak-candidate case; tests whether the evaluator treats Humidity Drop as weak because it has only `POSSIBLE_DRIVER_OF` evidence. |
| `hard_case_004` | Chile strongest compared with Australia; tests whether the evaluator identifies Chile as the strongest supported candidate. |
| `hard_case_005` | Travel Pressure as partial support; tests whether the evaluator explains why Travel Pressure is not the best hidden driver. |
| `hard_case_006` | Humidity Drop should not outrank importation candidates; tests whether the evaluator avoids promoting weak environmental support above importation-related support. |
| `hard_case_007` | Humidity as noisy or plausible environmental distractor; tests whether the evaluator separates plausible environmental signals from stronger outbreak-relevant support. |
| `hard_case_008` | Australia partial-vs-full support contrast; tests whether the evaluator recognizes partial support while identifying the more complete candidate. |
| `hard_case_009` | Travel mechanism-only/importation support; tests whether the evaluator recognizes mechanism and importation support while identifying missing leading-indicator evidence. |
| `hard_case_010` | Chile strongest-candidate completeness case; tests whether the evaluator returns the evaluated candidate itself when it is also strongest or most complete. |

The LLM-based hard-pilot runners now use stricter non-leaking edge-list guidance. Edge-list fields must contain only exact relationship type names: `LEADING_INDICATOR_FOR`, `IMPORTATION_LINK`, and `POSSIBLE_DRIVER_OF`. Comparison-candidate edges should appear only in the explanation, not in `mentioned_evidence_edges`, and if the evaluated candidate is itself strongest or most complete, `stronger_candidate_id` should return that candidate ID.

Current hard pilot results:

| Method | Cases | Candidate Accuracy | Present Edge Precision | Present Edge Recall | Missing Edge Recall | False Claims | Stronger Candidate Accuracy | Weak Candidate Rejection |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| KG-only | 10 | N/A | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| LLM-only | 10 | 0.900 | 0.900 | 0.617 | 0.950 | 1 | 0.900 | 0.667 |
| Text-RAG | 10 | 1.000 | 0.750 | 0.700 | 0.900 | 1 | 0.700 | 1.000 |
| GraphRAG | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |

## Ablation Study

I have started a first hard-pilot ablation study using `evals/run_hard_pilot_ablation_eval.py`. This runner compares Full GraphRAG, No validation, and Ranking only without support-subgraph evidence on the same 10 hard cases. Full GraphRAG receives an explicit `validation_summary` derived from retrieved graph evidence; No validation receives graph evidence/support context without that summary.

The ablation workflow is now reproducible. The runner writes `evals/results/hard_pilot_ablation_results.csv`, and `evals/summarize_hard_pilot_ablation_results.py` writes `evals/results/hard_pilot_ablation_summary.csv`.

```powershell
python evals\run_hard_pilot_ablation_eval.py
python evals\summarize_hard_pilot_ablation_results.py
```

Current ablation results:

| Variant | Cases | Candidate Accuracy | Present Edge Precision | Present Edge Recall | Missing Edge Recall | False Edge Claims | Stronger Candidate Accuracy | Weak Candidate Rejection |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Full GraphRAG | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| No validation | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| Ranking only, no support subgraph | 10 | 0.900 | 0.000 | 0.000 | 0.300 | 0 | 1.000 | 1.000 |

A repeated-run check was also added to estimate LLM variability. These repeated-run results are still from the earlier 6-case setup unless rerun later:

```powershell
python evals\run_hard_pilot_ablation_repeated_eval.py --runs 3
```

| Variant | Runs | Cases/Run | Candidate Accuracy Mean/Std | Present Edge Recall Mean/Std | Missing Edge Recall Mean/Std | Stronger Candidate Accuracy Mean/Std | Weak Candidate Rejection Mean/Std |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full GraphRAG | 3 | 6 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 0.944 / 0.096 | 1.000 / 0.000 |
| No validation | 3 | 6 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 0.833 / 0.289 |
| Ranking only, no support subgraph | 3 | 6 | 1.000 / 0.000 | 0.083 / 0.000 | 0.806 / 0.127 | 1.000 / 0.000 | 1.000 / 0.000 |

## Interpretation

The current results suggest that LLM-only reasoning is not reliable for this task. It produced plausible-sounding explanations, but it selected the correct candidate in only 20 percent of the cases and hallucinated evidence relationships that were not part of the expected graph evidence.

KG-only retrieval performed perfectly on this current benchmark, showing that the Neo4j evidence and ranking logic can recover the expected candidate and support edges for the current scenario.

Text-RAG performed strongly, but missed one candidate-selection case. This is useful because it begins to show a separation between flattened text retrieval and structured graph retrieval. However, Text-RAG is still advantaged by the fact that the current text corpus is small and directly states much of the answer.

GraphRAG + LLM also performed perfectly on the 10-case benchmark. It kept the LLM grounded in the support subgraph while still producing natural-language explanations and model-edit proposals. This is the main behavior the thesis is trying to study: using graph-structured retrieval to support evidence-grounded scientific reasoning.

The hard pilot now compares KG-only, LLM-only, Text-RAG, and GraphRAG on 10 missing-edge, partial-evidence, weak-candidate, candidate-contrast, and strongest-candidate completeness tasks. Stronger-candidate scoring uses an explicit `stronger_candidate_id` field, making that metric cleaner than the earlier inferred version.

The KG-only result confirms that the current graph evidence supports the expected hard-case distinctions. The graph representation recovers the expected present and missing edges, identifies the stronger candidate when applicable, and rejects the weak candidate in this pilot.

LLM-only improved after stricter edge-list formatting, but it remains weaker than the graph-based methods on present-edge recall and weak-candidate rejection. This suggests that plausible natural-language reasoning alone is still less reliable for tracking which graph relationships are present, absent, or comparatively stronger.

Text-RAG retrieval is now fairer because expected labels are excluded from the retrieval query; it uses only the hard-pilot question and failure-case values. The Text-RAG corpus now has 15 chunks, expanded from 7 by adding realistic distractors. Text-RAG gets candidate selection right across the current 10 hard cases, but it remains weaker on edge grounding and stronger-candidate identification.

GraphRAG is perfect across the current 10-case hard-pilot metrics. This supports graph-structured evidence as useful for grounded reasoning because it helps preserve edge-level distinctions that are easier to blur in text-only settings. The result is encouraging pilot evidence, not final thesis evidence.

The 10-case ablation shows that Full GraphRAG and No validation both perform perfectly. Ranking only preserves candidate selection fairly well at 0.900 candidate accuracy, but it fails on edge grounding: present-edge precision and recall are both 0.000. This shows that candidate ranking alone does not provide enough edge-level evidence for the hard-pilot tasks.

Graph evidence/support context is the key ablated factor in this run. Validation is not isolated in this 10-case run because Full GraphRAG and No validation perform the same. Validation may still matter in harder or more diverse settings, but this run does not show a separate validation benefit.

## Limitations

These results are promising, but they are not final thesis-level evidence. The benchmark is still small and focused on one Chile hidden-driver scenario. It does not yet include enough variation across diseases, regions, mechanisms, candidate types, or failure modes.

The hard pilot is also still small and remains within one influenza scenario. It now has 10 hard cases, which is useful for debugging and comparison but still too small for strong claims. LLM stochasticity can affect LLM-only, Text-RAG, and GraphRAG results, so repeated runs may vary.

The added Text-RAG distractors make the setting more realistic, but more diseases, regions, candidate types, and failure modes are needed before making strong claims about method differences.

The ablation is now 10 cases, but it is still one influenza scenario. Validation effects need a more targeted ablation design or more diverse cases. The repeated-run ablation results are still from the earlier 6-case setup unless rerun later.

## Next Steps

- Expand the hard pilot toward 15-30 hard cases.
- Add another disease, region, or failure scenario.
- Rerun repeated ablation on 10 cases later if needed.
- Revisit validation-specific ablation after adding more diverse cases.
- Consider more repeated runs later if cost and time allow.
- Later merge hard-case scoring into the main benchmark.
- Eventually merge hard-case and ablation findings into the thesis results section.
