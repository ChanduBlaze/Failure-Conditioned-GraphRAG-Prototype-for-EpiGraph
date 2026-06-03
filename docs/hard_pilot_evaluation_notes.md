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

## Current Results

These results compare the hard pilot versions of KG-only, LLM-only, Text-RAG, and GraphRAG. The KG-only result uses graph retrieval directly. The other methods ask an LLM to return extended fields such as `identified_missing_edges`, `rejected_candidate_ids`, and `weak_candidate_ids`.

| Method | Cases | Candidate Accuracy | Present Edge Precision | Present Edge Recall | Missing Edge Recall | False Claims | Stronger Candidate Accuracy | Weak Candidate Rejection |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| KG-only | 3 | N/A | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| LLM-only | 3 | 1.000 | 0.667 | 0.333 | 0.667 | 0 | 1.000 | 1.000 |
| Text-RAG | 3 | 1.000 | 0.667 | 0.500 | 1.000 | 0 | 1.000 | 1.000 |
| GraphRAG | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |

## Interpretation

The KG-only hard pilot shows that the graph evidence itself supports the hard-case distinctions. The current Neo4j ranking and evidence representation recover the present edges, identify the missing edges, rank Chile above the weaker or partial candidates, and reject the weak Humidity Drop candidate.

The stronger-candidate metric is now cleaner because the LLM-based hard-pilot runners explicitly ask for a `stronger_candidate_id` field instead of inferring the answer from raw response text.

LLM-only gets the candidate and stronger-candidate fields right, but its edge grounding is still weak. It has low present-edge recall and lower missing-edge recall than the retrieval-based methods. This suggests that the LLM can produce plausible answers to the hard-case questions, but without retrieval it is less reliable about which evidence relationships are present or absent.

Text-RAG retrieval is now fairer because expected labels are excluded from the retrieval query. It uses only the hard pilot question and failure-case values. After this change, Text-RAG still identifies missing edges, the stronger candidate, and the weak candidate, but its present-edge grounding drops.

GraphRAG remains perfect across the current hard-pilot metrics. It recovers the expected present and missing edges, identifies the stronger candidate, and rejects the weak candidate in all three pilot cases.

This is a useful next step because it begins testing the kinds of reasoning needed for a stronger thesis evaluation: not only finding the best-supported candidate, but also recognizing why other plausible candidates are incomplete or weak.

## Important Limitation

The pilot is very small: only 3 cases, all within the same U.S. influenza hidden-driver scenario. It should be treated as a schema and scoring sanity check, not final thesis evidence.

Text-RAG retrieval may still be helped by the small corpus. It no longer uses expected labels directly, but the current text corpus is compact and directly states the relevant edge patterns. Harder cases should reduce this advantage by adding more distractor chunks, more candidates, and more scenarios.

The hard-pilot comparison should be expanded before making strong claims about method differences.

## Next Steps

- Expand hard cases to more candidates and scenarios.
- Add more distractor chunks to the text corpus.
- Eventually merge hard-case scoring into the main benchmark once the schema and metrics are stable.
