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

These results come from `evals/run_hard_pilot_eval.py`, which uses Neo4j retrieval and shared metric helpers from `evals/eval_metrics.py`.

| Metric | Result |
|---|---:|
| Cases | 3 |
| Average present-edge precision | 1.000 |
| Average present-edge recall | 1.000 |
| Average missing-edge recall | 1.000 |
| Missing-edge false claim count | 0 |
| Stronger-candidate ranking accuracy | 1.000 |
| Weak-candidate rejection accuracy | 1.000 |

## Interpretation

The hard pilot shows that the current Neo4j/KG retrieval layer correctly represents the partial evidence patterns for Australia, Travel Pressure, and Humidity Drop. It can recover the present evidence edges, identify expected missing edges, and confirm that the stronger candidate, Chile Influenza Activity, ranks above the weaker or partial candidates.

This is a useful next step because it begins testing the kinds of reasoning needed for a stronger thesis evaluation: not only finding the best-supported candidate, but also recognizing why other plausible candidates are incomplete or weak.

## Important Limitation

This is currently a graph/KG-only hard pilot. It does not yet evaluate LLM-only, Text-RAG, or GraphRAG on these hard cases.

The current hard pilot therefore demonstrates that the graph-side evidence and scoring logic can support harder cases, but it does not yet show how LLM reasoning behaves when asked to identify missing edges, reject weak candidates, or reason over partial support. Those comparisons require extending the LLM output schemas and runners.

The pilot is also very small: only 3 cases, all within the same U.S. influenza hidden-driver scenario. It should be treated as a schema and scoring sanity check, not final thesis evidence.

## Next Steps

- Extend LLM output schemas to include `identified_missing_edges`, `rejected_candidate_ids`, `weak_candidate_ids`, and `mentioned_support_nodes`.
- Update LLM-only, Text-RAG, and GraphRAG runners to score missing-edge detection, weak-candidate rejection, and support-node reasoning.
- Add hard-pilot result summaries to the comparison workflow after the LLM-based runners support the new fields.
- Expand the hard cases beyond the current influenza scenario so the benchmark can test more diverse missing-driver and partial-evidence patterns.
