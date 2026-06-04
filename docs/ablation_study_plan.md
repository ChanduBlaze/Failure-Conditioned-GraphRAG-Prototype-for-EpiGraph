# Ablation Study Plan

## Purpose

The ablation study will test which parts of the GraphRAG prototype contribute most to evidence-grounded reasoning in the epidemiological model-revision setting.

The goal is not only to show that Full GraphRAG performs well, but to separate the effects of graph candidate ranking, support-subgraph retrieval, validation checks, and LLM prompting with graph evidence.

## Current Motivation

The project currently has a 10-case main benchmark and a 6-case hard pilot benchmark comparing KG-only, LLM-only, Text-RAG, and GraphRAG.

The hard pilot is the best starting point for ablations because it tests distinctions that go beyond top-candidate selection:

- Missing-edge detection.
- Partial-evidence detection.
- Weak-candidate rejection.
- Stronger-candidate identification.

Text-RAG retrieval now excludes expected labels and uses a corpus with distractor chunks. In the current 6-case hard pilot, GraphRAG remains perfect, while LLM-only and Text-RAG show weaker evidence grounding. This makes the hard pilot useful for testing which GraphRAG components are responsible for the improvement.

## Components To Ablate

| Component | Role In Full GraphRAG |
|---|---|
| Graph candidate ranking | Uses Neo4j evidence structure to rank candidate hidden drivers. |
| Support-subgraph retrieval | Retrieves structured evidence paths for the selected or contrasted candidates. |
| Validation / evidence checks | Checks whether expected evidence relationships are present, missing, or unsupported. |
| LLM prompting with graph evidence | Provides the LLM with graph-grounded evidence so it can explain candidates and propose model edits. |

## Proposed Ablation Variants

| Variant | Description | Purpose |
|---|---|---|
| Full GraphRAG | Uses graph ranking, support-subgraph retrieval, validation, and LLM prompting with graph evidence. | Main comparison point. |
| No validation | Uses graph ranking, support-subgraph retrieval, and LLM prompting, but removes explicit validation/evidence checks. | Tests whether validation is needed to reduce unsupported claims. |
| Ranking only, no support subgraph | Uses graph ranking to choose candidates, but does not provide support-subgraph evidence to the LLM. | Tests whether ranking alone is enough for candidate accuracy but insufficient for edge grounding. |
| Support subgraph without validation | Provides retrieved graph evidence to the LLM, but does not run explicit validation checks. | Tests whether structured evidence alone is enough without formal evidence checks. |
| Text-RAG baseline | Uses flattened text chunks, with expected labels excluded and distractor chunks included. | Compares graph-structured evidence against text retrieval. |
| LLM-only baseline | Uses the question and candidate context without retrieval evidence. | Measures how much the LLM can infer without retrieval. |

## Metrics To Compare

The hard-pilot ablation runner should preserve the current hard-pilot metrics where possible:

- Candidate accuracy.
- Present-edge precision.
- Present-edge recall.
- Missing-edge recall.
- False edge claims.
- Stronger-candidate accuracy.
- Weak-candidate rejection.
- Hallucinated evidence count where applicable.

For variants that do not produce a specific field, the runner should either record `N/A` or leave the metric out of that variant's aggregate, rather than forcing an artificial score.

## Expected Interpretation

If Full GraphRAG outperforms No Validation, then validation/evidence checks are likely helping prevent unsupported edge claims.

If Ranking Only keeps candidate accuracy high but weakens edge-level metrics, then graph ranking is useful for selecting candidates but not sufficient for grounded explanations.

If Support Subgraph Without Validation performs better than Ranking Only but worse than Full GraphRAG, then support-subgraph retrieval is helping, while validation adds an additional reliability layer.

If Text-RAG keeps candidate accuracy but remains weaker on edge grounding, missing-edge recall, stronger-candidate identification, or weak-candidate rejection, that supports the claim that flattened retrieval can find plausible text but may blur relationship-level distinctions.

If LLM-only remains weaker on evidence metrics, that supports the need for retrieval-grounded reasoning rather than relying on the LLM's prior knowledge or plausible narrative generation.

These interpretations should remain cautious because the current hard pilot is still small and uses one influenza scenario.

## Implementation Order

1. Create a separate hard-pilot ablation runner.
2. Start with the existing 6-case hard pilot rather than modifying the main benchmark runners.
3. Implement Full GraphRAG and one ablated variant at a time.
4. Write ablation results to a separate CSV file so existing result files remain stable.
5. Add a small summarizer for the ablation CSV after the runner output is stable.
6. Only after the hard-pilot ablation is useful, consider merging ablation logic into the main benchmark.

## Risks And Limitations

The current hard pilot still uses one U.S. influenza scenario. It does not yet test other diseases, regions, candidate types, mechanisms, or failure modes.

The ablation variants may differ in how much information they provide to the LLM. Prompts should be kept as similar as possible so the comparison reflects component differences rather than prompt wording differences.

Some metrics may not apply cleanly to every variant. For example, a ranking-only variant may not produce enough natural-language evidence to score hallucinated evidence in the same way as LLM-based variants.

The ablation should be treated as diagnostic evidence first. Strong thesis claims should wait until the hard cases are expanded and the benchmark includes more scenario diversity.

## Next Concrete Step

Create a new hard-pilot ablation runner that uses the existing 6-case hard pilot and writes to a separate ablation results CSV. The first implementation should compare Full GraphRAG, No Validation, and Support Subgraph Without Validation before adding the remaining variants.
