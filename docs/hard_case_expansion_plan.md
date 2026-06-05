# Hard Case Expansion Plan

## Purpose

This plan describes how to expand the hard pilot benchmark from 6 cases toward 15-30 cases without making the evaluation repetitive or overfitted to one small scenario.

The goal is to keep testing the behavior that matters for the thesis: whether graph-structured retrieval helps LLMs reason about present evidence, missing evidence, weak candidates, and candidate contrasts more reliably than LLM-only or flattened Text-RAG retrieval.

## Current Hard Pilot Status

The current hard pilot has 6 cases in one U.S. influenza missed-peak scenario. It tests:

- Missing-edge detection.
- Partial-evidence detection.
- Weak-candidate rejection.
- Stronger-candidate contrast.

The current candidate set is:

- `signal_chile_flu`
- `signal_australia_flu`
- `signal_travel_pressure`
- `signal_humidity_drop`

The current results show useful separation. LLM-only has weak edge grounding, Text-RAG has imperfect edge grounding and weak-candidate rejection, GraphRAG performs best on the current hard pilot, and ablation results suggest that ranking alone preserves candidate selection but not edge grounding.

## Expansion Goals

The expanded hard pilot should:

- Test more than top-candidate selection.
- Require methods to distinguish present edges from missing edges.
- Include plausible but incomplete candidates.
- Include weak or noisy candidates that should not be promoted.
- Avoid repeatedly asking the same question with different wording.
- Add scenario diversity before making strong thesis-level claims.

Adding more cases within the same four candidates is useful for debugging the schema and metrics, but it is limited. It can overfit the benchmark to the current U.S. influenza graph and make the results look more stable than they really are.

## Case Categories To Add

| Category | Purpose |
|---|---|
| Missing-edge cases | Test whether a method can identify a specific absent relationship that weakens a candidate. |
| Partial-support cases | Test whether a method can recognize candidates with some valid evidence but incomplete support. |
| Weak-candidate rejection cases | Test whether a method avoids promoting candidates with only one weak or indirect support edge. |
| Stronger-candidate contrast cases | Test whether a method can explain why one candidate is better supported than another. |
| Distractor/noisy-candidate cases | Test whether a method avoids being pulled toward plausible but noisy or generic background signals. |
| Evidence conflict or ambiguity cases | Test whether a method can handle mixed evidence or explain uncertainty without inventing support. |

## Candidate/Scenario Diversity Needed

Within the current influenza scenario, the next cases can still use the existing four candidates, but they should vary the reasoning pattern rather than simply repeat the same edge checks.

Before expanding to 15-30 hard cases, the benchmark should add at least one additional disease, region, or failure scenario. This would help test whether the approach generalizes beyond the current southern-hemisphere influenza importation pattern.

Useful forms of diversity include:

- A different disease or pathogen.
- A different region or target signal.
- A different failure mode, such as overprediction or mistimed peak.
- New candidate types, such as data-quality artifacts, policy changes, climate drivers, behavioral changes, or surveillance changes.
- Candidates with conflicting or ambiguous support instead of simply present or missing edges.

## Risks

The main risk is adding many cases that are superficially different but structurally identical. That would increase the case count without improving the evaluation.

Another risk is overfitting the benchmark to the current four candidates. If all hard cases depend on the same Chile/Australia/Travel/Humidity distinctions, the results may not reflect broader GraphRAG behavior.

There is also a risk of making cases too dependent on expected labels or wording. The hard cases should continue to test evidence structure, not whether retrieval can match a phrase from the expected answer.

## Proposed Expansion Stages

### Stage 1: Expand Current Influenza Scenario To 10-12 Hard Cases

Add 4-6 more cases within the current U.S. influenza scenario. These should focus on new reasoning patterns, such as noisy-candidate rejection, ambiguous evidence, and comparisons involving partial or weak support.

This stage is useful for testing the hard-pilot schema, runner behavior, and scoring metrics without adding new graph infrastructure immediately.

### Stage 2: Add Another Scenario Before Going To 15-30 Cases

Before expanding to 15-30 hard cases, add another disease, region, or failure scenario with new candidates and evidence relationships.

This stage should test whether the method differences hold outside the current influenza missed-peak setup. It would make the hard pilot more credible as thesis evidence rather than only a prototype sanity check.

## Next Concrete Step

Add 4-6 new hard cases within the current influenza scenario, targeting distractor/noisy-candidate reasoning and evidence conflict or ambiguity. After that, design one additional scenario before expanding the benchmark toward 15-30 hard cases.
