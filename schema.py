NODE_TYPES = {
    "MechanismEquation",
    "StateVariable",
    "Parameter",
    "Region",
    "Disease",
    "Signal",
    "Context",
    "Dataset",
    "Paper"
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
    "POSSIBLE_DRIVER_OF"
}

if __name__ == "__main__":
    print("Allowed node types:")
    for node_type in sorted(NODE_TYPES):
        print("-", node_type)

    print("\nAllowed edge types:")
    for edge_type in sorted(EDGE_TYPES):
        print("-", edge_type)