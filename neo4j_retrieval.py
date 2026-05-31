from neo4j import GraphDatabase
from failure_case import get_failure_case

NEO4J_URI = "bolt://127.0.0.1:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "chandu99999"
NEO4J_DATABASE = "neo4j"


def get_driver():
    return GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
    )


def run_candidate_ranking(tx, mechanism_id, target_signal):
    query = """
    MATCH (candidate:Signal)
    WITH candidate,
      CASE
        WHEN EXISTS {
          MATCH (candidate)-[:POSSIBLE_DRIVER_OF]->(:MechanismEquation {id: $mechanism_id})
        } THEN 2 ELSE 0
      END AS possible_score,
      CASE
        WHEN EXISTS {
          MATCH (candidate)-[:IMPORTATION_LINK]->(:MechanismEquation {id: $mechanism_id})
        } THEN 2 ELSE 0
      END AS import_score,
      CASE
        WHEN EXISTS {
          MATCH (candidate)-[:LEADING_INDICATOR_FOR]->(:Signal {id: $target_signal})
        } THEN 3 ELSE 0
      END AS lead_score

    WITH
      candidate,
      possible_score + import_score + lead_score AS score,
      [item IN [
        CASE WHEN possible_score > 0 THEN "POSSIBLE_DRIVER_OF -> mechanism (+2)" END,
        CASE WHEN import_score > 0 THEN "IMPORTATION_LINK -> mechanism (+2)" END,
        CASE WHEN lead_score > 0 THEN "LEADING_INDICATOR_FOR -> target signal (+3)" END
      ] WHERE item IS NOT NULL] AS evidence

    WHERE score > 0
    RETURN
      candidate.id AS candidate_id,
      candidate.name AS candidate_name,
      score,
      evidence
    ORDER BY score DESC, candidate_id
    """

    result = tx.run(
        query,
        mechanism_id=mechanism_id,
        target_signal=target_signal,
    )

    return [record.data() for record in result]


def run_support_subgraph_query(tx, candidate_id, mechanism_id, target_signal):
    query = """
    MATCH (candidate:Signal {id: $candidate_id})
    MATCH (mechanism:MechanismEquation {id: $mechanism_id})
    MATCH (target:Signal {id: $target_signal})

    OPTIONAL MATCH (candidate)-[r1:LEADING_INDICATOR_FOR]->(target)
    OPTIONAL MATCH (candidate)-[r2:IMPORTATION_LINK]->(mechanism)
    OPTIONAL MATCH (candidate)-[r3:POSSIBLE_DRIVER_OF]->(mechanism)

    RETURN
      candidate { .id, .name } AS candidate,
      mechanism { .id, .name } AS mechanism,
      target { .id, .name } AS target,
      CASE
        WHEN r1 IS NULL THEN NULL
        ELSE {
          source: candidate.id,
          type: type(r1),
          target: target.id
        }
      END AS edge1,
      CASE
        WHEN r2 IS NULL THEN NULL
        ELSE {
          source: candidate.id,
          type: type(r2),
          target: mechanism.id
        }
      END AS edge2,
      CASE
        WHEN r3 IS NULL THEN NULL
        ELSE {
          source: candidate.id,
          type: type(r3),
          target: mechanism.id
        }
      END AS edge3
    """

    record = tx.run(
        query,
        candidate_id=candidate_id,
        mechanism_id=mechanism_id,
        target_signal=target_signal,
    ).single()

    if not record:
        return None

    nodes = [
        {"id": record["candidate"]["id"], "type": "Signal", "name": record["candidate"]["name"]},
        {"id": record["mechanism"]["id"], "type": "MechanismEquation", "name": record["mechanism"]["name"]},
        {"id": record["target"]["id"], "type": "Signal", "name": record["target"]["name"]},
    ]

    edges = [edge for edge in [record["edge1"], record["edge2"], record["edge3"]] if edge is not None]

    return {
        "nodes": nodes,
        "edges": edges,
    }


def retrieve_failure_candidates_from_neo4j(driver, failure_case):
    with driver.session(database=NEO4J_DATABASE) as session:
        return session.execute_read(
            run_candidate_ranking,
            failure_case["mechanism_id"],
            failure_case["target_signal"],
        )


def get_top_candidate_support_subgraph(driver, candidate_id, failure_case):
    with driver.session(database=NEO4J_DATABASE) as session:
        return session.execute_read(
            run_support_subgraph_query,
            candidate_id,
            failure_case["mechanism_id"],
            failure_case["target_signal"],
        )


def print_ranked_candidates(candidates):
    print("Neo4j failure-conditioned retrieval complete.")
    print(f"Number of candidates found: {len(candidates)}")

    print("\nRanked candidates:")
    for candidate in candidates:
        print(
            f"- {candidate['candidate_id']} | "
            f"{candidate['candidate_name']} | "
            f"score={candidate['score']}"
        )
        for item in candidate["evidence"]:
            print(f"    evidence: {item}")


def print_support_subgraph(candidate, support_subgraph):
    print("\nTop candidate support subgraph:")
    print(f"Candidate: {candidate['candidate_name']}")

    print("\n  Nodes:")
    for node in support_subgraph["nodes"]:
        print(f"  - {node['id']} ({node['type']})")

    print("\n  Edges:")
    for edge in support_subgraph["edges"]:
        print(f"  - {edge['source']} --{edge['type']}--> {edge['target']}")


if __name__ == "__main__":
    failure_case = get_failure_case()
    driver = get_driver()

    try:
        candidates = retrieve_failure_candidates_from_neo4j(driver, failure_case)
        print_ranked_candidates(candidates)

        if candidates:
            top_candidate = candidates[0]
            support_subgraph = get_top_candidate_support_subgraph(
                driver,
                top_candidate["candidate_id"],
                failure_case,
            )
            print_support_subgraph(top_candidate, support_subgraph)
    finally:
        driver.close()