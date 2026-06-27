# Processed Real-Data Artifacts

This folder is for generated, normalized real-data artifacts. Files here should be reproducible from documented raw inputs and transformation rules.

## Canonical Evidence Artifact

The canonical artifact is:

`real_evidence_claims.csv`

It must contain these columns:

| Column |
|---|
| `case_id` |
| `candidate_id` |
| `candidate_name` |
| `target_signal_id` |
| `target_signal_name` |
| `edge_type` |
| `status` |
| `source_dataset` |
| `method` |
| `region` |
| `time_window_start` |
| `time_window_end` |
| `lag_weeks` |
| `score` |
| `threshold` |
| `evidence_sentence` |
| `limitation` |

Valid `status` values are:

- `present`
- `missing`
- `insufficient_data`

`real_evidence_claims.csv` is the shared source for:

- Real Neo4j KG loading.
- Real Text-RAG corpus generation.
- The real evaluation answer key.

All three consumers must derive their facts from this CSV so the graph, text, and evaluation representations remain aligned.
