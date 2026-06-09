# Ablation Results Notes

## Purpose

This note documents the first hard-pilot ablation result from `evals/run_hard_pilot_ablation_eval.py`.

The goal is to begin separating which parts of the GraphRAG pipeline contribute to the current hard-pilot performance: candidate ranking, graph evidence/support context, and validation.

## Ablation Variants

| Variant | Description |
|---|---|
| Full GraphRAG | Uses candidate ranking, graph evidence lists, support-subgraph-style nodes and edges, and an explicit `validation_summary` derived from retrieved graph evidence. |
| No validation | Uses graph evidence and support context, but does not receive the explicit `validation_summary`. |
| Ranking only, no support subgraph | Provides only candidate IDs, names, scores, and ranks. It does not provide support-subgraph edges or detailed evidence edge lists. |

## Current Results

| Variant | Cases | Candidate Accuracy | Present Edge Precision | Present Edge Recall | Missing Edge Recall | False Edge Claims | Stronger Candidate Accuracy | Weak Candidate Rejection |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Full GraphRAG | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| No validation | 10 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| Ranking only, no support subgraph | 10 | 0.900 | 0.000 | 0.000 | 0.300 | 0 | 1.000 | 1.000 |

## Reproducible Summary Script

The ablation results can now be regenerated and summarized with:

```powershell
python evals\run_hard_pilot_ablation_eval.py
python evals\summarize_hard_pilot_ablation_results.py
```

The summary script loads `evals/results/hard_pilot_ablation_results.csv`, groups rows by `variant_name`, computes the main ablation metrics, writes `evals/results/hard_pilot_ablation_summary.csv`, and prints a compact terminal table.

## Repeated-Run Ablation Check

The repeated-run ablation check below is still from the earlier 6-case setup. It
has not yet been rerun on the expanded 10-case hard pilot.

It was run with:

```powershell
python evals\run_hard_pilot_ablation_repeated_eval.py --runs 3
```

| Variant | Runs | Cases/Run | Candidate Accuracy Mean/Std | Present Edge Recall Mean/Std | Missing Edge Recall Mean/Std | Stronger Candidate Accuracy Mean/Std | Weak Candidate Rejection Mean/Std |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full GraphRAG | 3 | 6 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 0.944 / 0.096 | 1.000 / 0.000 |
| No validation | 3 | 6 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 0.833 / 0.289 |
| Ranking only, no support subgraph | 3 | 6 | 1.000 / 0.000 | 0.083 / 0.000 | 0.806 / 0.127 | 1.000 / 0.000 | 1.000 / 0.000 |

## Interpretation

Full GraphRAG and No validation both perform perfectly on the current 10-case ablation. Both variants recover the expected candidate, present edges, missing edges, stronger-candidate field, and weak-candidate rejection decisions.

Ranking only can still often preserve candidate selection, but it fails on edge grounding. Its candidate accuracy is 0.900, while present-edge precision and recall are both 0.000. This shows that candidate ranking alone does not provide enough edge-level evidence for the hard-pilot tasks.

Providing graph evidence/support context is the key ablated factor in this run. When graph evidence and support context are included, both Full GraphRAG and No validation recover perfect present-edge and missing-edge grounding.

The validation effect is not isolated in this 10-case run because Full GraphRAG and No validation perform the same. Validation may still matter in harder or more diverse settings, but this ablation does not currently show a separate validation benefit.

## Limitations

This is still a small result: only 10 hard cases, all within one influenza scenario.

LLM randomness may affect ablation results, especially because the variants depend on structured JSON responses from the model.

Validation effects need a more targeted ablation design or more diverse cases. The repeated-run results are still from the earlier 6-case setup unless rerun later.

## Next Steps

- Rerun repeated ablation on 10 cases later if needed.
- Expand hard cases toward 15-30.
- Add another disease, region, or failure scenario.
- Revisit validation-specific ablation after adding more diverse cases.
- Eventually merge hard-case and ablation findings into the thesis results section.
