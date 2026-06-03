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

## Current Results

These results compare the hard pilot versions of KG-only, LLM-only, Text-RAG, and GraphRAG. The KG-only result uses graph retrieval directly. The other methods ask an LLM to return extended fields such as `identified_missing_edges`, `rejected_candidate_ids`, and `weak_candidate_ids`.

| Method | Cases | Candidate Accuracy | Present Edge Precision | Present Edge Recall | Missing Edge Recall | False Claims | Stronger Candidate Accuracy | Weak Candidate Rejection |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| KG-only | 6 | N/A | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| LLM-only | 6 | 0.833 | 0.306 | 0.250 | 0.500 | 1 | 0.500 | 1.000 |
| Text-RAG | 6 | 1.000 | 0.667 | 0.583 | 0.750 | 0 | 0.667 | 0.500 |
| GraphRAG | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |

## Interpretation

The hard pilot has been expanded from 3 cases to 6 cases while staying within the same U.S. influenza scenario. The added cases test whether methods can explain why Chile is strongest compared with Australia, why Travel Pressure is partial support rather than the best hidden driver, and why Humidity Drop should not outrank importation-related candidates.

The KG-only hard pilot shows that the graph evidence itself supports these hard-case distinctions. The current Neo4j ranking and evidence representation recover the present edges, identify the missing edges, rank Chile above the weaker or partial candidates, and reject the weak Humidity Drop candidate.

The stronger-candidate metric is now cleaner because the LLM-based hard-pilot runners explicitly ask for a `stronger_candidate_id` field instead of inferring the answer from raw response text.

LLM-only becomes weaker on the expanded hard pilot. It now misses one candidate-selection case, has weak present-edge precision and recall, lower missing-edge recall, one false edge claim, and weaker stronger-candidate identification. This suggests that the LLM can still produce plausible explanations, but without retrieval it is less reliable about which evidence relationships are present, absent, or comparatively stronger.

Text-RAG retrieval is now fairer because expected labels are excluded from the retrieval query. It uses only the hard pilot question and failure-case values. The text corpus has also been expanded from 7 chunks to 15 chunks by adding realistic distractor chunks about surveillance, travel seasonality, respiratory transmission, hospitalization reporting lag, generic model underprediction, noisy warnings, incomplete evidence, and external-driver model edits.

Adding these distractor chunks makes the Text-RAG setting harder and more realistic. Text-RAG keeps candidate accuracy at 1.000, but its edge grounding remains imperfect. It has lower present-edge recall than GraphRAG, imperfect missing-edge recall, imperfect stronger-candidate identification, and weaker weak-candidate rejection.

GraphRAG remains perfect across the current 6-case hard-pilot metrics. It recovers the expected present and missing edges, identifies the stronger candidate, and rejects the weak candidate in the current pilot.

This gives a clearer separation between LLM-only reasoning, flattened Text-RAG retrieval, and graph-structured retrieval. The current result suggests that graph structure is helping preserve edge-level distinctions that become easier to blur in text-only settings.

## Important Limitation

The pilot is still small and remains within one U.S. influenza hidden-driver scenario. It should be treated as a schema and scoring sanity check, not final thesis evidence.

Text-RAG retrieval may still be helped by the limited corpus and narrow scenario. It no longer uses expected labels directly, and the added distractors make the setting more realistic, but more diseases, regions, candidate types, and failure modes are needed before making strong claims about method differences.

The hard-pilot comparison should be expanded before making strong claims about method differences.

## Next Steps

- Expand the hard pilot toward 15-30 hard cases.
- Add an ablation study next.
- Later merge hard-case scoring into the main benchmark once the schema and metrics are stable.
