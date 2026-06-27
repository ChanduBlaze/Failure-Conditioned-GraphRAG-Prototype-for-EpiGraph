# Real-Data Knowledge Graph Extension Plan

## 1. Goal

The goal is to construct an auditable, real-data evidence knowledge graph (KG) and use it to run the existing comparison among KG-only, LLM-only, Text-RAG, and GraphRAG methods. Instead of relying on hand-authored evidence relationships, the extension will generate evidence claims from public surveillance data and retain the source, method, time window, score, threshold, and limitations for every claim.

The first implementation will focus on whether Influenza A wastewater activity is a leading indicator of the U.S. influenza hospitalization rate. The resulting evidence claims will be represented in Neo4j and in a text corpus derived from the same source artifact. This will allow the benchmark to measure whether each method preserves data-derived evidence accurately while keeping every claim traceable to its inputs and computation.

## 2. Why This Is an Extension, Not a Replacement

The existing 50-case simulated benchmark remains the controlled benchmark. Its known, hand-authored evidence structures isolate retrieval and reasoning behavior: because the expected candidates, present edges, and missing edges are known in advance, errors can be attributed more cleanly to evidence retrieval or reasoning.

The real-data KG is an extension that demonstrates how the same evidence structure can be grounded in public datasets. It introduces additional sources of uncertainty, including data quality, temporal alignment, statistical choices, and provenance. Results from the real-data extension should therefore complement, rather than replace or be merged uncritically with, the controlled benchmark results.

## 3. Initial Scope

The first implementation target is deliberately narrow:

- **Disease:** Influenza.
- **Region:** United States.
- **Target signal:** U.S. influenza hospitalization rate.
- **Candidate signal:** Influenza A wastewater activity.
- **Initial evidence relationship:** `LEADING_INDICATOR_FOR`.
- **Initial evidence-generation method:** Lagged correlation between normalized weekly signals.

The pipeline will test a documented range of candidate lags and determine whether wastewater activity leads the hospitalization signal within a defined analysis window. The precise correlation measure, lag convention, missing-data policy, minimum overlap, threshold, and tie-breaking rule must be fixed before claims are generated and recorded with the result.

`IMPORTATION_LINK` is out of scope for v1 unless suitable travel, mobility, or genomic evidence becomes available. `POSSIBLE_DRIVER_OF` must not be inferred from temporal association alone; any future use must be supported by mechanism and provenance and described as plausible or supported, not as causal proof.

## 4. Data Sources

Planned public sources are:

- CDC FluSurv-NET or another appropriate CDC influenza hospitalization surveillance dataset for the target signal.
- CDC Influenza A wastewater surveillance data for the candidate signal.

During implementation, the exact download locations, formats, geographic coverage, revision behavior, licensing or usage notes, and field names must be inspected rather than assumed. In particular, implementation must identify the date or epidemiological-week field, value and unit fields, geographic identifiers, aggregation level, suppression or missing-value conventions, and any dataset version or retrieval timestamp needed for reproducibility.

If the two sources do not provide directly comparable national weekly series, the normalization step must document how site-level or regional values are aggregated and how weeks are aligned. Raw source files should remain unchanged in `data/real_raw/`, while all transformations should be reproducible.

## 5. Real EvidenceClaim Schema

The canonical processed artifact will be:

`data/real_processed/real_evidence_claims.csv`

It will contain the following columns:

| Column | Purpose |
|---|---|
| `case_id` | Stable identifier for the real-data evaluation case. |
| `candidate_id` | Stable identifier for the candidate signal or driver. |
| `candidate_name` | Human-readable candidate name. |
| `target_signal_id` | Stable identifier for the target signal. |
| `target_signal_name` | Human-readable target signal name. |
| `edge_type` | Evidence relationship type, initially `LEADING_INDICATOR_FOR`. |
| `status` | Claim outcome, such as `present`, `missing`, or `insufficient_data`, using a fixed vocabulary. |
| `source_dataset` | Dataset identifier or identifiers from which the claim was derived. |
| `method` | Evidence-generation method and, where needed, a versioned method identifier. |
| `region` | Geographic scope of the comparison. |
| `time_window_start` | Inclusive start of the analysis window. |
| `time_window_end` | Inclusive end of the analysis window. |
| `lag_weeks` | Selected lag in weeks under a documented sign convention. |
| `score` | Computed evidence score, initially the lagged-correlation value. |
| `threshold` | Predefined score threshold used to assign status. |
| `evidence_sentence` | Controlled natural-language statement of the computed result. |
| `limitation` | Claim-specific caveat covering association, data quality, or method limits. |

This CSV will be the single canonical source for three downstream uses:

1. The evaluation answer key.
2. The Neo4j load source.
3. The Text-RAG corpus source.

Using one artifact prevents the graph and text representations from silently acquiring different facts. Generated claim rows should be deterministic for a fixed set of raw inputs and method parameters. The pipeline should also preserve sufficient run-level metadata such as source retrieval dates, checksums, normalization choices, and code or method versionâ€”to reproduce the CSV.

## 6. Neo4j Schema Additions

The real-data graph will use the following node labels:

- `FailureCase`: the forecast failure or evaluation context.
- `CandidateDriver`: a candidate signal or explanatory driver being evaluated.
- `Signal`: the target surveillance signal.
- `EvidenceClaim`: a reified, auditable result of an evidence-generation method.
- `Dataset`: a public source dataset and its provenance metadata.
- `Region`: the geographic scope in which the evidence was evaluated.
- `TimeWindow`: the bounded period used for the computation.

The core relationships will be:

```text
(:FailureCase)-[:HAS_CANDIDATE]->(:CandidateDriver)
(:FailureCase)-[:HAS_TARGET_SIGNAL]->(:Signal)
(:CandidateDriver)-[:HAS_EVIDENCE]->(:EvidenceClaim)
(:EvidenceClaim)-[:SUPPORTS_TARGET]->(:Signal)
(:EvidenceClaim)-[:DERIVED_FROM]->(:Dataset)
(:EvidenceClaim)-[:OBSERVED_IN]->(:Region)
(:CandidateDriver)-[:LEADING_INDICATOR_FOR]->(:Signal)
```

`EvidenceClaim` is the audit object: it records the method, analysis window, threshold, score, status, evidence sentence, and limitation. It should also connect to the relevant `TimeWindow`, for example through an `EVALUATED_DURING` relationship, so temporal scope is queryable rather than embedded only in text.

The typed `LEADING_INDICATOR_FOR` edge is a convenient retrieval projection of a qualifying claim. It must include at least:

- `evidence_id`
- `score`
- `lag_weeks`
- `method`
- `status`

Only claims whose status meets the predefined evidence rule should create a present typed edge. Missing or insufficient evidence should remain explicit `EvidenceClaim` nodes without being converted into a positive typed relationship. The `evidence_id` on the typed edge must point back to the canonical claim row so a retrieved relationship can always be audited.

## 7. Text-RAG Information Parity

The Text-RAG corpus must be generated from the same `real_evidence_claims.csv` used to load Neo4j. Each text unit should preserve the claim's candidate, target, edge type, status, score, lag, method, region, time window, provenance, and limitation. No facts should be manually added to one representation but omitted from the other.

This establishes information parity: GraphRAG and Text-RAG receive equivalent facts in different representations. GraphRAG receives explicit nodes and relationships, while Text-RAG receives controlled textual renderings of those same claim rows. Corpus-generation rules, chunk identifiers, and the mapping from each chunk to `case_id` and evidence claim ID should be deterministic and retained for auditing.

Retrieval settings may still differ because graph traversal and text retrieval are different methods, but the underlying evidence content must be held constant.

## 8. Evaluation Plan

The real-data evaluation will reuse the existing evidence-preservation framework where applicable:

- **Candidate accuracy:** whether the method identifies the expected candidate.
- **Present-edge recall:** the fraction of expected present evidence edges correctly recovered.
- **Present-edge precision:** the fraction of claimed present evidence edges supported by the answer key.
- **Missing-edge recall:** the fraction of expected absent relationships explicitly recognized as missing.
- **False evidence claims:** the count of unsupported relationships asserted as present.
- **Stronger-candidate accuracy:** whether the method chooses the better-supported candidate when multiple candidates are available.
- **Weak-candidate rejection:** whether the method avoids promoting candidates that do not meet the evidence rule.

For v1, the principal evaluation may contain one candidate and one computed edge type. Candidate accuracy will consequently have limited discriminative value, while present-edge, missing-edge, and false-claim metrics can still test evidence preservation. The v1 results should be reported separately from the simulated benchmark and should clearly state that fewer edge types are being tested.

If additional candidate signals are later included, the answer key should use the same predeclared method, lag search, threshold, time window, and missing-data rules wherever scientifically appropriate. Stronger and weaker candidates should be defined by those recorded rules rather than by desired model outputs. Evaluation should also distinguish `missing` from `insufficient_data`; lack of adequate observations is not evidence that a relationship is absent.

## 9. Proposed New Files

Planned scripts:

```text
scripts/real_kg/download_real_data.py
scripts/real_kg/normalize_real_signals.py
scripts/real_kg/build_real_evidence_claims.py
scripts/real_kg/load_real_kg_to_neo4j.py
scripts/real_kg/build_real_text_corpus.py
scripts/real_kg/run_real_eval.py
```

Planned data and output folders:

```text
data/real_raw/
data/real_processed/
evals/results_real/
```

The raw folder will preserve downloaded or manually supplied source files. The processed folder will hold normalized signals, the canonical evidence-claim CSV, and associated reproducibility metadata. The results folder will keep real-data evaluations separate from controlled benchmark outputs.

## 10. Implementation Phases

### Phase 1: Create the plan document

Create and review this implementation plan without changing the current benchmark.

### Phase 2: Inspect the existing repository structure and current evaluation/loader patterns

Document the current case schema, metric helpers, runner outputs, Neo4j constraints and merge behavior, identifier conventions, and Text-RAG corpus format. Identify the smallest compatible extension points.

### Phase 3: Create real-data folders and a placeholder README

Add the planned directories and document raw-data placement, generated artifacts, provenance expectations, and which files should or should not be committed.

### Phase 4: Download or manually place raw data

Acquire the selected CDC hospitalization and Influenza A wastewater datasets. Record source URLs or API requests, retrieval timestamps, versions where available, and checksums. Preserve raw files without transformation.

### Phase 5: Normalize weekly signals

Inspect source fields, select compatible geography and time coverage, convert both sources to an explicit epidemiological-week convention, reconcile units, aggregate where necessary, handle missing or suppressed values, and output analysis-ready weekly series. Produce validation summaries for overlap, missingness, and coverage.

### Phase 6: Compute lagged-correlation evidence claims

Predeclare the correlation measure, tested lag range, lag sign convention, minimum paired observations, treatment of trends and seasonality, threshold, and status rules. Compute scores without future leakage, select or report lags deterministically, and write `real_evidence_claims.csv` with a limitation for every claim.

### Phase 7: Load the real KG into Neo4j

Add idempotent constraints and loader operations for the proposed labels and relationships. Load the canonical claims and their provenance, then create typed evidence edges only for qualifying claims. Validate node counts, relationship counts, required properties, and evidence-ID traceability.

### Phase 8: Generate the real Text-RAG corpus

Render each canonical claim into controlled text, preserving positive, missing, and insufficient-data statuses as well as provenance and limitations. Validate row-to-chunk coverage and parity with the Neo4j representation.

### Phase 9: Run the real evaluation

Create real-data cases and run KG-only, LLM-only, Text-RAG, and GraphRAG under recorded configurations. Store raw responses and method outputs, apply the relevant existing metrics, and verify that no method receives evidence outside the canonical claims.

### Phase 10: Summarize results and compare with the simulated benchmark

Report real-data results separately, then compare patterns in evidence preservation with the controlled 50-case benchmark. Discuss differences in scope, edge diversity, data uncertainty, and claim-generation error so the comparison does not imply direct equivalence.

## 11. Limitations

- This extension does not prove causal discovery.
- This extension does not prove forecasting improvement.
- Lagged correlation is associational evidence, even when the candidate series temporally precedes the target.
- Searching multiple lags can inflate apparent evidence unless the search and threshold rules are predeclared and interpreted cautiously.
- Shared seasonality, trends, reporting processes, and unmeasured factors can produce correlation without a direct relationship.
- Real surveillance data may be noisy, incomplete, revised, delayed, suppressed, or regionally inconsistent.
- Wastewater site coverage and aggregation may change over time and may not represent the same population as hospitalization surveillance.
- A missing edge may reflect inadequate data or a conservative threshold rather than evidence that no relationship exists.
- The v1 graph tests a narrow disease, geography, candidate, method, and edge type, so its findings should not be generalized to all epidemiological evidence.
- The real-data extension demonstrates evidence grounding and auditability, not production-level epidemiological validation.

Any future `POSSIBLE_DRIVER_OF` claim must include mechanism and provenance support and must not be described as causal proof. Any future `IMPORTATION_LINK` claim must be based on appropriate travel, mobility, case-history, or genomic evidence rather than inferred from temporal correlation.

## 12. Thesis-Safe Claim

"The controlled benchmark evaluates GraphRAG under known evidence structures. The real-data extension demonstrates how similar evidence claims can be generated from public surveillance data, stored as auditable graph evidence, and evaluated using the same evidence-preservation framework."

