# Evaluation Notes

## Current Thesis Question

The current thesis question is whether graph-structured retrieval can improve LLM-based scientific reasoning for discovering and explaining missing drivers in epidemiological models.

In this prototype, the motivating case is a U.S. influenza forecast-failure scenario where the baseline mechanism underpredicted a missed hospitalization peak. The current GraphRAG layer retrieves Neo4j support evidence for candidate hidden drivers, with the strongest current candidate being `signal_chile_flu`.

## Methods Compared

### KG-only

The KG-only baseline uses Neo4j retrieval and graph validation without calling an LLM. It ranks candidate hidden drivers using graph relationships such as `LEADING_INDICATOR_FOR`, `IMPORTATION_LINK`, and `POSSIBLE_DRIVER_OF`, then compares the top retrieved candidate and evidence edges against the expected eval-case labels.

### LLM-only

The LLM-only baseline uses the failure case details, eval question, and a small candidate list, but does not use Neo4j retrieval, support subgraphs, or GraphRAG evidence. This baseline tests whether the LLM can identify the correct driver and evidence relationships without access to the structured graph.

### GraphRAG + LLM

The GraphRAG + LLM method uses Neo4j retrieval to rank candidates, retrieves the top candidate support subgraph, validates the candidate, and then asks the LLM to reason only from that retrieved graph evidence. This tests whether the structured support subgraph helps keep the LLM's explanation grounded.

## Starter Benchmark Results

| Method | Cases | Top-1 Accuracy | Avg. Evidence Precision | Avg. Evidence Recall | Hallucinated Evidence Count |
|---|---:|---:|---:|---:|---:|
| KG-only | 3 | 1.000 | 1.000 | 1.000 | 0 |
| LLM-only | 3 | 0.333 | 0.000 | 0.000 | 6 |
| GraphRAG + LLM | 3 | 1.000 | 1.000 | 1.000 | 0 |

## Interpretation

These starter results suggest that the LLM-only baseline can produce plausible epidemiological reasoning, but that reasoning is not reliably grounded in the expected graph evidence. In the current three-case benchmark, the LLM-only baseline selected the correct candidate in only one case and mentioned evidence relationships that did not match the expected graph edge types.

The KG-only baseline retrieved the correct graph evidence for the current Chile hidden-driver scenario. It identified `signal_chile_flu` as the top candidate and recovered the expected support edge types: `LEADING_INDICATOR_FOR`, `IMPORTATION_LINK`, and `POSSIBLE_DRIVER_OF`.

The GraphRAG + LLM method kept the LLM grounded in the retrieved support subgraph. Its explanations used the expected graph relationships and avoided hallucinated evidence in this starter benchmark, while still producing a natural-language rationale and model-edit proposal.

## Important Limitation

This is only a 3-case starter benchmark based on the current Chile hidden-driver scenario. These numbers are not final thesis results yet.

The current benchmark is useful as an early sanity check that the evaluation scripts and prototype reasoning layer are working, but it is too small and too scenario-specific to support strong empirical claims. More diverse eval cases are needed before drawing thesis-level conclusions.

## Next Steps

- Expand `evals/eval_cases.json` to 15-30 cases.
- Add a text-based RAG baseline.
- Add an ablation study to separate the effects of ranking, support-subgraph retrieval, validation, and LLM prompting.
- Later connect this reasoning-layer evaluation to a forecasting failure or surprisal signal.
