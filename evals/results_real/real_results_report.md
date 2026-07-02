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

## 3. Empirical Hard-Pilot Stress Evaluation

To make the empirical extension more comparable to the controlled hard-pilot benchmark, I built 24 empirical evidence-preservation stress cases from the four real influenza KG evidence claims. These are not 24 independent outbreaks. They are stress cases over real surveillance-derived evidence claims.

Methods included: `empirical_graphrag_context`, `empirical_llm_only`, `empirical_text_rag_blended`, `empirical_text_rag_clean`. Each method reports 24 empirical hard-pilot stress cases. Overall pass rate was empirical_graphrag_context=1.000; empirical_llm_only=0.042; empirical_text_rag_blended=1.000; empirical_text_rag_clean=1.000. Average include score was empirical_graphrag_context=1.000; empirical_llm_only=0.121; empirical_text_rag_blended=1.000; empirical_text_rag_clean=1.000. Forbidden-content compliance was empirical_graphrag_context=1.000; empirical_llm_only=1.000; empirical_text_rag_blended=1.000; empirical_text_rag_clean=1.000.

The main observation is that LLM-only avoided forbidden overclaims but failed most exact-evidence preservation cases because empirical lag, score, paired-week count, threshold, and KG edge evidence were intentionally withheld. Clean Text-RAG, blended Text-RAG, and GraphRAG context all preserved the supplied empirical evidence in this 24-case stress set.

| method | case_count | overall_pass_rate | avg_include_score | forbidden_ok_rate | failed_case_count | forbidden_violation_count | avg_answer_length_chars |
| --- | --- | --- | --- | --- | --- | --- | --- |
| empirical_graphrag_context | 24 | 1.000 | 1.000 | 1.000 | 0 | 0 | 296.5 |
| empirical_llm_only | 24 | 0.042 | 0.121 | 1.000 | 23 | 0 | 303.0 |
| empirical_text_rag_blended | 24 | 1.000 | 1.000 | 1.000 | 0 | 0 | 296.0 |
| empirical_text_rag_clean | 24 | 1.000 | 1.000 | 1.000 | 0 | 0 | 298.6 |

## 4. Interpretation

The controlled fixture result shows why evidence-status preservation matters when candidate relationships are known. Accurate candidate selection alone does not ensure that present and missing evidence is represented correctly. This comparison evaluates evidence preservation, not causal discovery.

The empirical result shows that the evidence-claim representation can be populated from real surveillance signals and that retrieval contexts can preserve score, threshold, lag, and paired-week details. The empirical evidence is screening evidence, not causal proof, and this small extension does not prove generalization to all disease systems.

The empirical hard-pilot stress evaluation adds a harder evidence-preservation layer over the same real influenza claims. It shows that exact evidence facts are not recoverable from LLM-only context when they are withheld, but can be preserved when they are supplied through Text-RAG or GraphRAG context. In this small empirical stress set, Text-RAG and GraphRAG show preservation parity; the stronger GraphRAG-over-Text-RAG separation remains in the controlled 50-case benchmark.

## 5. Limitations

- The empirical extension is small.
- It covers one influenza target case.
- The negative control is deterministic and synthetic.
- The empirical hard-pilot stress cases are generated from four real evidence claims; they are not independent outbreaks.
- The LLM-only and filled-output baselines are single-sample outputs rather than repeated stochastic runs.
- Empirical evidence depends on source coverage, normalization, the lag window, the threshold, and reporting artifacts.
- Lagged correlation is screening evidence, not causal proof.

## 6. Thesis-Ready Takeaway

The real-data extension supports the thesis by showing that GraphRAG can preserve candidate-specific evidence facts from a pipeline-scoped KG context, while LLM-only reasoning may be plausible but does not recover exact empirical evidence details such as lag, score, threshold, and paired-week counts unless those facts are supplied.

The empirical hard-pilot comparison further shows that retrieval context is necessary for exact empirical evidence preservation: LLM-only failed most exact-evidence cases when evidence was withheld, while clean Text-RAG, blended Text-RAG, and GraphRAG context all preserved the supplied evidence in the 24-case stress set.
