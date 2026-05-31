def build_node_lookup(graph):
    return {node["id"]: node for node in graph.get("nodes", [])}


def get_node_by_id(graph, node_id):
    node_lookup = build_node_lookup(graph)
    return node_lookup.get(node_id)


def get_neighbor_edges(graph, node_id):
    return [
        edge
        for edge in graph.get("edges", [])
        if edge["source"] == node_id or edge["target"] == node_id
    ]


def get_outgoing_edges(graph, node_id):
    return [
        edge
        for edge in graph.get("edges", [])
        if edge["source"] == node_id
    ]


def get_incoming_edges(graph, node_id):
    return [
        edge
        for edge in graph.get("edges", [])
        if edge["target"] == node_id
    ]


def retrieve_local_subgraph(graph, start_node_id):
    node_lookup = build_node_lookup(graph)

    if start_node_id not in node_lookup:
        raise ValueError(f"Unknown start node id: {start_node_id}")

    neighbor_edges = get_neighbor_edges(graph, start_node_id)

    connected_node_ids = {start_node_id}
    for edge in neighbor_edges:
        connected_node_ids.add(edge["source"])
        connected_node_ids.add(edge["target"])

    subgraph_nodes = [
        node_lookup[node_id]
        for node_id in connected_node_ids
        if node_id in node_lookup
    ]

    return {
        "nodes": subgraph_nodes,
        "edges": neighbor_edges,
    }


def print_subgraph(subgraph):
    print("Subgraph Nodes")
    print("-" * 40)
    for node in subgraph.get("nodes", []):
        print(f"- {node['id']} ({node['type']})")

    print("\nSubgraph Edges")
    print("-" * 40)
    for edge in subgraph.get("edges", []):
        print(f"- {edge['source']} --{edge['type']}--> {edge['target']}")

if __name__ == "__main__":
    from seed_graph import GRAPH

    subgraph = retrieve_local_subgraph(GRAPH, "signal_chile_flu")
    print_subgraph(subgraph)