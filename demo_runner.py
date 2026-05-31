import argparse

from llm_reasoner import generate_llm_analysis
from neo4j_llm_reasoner import generate_neo4j_llm_analysis


def run_demo(mode: str):
    print("KG-LLM / GraphRAG Demo Runner")
    print("-" * 40)
    print(f"Mode: {mode}")

    if mode == "in_memory":
        return generate_llm_analysis()

    if mode == "neo4j":
        return generate_neo4j_llm_analysis()

    raise ValueError(f"Unknown mode: {mode}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Run the EpiGraph failure-conditioned GraphRAG demo."
    )
    parser.add_argument(
        "--mode",
        choices=["in_memory", "neo4j"],
        default="neo4j",
        help="Choose which backend to run.",
    )

    args = parser.parse_args()
    run_demo(args.mode)