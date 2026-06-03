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
| LLM-only | 3 | 1.000 | 0.500 | 0.333 | 0.667 | 1 | 0.667 | 1.000 |
| Text-RAG | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0.000 | 1.000 |
| GraphRAG | 3 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0.000 | 1.000 |

## Interpretation

The KG-only hard pilot shows that the graph evidence itself supports the hard-case distinctions. The current Neo4j ranking and evidence representation recover the present edges, identify the missing edges, rank Chile above the weaker or partial candidates, and reject the weak Humidity Drop candidate.

LLM-only gets the candidate IDs right, but its edge grounding is weak. It has low present-edge recall, lower missing-edge recall, and one false missing-edge claim. This suggests that the LLM can produce plausible answers to the hard-case questions, but without retrieval it is less reliable about which evidence relationships are present or absent.

Text-RAG and GraphRAG both do well on the present-edge and missing-edge metrics in this 3-case pilot. Both methods identify the expected candidate, recover the expected present evidence, identify the expected missing evidence, and avoid false edge claims.

The stronger-candidate identification metric is currently not reliable. The current LLM hard-pilot schemas do not directly ask for a `stronger_candidate_id` field, so the evaluator infers this metric from the predicted candidate or raw response text. That makes the metric too brittle to interpret as a clean comparison between Text-RAG and GraphRAG yet.

This is a useful next step because it begins testing the kinds of reasoning needed for a stronger thesis evaluation: not only finding the best-supported candidate, but also recognizing why other plausible candidates are incomplete or weak.

## Important Limitation

The pilot is very small: only 3 cases, all within the same U.S. influenza hidden-driver scenario. It should be treated as a schema and scoring sanity check, not final thesis evidence.

The stronger-candidate metric needs a cleaner schema. Future LLM hard-pilot outputs should include an explicit `stronger_candidate_id` field rather than relying on text matching or indirect inference.

Text-RAG retrieval may still be helped by the small corpus. Because the current text corpus is compact and directly states the relevant edge patterns, Text-RAG can retrieve highly targeted chunks. Harder cases should reduce this advantage by adding more distractor chunks, more candidates, and more scenarios.

## Next Steps

- Add a stricter `stronger_candidate_id` output field to the LLM-only, Text-RAG, and GraphRAG hard-pilot schemas.
- Remove answer-key leakage from the Text-RAG hard-pilot retrieval query if present, especially direct use of expected candidate IDs or expected edge fields.
- Expand hard cases to more candidates and scenarios.
- Eventually merge hard-case scoring into the main benchmark once the schema and metrics are stable.
