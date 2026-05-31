NODE_TYPES = {
    "MechanismEquation",
    "StateVariable",
    "Parameter",
    "Region",
    "Disease",
    "Signal",
    "Context",
    "Dataset",
    "Paper",
}

EDGE_TYPES = {
    "MODELS",
    "APPLIES_TO",
    "USES_VARIABLE",
    "USES_PARAMETER",
    "HAS_CONTEXT",
    "SUPPORTED_BY",
    "HAS_DATASET",
    "IMPORTATION_LINK",
    "LEADING_INDICATOR_FOR",
    "POSSIBLE_DRIVER_OF",
}

# Minimal expected properties by node type
REQUIRED_NODE_FIELDS = {
    "MechanismEquation": {"id", "type", "name"},
    "StateVariable": {"id", "type", "name"},
    "Parameter": {"id", "type", "name"},
    "Region": {"id", "type", "name"},
    "Disease": {"id", "type", "name"},
    "Signal": {"id", "type", "name"},
    "Context": {"id", "type", "name"},
    "Dataset": {"id", "type", "name"},
    "Paper": {"id", "type", "name"},
}

# Minimal expected properties for edges
REQUIRED_EDGE_FIELDS = {"source", "target", "type"}


def is_valid_node_type(node_type: str) -> bool:
    return node_type in NODE_TYPES


def is_valid_edge_type(edge_type: str) -> bool:
    return edge_type in EDGE_TYPES


def validate_node(node: dict) -> None:
    node_type = node.get("type")
    if not node_type:
        raise ValueError(f"Node missing 'type': {node}")

    if not is_valid_node_type(node_type):
        raise ValueError(f"Invalid node type '{node_type}' for node: {node}")

    missing = REQUIRED_NODE_FIELDS[node_type] - set(node.keys())
    if missing:
        raise ValueError(
            f"Node '{node.get('id', '<missing id>')}' is missing required fields: {sorted(missing)}"
        )


def validate_edge(edge: dict) -> None:
    edge_type = edge.get("type")
    if not edge_type:
        raise ValueError(f"Edge missing 'type': {edge}")

    if not is_valid_edge_type(edge_type):
        raise ValueError(f"Invalid edge type '{edge_type}' for edge: {edge}")

    missing = REQUIRED_EDGE_FIELDS - set(edge.keys())
    if missing:
        raise ValueError(f"Edge is missing required fields: {sorted(missing)} | edge={edge}")


def get_neo4j_label(node: dict) -> str:
    """
    In this prototype, the in-memory node type maps directly to the Neo4j label.
    Example: {"type": "Signal", ...} -> (:Signal {...})
    """
    validate_node(node)
    return node["type"]


def get_neo4j_relationship_type(edge: dict) -> str:
    """
    In this prototype, the in-memory edge type maps directly to the Neo4j relationship type.
    Example: {"type": "LEADING_INDICATOR_FOR", ...} -> [:LEADING_INDICATOR_FOR]
    """
    validate_edge(edge)
    return edge["type"]


def validate_graph_schema(graph: dict) -> None:
    for node in graph.get("nodes", []):
        validate_node(node)

    for edge in graph.get("edges", []):
        validate_edge(edge)


if __name__ == "__main__":
    print("Allowed node types:")
    for node_type in sorted(NODE_TYPES):
        print("-", node_type)

    print("\nAllowed edge types:")
    for edge_type in sorted(EDGE_TYPES):
        print("-", edge_type)