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
| Full GraphRAG | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| No validation | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 0.833 | 1.000 |
| Ranking only, no support subgraph | 6 | 1.000 | 0.167 | 0.083 | 0.750 | 0 | 1.000 | 1.000 |

## Reproducible Summary Script

The ablation results can now be regenerated and summarized with:

```powershell
python evals\run_hard_pilot_ablation_eval.py
python evals\summarize_hard_pilot_ablation_results.py
```

The summary script loads `evals/results/hard_pilot_ablation_results.csv`, groups rows by `variant_name`, computes the main ablation metrics, writes `evals/results/hard_pilot_ablation_summary.csv`, and prints a compact terminal table.

## Interpretation

Ranking alone can still preserve candidate selection in the current 6-case hard pilot. The ranking-only variant achieves 1.000 candidate accuracy, stronger-candidate accuracy, and weak-candidate rejection accuracy.

However, ranking alone performs poorly on edge-grounded reasoning. Without support-subgraph edges or detailed evidence lists, present-edge precision and recall drop sharply.

Providing graph evidence/support context restores present-edge and missing-edge grounding. Both Full GraphRAG and No Validation recover all current present and missing edge expectations.

The `validation_summary` may help stronger-candidate consistency: Full GraphRAG reaches 1.000 stronger-candidate accuracy, while No Validation is 0.833. This is promising, but it should not be overclaimed because the result comes from a small, stochastic 6-case pilot.

## Limitations

This is still a small result: only 6 hard cases, all within one influenza scenario.

LLM randomness may affect ablation results, especially because the variants depend on structured JSON responses from the model.

The validation effect is promising but still preliminary. It needs more cases and repeated runs before it can support a strong claim about the independent value of validation.

## Next Steps

- Add repeated-run or fixed-seed-style evaluation if feasible.
- Expand hard cases before making strong claims.
