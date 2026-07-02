# Empirical Influenza Hard-Pilot Stress Cases

This package creates a real-KG stress set that is comparable to the controlled hard-pilot cases, but it is built from the empirical influenza evidence claims.

## Defense-safe framing

These are not 24 independent outbreaks. They are 24 evidence-preservation stress cases generated from the real empirical influenza KG candidates. The goal is to compare whether Text-RAG and GraphRAG preserve candidate-specific empirical evidence attributes.

## Source facts used

Target:
- FluSurv-NET influenza hospitalization rate

Candidates:
- Outpatient ILI activity: present, lag 1 week, r=0.958037, paired weeks 29
- Influenza A wastewater concentration: present, lag 1 week, r=0.947016, paired weeks 26
- Influenza test positivity: present, lag 1 week, r=0.925810, paired weeks 29
- Negative-control permuted surveillance signal: missing, best positive lag 4 weeks, r=-0.048027, paired weeks 26

KG behavior:
- 4 EvidenceClaims total
- 3 positive typed LEADING_INDICATOR_FOR edges
- 1 missing negative-control claim retained as EvidenceClaim only
- Negative control is not promoted into a typed KG edge

## Files

- `real_empirical_hard_pilot_cases.csv`
- `real_empirical_hard_pilot_cases.json`
- `real_empirical_candidate_facts.csv`
- `real_empirical_hard_pilot_rubric.csv`
- `real_empirical_text_rag_clean_chunks.json`
- `real_empirical_text_rag_blended_chunks.json`
- `score_empirical_hard_pilot_outputs.py`

## Suggested repo locations

From repo root:

```powershell
mkdir evals\empirical_hard_pilot
mkdir data\real_processed\empirical_hard_pilot
mkdir scripts\real_kg
```

Copy files:

```powershell
copy real_empirical_hard_pilot_cases.csv evals\empirical_hard_pilot\
copy real_empirical_hard_pilot_cases.json evals\empirical_hard_pilot\
copy real_empirical_hard_pilot_rubric.csv evals\empirical_hard_pilot\
copy real_empirical_candidate_facts.csv data\real_processed\empirical_hard_pilot\
copy real_empirical_text_rag_clean_chunks.json data\real_processed\empirical_hard_pilot\
copy real_empirical_text_rag_blended_chunks.json data\real_processed\empirical_hard_pilot\
copy score_empirical_hard_pilot_outputs.py scripts\real_kg\
```

## Methods to compare

Recommended:

1. `empirical_llm_only`
2. `empirical_text_rag_clean`
3. `empirical_text_rag_blended`
4. `empirical_graphrag_context`

The clean Text-RAG condition uses one candidate-specific chunk per candidate.
The blended Text-RAG condition uses multi-candidate chunks designed to test evidence blurring.
GraphRAG should use the pipeline-scoped `empirical_influenza` KG context.

## Metrics

Use the rubric file. The most important metrics are:

- candidate accuracy
- status accuracy
- lag accuracy
- score accuracy
- paired-week accuracy
- candidate-score binding accuracy
- present-edge recall
- missing-edge recall
- false positive edge claims
- causal-overclaim violations
- pipeline leakage violations

## Expected interpretation

LLM-only may reason plausibly but should not recover exact evidence attributes unless those facts are supplied.
Clean Text-RAG may perform very well because each claim has a clean chunk.
Blended Text-RAG is the harder text condition because several candidates and scores are placed together.
GraphRAG should preserve candidate-specific evidence through structured KG context.

Defense-safe claim:
The empirical stress set tests evidence preservation over real surveillance-derived claims. It does not claim causal discovery or validated forecast improvement.
