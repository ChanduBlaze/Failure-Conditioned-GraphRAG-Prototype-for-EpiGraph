# Real-KG and Empirical Influenza Results Report

## 1. Controlled Fixture Real-KG Comparison

Methods included: `llm_only`, `text_rag`, `graphrag_context`. Each method reports 4 controlled cases. Candidate accuracy was llm_only=1.0; text_rag=1.0; graphrag_context=1.0; status accuracy was llm_only=0.75; text_rag=1.0; graphrag_context=1.0. Average present-edge recall was llm_only=1.0; text_rag=1.0; graphrag_context=1.0, and average missing-edge recall was llm_only=0.75; text_rag=1.0; graphrag_context=1.0.

The main observation is that LLM-only selected candidates well but had weaker evidence-status preservation, while Text-RAG and GraphRAG preserved the evidence structure.

| method | case_count | status_accuracy | candidate_accuracy | avg_present_edge_recall | avg_missing_edge_recall | lag_accuracy | score_accuracy | threshold_accuracy | paired_week_count_accuracy | false_positive_edge_claims | total_must_not_include_violations | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| llm_only | 4 | 0.75 | 1.0 | 1.0 | 0.75 | 0.0 |  |  |  | 1 | 0 | Controlled fixture real-KG comparison with known evidence status and candidate structure. |
| text_rag | 4 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |  |  |  | 0 | 0 | Controlled fixture real-KG comparison with known evidence status and candidate structure. |
| graphrag_context | 4 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |  |  |  | 0 | 0 | Controlled fixture real-KG comparison with known evidence status and candidate structure. |

## 2. Empirical Influenza Real-Data Extension

Methods included: `empirical_llm_only`, `empirical_text_rag`, `empirical_graphrag_context`. Each method reports 4 empirical claims. The LLM-only baseline used general epidemiological reasoning. Text-RAG and GraphRAG preserved empirical evidence artifacts supplied through their retrieval contexts.

The main observation is that LLM-only recovered status but not exact empirical lag evidence, while Text-RAG and GraphRAG preserved lag, score, threshold, and paired-week evidence.

| method | case_count | status_accuracy | candidate_accuracy | avg_present_edge_recall | avg_missing_edge_recall | lag_accuracy | score_accuracy | threshold_accuracy | paired_week_count_accuracy | false_positive_edge_claims | total_must_not_include_violations | notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| empirical_llm_only | 4 | 1.0 |  | 1.0 | 1.0 | 0.0 |  |  |  | 0 | 0 | LLM-only used general epidemiological reasoning without empirical score, threshold, lag, paired-week, Text-RAG, or graph evidence. |
| empirical_text_rag | 4 | 1.0 |  | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |  | 0 | Text-RAG evaluated artifact preservation from empirical evidence-claim chunks. |
| empirical_graphrag_context | 4 | 1.0 |  | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 |  | 0 | GraphRAG evaluated artifact preservation from pipeline-scoped Neo4j graph context. |

## 3. Interpretation

The controlled fixture result shows why evidence-status preservation matters when candidate relationships are known. Accurate candidate selection alone does not ensure that present and missing evidence is represented correctly. This comparison evaluates evidence preservation, not causal discovery.

The empirical result shows that the evidence-claim representation can be populated from real surveillance signals and that retrieval contexts can preserve score, threshold, lag, and paired-week details. The empirical evidence is screening evidence, not causal proof, and this small extension does not prove generalization to all disease systems.

## 4. Limitations

- The empirical extension is small.
- It covers one influenza target case.
- The negative control is deterministic and synthetic.
- The LLM-only manual baseline is based on one fresh-chat sample.
- Empirical evidence depends on source coverage, normalization, the lag window, the threshold, and reporting artifacts.

## 5. Thesis-Ready Takeaway

The real-data extension supports the thesis by showing that GraphRAG can preserve candidate-specific evidence facts from a pipeline-scoped KG context, while LLM-only reasoning may be plausible but does not recover exact empirical evidence details such as lag, score, threshold, and paired-week counts unless those facts are supplied.
