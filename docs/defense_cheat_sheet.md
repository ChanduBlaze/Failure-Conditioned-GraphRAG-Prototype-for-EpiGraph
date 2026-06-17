# Defense Cheat Sheet

## 1. One-Sentence Thesis

This thesis evaluates whether graph-structured retrieval improves LLM reasoning about evidence-grounded model revision after epidemiological forecast failures.

## 2. Problem

After a forecast failure, the difficult task is not only selecting a plausible hidden driver. The harder problem is preserving which evidence relationships support each candidate, which relationships are missing, and whether another candidate is stronger.

## 3. System Pipeline

```text
Forecast failure
-> candidate hidden drivers
-> Neo4j knowledge graph evidence
-> retrieval/ranking
-> support context
-> LLM reasoning
-> structured output
-> evaluation metrics
```

## 4. Data Boundary

- Real-world data: The U.S. flu hospitalization signal grounds the missed-peak scenario.
- Prototype/manual data: Candidate drivers, evidence edges, hard-pilot cases, dengue scenario, and Text-RAG corpus.
- Generated data: Evaluation result CSVs.

## 5. Methods Compared

- KG-only: Uses the graph evidence directly without LLM reasoning.
- LLM-only: Gives the LLM the failure case and candidates without retrieval evidence.
- Text-RAG: Retrieves text evidence from a small corpus, without graph structure.
- GraphRAG: Retrieves structured graph evidence and support context before LLM reasoning.

## 6. Main Results

- The current benchmark has 14 cases across 2 prototype scenarios.
- GraphRAG achieved perfect single-run and repeated results in the current benchmark.
- LLM-only was strong on candidate selection but weaker on present-edge recall and stronger-candidate identification.
- Text-RAG retrieved useful evidence but could blur candidate-specific evidence and produce false edge claims.
- The ablation shows graph evidence/support context is the key factor; validation does not yet show independent benefit.

## 7. Limitations

- The benchmark is small.
- The evidence graph is controlled/prototype evidence.
- The dengue scenario is not a final scientific causal claim.
- GraphRAG's perfect scores should be interpreted as preserving known graph relationships, not proving real-world epidemiological discovery.

## 8. Best Defense Line

The thesis is not claiming automatic causal discovery. It evaluates whether graph-structured retrieval helps LLMs preserve evidence relationships during model-revision reasoning.

## 9. Future Work

- Larger real-world graph construction.
- Automatic or semi-automatic edge assignment.
- More scenarios.
- Downstream forecasting validation.
- Observation/time-series graph scaling.
