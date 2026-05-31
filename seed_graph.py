from schema import validate_graph_schema

GRAPH = {
    "nodes": [
        {"id": "disease_influenza", "type": "Disease", "name": "Influenza"},
        {"id": "region_us", "type": "Region", "name": "United States"},
        {"id": "region_chile", "type": "Region", "name": "Chile"},

        {"id": "eq_us_flu_base", "type": "MechanismEquation", "name": "US Influenza Base Mechanism"},

        {"id": "state_i_us", "type": "StateVariable", "name": "Infectious Population in US"},
        {"id": "param_beta_us", "type": "Parameter", "name": "US Transmission Rate"},

        {"id": "signal_us_hosp", "type": "Signal", "name": "US Influenza Hospitalizations"},
        {"id": "signal_chile_flu", "type": "Signal", "name": "Chile Influenza Activity"},

        {"id": "context_sh_lead", "type": "Context", "name": "Southern Hemisphere Lead Signal"},
        {"id": "dataset_us_flu", "type": "Dataset", "name": "US Flu Dataset"},
        {"id": "dataset_chile_flu", "type": "Dataset", "name": "Chile Flu Dataset"},
        {"id": "paper_importation", "type": "Paper", "name": "Paper on Importation and Influenza Spread"},

        {"id": "region_australia", "type": "Region", "name": "Australia"},

        {"id": "signal_australia_flu", "type": "Signal", "name": "Australia Influenza Activity"},
        {"id": "signal_travel_pressure", "type": "Signal", "name": "Travel Importation Pressure"},
        {"id": "signal_humidity_drop", "type": "Signal", "name": "Humidity Drop Anomaly"},

        {"id": "context_travel_importation", "type": "Context", "name": "Travel-Driven Importation Pressure"},
        {"id": "context_climate_forcing", "type": "Context", "name": "Climate Forcing"},

        {"id": "dataset_australia_flu", "type": "Dataset", "name": "Australia Flu Dataset"},
        {"id": "dataset_travel_pressure", "type": "Dataset", "name": "Travel Pressure Dataset"},
        {"id": "dataset_humidity", "type": "Dataset", "name": "Humidity Dataset"},

        {"id": "paper_climate", "type": "Paper", "name": "Paper on Climate and Influenza Dynamics"},
    ],
    "edges": [
        {"source": "eq_us_flu_base", "type": "MODELS", "target": "disease_influenza"},
        {"source": "eq_us_flu_base", "type": "APPLIES_TO", "target": "region_us"},
        {"source": "eq_us_flu_base", "type": "USES_VARIABLE", "target": "state_i_us"},
        {"source": "eq_us_flu_base", "type": "USES_PARAMETER", "target": "param_beta_us"},

        {"source": "signal_us_hosp", "type": "APPLIES_TO", "target": "region_us"},
        {"source": "signal_us_hosp", "type": "MODELS", "target": "disease_influenza"},
        {"source": "signal_us_hosp", "type": "HAS_DATASET", "target": "dataset_us_flu"},

        {"source": "signal_chile_flu", "type": "APPLIES_TO", "target": "region_chile"},
        {"source": "signal_chile_flu", "type": "MODELS", "target": "disease_influenza"},
        {"source": "signal_chile_flu", "type": "HAS_CONTEXT", "target": "context_sh_lead"},
        {"source": "signal_chile_flu", "type": "HAS_DATASET", "target": "dataset_chile_flu"},
        {"source": "signal_chile_flu", "type": "SUPPORTED_BY", "target": "paper_importation"},

        {"source": "signal_chile_flu", "type": "LEADING_INDICATOR_FOR", "target": "signal_us_hosp"},
        {"source": "signal_chile_flu", "type": "IMPORTATION_LINK", "target": "eq_us_flu_base"},
        {"source": "signal_chile_flu", "type": "POSSIBLE_DRIVER_OF", "target": "eq_us_flu_base"},

        {"source": "signal_australia_flu", "type": "APPLIES_TO", "target": "region_australia"},
        {"source": "signal_australia_flu", "type": "MODELS", "target": "disease_influenza"},
        {"source": "signal_australia_flu", "type": "HAS_CONTEXT", "target": "context_sh_lead"},
        {"source": "signal_australia_flu", "type": "HAS_DATASET", "target": "dataset_australia_flu"},
        {"source": "signal_australia_flu", "type": "SUPPORTED_BY", "target": "paper_importation"},
        {"source": "signal_australia_flu", "type": "LEADING_INDICATOR_FOR", "target": "signal_us_hosp"},
        {"source": "signal_australia_flu", "type": "POSSIBLE_DRIVER_OF", "target": "eq_us_flu_base"},

        {"source": "signal_travel_pressure", "type": "APPLIES_TO", "target": "region_us"},
        {"source": "signal_travel_pressure", "type": "MODELS", "target": "disease_influenza"},
        {"source": "signal_travel_pressure", "type": "HAS_CONTEXT", "target": "context_travel_importation"},
        {"source": "signal_travel_pressure", "type": "HAS_DATASET", "target": "dataset_travel_pressure"},
        {"source": "signal_travel_pressure", "type": "SUPPORTED_BY", "target": "paper_importation"},
        {"source": "signal_travel_pressure", "type": "IMPORTATION_LINK", "target": "eq_us_flu_base"},
        {"source": "signal_travel_pressure", "type": "POSSIBLE_DRIVER_OF", "target": "eq_us_flu_base"},

        {"source": "signal_humidity_drop", "type": "APPLIES_TO", "target": "region_us"},
        {"source": "signal_humidity_drop", "type": "MODELS", "target": "disease_influenza"},
        {"source": "signal_humidity_drop", "type": "HAS_CONTEXT", "target": "context_climate_forcing"},
        {"source": "signal_humidity_drop", "type": "HAS_DATASET", "target": "dataset_humidity"},
        {"source": "signal_humidity_drop", "type": "SUPPORTED_BY", "target": "paper_climate"},
        {"source": "signal_humidity_drop", "type": "POSSIBLE_DRIVER_OF", "target": "eq_us_flu_base"},
    ]
}
def build_graph_summary(graph):
    return {
        "node_count": len(graph.get("nodes", [])),
        "edge_count": len(graph.get("edges", [])),
        "node_types": sorted({node["type"] for node in graph.get("nodes", [])}),
        "edge_types": sorted({edge["type"] for edge in graph.get("edges", [])}),
    }


def print_graph_summary(graph):
    summary = build_graph_summary(graph)
    print("Graph Summary")
    print("-" * 40)
    print("Nodes:", summary["node_count"])
    print("Edges:", summary["edge_count"])
    print("Node types:", ", ".join(summary["node_types"]))
    print("Edge types:", ", ".join(summary["edge_types"]))

def validate_graph(graph):
    for node in graph["nodes"]:
        if node["type"] not in NODE_TYPES:
            raise ValueError(f"Invalid node type: {node['type']} for node {node['id']}")

    for edge in graph["edges"]:
        if edge["type"] not in EDGE_TYPES:
            raise ValueError(
                f"Invalid edge type: {edge['type']} from {edge['source']} to {edge['target']}"
            )

    return True


if __name__ == "__main__":
    validate_graph_schema(GRAPH)
    print("Graph schema is valid.\n")
    print_graph_summary(GRAPH)