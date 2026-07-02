# Adversarial Evidence-Binding Evaluation

This evaluation tests whether a method preserves candidate-specific evidence
bindings under overloaded retrieval context.

It is designed to stress these failure modes:

1. Score-to-candidate binding.
2. Lag-to-candidate binding.
3. EvidenceClaim versus promoted typed edge.
4. Missing negative-control preservation.
5. Pipeline isolation from controlled-fixture distractors.
6. Model-revision recommendations without causal overclaiming.

This is not an independent outbreak evaluation. It is an adversarial
evidence-preservation benchmark derived from the empirical influenza KG claims.

The expected thesis interpretation is conditional: GraphRAG should only be
claimed better than Text-RAG if it preserves these bindings more reliably under
the adversarial text condition.
