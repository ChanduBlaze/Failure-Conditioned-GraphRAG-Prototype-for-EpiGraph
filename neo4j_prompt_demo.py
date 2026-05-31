from failure_case import get_failure_case
from prompt_builder import build_failure_analysis_prompt
from neo4j_retrieval import (
    get_driver,
    retrieve_failure_candidates_from_neo4j,
    get_top_candidate_support_subgraph,
)
from neo4j_validator import validate_candidate_neo4j


def attach_top_support_subgraph(driver, candidates, failure_case):
    if not candidates:
        return candidates

    top_candidate = candidates[0]
    support_subgraph = get_top_candidate_support_subgraph(
        driver,
        top_candidate["candidate_id"],
        failure_case,
    )
    top_candidate["support_subgraph"] = support_subgraph
    return candidates


def print_prompt_header():
    print("Neo4j grounded prompt")
    print("-" * 40)


if __name__ == "__main__":
    failure_case = get_failure_case()
    driver = get_driver()

    try:
        candidates = retrieve_failure_candidates_from_neo4j(driver, failure_case)

        if not candidates:
            print("No candidates found. Prompt will not be built.")
        else:
            candidates = attach_top_support_subgraph(driver, candidates, failure_case)

            validation = validate_candidate_neo4j(driver, candidates[0])

            if not validation["passed"]:
                print("Top candidate failed validation. Prompt will not be built.")
                for reason in validation["reasons"]:
                    print(f"- {reason}")
            else:
                prompt = build_failure_analysis_prompt(failure_case, candidates)
                print_prompt_header()
                print(prompt)

    finally:
        driver.close()