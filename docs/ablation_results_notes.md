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

## Repeated-Run Ablation Check

The repeated-run ablation check was run with:

```powershell
python evals\run_hard_pilot_ablation_repeated_eval.py --runs 3
```

| Variant | Runs | Cases/Run | Candidate Accuracy Mean/Std | Present Edge Recall Mean/Std | Missing Edge Recall Mean/Std | Stronger Candidate Accuracy Mean/Std | Weak Candidate Rejection Mean/Std |
|---|---:|---:|---:|---:|---:|---:|---:|
| Full GraphRAG | 3 | 6 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 0.944 / 0.096 | 1.000 / 0.000 |
| No validation | 3 | 6 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 0.833 / 0.289 |
| Ranking only, no support subgraph | 3 | 6 | 1.000 / 0.000 | 0.083 / 0.000 | 0.806 / 0.127 | 1.000 / 0.000 | 1.000 / 0.000 |

## Interpretation

Ranking alone can still preserve candidate selection in the current 6-case hard pilot. The ranking-only variant achieves 1.000 candidate accuracy, stronger-candidate accuracy, and weak-candidate rejection accuracy.

However, ranking alone performs poorly on edge-grounded reasoning. Without support-subgraph edges or detailed evidence lists, present-edge precision and recall drop sharply. The repeated-run check confirms that ranking-only remains weak on present-edge recall.

Providing graph evidence/support context restores present-edge and missing-edge grounding. Across the repeated runs, both Full GraphRAG and No Validation maintain perfect present-edge and missing-edge recall.

The validation effect is mixed in the 3-run sample. Full GraphRAG is stronger on weak-candidate rejection, while No Validation is stronger on stronger-candidate accuracy. This means validation effects should not be overclaimed yet.

## Limitations

This is still a small result: only 6 hard cases, all within one influenza scenario.

LLM randomness may affect ablation results, especially because the variants depend on structured JSON responses from the model.

The repeated-run check has only 3 runs. It is useful as a first variability check, but it is not enough to make strong claims about validation effects.

## Next Steps

- Expand hard cases before making strong claims.
- Consider more repeated runs later if cost and time allow.
- Eventually merge hard-case and ablation findings into the thesis results section.
