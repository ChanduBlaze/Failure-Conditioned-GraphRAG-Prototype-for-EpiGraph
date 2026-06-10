# Hard Pilot Evaluation Notes

## Purpose

The hard pilot tests reasoning tasks that go beyond simple top-candidate selection. It evaluates whether a method can identify missing evidence, distinguish partial from complete support, reject weak candidates, identify a stronger comparison candidate, and preserve candidate-specific edge grounding.

The cases remain separate from the main benchmark in `evals/eval_cases_hard_pilot.json` so the extended schema and scoring logic can be evaluated independently.

## Benchmark Scope

The current hard pilot has 14 cases across 2 prototype scenarios:

1. U.S. influenza missed hospitalization peak.
2. Puerto Rico dengue regional outbreak underprediction.

| Case Range | Scenario |
|---|---|
| `hard_case_001`-`hard_case_010` | U.S. influenza missed hospitalization peak |
| `hard_case_011`-`hard_case_014` | Puerto Rico dengue regional outbreak underprediction |

The dengue scenario provides prototype evidence for pipeline evaluation. It is not a final scientific claim about dengue causality.

## What The Hard Pilot Tests

### Missing-Edge Detection

Missing-edge detection checks whether a method can identify that a candidate lacks an important relationship, even when other relevant relationships are present.

### Partial-Evidence Detection

Partial-evidence detection checks whether a method can recognize valid but incomplete support rather than treating every plausible candidate as fully supported.

### Weak-Candidate Rejection

Weak-candidate rejection checks whether a method avoids promoting candidates supported by only a limited subset of the expected evidence.

### Candidate Comparison

The benchmark also tests whether a method can identify the strongest or most complete candidate without mixing that candidate's evidence into the evaluated candidate's edge list.

## Pilot Cases

| Case | Task | What It Tests |
|---|---|---|
| `hard_case_001` | Australia missing `IMPORTATION_LINK` | Identifies partial influenza support and the missing importation relationship. |
| `hard_case_002` | Travel Pressure missing `LEADING_INDICATOR_FOR` | Identifies importation and possible-driver support while recognizing the missing leading-indicator relationship. |
| `hard_case_003` | Humidity Drop weak-candidate case | Treats a candidate with only `POSSIBLE_DRIVER_OF` as weak and incomplete. |
| `hard_case_004` | Chile strongest compared with Australia | Identifies Chile Influenza Activity as the strongest supported candidate. |
| `hard_case_005` | Travel Pressure as partial support | Explains why partial support does not make Travel Pressure the best hidden driver. |
| `hard_case_006` | Humidity Drop should not outrank importation candidates | Avoids promoting weak environmental support above stronger importation-related support. |
| `hard_case_007` | Humidity as an environmental distractor | Separates a plausible environmental signal from candidates with stronger outbreak-relevant support. |
| `hard_case_008` | Australia partial-vs-full support contrast | Recognizes Australia's partial support while identifying the more complete candidate. |
| `hard_case_009` | Travel mechanism/importation support | Recognizes mechanism and importation support while identifying missing leading-indicator evidence. |
| `hard_case_010` | Chile strongest-candidate completeness | Returns the evaluated candidate itself when it is also the strongest or most complete candidate. |
| `hard_case_011` | Mosquito Vector Index strongest candidate | Identifies Mosquito Vector Index as the strongest candidate in the dengue scenario. |
| `hard_case_012` | Rainfall Anomaly partial support | Recognizes partial dengue support and the missing `IMPORTATION_LINK`. |
| `hard_case_013` | Temperature Anomaly weak/incomplete support | Treats Temperature Anomaly as weak or incomplete rather than fully supported. |
| `hard_case_014` | Dengue Travel Importation Pressure partial support | Recognizes partial support and the missing `LEADING_INDICATOR_FOR`. |

The LLM-based prompts use strict, non-leaking guidance for edge-list fields. These fields may contain only exact relationship type names such as `LEADING_INDICATOR_FOR`, `IMPORTATION_LINK`, and `POSSIBLE_DRIVER_OF`. Evidence from comparison candidates belongs in the explanation, not in the evaluated candidate's edge list.

## Current Results

Single-run results from `evals/results/hard_pilot_summary.csv`:

| Method | Cases | Candidate Accuracy | Present Edge Precision | Present Edge Recall | Missing Edge Recall | False Claims | Stronger Candidate Accuracy | Weak Candidate Rejection |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| KG-only | 14 | N/A | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |
| LLM-only | 14 | 1.000 | 1.000 | 0.726 | 0.929 | 0 | 0.929 | 1.000 |
| Text-RAG | 14 | 0.929 | 0.845 | 0.857 | 0.821 | 3 | 0.643 | 1.000 |
| GraphRAG | 14 | 1.000 | 1.000 | 1.000 | 1.000 | 0 | 1.000 | 1.000 |

## Repeated Method Comparison

Three-run results from `evals/results/hard_pilot_repeated_summary.csv`:

| Method | Runs | Cases/Run | Candidate Accuracy Mean/Std | Present Edge Precision Mean/Std | Present Edge Recall Mean/Std | Missing Edge Recall Mean/Std | False Claims Mean/Std | Stronger Candidate Accuracy Mean/Std | Weak Candidate Rejection Mean/Std |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LLM-only | 3 | 14 | 0.976 / 0.041 | 0.988 / 0.021 | 0.706 / 0.025 | 0.905 / 0.041 | 0.333 / 0.577 | 0.905 / 0.041 | 1.000 / 0.000 |
| Text-RAG | 3 | 14 | 0.976 / 0.041 | 0.817 / 0.055 | 0.786 / 0.062 | 0.964 / 0.036 | 0.667 / 1.155 | 0.643 / 0.071 | 1.000 / 0.000 |
| GraphRAG | 3 | 14 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 | 0.000 / 0.000 | 1.000 / 0.000 | 1.000 / 0.000 |

## Interpretation

The benchmark now covers two prototype scenarios rather than influenza alone. This adds a second disease, region, target signal, mechanism, and candidate set to the pipeline evaluation.

GraphRAG remains stable across both prototype scenarios. It achieves perfect single-run and repeated-run results on candidate selection, present-edge recall, missing-edge recall, stronger-candidate identification, and weak-candidate rejection.

LLM-only is strong on candidate selection, but it is weaker on edge recall and stronger-candidate identification. This suggests that plausible language reasoning can often select the expected candidate without preserving every graph evidence distinction.

Text-RAG retrieves useful text, but it can blur candidate-specific evidence with comparison evidence. Its weaker stronger-candidate identification and nonzero false-claim results show the difficulty of preserving candidate boundaries in flattened text retrieval.

These results support graph-structured retrieval as useful for edge-grounded reasoning in the current prototype benchmark. They remain pilot evidence rather than final thesis evidence.

## Limitations

The benchmark is still small, with 14 cases across 2 prototype scenarios.

The dengue scenario is prototype evidence for evaluation, not a final scientific claim. The graph and text evidence are still manually constructed for pipeline testing.

More real-data grounding and greater scenario diversity are needed before making broad thesis-level claims about epidemiological discovery or general method performance.

## Next Steps

- Stabilize the current results.
- Avoid major new feature work unless necessary.
- Prepare thesis and presentation interpretation around the 14-case, two-scenario findings.
- Add real-data grounding only if time allows.
