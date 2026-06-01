# Evaluation Notes

## Current Thesis Question

The current thesis question is whether graph-structured retrieval can improve LLM-based scientific reasoning for discovering and explaining missing drivers in epidemiological models.

In this prototype, the motivating case is a U.S. influenza forecast-failure scenario where the baseline mechanism underpredicted a missed hospitalization peak. The current GraphRAG layer retrieves Neo4j support evidence for candidate hidden drivers, with the strongest current candidate being `signal_chile_flu`.

## Methods Compared

### KG-only

The KG-only baseline uses Neo4j retrieval and graph validation without calling an LLM. It ranks candidate hidden drivers using graph relationships such as `LEADING_INDICATOR_FOR`, `IMPORTATION_LINK`, and `POSSIBLE_DRIVER_OF`, then compares the top retrieved candidate and evidence edges against the expected eval-case labels.

### LLM-only

The LLM-only baseline uses the failure case details, eval question, and a small candidate list, but does not use Neo4j retrieval, support subgraphs, or GraphRAG evidence. This baseline tests whether the LLM can identify the correct driver and evidence relationships without access to the structured graph.

### Text-RAG

The Text-RAG baseline retrieves plain text chunks from `evals/text_rag_corpus.json` and sends those chunks to the LLM. It does not use Neo4j paths, graph traversal, or structured support subgraphs. This represents a regular retrieval-augmented generation baseline where graph knowledge has been flattened into readable text passages.

### GraphRAG + LLM

The GraphRAG + LLM method uses Neo4j retrieval to rank candidates, retrieves the top candidate support subgraph, validates the candidate, and then asks the LLM to reason only from that retrieved graph evidence. This tests whether the structured support subgraph helps keep the LLM's explanation grounded.

## Starter Benchmark Results

| Method | Cases | Top-1 Accuracy | Avg. Evidence Precision | Avg. Evidence Recall | Hallucinated Evidence Count |
|---|---:|---:|---:|---:|---:|
| KG-only | 10 | 1.000 | 1.000 | 1.000 | 0 |
| LLM-only | 10 | 0.200 | 0.000 | 0.000 | 20 |
| Text-RAG | 10 | 0.900 | 1.000 | 1.000 | 0 |
| GraphRAG + LLM | 10 | 1.000 | 1.000 | 1.000 | 0 |

## Interpretation

These starter results suggest that the LLM-only baseline can produce plausible epidemiological reasoning, but that reasoning is much weaker than the retrieval-based methods and is not reliably grounded in the expected graph evidence. In the current 10-case benchmark, the LLM-only baseline selected the correct candidate in only two cases and hallucinated evidence relationships that did not match the expected graph edge types.

The KG-only and GraphRAG + LLM methods remain perfect on this 10-case benchmark. KG-only retrieved the correct graph evidence for the current Chile hidden-driver scenario, identifying `signal_chile_flu` as the top candidate and recovering the expected support edge types: `LEADING_INDICATOR_FOR`, `IMPORTATION_LINK`, and `POSSIBLE_DRIVER_OF`.

Text-RAG improves substantially over LLM-only and also stays grounded in the expected evidence edges, but it misses one candidate-selection case. This is useful because it begins to show a separation between flattened text retrieval and the structured GraphRAG method. Text-RAG still performs well overall because the current text corpus is small and directly contains much of the answer.

The GraphRAG + LLM method keeps the LLM grounded in the retrieved support subgraph while still producing natural-language explanations and model-edit proposals. Its explanations use the expected graph relationships and avoid hallucinated evidence in this benchmark.

More diverse and harder cases are needed to separate Text-RAG from GraphRAG. The expected advantage of GraphRAG should become clearer when the task requires multi-hop structure, relationship constraints, provenance checks, or distinguishing candidates whose textual descriptions are superficially similar.

## Important Limitation

This is now a 10-case starter benchmark based on the current Chile hidden-driver scenario. These numbers are not final thesis-level evidence yet.

The current benchmark is useful as an early sanity check that the evaluation scripts and prototype reasoning layer are working, but it is still too small and too scenario-specific to support strong empirical claims. It remains somewhat easy for Text-RAG because the text corpus is small and directly encodes much of the expected answer. Final thesis claims should target 25-50 diverse eval cases before drawing stronger conclusions.

Future cases should include missing-edge detection and weak-candidate rejection, but those will need updated scoring fields and evaluation logic. In particular, the benchmark should eventually score whether a method correctly identifies absent edges, rejects weak candidates, and avoids treating partial evidence as full support.

## Next Steps

- Expand `evals/eval_cases.json` to 25-50 diverse cases.
- Expand and harden the text-based RAG baseline with more challenging retrieval cases.
- Add an ablation study to separate the effects of ranking, support-subgraph retrieval, validation, and LLM prompting.
- Later connect this reasoning-layer evaluation to a forecasting failure or surprisal signal.
