# Real-Data KG Repository Inspection

## 1. Existing Benchmark Entry Points

The current simulated benchmark is run as a collection of Python scripts rather than through one top-level command. Commands below assume the repository root is the working directory.

### Reseed Neo4j

```powershell
python neo4j_loader.py
```

This command is destructive: `neo4j_loader.py` calls `clear_graph()` and executes `MATCH (n) DETACH DELETE n` before loading `seed_graph.GRAPH`. It should be understood as "replace the current database contents with the simulated seed graph," not as an additive loader. Running it after loading real observations or evidence claims into the same Neo4j database would delete them.

### Run the 50-case hard pilot

```powershell
# Deterministic KG-only hard pilot
python evals\run_hard_pilot_eval.py

# LLM-only hard pilot
python evals\run_llm_hard_pilot_eval.py

# Text-RAG hard pilot
python evals\run_text_rag_hard_pilot_eval.py

# Neo4j-backed GraphRAG hard pilot
python evals\run_graphrag_hard_pilot_eval.py
```

The four scripts read `evals/eval_cases_hard_pilot.json` and write separate CSVs under `evals/results/`.

### Summarize hard-pilot results

```powershell
python evals\summarize_hard_pilot_results.py
```

This reads the four hard-pilot result CSVs and writes `evals/results/hard_pilot_summary.csv`.

### Repeated evaluation

The current parameterized repeated runner is:

```powershell
python evals\run_hard_pilot_repeated_eval.py --runs 3
```

It imports and repeats the three LLM-based hard-pilot methods, then writes detailed and aggregate files:

- `evals/results/hard_pilot_repeated_results.csv`
- `evals/results/hard_pilot_repeated_summary.csv`

There is also an older fixed-run orchestrator:

```powershell
python evals\run_repeated_hard_pilot_eval.py
```

That script uses a fixed `RUNS = 5`, runs KG-only once, invokes the three LLM-based scripts and the single-run summarizer on every iteration, and writes `evals/results/repeated_hard_pilot_summary.csv`. The similarly named repeated runners should not be treated as interchangeable; the parameterized `run_hard_pilot_repeated_eval.py` is the clearer pattern for a new implementation.

### Ablation evaluation

```powershell
# Single ablation run
python evals\run_hard_pilot_ablation_eval.py

# Summarize the single ablation run
python evals\summarize_hard_pilot_ablation_results.py

# Repeated ablation runs
python evals\run_hard_pilot_ablation_repeated_eval.py --runs 3
```

The ablation compares `Full GraphRAG`, `No validation`, and `Ranking only, no support subgraph`. Its single-run and repeated outputs are kept in separate `hard_pilot_ablation_*` CSVs under `evals/results/`.

The older 10-case benchmark remains available through:

```powershell
python evals\run_kg_only_eval.py
python evals\run_llm_only_eval.py
python evals\run_text_rag_eval.py
python evals\run_graphrag_eval.py
python evals\summarize_eval_results.py
```

## 2. Existing Data and Case Files

The simulated benchmark's facts are distributed across Python and JSON artifacts:

| File | Current role |
|---|---|
| `seed_graph.py` | Canonical in-memory simulated graph. It defines nodes, candidate signals, datasets, papers, mechanisms, and all hand-authored relationships. |
| `schema.py` | Allowlist and minimal validation for seed-graph node types and edge types. |
| `failure_case.py` | Four failure-case dictionaries and their candidate lists: influenza, dengue, RSV, and COVID-19. |
| `evals/eval_cases.json` | Original 10-case evaluation set and expected candidate/evidence fields. |
| `evals/eval_cases_hard_pilot.json` | Current 50-case hard-pilot answer key. The cases cover four failure scenarios. |
| `evals/text_rag_corpus.json` | Current simulated Text-RAG corpus containing 32 hand-authored chunks. |
| `evals/eval_metrics.py` | Shared set-based evidence, missing-edge, support-node, parsing, and mean helpers. |
| `validator.py` | In-memory candidate validation for the simulated graph. |
| `neo4j_validator.py` | Neo4j candidate validation based on score, support-edge, dataset, and paper-provenance counts. |

The 50 hard-pilot cases use these fields across the file:

- `id`
- `task_type`
- `expected_answer_type`
- `question`
- `failure_case_id`
- `expected_candidate_id`
- `expected_present_edges`
- `expected_missing_edges`
- `expected_stronger_candidate_id`
- `expected_weak_candidate_id`
- `must_not_include`

The candidate entities and their positive graph relationships live in `seed_graph.py`; candidate membership by failure case lives in `failure_case.py`; expected present and missing relationships live in `evals/eval_cases_hard_pilot.json`. This separation means the current benchmark does not have one canonical evidence-claim table.

The Text-RAG corpus uses:

- `chunk_id`
- `title`
- `text`
- `source_type`
- `related_candidate_id`
- `edge_types`

Candidate-summary chunks state both present and missing edges in prose. Other chunks describe mechanisms, target signals, scoring rules, background, data quality, model revision, evaluation warnings, and failure cases.

Generated outputs live under `evals/results/`. They are experiment results, not source evidence.

The repository also contains earlier real-signal prototypes at the repository root:

- `prepare_us_hosp_series.py`
- `ingest_us_hosp_real_data.py`
- `neo4j_timeseries.py`
- `prepare_chile_flu_series.py`
- `ingest_chile_flu_real_data.py`
- `neo4j_chile_timeseries.py`
- `real_signal_lag_check.py`
- `neo4j_signal_summary.py`
- `neo4j_chile_signal_summary.py`
- `neo4j_prompt_with_data_demo.py`

These scripts establish useful precedents for `Week` and `Observation` nodes, anchor-node checks, uniqueness constraints, signal summaries, and exploratory lagged Pearson correlation. They are not yet the planned Influenza A wastewater evidence-claim pipeline, and they depend on the simulated seed graph's anchor IDs.

## 3. Existing Neo4j Loading Pattern

`neo4j_loader.py` imports the entire `GRAPH` dictionary from `seed_graph.py`. Its load sequence is:

1. Connect to the hard-coded `neo4j` database.
2. Delete every node and relationship.
3. Iterate over `GRAPH["nodes"]`.
4. Create or update each node with a dynamic label and `id`.
5. Iterate over `GRAPH["edges"]`.
6. Match endpoints by globally queried `id` values and merge the typed relationship.
7. Print total node and relationship counts.

Nodes are loaded with:

```cypher
MERGE (n:<type> {id: $id})
SET n += $properties
```

Relationships are loaded with:

```cypher
MATCH (a {id: $source_id})
MATCH (b {id: $target_id})
MERGE (a)-[r:<type>]->(b)
```

Important characteristics of this pattern are:

- The node's `type` maps directly to its Neo4j label.
- The edge's `type` maps directly to its Neo4j relationship type.
- Nodes use string IDs with semantic prefixes such as `disease_`, `region_`, `eq_`, `signal_`, `dataset_`, `context_`, `paper_`, `state_`, and `param_`.
- Failure-case IDs use `failure_case_...`, but failure cases currently remain Python dictionaries rather than Neo4j nodes.
- Candidate drivers are represented as `Signal` nodes, not `CandidateDriver` nodes.
- Evidence edges are direct relationships from a candidate `Signal` to either a target `Signal` or a `MechanismEquation`.
- `LEADING_INDICATOR_FOR` points to the target `Signal`.
- `IMPORTATION_LINK` and `POSSIBLE_DRIVER_OF` point to the failure case's `MechanismEquation`.
- The generic seed loader does not set relationship properties.
- The generic seed loader creates no constraints or indexes.
- Its endpoint matches do not specify labels, so the repository relies on IDs being globally unique.
- Although `schema.py` validates allowlisted seed types when `seed_graph.py` is run directly, `neo4j_loader.py` does not call schema validation before loading.

The current seed labels are:

- `MechanismEquation`
- `StateVariable`
- `Parameter`
- `Region`
- `Disease`
- `Signal`
- `Context`
- `Dataset`
- `Paper`

The seed schema does not currently include `FailureCase`, `CandidateDriver`, `EvidenceClaim`, `TimeWindow`, `Week`, or `Observation`. The last two labels are nevertheless used by direct-Cypher real-signal ingestion scripts, which bypass `schema.py`.

`ingest_us_hosp_real_data.py` and `ingest_chile_flu_real_data.py` show an additive pattern that is safer for real data:

- Verify that the expected `Signal`, `Region`, and `Disease` anchor nodes already exist.
- Create `Observation` and `Week` nodes with `MERGE`.
- Add `OF_SIGNAL`, `IN_REGION`, `ABOUT_DISEASE`, and `FOR_WEEK` relationships.
- Create uniqueness constraints for `Observation.id`; the U.S. loader also creates one for `Week.id`.

There is, however, a week-key inconsistency to resolve before reuse. The U.S. loader merges `Week` by `id`, while the Chile loader merges by `{calendar_year, mmwr_week}` and then assigns an ID. The Chile source is ISO-week based even though the merge keys use `calendar_year` and `mmwr_week` property names. A new pipeline should define one explicit weekly calendar and identifier rule rather than inherit both conventions.

## 4. Existing GraphRAG Retrieval Pattern

`neo4j_retrieval.py` contains the current Neo4j ranking and support-subgraph queries.

For a given failure case, `run_candidate_ranking()`:

1. Matches every `Signal` as a possible candidate.
2. Checks whether it has `POSSIBLE_DRIVER_OF` to the specified mechanism.
3. Checks whether it has `IMPORTATION_LINK` to the specified mechanism.
4. Checks whether it has `LEADING_INDICATOR_FOR` to the specified target signal.
5. Assigns fixed weights of 2, 2, and 3 respectively.
6. Keeps candidates with a score above zero.
7. Returns candidate ID, name, score, and evidence strings ordered by descending score and then candidate ID.

`run_support_subgraph_query()` then retrieves exactly three anchor nodes—the candidate `Signal`, target `Signal`, and `MechanismEquation`—plus any of the three evidence relationships between them. Dataset, paper, context, observation, and provenance paths are not included in this support subgraph.

The 50-case GraphRAG runner, `evals/run_graphrag_hard_pilot_eval.py`, fetches rankings and support subgraphs for every candidate once per failure case. It passes the LLM:

- The failure-case dictionary.
- The case question.
- Each candidate's rank, ID, name, and score.
- Ranking evidence strings.
- Support-subgraph nodes.
- Support-subgraph edges.

The prompt requires JSON and limits edge outputs to the three simulated relationship types. The runner then scores the LLM output against the hard-pilot answer key.

There are two validation patterns:

- The original `evals/run_graphrag_eval.py` validates the top candidate with `neo4j_validator.py`.
- The 50-case GraphRAG runner does not call that validator directly; it supplies graph context for all ranked candidates.
- `evals/run_hard_pilot_ablation_eval.py` constructs variants with and without an explicit validation summary to test validation separately.

The current retrieval code is therefore not a drop-in query for the proposed real graph. It assumes candidates have the `Signal` label, uses only the three direct relationship types, targets a mechanism for two of them, assigns fixed relationship weights, and does not retrieve `EvidenceClaim` provenance or typed-edge properties.

## 5. Existing Text-RAG Pattern

The shared corpus is `evals/text_rag_corpus.json`. Both `evals/run_text_rag_eval.py` and `evals/run_text_rag_hard_pilot_eval.py` implement similar retrieval logic locally rather than importing a shared retrieval helper.

The hard-pilot retrieval process is:

1. Build query text from the case question and scalar values in the failure-case dictionary.
2. Deliberately exclude answer-key fields.
3. Lowercase and tokenize with a regular expression.
4. Remove a small fixed stopword list.
5. Score each chunk by token overlap.
6. Add a bonus for query tokens found in the chunk title.
7. Sort by descending score and then `chunk_id`.
8. Return the top three chunks by default.

The prompt receives:

- The failure case.
- The hard-pilot question.
- The retrieved chunk objects, including their retrieval scores.
- The list of possible candidates for that failure case.

The LLM is told not to use Neo4j or assume graph paths. Its output schema otherwise matches the LLM-only and GraphRAG hard-pilot schemas.

For the real-data extension, the safest parity design is to generate a separate real corpus deterministically from `data/real_processed/real_evidence_claims.csv`. The existing hand-authored `evals/text_rag_corpus.json` should not be appended to or regenerated. Initially, the real runner may reuse the lexical retrieval algorithm, but the duplication between the two current Text-RAG runners should not be expanded casually into a third copy without deciding whether to extract a read-only helper.

## 6. Existing Evaluation Schema

### Answer-key schema

The 50-case answer key in `evals/eval_cases_hard_pilot.json` distinguishes:

- The candidate being evaluated.
- Evidence edges expected to be present.
- Evidence edges expected to be missing.
- A stronger candidate when comparison is required.
- A weak candidate when rejection or demotion is required.
- Natural-language claims that should not appear.

`must_not_include` is present in the cases but is not currently machine-scored by the hard-pilot runners.

### LLM-method output schema

LLM-only, Text-RAG, GraphRAG, and the ablation runner require:

```json
{
  "predicted_candidate_id": "...",
  "predicted_candidate_name": "...",
  "explanation": "...",
  "mentioned_evidence_edges": [],
  "identified_missing_edges": [],
  "rejected_candidate_ids": [],
  "weak_candidate_ids": [],
  "stronger_candidate_id": "..."
}
```

The runners validate the field types, normalize non-empty strings in list fields, preserve the raw response, and serialize list values into semicolon-delimited CSV cells.

The KG-only hard-pilot runner is deterministic and has a different output shape. Instead of generating `predicted_candidate_id`, it records whether the expected candidate was found, its rank, retrieved present edges, inferred missing edges, stronger-candidate rank, and weak-candidate rank.

### Current metrics

`evals/eval_metrics.py` supplies:

- Set-based evidence precision and recall.
- A general `hallucinated_evidence_count`.
- Missing-edge correctness and recall.
- `missing_edge_false_claim_count`.
- Support-node precision and recall helpers.
- Boolean, float, and mean utilities.

The hard-pilot scripts report:

- Candidate accuracy for LLM-based methods.
- Average present-edge precision.
- Average present-edge recall.
- Average missing-edge recall.
- Missing-edge false claim count.
- Stronger-candidate identification or ranking accuracy.
- Weak-candidate rejection accuracy.

For LLM-based methods:

- `candidate_correct` is exact equality between `predicted_candidate_id` and `expected_candidate_id`.
- `stronger_candidate_identified` is exact equality between `stronger_candidate_id` and `expected_stronger_candidate_id`.
- `weak_candidate_rejected` is true when the expected weak candidate appears in either `rejected_candidate_ids` or `weak_candidate_ids`.
- `missing_edge_false_claim_count` counts expected-missing edges that also appear in `mentioned_evidence_edges`.

The original 10-case runners persist the general `hallucinated_evidence_count`. The 50-case runners call the general evidence metric for precision and recall but do not persist its hallucinated-edge count; their explicit false-claim total is the narrower missing-edge false-claim count. The support-node metric helper also exists but is not used by the current hard-pilot runners.

`evals/summarize_hard_pilot_results.py` accommodates the KG-only column names with fallbacks:

- `stronger_candidate_identified` falls back to `stronger_candidate_ranks_above`.
- `weak_candidate_rejected` falls back to `weak_candidate_not_top`.

It leaves KG-only candidate accuracy blank because that result file does not contain `candidate_correct`.

For the real-data pipeline, the reusable metric core is the set comparison in `evals/eval_metrics.py`. Reuse still requires explicit decisions about how `status = missing` differs from `status = insufficient_data`, whether a one-candidate v1 should report candidate accuracy, and whether all unsupported claims—not only claims for expected-missing edges—should count as false evidence.

## 7. Safe Real-Data Extension Points

The safest design is an isolated, additive pipeline with its own inputs, generated artifacts, Cypher, cases, corpus, and result directory. It should consume existing benchmark helpers only where their assumptions are demonstrably compatible.

### Proposed scripts

```text
scripts/real_kg/download_real_data.py
scripts/real_kg/normalize_real_signals.py
scripts/real_kg/build_real_evidence_claims.py
scripts/real_kg/load_real_kg_to_neo4j.py
scripts/real_kg/build_real_text_corpus.py
scripts/real_kg/run_real_eval.py
```

Recommended responsibilities:

- `download_real_data.py`: acquire or verify source files and record source URL, retrieval time, and checksum; never alter raw files.
- `normalize_real_signals.py`: inspect and normalize source-specific fields into a documented weekly signal format.
- `build_real_evidence_claims.py`: compute lagged-correlation evidence and write the canonical `real_evidence_claims.csv`.
- `load_real_kg_to_neo4j.py`: perform additive, idempotent loading and set evidence relationship properties; never call `clear_graph()`.
- `build_real_text_corpus.py`: render the same claim rows into a separate deterministic corpus with claim-to-chunk traceability.
- `run_real_eval.py`: read only real cases, real corpus, and real graph evidence and write only to `evals/results_real/`.

### Proposed directories

```text
data/real_raw/
data/real_processed/
evals/results_real/
```

Useful additional isolated artifacts are:

```text
data/real_processed/real_evidence_claims.csv
data/real_processed/real_text_rag_corpus.json
evals/real_eval_cases.json
```

The real cases and corpus should not be merged into the simulated JSON files.

### Neo4j extension seam

A new loader should use direct, parameterized Cypher, following the additive style of the existing observation ingesters rather than the destructive generic seed loader. It should:

- Create explicit uniqueness constraints for new stable IDs.
- Use a `real_` ID namespace or another documented collision-proof convention.
- Match endpoints by both label and ID.
- Load `EvidenceClaim`, `Dataset`, `Region`, `TimeWindow`, and failure/candidate/target entities idempotently.
- Set `evidence_id`, `score`, `lag_weeks`, `method`, and `status` on a qualifying `LEADING_INDICATOR_FOR` edge.
- Keep missing and insufficient claims as auditable `EvidenceClaim` nodes without creating a positive typed edge.
- Verify claim-row counts and evidence-ID traceability after loading.

Database isolation must be decided before this loader is implemented. A separate Neo4j database is the cleanest protection if the installed Neo4j edition and environment support it. If both graphs must share the `neo4j` database, the real loader must be additive and the destructive simulated reseed command must be treated as incompatible with preserving real graph contents.

### Retrieval extension seam

Real-specific Cypher should live with the new pipeline initially. It can return a context object shaped similarly to the current GraphRAG runner—candidate ID, name, rank or score, evidence, and support nodes/edges—without changing `neo4j_retrieval.py`.

This avoids forcing the real schema into current assumptions. In particular, the planned `CandidateDriver` label will not be found by the current `MATCH (candidate:Signal)` query unless real candidates are multi-labeled. A real-specific query can match `CandidateDriver`, traverse `HAS_EVIDENCE`, retrieve `EvidenceClaim` provenance and limitations, and follow `SUPPORTS_TARGET`.

### Text-RAG extension seam

Generate a new real corpus from `real_evidence_claims.csv`; do not hand-author it and do not add it to `evals/text_rag_corpus.json`. The initial real runner can reproduce the existing deterministic top-three lexical algorithm so representation—not source facts—is the primary difference. A later refactor may extract tokenization and scoring into a shared helper after parity tests show identical behavior.

### Evaluation extension seam

The real runner can reuse `compute_evidence_metrics()`, `compute_missing_edge_metrics()`, normalization, and summary utilities conceptually or by import. It should use separate constants for:

- Real case path.
- Real corpus path.
- Real result paths.
- Real edge vocabulary.
- Real Neo4j query functions.

No existing runner should be given mode flags initially. Separate entry points reduce the chance that a path or schema change silently alters the 50-case benchmark.

## 8. Files That Should Not Be Modified Initially

The following files should remain unchanged during the first real-data implementation:

### Simulated graph and failure definitions

- `seed_graph.py`
- `schema.py`
- `failure_case.py`
- `neo4j_loader.py`
- `failure_retrieval.py`
- `neo4j_retrieval.py`
- `validator.py`
- `neo4j_validator.py`

Changing these could alter graph contents, ranking, relationship weights, candidate membership, or validation behavior for the simulated benchmark.

### Existing prompts and model helpers

- `prompt_builder.py`
- `llm_reasoner.py`
- `neo4j_prompt_demo.py`
- `neo4j_prompt_with_data_demo.py`

The real runner should initially own its prompt so the simulated prompt contract remains stable.

### Existing cases and corpora

- `evals/eval_cases.json`
- `evals/eval_cases_hard_pilot.json`
- `evals/text_rag_corpus.json`

### Existing evaluation and summary scripts

- `evals/run_kg_only_eval.py`
- `evals/run_llm_only_eval.py`
- `evals/run_text_rag_eval.py`
- `evals/run_graphrag_eval.py`
- `evals/run_hard_pilot_eval.py`
- `evals/run_llm_hard_pilot_eval.py`
- `evals/run_text_rag_hard_pilot_eval.py`
- `evals/run_graphrag_hard_pilot_eval.py`
- `evals/run_hard_pilot_repeated_eval.py`
- `evals/run_repeated_hard_pilot_eval.py`
- `evals/run_hard_pilot_ablation_eval.py`
- `evals/run_hard_pilot_ablation_repeated_eval.py`
- `evals/summarize_eval_results.py`
- `evals/summarize_hard_pilot_results.py`
- `evals/summarize_hard_pilot_ablation_results.py`
- `evals/eval_metrics.py`

The metric helper may eventually be imported by real code, but it does not need modification for the first isolated implementation.

### Existing generated results

- Everything under `evals/results/`

Real outputs should go to `evals/results_real/`.

### Existing real-signal prototypes

- `prepare_us_hosp_series.py`
- `ingest_us_hosp_real_data.py`
- `prepare_chile_flu_series.py`
- `ingest_chile_flu_real_data.py`
- `real_signal_lag_check.py`
- Existing Neo4j time-series and signal-summary helpers.

These should be treated as inspected references. Refactoring them during v1 would mix cleanup of earlier prototypes with implementation of the new U.S. hospitalization/Influenza A wastewater pipeline.

## 9. Open Questions Before Coding

### Neo4j isolation and lifecycle

- Will the real graph use a separate Neo4j database, a separate server, or the same `neo4j` database?
- If it shares the database, how will users be prevented from running the destructive simulated reseed after real data is loaded?
- Should the real loader create all anchor nodes itself, or require selected simulated anchors to exist as the older observation loaders do?
- Should connection settings remain imported from `neo4j_retrieval.py`, or move later to environment variables and shared configuration?

### Schema compatibility

- Should the wastewater candidate be only `CandidateDriver`, or carry both `CandidateDriver` and `Signal` labels?
- Should `FailureCase` become a Neo4j node for real evaluation while simulated failure cases remain Python dictionaries?
- What relationship connects `EvidenceClaim` to `TimeWindow`? The plan names the node but not the relationship.
- Is the typed `LEADING_INDICATOR_FOR` edge created only for `status = present`, and how are `missing` and `insufficient_data` distinguished in graph queries?
- What stable `evidence_id` and ID-prefix conventions will prevent collisions with simulated IDs?

### Time-series normalization

- Which CDC hospitalization endpoint or export is authoritative for v1, and what exact fields define national weekly hospitalization rate?
- Which CDC Influenza A wastewater endpoint and aggregation level produce a comparable U.S. weekly series?
- Will week alignment use MMWR week, ISO week, or an explicit week-start date?
- How will changing site coverage, missingness, suppression, revisions, and aggregation be handled?
- What lag sign convention, lag range, minimum overlap, correlation measure, threshold, and multiple-lag policy are fixed before claim generation?

### Evaluation organization

- Should `run_real_eval.py` contain four methods, or should it orchestrate separate real KG-only, LLM-only, Text-RAG, and GraphRAG runners?
- With one v1 candidate and one edge type, which metrics are informative enough to report?
- Can existing metric functions be imported directly from `evals/eval_metrics.py` without path manipulation, or should a shared package be introduced later?
- Should `insufficient_data` be excluded from missing-edge recall or scored as a separate outcome?
- Should real evaluation count every unsupported mentioned edge as a false evidence claim, rather than only expected-missing edges?
- Should `must_not_include` finally be machine-scored for real cases, or kept as an unscored review aid for parity with the hard pilot?

### Text-RAG parity

- Should lexical retrieval be copied unchanged for the first parity test, or extracted into a shared helper?
- Which claim fields must appear in every text chunk so score, lag, method, status, provenance, time window, and limitation remain equivalent to graph evidence?
- Will missing and insufficient claims receive their own chunks, and how will retrieval avoid treating a sentence describing an absent edge as a positive claim?

## 10. Recommended Next Coding Step

The lowest-risk next repository change is to scaffold the isolated real-data namespace without executable behavior:

```text
scripts/real_kg/README.md
data/real_raw/README.md
data/real_processed/README.md
evals/results_real/README.md
```

Those READMEs should define file ownership, input/output boundaries, ignored raw-data expectations, the exact `real_evidence_claims.csv` columns, ID rules, week convention, and the rule that no real-data script may write to `evals/results/` or call `neo4j_loader.clear_graph()`.

After that scaffold is reviewed, the first executable addition should be `scripts/real_kg/build_real_evidence_claims.py` operating on a tiny checked or manually supplied normalized fixture. It should validate the proposed CSV schema and deterministically emit `data/real_processed/real_evidence_claims.csv` without connecting to Neo4j, calling an LLM, or downloading data. This isolates the most important contract—the canonical evidence claim—from network, database, prompt, and evaluation concerns. Neo4j loading and Text-RAG generation should be implemented only after that artifact and its status semantics are stable.
