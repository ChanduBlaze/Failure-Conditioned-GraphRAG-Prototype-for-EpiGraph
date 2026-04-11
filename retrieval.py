from seed_graph import GRAPH


def build_node_lookup(graph):
    return {node["id"]: node for node in graph["nodes"]}


def get_neighbor_edges(graph, node_id):
    return [
        edge for edge in graph["edges"]
        if edge["source"] == node_id or edge["target"] == node_id
    ]


def retrieve_local_subgraph(graph, start_node_id):
    node_lookup = build_node_lookup(graph)
    if start_node_id not in node_lookup:
        raise ValueError(f"Node '{start_node_id}' not found in graph.")

    neighbor_edges = get_neighbor_edges(graph, start_node_id)

    connected_node_ids = {start_node_id}
    for edge in neighbor_edges:
        connected_node_ids.add(edge["source"])
        connected_node_ids.add(edge["target"])

    subgraph_nodes = [node_lookup[node_id] for node_id in connected_node_ids]
    subgraph = {
        "nodes": subgraph_nodes,
        "edges": neighbor_edges
    }
    return subgraph


if __name__ == "__main__":
    subgraph = retrieve_local_subgraph(GRAPH, "eq_us_flu_base")

    print("Retrieved local subgraph successfully.")
    print(f"Number of nodes: {len(subgraph['nodes'])}")
    print(f"Number of edges: {len(subgraph['edges'])}")
    print("\nNodes:")
    for node in subgraph["nodes"]:
        print(f"- {node['id']} ({node['type']})")

    print("\nEdges:")
    for edge in subgraph["edges"]:
        print(f"- {edge['source']} --{edge['type']}--> {edge['target']}")