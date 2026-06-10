# Ablation Results Notes

## Purpose

This note documents the hard-pilot ablation implemented in `evals/run_hard_pilot_ablation_eval.py`.

The ablation tests which GraphRAG inputs matter for edge-grounded reasoning. It compares candidate ranking alone with graph evidence/support context and with the additional explicit validation summary.

## Benchmark Scope

The ablation uses the current hard pilot: 14 cases across 2 prototype scenarios.

1. U.S. influenza missed hospitalization peak.
2. Puerto Rico dengue regional outbreak underprediction.

The dengue scenario is prototype evidence for evaluation, not a final scientific claim about dengue causality.

## Ablation Variants

| Variant | Description |
|---|---|
| Full GraphRAG | Uses candidate ranking, graph evidence lists, support-subgraph-style nodes and edges, and an explicit `validation_summary` derived from retrieved graph evidence. |
| No validation | Uses graph evidence and support context but does not receive the explicit `validation_summary`. |
| Ranking only, no support subgraph | Receives candidate IDs, names, scores, and ranks without support-subgraph edges or detailed evidence edge lists. |

## Current Results

Single-run results from `evals/results/hard_pilot_ablation_summary.csv`:

| Variant | Cases | Candidate Accuracy | Present Edge Precision | Present Edge Recall | Missing Edge Recall | False Edge Claims | Stronger Candidate Accuracy | Weak Candidate Rejection |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Full GraphRAG | 14 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| No validation | 14 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| Ranking only, no support subgraph | 14 | 0.929 | 0.000 | 0.000 | 0.286 | 0 | 1.000 | 1.000 |

## Repeated Ablation Check

Three-run results from `evals/results/hard_pilot_ablation_repeated_summary.csv`:

| Variant | Runs | Cases/Run | Candidate Accuracy Mean/Std | Present Edge Precision Mean/Std | Present Edge Recall Mean/Std | Missing Edge Recall Mean/Std | False Edge Claims Mean/Std | Stronger Candidate Accuracy Mean/Std | Weak Candidate Rejection Mean/Std |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Full GraphRAG | 3 | 14 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 0.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 |
| No validation | 3 | 14 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 0.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 |
| Ranking only, no support subgraph | 3 | 14 | 0.929 / 0.000 | 0.024 / 0.041 | 0.012 / 0.021 | 0.286 / 0.071 | 0.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 |

## Reproducibility

The ablation can be regenerated and summarized with:

```powershell
python evals\run_hard_pilot_ablation_eval.py
python evals\summarize_hard_pilot_ablation_results.py
python evals\run_hard_pilot_ablation_repeated_eval.py --runs 3
```

## Interpretation

Full GraphRAG and No validation perform identically in both the single-run and repeated results. Both variants recover the expected candidates and achieve perfect present-edge, missing-edge, stronger-candidate, and weak-candidate metrics.

The current benchmark therefore does not isolate an independent validation benefit. Validation may still matter under harder conditions, but these results do not provide evidence for that claim.

Ranking only often preserves candidate selection, with 0.929 accuracy in both the single-run and repeated summaries, but it is substantially weaker on edge grounding. Single-run present-edge precision and recall are both 0.000, and repeated present-edge recall is 0.012. Missing-edge recall is also limited to 0.286 in the single-run summary and 0.286 mean across repeated runs.

Graph evidence/support context is the key factor isolated by this ablation. The variants that receive this context preserve edge-level distinctions, while candidate ranking alone does not support reliable edge-grounded reasoning.

## Limitations

The ablation remains small, with 14 cases across 2 prototype scenarios.

The dengue scenario is prototype evidence for evaluation, not a final scientific claim. The evidence and benchmark design are still intended primarily for pipeline testing.

Validation-specific effects require harder or more targeted cases that can separate the explicit validation summary from the underlying graph evidence/support context.

More real-data grounding and scenario diversity are needed before making broad thesis-level claims.

## Next Steps

- Stabilize the current results.
- Use the ablation mainly to support thesis and presentation interpretation.
- Avoid major new ablation work unless it is necessary for the thesis.
- Add targeted validation stress tests only if time allows.
