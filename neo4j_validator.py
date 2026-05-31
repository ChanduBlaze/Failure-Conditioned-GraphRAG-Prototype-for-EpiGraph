from neo4j import GraphDatabase
from failure_case import get_failure_case
from neo4j_retrieval import (
    get_driver,
    retrieve_failure_candidates_from_neo4j,
    NEO4J_DATABASE,
)

MIN_SCORE_THRESHOLD = 4
MIN_SUPPORT_EDGE_COUNT = 2
MIN_DATASET_LINK_COUNT = 1
MIN_PROVENANCE_LINK_COUNT = 1


def count_candidate_links(tx, candidate_id):
    query = """
    MATCH (candidate:Signal {id: $candidate_id})
    OPTIONAL MATCH (candidate)-[:HAS_DATASET]->(d:Dataset)
    WITH candidate, count(DISTINCT d) AS dataset_count
    OPTIONAL MATCH (candidate)-[:SUPPORTED_BY]->(p:Paper)
    RETURN dataset_count, count(DISTINCT p) AS provenance_count
    """
    record = tx.run(query, candidate_id=candidate_id).single()
    return {
        "dataset_count": record["dataset_count"],
        "provenance_count": record["provenance_count"],
    }


def validate_candidate_neo4j(driver, candidate):
    support_edge_count = len(candidate["support_subgraph"]["edges"])

    with driver.session(database=NEO4J_DATABASE) as session:
        counts = session.execute_read(
            count_candidate_links,
            candidate["candidate_id"],
        )

    passed = True
    reasons = []

    if candidate["score"] < MIN_SCORE_THRESHOLD:
        passed = False
        reasons.append(
            f"score {candidate['score']} below threshold {MIN_SCORE_THRESHOLD}"
        )

    if support_edge_count < MIN_SUPPORT_EDGE_COUNT:
        passed = False
        reasons.append(
            f"support edge count {support_edge_count} below threshold {MIN_SUPPORT_EDGE_COUNT}"
        )

    if counts["dataset_count"] < MIN_DATASET_LINK_COUNT:
        passed = False
        reasons.append(
            f"dataset link count {counts['dataset_count']} below threshold {MIN_DATASET_LINK_COUNT}"
        )

    if counts["provenance_count"] < MIN_PROVENANCE_LINK_COUNT:
        passed = False
        reasons.append(
            f"provenance link count {counts['provenance_count']} below threshold {MIN_PROVENANCE_LINK_COUNT}"
        )

    return {
        "passed": passed,
        "reasons": reasons,
        "score": candidate["score"],
        "support_edge_count": support_edge_count,
        "dataset_count": counts["dataset_count"],
        "provenance_count": counts["provenance_count"],
    }


if __name__ == "__main__":
    from neo4j_retrieval import get_top_candidate_support_subgraph

    failure_case = get_failure_case()
    driver = get_driver()

    try:
        candidates = retrieve_failure_candidates_from_neo4j(driver, failure_case)

        if not candidates:
            print("No candidates found.")
        else:
            top_candidate = candidates[0]
            support_subgraph = get_top_candidate_support_subgraph(
                driver,
                top_candidate["candidate_id"],
                failure_case,
            )
            top_candidate["support_subgraph"] = support_subgraph

            result = validate_candidate_neo4j(driver, top_candidate)

            print("Neo4j candidate validation")
            print("-" * 40)
            print(f"candidate_id: {top_candidate['candidate_id']}")
            print(f"candidate_name: {top_candidate['candidate_name']}")
            print(f"passed: {result['passed']}")
            print(f"score: {result['score']}")
            print(f"support_edge_count: {result['support_edge_count']}")
            print(f"dataset_count: {result['dataset_count']}")
            print(f"provenance_count: {result['provenance_count']}")

            if result["reasons"]:
                print("reasons:")
                for reason in result["reasons"]:
                    print(f"- {reason}")
    finally:
        driver.close()