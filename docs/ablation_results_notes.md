# Ablation Results Notes

## Purpose

This note documents the first hard-pilot ablation result from `evals/run_hard_pilot_ablation_eval.py`.

The goal is to begin separating which parts of the GraphRAG pipeline contribute to the current hard-pilot performance: candidate ranking, graph evidence/support context, and validation.

## Ablation Variants

| Variant | Description |
|---|---|
| Full GraphRAG | Uses candidate ranking, graph evidence lists, support-subgraph-style nodes and edges, and the full GraphRAG prompt context. |
| No validation | Uses the same graph evidence and support context as Full GraphRAG, but records validation as disabled. |
| Ranking only, no support subgraph | Provides only candidate IDs, names, scores, and ranks. It does not provide support-subgraph edges or detailed evidence edge lists. |

## Current Results

| Variant | Cases | Candidate Accuracy | Present Edge Precision | Present Edge Recall | Missing Edge Recall | False Edge Claims | Stronger Candidate Accuracy | Weak Candidate Rejection |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Full GraphRAG | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| No validation | 6 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| Ranking only, no support subgraph | 6 | 1.000 | 0.333 | 0.167 | 0.667 | 0 | 1.000 | 1.000 |

## Interpretation

Ranking alone can preserve candidate selection in the current 6-case hard pilot. The ranking-only variant still achieves 1.000 candidate accuracy, stronger-candidate accuracy, and weak-candidate rejection accuracy.

However, ranking alone is not enough for edge-grounded reasoning. Without support-subgraph edges or detailed evidence lists, present-edge precision and recall drop sharply, and missing-edge recall is also lower.

Providing graph evidence/support context improves present-edge and missing-edge grounding. Both Full GraphRAG and No Validation recover all current present and missing edge expectations.

Full GraphRAG and No Validation currently perform the same. This first runner therefore does not yet isolate validation effects well; it mainly shows that graph evidence context matters more than ranking alone in this pilot.

## Limitations

This is still a small result: only 6 hard cases, all within one influenza scenario.

LLM randomness may affect ablation results, especially because the variants depend on structured JSON responses from the model.

The No Validation variant currently receives the same graph evidence context as Full GraphRAG. As a result, the validation ablation needs refinement before it can support claims about the independent value of validation.

## Next Steps

- Refine the validation ablation so validation affects prompt context or post-checking more meaningfully.
- Add Support Subgraph Without Validation as a distinct variant if it is not already separated clearly enough.
- Add a small ablation summary script later.
- Expand hard cases before making strong claims.
