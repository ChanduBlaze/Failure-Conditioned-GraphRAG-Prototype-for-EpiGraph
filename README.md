# KG-LLM GraphRAG

A knowledge graph + LLM prototype for **traceable reasoning over structured evidence**.  
This project uses a graph-based retrieval pipeline to connect entities, relationships, and supporting evidence, then uses an LLM to generate grounded reasoning over the retrieved subgraph.

## Overview

KG-LLM GraphRAG is designed to move beyond standard text-only retrieval by combining:

- **Knowledge Graphs** for structured relationships
- **Graph Retrieval** for focused evidence selection
- **LLMs** for explanation, ranking, and reasoning

The goal is to support more interpretable and evidence-aware reasoning by retrieving relevant nodes and edges from a graph, then asking the LLM to reason only over that grounded context.

## Motivation

Traditional RAG systems retrieve text chunks, but they often miss important multi-hop relationships between entities.  
This project explores a **GraphRAG-style workflow** where:

1. relevant entities and signals are represented in a graph,
2. connected evidence is retrieved through graph structure,
3. the LLM reasons over the retrieved subgraph,
4. outputs remain more traceable and explainable.

This is especially useful for workflows where relationships, causality, or signal dependencies matter.

## Features

- Graph-based retrieval over connected entities
- Evidence-aware candidate ranking
- LLM-generated reasoning over retrieved subgraphs
- More interpretable outputs than standard flat retrieval
- Neo4j-compatible workflow for graph storage and querying
- Prototype scripts for experimentation and reasoning

## Project Structure

```text
KG-LLM GraphRAG/
│
├── llm_reasoner.py          # LLM-based reasoning over retrieved graph evidence
├── README.md                # Project documentation
├── requirements.txt         # Python dependencies
├── data/                    # Input files / graph data / exports
├── notebooks/               # Exploration and prototype notebooks
├── scripts/                 # Utility scripts for graph building or retrieval
└── outputs/                 # Generated reasoning outputs / logs
