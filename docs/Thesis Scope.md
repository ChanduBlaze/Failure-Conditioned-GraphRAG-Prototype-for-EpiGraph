# Thesis Scope

## Working Title
Graph-Structured Retrieval for LLM-Guided Scientific Reasoning in Epidemiological Model Revision

## Main Research Question
How can graph-structured retrieval improve LLM-based scientific reasoning for discovering and explaining missing drivers in epidemiological models?

## Core Idea
A forecasting model produces a failure signal or surprisal signal. This failure becomes the trigger for a Neo4j-backed GraphRAG system, which retrieves connected scientific evidence from a knowledge graph. The LLM then uses this evidence to explain possible hidden drivers and suggest testable mechanism or model edits.

## What This Thesis Focuses On
- Neo4j knowledge graph design
- Graph population from epidemiological entities and observations
- GraphRAG retrieval of support subgraphs
- LLM reasoning over retrieved graph evidence
- Comparison against LLM-only and text-based RAG baselines
- Ablation study to test which graph components matter

## What This Thesis Does Not Try to Fully Build
- A complete EpiGraph system
- A full production forecasting engine
- Full literature-to-KG ingestion
- Full symbolic regression or MCTS equation discovery
- Full causal discovery

## Current Prototype Example
The prototype starts from a U.S. influenza forecast failure. The Neo4j graph retrieves Chile influenza activity as a plausible hidden driver because it has:
- LEADING_INDICATOR_FOR → US hospitalizations
- IMPORTATION_LINK → US flu mechanism
- POSSIBLE_DRIVER_OF → US flu mechanism

The LLM then proposes a testable edit: add a lagged Chile importation signal to the model.

## Immediate Next Goal
Turn the prototype from a demo into an evaluable study by creating evaluation cases and comparing:
1. LLM-only
2. Text-based RAG
3. KG-only retrieval
4. Neo4j-backed GraphRAG + LLM