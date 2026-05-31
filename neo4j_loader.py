from neo4j import GraphDatabase
from seed_graph import GRAPH

NEO4J_URI = "neo4j://127.0.0.1:7687"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "chandu99999"


def get_driver():
    return GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
    )


def clear_graph(driver):
    with driver.session(database="neo4j") as session:
        session.run("MATCH (n) DETACH DELETE n")


def create_node(tx, node):
    node_id = node["id"]
    label = node["type"]
    properties = {k: v for k, v in node.items() if k != "type"}

    query = f"""
    MERGE (n:{label} {{id: $id}})
    SET n += $properties
    """
    tx.run(query, id=node_id, properties=properties)


def create_edge(tx, edge):
    source_id = edge["source"]
    target_id = edge["target"]
    rel_type = edge["type"]

    query = f"""
    MATCH (a {{id: $source_id}})
    MATCH (b {{id: $target_id}})
    MERGE (a)-[r:{rel_type}]->(b)
    """
    tx.run(query, source_id=source_id, target_id=target_id)


def load_graph(driver, graph):
    with driver.session(database="neo4j") as session:
        for node in graph["nodes"]:
            session.execute_write(create_node, node)

        for edge in graph["edges"]:
            session.execute_write(create_edge, edge)


def print_db_summary(driver):
    with driver.session(database="neo4j") as session:
        node_count = session.run(
            "MATCH (n) RETURN count(n) AS count"
        ).single()["count"]
        edge_count = session.run(
            "MATCH ()-[r]->() RETURN count(r) AS count"
        ).single()["count"]

        print("Neo4j Graph Load Complete")
        print("-" * 40)
        print(f"Nodes: {node_count}")
        print(f"Edges: {edge_count}")


if __name__ == "__main__":
    driver = get_driver()

    try:
        clear_graph(driver)
        load_graph(driver, GRAPH)
        print_db_summary(driver)
    finally:
        driver.close()