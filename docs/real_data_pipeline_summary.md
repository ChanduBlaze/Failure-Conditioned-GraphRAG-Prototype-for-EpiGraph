# Real-Data KG Extension Pipeline Summary

## 1. Purpose

The real-data knowledge graph (KG) extension moves the prototype beyond a
purely simulated benchmark toward a small, reproducible real-data evidence
pipeline. It demonstrates how normalized signal observations can be converted
into an auditable evidence claim, represented in parallel Text-RAG and GraphRAG
artifacts, loaded into Neo4j without removing existing data, and evaluated
deterministically.

## 2. Scope

The current v1 case evaluates U.S. influenza hospitalization rate as the target
signal and Influenza A wastewater activity as the candidate signal. The tested
relationship is `LEADING_INDICATOR_FOR`, assessed with lagged Pearson
correlation.

The present input is a fixture/synthetic-normalized real-data placeholder. It
is intentionally small and reproducible so that the pipeline, schema,
provenance, retrieval context, and evaluation logic can be validated before
substituting larger API-derived epidemiological datasets.

## 3. Pipeline Steps

Run the pipeline from the repository root in the following order:

```text
python scripts/real_kg/build_real_evidence_claims.py
python scripts/real_kg/build_real_text_corpus.py
python scripts/real_kg/load_real_kg_to_neo4j.py --dry-run
python scripts/real_kg/load_real_kg_to_neo4j.py
python scripts/real_kg/query_real_kg_context.py
python scripts/real_kg/run_real_eval.py
```

The dry run validates the evidence-claim input before any Neo4j connection is
made. The live load and graph-context export require the configured Neo4j
environment variables.

## 4. Main Artifacts

- `data/real_processed/real_evidence_claims.csv` is the canonical,
  provenance-carrying evidence-claim table.
- `data/real_processed/real_text_rag_corpus.json` is the parallel textual
  representation used for deterministic Text-RAG evaluation.
- Neo4j stores the corresponding `EvidenceClaim`, `CandidateDriver`, and
  `Signal` records together with dataset, region, time-window, and relationship
  provenance.
- `data/real_processed/real_graph_context.json` is the exported graph retrieval
  context for the selected real failure case.
- `evals/real_eval_cases.json` defines the expected candidate, relationship,
  status, lag, minimum score, and prohibited overclaims.
- `evals/results_real/real_text_rag_results.csv` records deterministic Text-RAG
  results.
- `evals/results_real/real_graphrag_context_results.csv` records deterministic
  GraphRAG-context results.
- `evals/results_real/real_summary.csv` summarizes the two evaluation methods.

## 5. Neo4j Safety

`scripts/real_kg/load_real_kg_to_neo4j.py` is additive and idempotent. It uses
label-and-ID `MERGE` operations and does not delete existing graph data. This
allows the real-data records to coexist with other graph content.

The existing `neo4j_loader.py` is destructive and should not be used when
additive real-data records must be preserved.

## 6. Evaluation Meaning

The current real-data evaluation is a deterministic artifact-level evaluation.
It verifies information parity between the real Text-RAG corpus and the real
GraphRAG context export, including preservation of the expected candidate,
evidence status, relationship type, lag, and score threshold.

It does not evaluate LLM reasoning quality. Both methods pass the current
single real-data case because both representations are generated from the same
underlying evidence claim. The result therefore validates representation and
retrieval consistency rather than demonstrating that one retrieval method
reasons better than the other.

## 7. Current Results

The current evaluation contains one real-data case.

| Metric | Text-RAG | GraphRAG context |
|---|---:|---:|
| Candidate accuracy | 1.0 | 1.0 |
| Present edge recall | 1.0 | 1.0 |
| Lag accuracy | 1.0 | 1.0 |
| Must-not-include violations | 0 | 0 |

These results indicate complete information preservation for the current
fixture-based case; they should not be interpreted as evidence of broad
epidemiological validity or model generalization.

## 8. Thesis-Safe Claim

The real-data extension demonstrates that the proposed evidence representation
can be populated from normalized epidemiological signals, loaded additively
into Neo4j, exported as graph retrieval context, and evaluated against a
parallel Text-RAG artifact while preserving candidate, edge type, lag, score,
source, region, time window, and limitation fields. This is a pipeline
validation and evidence-preservation demonstration, not a causal discovery
result or proof of epidemiological generalization.

## 9. Limitations

- The current evaluation contains only one case.
- The input remains fixture/synthetic-normalized for reproducibility.
- The evidence is associational.
- Lagged correlation does not establish causality.
- LLM-based real-data reasoning evaluation remains future work.
- Additional signals, regions, and negative, missing, or insufficient-data
  evidence cases are needed.

## 10. Next Work

- Replace the fixture with real CDC/API-normalized data.
- Add more evaluation cases.
- Add missing and insufficient-evidence cases.
- Run an LLM-based comparison of real Text-RAG and real GraphRAG.
- Incorporate provenance and confidence more deeply into retrieval and
  evaluation.
