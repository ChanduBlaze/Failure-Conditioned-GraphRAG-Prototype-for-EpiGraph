# Real-Data KG Pipeline Scripts

This folder will contain the isolated real-data knowledge graph pipeline scripts. These scripts must not modify the simulated benchmark or its cases, corpus, loaders, prompts, evaluations, or results.

Scripts in this folder must not call `neo4j_loader.clear_graph()`. Any future Neo4j loading must be additive and must preserve the controlled simulated benchmark.

Planned scripts:

- `download_real_data.py`
- `normalize_real_signals.py`
- `build_real_evidence_claims.py`
- `load_real_kg_to_neo4j.py`
- `build_real_text_corpus.py`
- `run_real_eval.py`

The first executable script should be `build_real_evidence_claims.py`. It should operate on normalized inputs or intentionally small fixtures and generate the canonical evidence-claim artifact without connecting to Neo4j or making LLM calls.
