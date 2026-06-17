# Data Lineage and Graph Construction

## 1. Purpose

This document clarifies the data lineage for the project and explains how the current knowledge graph is constructed. Its purpose is to separate real-world input data from prototype/manual evidence data, generated evaluation outputs, and documentation artifacts.

The distinction is important for thesis interpretation. The project includes real epidemiological time-series grounding, but the current evidence graph is also intentionally controlled and manually/prototypically constructed. Therefore, the evaluation should be read as an assessment of graph-structured retrieval for evidence-grounded reasoning behavior, not as a fully automated real-world epidemiological discovery system.

## 2. Data Categories

The project data can be separated into four categories:

| Category | Role in the project |
|---|---|
| Real-world input data | External epidemiological time-series data used to ground the target signal and failure scenario. |
| Prototype/manual evidence data | Manually or prototypically constructed candidates, relationships, hard-pilot cases, expected outputs, scenario evidence, and Text-RAG corpus content used to evaluate reasoning behavior. |
| Generated evaluation outputs | CSV result files produced by evaluation scripts after running LLM-only, Text-RAG, KG-only, GraphRAG, or ablation experiments. |
| Documentation artifacts | Markdown notes and thesis-facing interpretation files that summarize design choices, results, limitations, and next steps. |

## 3. Real-World Data

The strongest real-world grounding in the current project is the U.S. influenza hospitalization time series. This data grounds the missed-peak failure scenario used in the influenza prototype.

The real-world influenza hospitalization series includes:

- 30 weekly observations.
- Weeks from 2024-W40 to 2025-W17.
- A peak weekly hospitalization rate of 13.5.
- A peak week of 2025-W06.
- A latest cumulative rate of 126.2 at 2025-W17.

This real data grounds the target signal and the failure context: the system is reasoning about a real missed influenza hospitalization peak rather than a purely imaginary target signal. However, this real-world time series does not automatically generate all evidence edges in the current prototype. In particular, the presence of real U.S. hospitalization data should not be interpreted as meaning that every candidate driver, evidence relationship, or graph edge was inferred directly from the real data.

## 4. Prototype/Manual Data

The current project also uses controlled prototype/manual evidence data. This includes candidate drivers, evidence relationships, hard-pilot cases, expected outputs, dengue scenario evidence, and the Text-RAG corpus.

These artifacts are manually or prototypically constructed to evaluate reasoning behavior across LLM-only, Text-RAG, and GraphRAG methods. They allow the project to test whether each method can preserve candidate-specific evidence, identify missing relationships, distinguish partial support from complete support, reject weak candidates, and compare candidates without mixing their evidence.

Examples of prototype/manual candidate or signal entities include:

- Chile Influenza Activity.
- Australia Influenza Activity.
- Travel Importation Pressure.
- Humidity Drop.
- Mosquito Vector Index.
- Rainfall Anomaly.
- Temperature Anomaly.
- Dengue Travel Importation Pressure.

The current prototype uses evidence edge types such as:

- `LEADING_INDICATOR_FOR`.
- `IMPORTATION_LINK`.
- `POSSIBLE_DRIVER_OF`.

These relationships are useful for evaluating graph-grounded reasoning, but they should be interpreted as controlled prototype evidence unless separately validated against real temporal, statistical, mobility, genomic, mechanistic, or literature-based evidence.

## 5. Generated Data

The result CSV files are generated outputs from evaluation scripts. They are not input evidence used to construct the graph.

Examples include:

- `hard_pilot_summary.csv`.
- `hard_pilot_repeated_summary.csv`.
- `hard_pilot_ablation_summary.csv`.
- `hard_pilot_ablation_repeated_summary.csv`.

These files summarize evaluation results after the methods have been run. They should be cited as experiment outputs, not as source evidence for the epidemiological graph.

## 6. Node Construction

Nodes in the current knowledge graph represent the main entities needed for failure analysis and evidence-grounded retrieval. These include:

- Diseases.
- Regions.
- Signals.
- Datasets.
- Candidate drivers.
- Mechanism equations.
- Parameters.
- Failure cases.

This node structure supports retrieval that can connect a forecast failure to a target signal, a disease and region, possible missing drivers, and the graph evidence associated with those drivers.

## 7. Edge Construction

Current edges are manually/prototypically constructed evidence relationships. They encode the controlled support structure used by the retrieval and evaluation pipeline.

In a real deployment, each edge type would require stronger evidence standards:

| Edge type | Evidence required in a real deployment |
|---|---|
| `LEADING_INDICATOR_FOR` | Temporal precedence and demonstrated predictive value for the target signal. |
| `IMPORTATION_LINK` | Travel, mobility, case-history, or genomic evidence connecting source and target contexts. |
| `POSSIBLE_DRIVER_OF` | A plausible mechanism, temporal alignment, and statistical or literature support. |

Under those standards, graph construction would become an empirical task. Candidate edges would need to be generated, tested, validated, and assigned provenance rather than manually asserted for controlled evaluation.

## 8. Circularity and Evaluation Limitation

Because the hard-pilot cases are designed around the constructed evidence graph, GraphRAG's perfect scores should be interpreted as evidence that structured retrieval preserves known graph relationships, not as proof of real-world epidemiological discovery.

This distinction is central to thesis interpretation. The current evaluation shows that GraphRAG can retrieve and preserve structured evidence more reliably than flattened or non-retrieval baselines in the controlled benchmark. It does not show that the graph itself was automatically discovered from raw epidemiological data, nor that every encoded relationship is scientifically established in the real world.

## 9. Why Controlled Prototype Data Is Still Valid

Controlled evidence relationships are still valid for this stage of the thesis because they isolate the reasoning behavior of the evaluated methods.

The comparison among LLM-only, Text-RAG, and GraphRAG depends on knowing which relationships are expected, which relationships are missing, and which candidates are weak or partially supported. A controlled graph makes it possible to test whether a method preserves those distinctions.

If the graph were automatically generated from noisy real data at this stage, graph construction errors and LLM reasoning errors would be confounded. A wrong answer could be caused by a flawed graph edge, missing source data, noisy extraction, weak retrieval, or poor reasoning. The controlled prototype avoids that confounding and makes the evaluation focus on retrieval structure and reasoning fidelity.

## 10. Scaling Path

The graph could scale to hundreds or thousands of nodes by making the temporal, spatial, observational, and provenance structure more explicit. A larger real-world graph could include:

- Week nodes.
- Region nodes.
- Signal nodes.
- Observation nodes.
- Dataset nodes.
- Evidence-test nodes.
- Provenance nodes.

For example, a single observed U.S. influenza hospitalization value could be represented as:

```text
Observation_US_Flu_2025_W06
  -> OBSERVES_SIGNAL -> US_Flu_Hospitalization
  -> IN_WEEK -> Week_2025_W06
  -> IN_REGION -> United_States
  -> FROM_DATASET -> FluSurv_NET
  value: 13.5
```

This structure would allow the graph to distinguish raw observations from derived signals, evidence tests, candidate-driver hypotheses, and provenance metadata. It would also make it easier to audit which source dataset supports each value or relationship.

## 11. Thesis-Safe Conclusion

The current thesis evaluates graph-structured retrieval for evidence-grounded reasoning behavior. It shows how a knowledge graph can help preserve candidate-specific evidence relationships during LLM-guided analysis of epidemiological forecast failures.

The current system should not be framed as a completed real-world graph construction or forecasting system. Larger-scale graph construction from real epidemiological, mobility, genomic, environmental, and literature sources, along with downstream forecasting or model-revision validation, remains future work.
