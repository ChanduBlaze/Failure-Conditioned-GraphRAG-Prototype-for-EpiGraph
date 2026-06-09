# Hard Pilot Evaluation Notes

## Purpose

The hard pilot benchmark was created to test evaluation tasks that go beyond simple top-candidate selection. The main benchmark in `evals/eval_cases.json` currently focuses on selecting the expected top candidate and matching expected evidence edges. That is useful, but it does not fully test whether a method can recognize missing evidence, partial support, or weak candidates.

For that reason, the hard pilot cases are kept in a separate file: `evals/eval_cases_hard_pilot.json`. This keeps the current 10-case benchmark stable while allowing the evaluation schema and scoring logic to be extended safely.

## What The Hard Pilot Tests

### Missing-Edge Detection

Missing-edge detection means checking whether a method can identify that a candidate lacks an important relationship. For example, Australia Influenza Activity has some relevant evidence, but it does not have an `IMPORTATION_LINK` to the U.S. influenza base mechanism in the current graph.

### Partial-Evidence Detection

Partial-evidence detection means recognizing that a candidate has some valid support but not the complete evidence pattern needed for full support. Travel Importation Pressure has importation and possible-driver evidence, but it lacks the `LEADING_INDICATOR_FOR` relationship to U.S. hospitalizations.

### Weak-Candidate Rejection

Weak-candidate rejection means avoiding the mistake of treating a weakly supported candidate as a fully supported explanation. Humidity Drop Anomaly has only `POSSIBLE_DRIVER_OF` evidence in the current graph, so it should be treated as weak compared with Chile Influenza Activity.

## Pilot Cases

| Case | Task | What It Tests |
|---|---|---|
| `hard_case_001` | Australia missing `IMPORTATION_LINK` | Tests whether the evaluator can identify that Australia has `LEADING_INDICATOR_FOR` and `POSSIBLE_DRIVER_OF`, but lacks `IMPORTATION_LINK`. |
| `hard_case_002` | Travel Pressure missing `LEADING_INDICATOR_FOR` | Tests whether the evaluator can identify that Travel Pressure has `IMPORTATION_LINK` and `POSSIBLE_DRIVER_OF`, but lacks `LEADING_INDICATOR_FOR`. |
| `hard_case_003` | Humidity Drop weak-candidate case | Tests whether the evaluator can treat Humidity Drop as weak because it has only `POSSIBLE_DRIVER_OF` and lacks both `LEADING_INDICATOR_FOR` and `IMPORTATION_LINK`. |
| `hard_case_004` | Chile strongest compared with Australia | Tests whether the evaluator can identify Chile as the strongest supported candidate because it has all three expected support edges. |
| `hard_case_005` | Travel Pressure as partial support | Tests whether the evaluator can explain why Travel Pressure has partial support but should not be treated as the best hidden driver. |
| `hard_case_006` | Humidity Drop should not outrank importation candidates | Tests whether the evaluator can avoid promoting Humidity Drop above candidates with importation-related support. |
| `hard_case_007` | Humidity as noisy environmental distractor | Tests whether the evaluator can distinguish a plausible environmental signal from candidates with stronger outbreak-relevant support. |
| `hard_case_008` | Australia partial-vs-full support contrast | Tests whether the evaluator can recognize Australia as partially supported while identifying the more complete candidate. |
| `hard_case_009` | Travel mechanism-only/importation support | Tests whether the evaluator can identify mechanism and importation support while recognizing missing leading-indicator evidence. |
| `hard_case_010` | Chile strongest-candidate completeness case | Tests whether the evaluator can return the evaluated candidate itself when it is also the strongest or most complete candidate. |

The LLM-based hard-pilot prompts now use stricter non-leaking guidance for edge-list fields. The fields must contain only exact relationship type names: `LEADING_INDICATOR_FOR`, `IMPORTATION_LINK`, and `POSSIBLE_DRIVER_OF`. Comparison-candidate edges belong in the explanation only, not in `mentioned_evidence_edges`, and explanatory phrases, node names, arrows, and parentheses are not allowed in either edge list. A domain-specific Humidity/Chile formatting example was removed to avoid leaking answer patterns into the prompt.

## Current Results

These results compare the hard pilot versions of KG-only, LLM-only, Text-RAG, and GraphRAG. The KG-only result uses graph retrieval directly. The other methods ask an LLM to return extended fields such as `identified_missing_edges`, `rejected_candidate_ids`, and `weak_candidate_ids`.

| Method | Cases | Candidate Accuracy | Present Edge Precision | Present Edge Recall | Missing Edge Recall | False Claims | Stronger Candidate Accuracy | Weak Candidate Rejection |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| KG-only | 10 | N/A | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| LLM-only | 10 | 0.900 | 0.900 | 0.617 | 0.950 | 1 | 0.900 | 0.667 |
| Text-RAG | 10 | 1.000 | 0.750 | 0.700 | 0.900 | 1 | 0.700 | 1.000 |
| GraphRAG | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |

## Interpretation

The hard pilot has been expanded from 6 cases to 10 cases while staying within the same U.S. influenza scenario. The added cases increase coverage of noisy environmental distractors, partial-vs-full support, mechanism-only/importation support, and cases where the evaluated candidate is itself the strongest candidate.

The KG-only hard pilot shows that the graph evidence itself supports these hard-case distinctions. The current Neo4j ranking and evidence representation recover the expected present and missing edges, identify the stronger candidate when applicable, and reject the weak candidate in the current pilot.

The stronger-candidate metric is now cleaner because the LLM-based hard-pilot runners explicitly ask for a `stronger_candidate_id` field instead of inferring the answer from raw response text. The prompts also clarify that if the predicted or evaluated candidate is itself the strongest or most complete candidate, `stronger_candidate_id` should return that same candidate ID.

LLM-only performs better than in the earlier hard pilot after stricter edge-list formatting, but it still has weaker present-edge recall and weak-candidate rejection than the graph-based methods. This suggests that the LLM can produce plausible explanations, but without retrieval it remains less reliable about which evidence relationships are present, absent, or comparatively stronger.

Text-RAG retrieval is now fairer because expected labels are excluded from the retrieval query. It uses only the hard pilot question and failure-case values. The text corpus has also been expanded from 7 chunks to 15 chunks by adding realistic distractor chunks about surveillance, travel seasonality, respiratory transmission, hospitalization reporting lag, generic model underprediction, noisy warnings, incomplete evidence, and external-driver model edits.

Adding these distractor chunks makes the Text-RAG setting harder and more realistic. Text-RAG gets candidate selection right across the current 10 cases, but its edge grounding remains imperfect. It has lower present-edge precision and recall than GraphRAG, one false edge claim, and weaker stronger-candidate identification.

GraphRAG is perfect across the current 10-case hard-pilot metrics. It recovers the expected present and missing edges, identifies the stronger candidate, and rejects the weak candidate in the current pilot.

This gives a clearer separation between LLM-only reasoning, flattened Text-RAG retrieval, and graph-structured retrieval. The current result supports graph-structured evidence as useful for grounded reasoning because it helps preserve edge-level distinctions that are easier to blur in text-only settings. The benchmark is still small, so this should be treated as encouraging pilot evidence rather than a final thesis claim.

## Important Limitation

The pilot is still small and remains within one U.S. influenza hidden-driver scenario. It should be treated as a schema and scoring sanity check, not final thesis evidence.

The benchmark now has 10 hard cases, which is useful for debugging and comparison but still too small for strong general claims. LLM stochasticity can also affect LLM-only, Text-RAG, and GraphRAG results, so repeated runs may vary.

Text-RAG retrieval may still be helped by the limited corpus and narrow scenario. It no longer uses expected labels directly, and the added distractors make the setting more realistic, but more diseases, regions, candidate types, and failure modes are needed before making strong claims about method differences.

## Next Steps

- Update `current_progress_summary.md` next.
- Expand the hard pilot toward 15-30 hard cases.
- Add another disease, region, or failure scenario before relying on large claims.
- Rerun or extend the ablation study after the hard pilot includes more cases or another scenario.
- Later merge hard-case scoring into the main benchmark once the schema and metrics are stable.
