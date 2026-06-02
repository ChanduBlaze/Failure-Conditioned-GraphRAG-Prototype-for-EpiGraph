# Evaluation Schema Extension Plan

## Current Evaluation Setup

The current benchmark uses `evals/eval_cases.json` and four method-specific runners:

| Script | Method | Current Behavior |
|---|---|---|
| `evals/run_kg_only_eval.py` | KG-only | Runs Neo4j retrieval once for the current failure case, compares the top candidate against `expected_candidate_id`, extracts edge types from candidate evidence strings, and computes evidence precision/recall. |
| `evals/run_llm_only_eval.py` | LLM-only | Sends the failure case, eval question, and candidate list to the LLM without retrieval evidence. It expects JSON output and scores candidate ID plus mentioned evidence edges. |
| `evals/run_text_rag_eval.py` | Text-RAG | Retrieves top-k text chunks from `evals/text_rag_corpus.json` using lexical overlap, sends those chunks to the LLM, and scores candidate ID plus mentioned evidence edges. |
| `evals/run_graphrag_eval.py` | GraphRAG + LLM | Runs Neo4j retrieval, attaches the top candidate support subgraph, validates the candidate, sends graph evidence to the LLM, and scores candidate ID plus mentioned evidence edges. |
| `evals/summarize_eval_results.py` | Summary | Combines result CSVs and reports case count, top-1 accuracy, average evidence precision, average evidence recall, and total hallucinated evidence count. |

The current eval case schema supports these fields:

| Field | Current Use |
|---|---|
| `id` | Case identifier used in output CSVs. |
| `task_type` | Descriptive grouping only; not yet used for specialized scoring. |
| `question` | Prompt input for LLM-based methods. |
| `failure_case_id` | Metadata; the current scripts still use `get_failure_case()` directly. |
| `expected_candidate_id` | Main top-candidate scoring target. |
| `expected_candidate_name` | Metadata; not directly scored. |
| `expected_evidence_edges` | Compared against mentioned or retrieved edge types for precision/recall. |
| `expected_support_nodes` | Present in some cases, but not currently scored. |
| `expected_edit_type` | Metadata; not currently scored. |
| `acceptable_edit_keywords` | Present in one case, but not currently scored. |
| `must_not_include` | Prompt/evaluation intent, but not currently machine-scored. |

## Current Scoring Limitations

The current scoring logic is useful for top-candidate selection and evidence-edge overlap, but it does not yet support harder reasoning tasks:

- Missing-edge detection: whether a method correctly says an edge is absent.
- Weak-candidate rejection: whether a method avoids promoting a candidate with partial evidence.
- Partial-evidence detection: whether a method recognizes that a candidate has some support but not full support.
- Candidate contrast: whether a method correctly explains why one candidate is stronger than another.
- Support-node reasoning: whether a method recovers the expected subgraph nodes, not only edge types.
- Negative constraints: whether a method avoids claims listed in `must_not_include`.

Because the current runners compare only `predicted_candidate_id` and `mentioned_evidence_edges`, cases where the correct answer is "this candidate is weak" or "this edge is missing" need additional schema fields and scoring logic.

## Proposed Optional Fields

These fields should be optional so existing cases and scripts can remain backward-compatible.

### `expected_missing_edges`

Example:

```json
"expected_missing_edges": ["IMPORTATION_LINK"]
```

Purpose:

Use this when the case asks whether a candidate lacks a relationship. For example, Australia has `LEADING_INDICATOR_FOR` and `POSSIBLE_DRIVER_OF`, but lacks `IMPORTATION_LINK`.

Scoring:

- Add `missing_edge_correct`: true if the model output explicitly identifies all expected missing edges as absent.
- Add `missing_edge_recall`: fraction of expected missing edges correctly identified as absent.
- Add `missing_edge_false_claim_count`: count of expected missing edges that the model incorrectly claims are present in `mentioned_evidence_edges`.

Practical note:

The LLM JSON schema should be extended with a field such as `identified_missing_edges` before this can be scored cleanly.

### `expected_rejected_candidate_id`

Example:

```json
"expected_rejected_candidate_id": "signal_humidity_drop"
```

Purpose:

Use this when a case asks the method to reject or avoid selecting a weak candidate.

Scoring:

- Add `rejected_candidate_correct`: true if the model identifies the rejected candidate as unsupported or weaker.
- Add `rejected_candidate_selected`: true if the model incorrectly predicts the rejected candidate as the main answer.

Practical note:

The LLM JSON schema should include a field such as `rejected_candidate_ids` for LLM-based methods. For KG-only, this can be approximated using rank position and validation result.

### `expected_answer_type`

Example:

```json
"expected_answer_type": "missing_edge_detection"
```

Purpose:

Use this to tell the evaluator what kind of scoring applies to the case. This avoids forcing every case into top-candidate accuracy.

Recommended values:

- `top_candidate_selection`
- `candidate_contrast`
- `evidence_edge_retrieval`
- `missing_edge_detection`
- `weak_candidate_rejection`
- `partial_evidence_detection`
- `support_subgraph_reasoning`
- `provenance_dataset_support`

Scoring:

- Route each case to the relevant metric set.
- Keep `top1_correct` only for answer types where selecting a top candidate is meaningful.
- Add task-specific metrics for missing edges, rejection, partial support, or support nodes.

Practical note:

This is the most important field to add first because it prevents misleading top-1 scoring on cases where the desired answer is not simply "select the top candidate."

### `expected_support_nodes`

Example:

```json
"expected_support_nodes": [
  "signal_chile_flu",
  "signal_us_hosp",
  "eq_us_flu_base"
]
```

Purpose:

Use this when the case asks for support-subgraph reasoning. This field already appears in the current eval cases but is not yet scored.

Scoring:

- Add `support_node_precision`: expected-vs-mentioned node precision.
- Add `support_node_recall`: expected-vs-mentioned node recall.
- Add `hallucinated_support_node_count`: mentioned nodes not in expected nodes.

Practical note:

LLM-based methods need a new JSON field such as `mentioned_support_nodes`. KG-only and GraphRAG can also record retrieved support nodes directly.

### `expected_weak_candidate_id`

Example:

```json
"expected_weak_candidate_id": "signal_humidity_drop"
```

Purpose:

Use this when a candidate has some evidence but should be treated as weak or partial support rather than a full explanation.

Scoring:

- Add `weak_candidate_flagged`: true if the method describes the candidate as weak, partial, or insufficiently supported.
- Add `weak_candidate_overstated`: true if the method treats the weak candidate as fully supported.

Practical note:

This is different from `expected_rejected_candidate_id`: a weak candidate may still be relevant, but should not be promoted as fully supported.

### `expected_stronger_candidate_id`

Example:

```json
"expected_stronger_candidate_id": "signal_chile_flu"
```

Purpose:

Use this for contrast cases where the model must explain that one candidate is stronger than another due to more complete graph support.

Scoring:

- Add `stronger_candidate_correct`: true if the predicted or explained stronger candidate matches this field.
- Add `contrast_explanation_edges_correct`: true if the explanation uses the edge difference that makes the stronger candidate stronger.

Practical note:

This pairs well with `expected_weak_candidate_id` or `expected_rejected_candidate_id`.

### `expected_present_edges`

Example:

```json
"expected_present_edges": ["LEADING_INDICATOR_FOR", "POSSIBLE_DRIVER_OF"]
```

Purpose:

Use this when a case needs to distinguish present evidence from missing evidence. This is useful for partial-evidence cases like Australia or Travel Pressure.

Scoring:

- Compare `mentioned_evidence_edges` against `expected_present_edges`.
- Compare `identified_missing_edges` against `expected_missing_edges`.
- Score both sides so the method gets credit for saying what is present and what is absent.

Practical note:

This could eventually replace `expected_evidence_edges`, but initially it should be optional and backward-compatible.

### `must_not_include`

Current status:

This field already exists, but it is not machine-scored.

Proposed scoring:

- Add `forbidden_claim_count`: count of forbidden phrases or normalized forbidden claims found in the explanation/raw response.
- Add `passes_negative_constraints`: true if no forbidden claims are found.

Practical note:

Start with simple case-insensitive substring matching. It will not be perfect, but it is useful for catching obvious hallucinations like "claim Australia has IMPORTATION_LINK."

## Recommended Output Schema Extension

The LLM-based runners currently request:

```json
{
  "predicted_candidate_id": "...",
  "predicted_candidate_name": "...",
  "explanation": "...",
  "proposed_edit_type": "...",
  "mentioned_evidence_edges": []
}
```

For extended scoring, add optional output fields:

```json
{
  "predicted_candidate_id": "...",
  "predicted_candidate_name": "...",
  "explanation": "...",
  "proposed_edit_type": "...",
  "mentioned_evidence_edges": [],
  "identified_missing_edges": [],
  "mentioned_support_nodes": [],
  "rejected_candidate_ids": [],
  "weak_candidate_ids": [],
  "stronger_candidate_id": "..."
}
```

These should be optional at first. Existing metrics can still run if the fields are absent.

## Practical Scoring Additions

The smallest useful metric additions are:

| Metric | Inputs | Meaning |
|---|---|---|
| `missing_edge_recall` | `expected_missing_edges`, `identified_missing_edges` | Did the method identify absent evidence? |
| `missing_edge_false_claim_count` | `expected_missing_edges`, `mentioned_evidence_edges` | Did the method hallucinate missing edges as present? |
| `support_node_recall` | `expected_support_nodes`, `mentioned_support_nodes` or retrieved nodes | Did the method recover expected support nodes? |
| `rejected_candidate_correct` | `expected_rejected_candidate_id`, `rejected_candidate_ids` | Did the method reject the intended weak/invalid candidate? |
| `weak_candidate_overstated` | `expected_weak_candidate_id`, explanation/prediction | Did the method overstate partial evidence? |
| `stronger_candidate_correct` | `expected_stronger_candidate_id`, `stronger_candidate_id` or prediction | Did the method choose the stronger candidate in a contrast case? |
| `forbidden_claim_count` | `must_not_include`, explanation/raw response | Did the method include forbidden claims? |

## Smallest Safe Next Implementation Step

The safest next step is to add an evaluator helper module without changing the research meaning of the existing cases.

Recommended first implementation:

1. Create a new helper file, for example `evals/eval_metrics.py`.
2. Move shared metric utilities into it:
   - `normalize_edge_types`
   - evidence precision/recall
   - hallucinated evidence count
   - optional missing-edge scoring
   - optional support-node scoring
   - optional forbidden-claim scoring
3. Update one runner first, preferably `run_graphrag_eval.py`, to use the helper while preserving the current CSV columns.
4. Add new CSV columns only when the matching optional fields exist in an eval case.
5. Add 2-3 pilot cases with `expected_answer_type`, `expected_missing_edges`, and `expected_weak_candidate_id`.
6. Run all methods and inspect whether the new metrics separate Text-RAG from GraphRAG.

Why this is safest:

- It avoids rewriting all eval scripts at once.
- It keeps the existing 10-case benchmark compatible.
- It lets missing-edge and weak-candidate cases be added gradually.
- It makes the scoring logic consistent across KG-only, LLM-only, Text-RAG, and GraphRAG.

## Suggested Pilot Cases After Schema Update

After scoring is extended, add cases like:

- Australia partial support: present `LEADING_INDICATOR_FOR` and `POSSIBLE_DRIVER_OF`, missing `IMPORTATION_LINK`.
- Travel Pressure partial support: present `IMPORTATION_LINK` and `POSSIBLE_DRIVER_OF`, missing `LEADING_INDICATOR_FOR`.
- Humidity weak support: present only `POSSIBLE_DRIVER_OF`, missing both `LEADING_INDICATOR_FOR` and `IMPORTATION_LINK`.
- Chile vs Australia contrast: Chile stronger because it has all three expected evidence edges.
- Chile vs Travel Pressure contrast: Chile stronger because Travel Pressure lacks the leading-indicator edge.

These cases should help separate methods that merely retrieve plausible text from methods that preserve graph structure and relationship constraints.
