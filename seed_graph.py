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

        # Prototype dengue scenario for multi-failure-case evaluation. These
        # edges reuse the hard-pilot relationship types for metric compatibility,
        # not as a final scientific claim about dengue causality.
        {"id": "disease_dengue", "type": "Disease", "name": "Dengue"},
        {"id": "region_puerto_rico", "type": "Region", "name": "Puerto Rico"},
        {"id": "eq_dengue_base", "type": "MechanismEquation", "name": "Puerto Rico Dengue Base Mechanism"},
        {"id": "state_i_pr_dengue", "type": "StateVariable", "name": "Infectious Dengue Population in Puerto Rico"},
        {"id": "param_beta_pr_dengue", "type": "Parameter", "name": "Puerto Rico Dengue Transmission Rate"},
        {"id": "signal_pr_dengue_cases", "type": "Signal", "name": "Puerto Rico Dengue Cases"},
        {"id": "signal_rainfall_anomaly", "type": "Signal", "name": "Rainfall Anomaly"},
        {"id": "signal_temperature_anomaly", "type": "Signal", "name": "Temperature Anomaly"},
        {"id": "signal_vector_index", "type": "Signal", "name": "Mosquito Vector Index"},
        {"id": "signal_travel_importation_dengue", "type": "Signal", "name": "Dengue Travel Importation Pressure"},
        {"id": "context_vector_surveillance", "type": "Context", "name": "Vector Surveillance"},
        {"id": "context_dengue_climate", "type": "Context", "name": "Dengue Climate Forcing"},
        {"id": "context_dengue_importation", "type": "Context", "name": "Dengue Importation Pressure"},
        {"id": "dataset_pr_dengue_cases", "type": "Dataset", "name": "Puerto Rico Dengue Cases Dataset"},
        {"id": "dataset_rainfall_anomaly", "type": "Dataset", "name": "Rainfall Anomaly Dataset"},
        {"id": "dataset_temperature_anomaly", "type": "Dataset", "name": "Temperature Anomaly Dataset"},
        {"id": "dataset_vector_index", "type": "Dataset", "name": "Mosquito Vector Index Dataset"},
        {"id": "dataset_dengue_travel_importation", "type": "Dataset", "name": "Dengue Travel Importation Dataset"},
        {"id": "paper_vector_surveillance", "type": "Paper", "name": "Paper on Vector Surveillance and Dengue Risk"},
        {"id": "paper_dengue_climate", "type": "Paper", "name": "Paper on Climate and Dengue Dynamics"},
        {"id": "paper_dengue_importation", "type": "Paper", "name": "Paper on Dengue Importation Pressure"},

        # Prototype RSV scenario for additional multi-failure-case evaluation.
        # These edges reuse the same hard-pilot relationship types for metric
        # compatibility, not as a final scientific claim about RSV causality.
        {"id": "disease_rsv", "type": "Disease", "name": "Respiratory Syncytial Virus"},
        {"id": "region_southeast_us", "type": "Region", "name": "Southeast United States"},
        {"id": "region_rsv_surveillance_network", "type": "Region", "name": "Regional RSV Surveillance Network"},
        {"id": "eq_rsv_pediatric_base", "type": "MechanismEquation", "name": "Southeast US Pediatric RSV Base Mechanism"},
        {"id": "state_i_rsv_peds", "type": "StateVariable", "name": "Infectious Pediatric RSV Population"},
        {"id": "param_beta_rsv_peds", "type": "Parameter", "name": "Pediatric RSV Transmission Rate"},
        {"id": "signal_rsv_pediatric_hosp", "type": "Signal", "name": "Pediatric RSV Hospitalizations"},
        {"id": "signal_regional_rsv_early", "type": "Signal", "name": "Regional RSV Early Signal"},
        {"id": "signal_school_reopening_pressure", "type": "Signal", "name": "School Reopening Contact Pressure"},
        {"id": "signal_mobility_pressure_rsv", "type": "Signal", "name": "RSV Mobility Pressure"},
        {"id": "signal_cold_weather_anomaly_rsv", "type": "Signal", "name": "Cold Weather Anomaly"},
        {"id": "context_rsv_surveillance", "type": "Context", "name": "RSV Surveillance Lead Signal"},
        {"id": "context_school_contact", "type": "Context", "name": "School Contact Pattern Shift"},
        {"id": "context_rsv_mobility", "type": "Context", "name": "Respiratory Virus Mobility Pressure"},
        {"id": "context_rsv_climate", "type": "Context", "name": "RSV Weather Forcing"},
        {"id": "dataset_rsv_pediatric_hosp", "type": "Dataset", "name": "Pediatric RSV Hospitalization Dataset"},
        {"id": "dataset_regional_rsv_early", "type": "Dataset", "name": "Regional RSV Early Signal Dataset"},
        {"id": "dataset_school_reopening", "type": "Dataset", "name": "School Reopening Contact Dataset"},
        {"id": "dataset_mobility_pressure_rsv", "type": "Dataset", "name": "RSV Mobility Pressure Dataset"},
        {"id": "dataset_cold_weather_rsv", "type": "Dataset", "name": "Cold Weather RSV Dataset"},
        {"id": "paper_rsv_surveillance", "type": "Paper", "name": "Paper on RSV Surveillance and Pediatric Hospitalization Risk"},
        {"id": "paper_school_contact", "type": "Paper", "name": "Paper on School Contacts and Respiratory Virus Spread"},
        {"id": "paper_respiratory_mobility", "type": "Paper", "name": "Paper on Mobility and Respiratory Virus Importation"},
        {"id": "paper_rsv_weather", "type": "Paper", "name": "Paper on Weather and RSV Transmission"},

        # Prototype COVID scenario for additional multi-failure-case evaluation.
        # These edges reuse the same hard-pilot relationship types for metric
        # compatibility, not as a final scientific claim about COVID causality.
        {"id": "disease_covid19", "type": "Disease", "name": "COVID-19"},
        {"id": "region_northeast_us", "type": "Region", "name": "Northeast United States"},
        {"id": "region_variant_surveillance_network", "type": "Region", "name": "Variant Surveillance Network"},
        {"id": "eq_covid_hosp_base", "type": "MechanismEquation", "name": "Northeast US COVID Hospitalization Base Mechanism"},
        {"id": "state_i_covid", "type": "StateVariable", "name": "Infectious COVID Population"},
        {"id": "param_beta_covid", "type": "Parameter", "name": "COVID Transmission Rate"},
        {"id": "signal_covid_hosp", "type": "Signal", "name": "COVID Hospitalizations"},
        {"id": "signal_variant_growth_covid", "type": "Signal", "name": "COVID Variant Growth Signal"},
        {"id": "signal_wastewater_surge_covid", "type": "Signal", "name": "Wastewater Viral Load Surge"},
        {"id": "signal_mobility_rebound_covid", "type": "Signal", "name": "COVID Mobility Rebound Pressure"},
        {"id": "signal_immunity_waning_covid", "type": "Signal", "name": "Immunity Waning Gap"},
        {"id": "context_variant_growth", "type": "Context", "name": "Variant Growth and Replacement"},
        {"id": "context_wastewater_surveillance", "type": "Context", "name": "Wastewater Surveillance"},
        {"id": "context_covid_mobility", "type": "Context", "name": "COVID Mobility Rebound"},
        {"id": "context_immunity_waning", "type": "Context", "name": "Population Immunity Waning"},
        {"id": "dataset_covid_hosp", "type": "Dataset", "name": "COVID Hospitalization Dataset"},
        {"id": "dataset_variant_growth_covid", "type": "Dataset", "name": "COVID Variant Growth Dataset"},
        {"id": "dataset_wastewater_covid", "type": "Dataset", "name": "COVID Wastewater Viral Load Dataset"},
        {"id": "dataset_mobility_rebound_covid", "type": "Dataset", "name": "COVID Mobility Rebound Dataset"},
        {"id": "dataset_immunity_waning_covid", "type": "Dataset", "name": "COVID Immunity Waning Dataset"},
        {"id": "paper_covid_variant_growth", "type": "Paper", "name": "Paper on Variant Growth and Hospitalization Rebounds"},
        {"id": "paper_covid_wastewater", "type": "Paper", "name": "Paper on Wastewater Surveillance and COVID Hospitalizations"},
        {"id": "paper_covid_mobility", "type": "Paper", "name": "Paper on Mobility and COVID Transmission"},
        {"id": "paper_covid_immunity", "type": "Paper", "name": "Paper on Waning Immunity and COVID Rebounds"},
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

        {"source": "eq_dengue_base", "type": "MODELS", "target": "disease_dengue"},
        {"source": "eq_dengue_base", "type": "APPLIES_TO", "target": "region_puerto_rico"},
        {"source": "eq_dengue_base", "type": "USES_VARIABLE", "target": "state_i_pr_dengue"},
        {"source": "eq_dengue_base", "type": "USES_PARAMETER", "target": "param_beta_pr_dengue"},

        {"source": "signal_pr_dengue_cases", "type": "APPLIES_TO", "target": "region_puerto_rico"},
        {"source": "signal_pr_dengue_cases", "type": "MODELS", "target": "disease_dengue"},
        {"source": "signal_pr_dengue_cases", "type": "HAS_DATASET", "target": "dataset_pr_dengue_cases"},

        {"source": "signal_vector_index", "type": "APPLIES_TO", "target": "region_puerto_rico"},
        {"source": "signal_vector_index", "type": "MODELS", "target": "disease_dengue"},
        {"source": "signal_vector_index", "type": "HAS_CONTEXT", "target": "context_vector_surveillance"},
        {"source": "signal_vector_index", "type": "HAS_DATASET", "target": "dataset_vector_index"},
        {"source": "signal_vector_index", "type": "SUPPORTED_BY", "target": "paper_vector_surveillance"},
        {"source": "signal_vector_index", "type": "LEADING_INDICATOR_FOR", "target": "signal_pr_dengue_cases"},
        {"source": "signal_vector_index", "type": "IMPORTATION_LINK", "target": "eq_dengue_base"},
        {"source": "signal_vector_index", "type": "POSSIBLE_DRIVER_OF", "target": "eq_dengue_base"},

        {"source": "signal_rainfall_anomaly", "type": "APPLIES_TO", "target": "region_puerto_rico"},
        {"source": "signal_rainfall_anomaly", "type": "MODELS", "target": "disease_dengue"},
        {"source": "signal_rainfall_anomaly", "type": "HAS_CONTEXT", "target": "context_dengue_climate"},
        {"source": "signal_rainfall_anomaly", "type": "HAS_DATASET", "target": "dataset_rainfall_anomaly"},
        {"source": "signal_rainfall_anomaly", "type": "SUPPORTED_BY", "target": "paper_dengue_climate"},
        {"source": "signal_rainfall_anomaly", "type": "LEADING_INDICATOR_FOR", "target": "signal_pr_dengue_cases"},
        {"source": "signal_rainfall_anomaly", "type": "POSSIBLE_DRIVER_OF", "target": "eq_dengue_base"},

        {"source": "signal_temperature_anomaly", "type": "APPLIES_TO", "target": "region_puerto_rico"},
        {"source": "signal_temperature_anomaly", "type": "MODELS", "target": "disease_dengue"},
        {"source": "signal_temperature_anomaly", "type": "HAS_CONTEXT", "target": "context_dengue_climate"},
        {"source": "signal_temperature_anomaly", "type": "HAS_DATASET", "target": "dataset_temperature_anomaly"},
        {"source": "signal_temperature_anomaly", "type": "SUPPORTED_BY", "target": "paper_dengue_climate"},
        {"source": "signal_temperature_anomaly", "type": "POSSIBLE_DRIVER_OF", "target": "eq_dengue_base"},

        {"source": "signal_travel_importation_dengue", "type": "APPLIES_TO", "target": "region_puerto_rico"},
        {"source": "signal_travel_importation_dengue", "type": "MODELS", "target": "disease_dengue"},
        {"source": "signal_travel_importation_dengue", "type": "HAS_CONTEXT", "target": "context_dengue_importation"},
        {"source": "signal_travel_importation_dengue", "type": "HAS_DATASET", "target": "dataset_dengue_travel_importation"},
        {"source": "signal_travel_importation_dengue", "type": "SUPPORTED_BY", "target": "paper_dengue_importation"},
        {"source": "signal_travel_importation_dengue", "type": "IMPORTATION_LINK", "target": "eq_dengue_base"},
        {"source": "signal_travel_importation_dengue", "type": "POSSIBLE_DRIVER_OF", "target": "eq_dengue_base"},

        {"source": "eq_rsv_pediatric_base", "type": "MODELS", "target": "disease_rsv"},
        {"source": "eq_rsv_pediatric_base", "type": "APPLIES_TO", "target": "region_southeast_us"},
        {"source": "eq_rsv_pediatric_base", "type": "USES_VARIABLE", "target": "state_i_rsv_peds"},
        {"source": "eq_rsv_pediatric_base", "type": "USES_PARAMETER", "target": "param_beta_rsv_peds"},

        {"source": "signal_rsv_pediatric_hosp", "type": "APPLIES_TO", "target": "region_southeast_us"},
        {"source": "signal_rsv_pediatric_hosp", "type": "MODELS", "target": "disease_rsv"},
        {"source": "signal_rsv_pediatric_hosp", "type": "HAS_DATASET", "target": "dataset_rsv_pediatric_hosp"},

        {"source": "signal_regional_rsv_early", "type": "APPLIES_TO", "target": "region_rsv_surveillance_network"},
        {"source": "signal_regional_rsv_early", "type": "MODELS", "target": "disease_rsv"},
        {"source": "signal_regional_rsv_early", "type": "HAS_CONTEXT", "target": "context_rsv_surveillance"},
        {"source": "signal_regional_rsv_early", "type": "HAS_DATASET", "target": "dataset_regional_rsv_early"},
        {"source": "signal_regional_rsv_early", "type": "SUPPORTED_BY", "target": "paper_rsv_surveillance"},
        {"source": "signal_regional_rsv_early", "type": "LEADING_INDICATOR_FOR", "target": "signal_rsv_pediatric_hosp"},
        {"source": "signal_regional_rsv_early", "type": "IMPORTATION_LINK", "target": "eq_rsv_pediatric_base"},
        {"source": "signal_regional_rsv_early", "type": "POSSIBLE_DRIVER_OF", "target": "eq_rsv_pediatric_base"},

        {"source": "signal_school_reopening_pressure", "type": "APPLIES_TO", "target": "region_southeast_us"},
        {"source": "signal_school_reopening_pressure", "type": "MODELS", "target": "disease_rsv"},
        {"source": "signal_school_reopening_pressure", "type": "HAS_CONTEXT", "target": "context_school_contact"},
        {"source": "signal_school_reopening_pressure", "type": "HAS_DATASET", "target": "dataset_school_reopening"},
        {"source": "signal_school_reopening_pressure", "type": "SUPPORTED_BY", "target": "paper_school_contact"},
        {"source": "signal_school_reopening_pressure", "type": "LEADING_INDICATOR_FOR", "target": "signal_rsv_pediatric_hosp"},
        {"source": "signal_school_reopening_pressure", "type": "POSSIBLE_DRIVER_OF", "target": "eq_rsv_pediatric_base"},

        {"source": "signal_mobility_pressure_rsv", "type": "APPLIES_TO", "target": "region_southeast_us"},
        {"source": "signal_mobility_pressure_rsv", "type": "MODELS", "target": "disease_rsv"},
        {"source": "signal_mobility_pressure_rsv", "type": "HAS_CONTEXT", "target": "context_rsv_mobility"},
        {"source": "signal_mobility_pressure_rsv", "type": "HAS_DATASET", "target": "dataset_mobility_pressure_rsv"},
        {"source": "signal_mobility_pressure_rsv", "type": "SUPPORTED_BY", "target": "paper_respiratory_mobility"},
        {"source": "signal_mobility_pressure_rsv", "type": "IMPORTATION_LINK", "target": "eq_rsv_pediatric_base"},
        {"source": "signal_mobility_pressure_rsv", "type": "POSSIBLE_DRIVER_OF", "target": "eq_rsv_pediatric_base"},

        {"source": "signal_cold_weather_anomaly_rsv", "type": "APPLIES_TO", "target": "region_southeast_us"},
        {"source": "signal_cold_weather_anomaly_rsv", "type": "MODELS", "target": "disease_rsv"},
        {"source": "signal_cold_weather_anomaly_rsv", "type": "HAS_CONTEXT", "target": "context_rsv_climate"},
        {"source": "signal_cold_weather_anomaly_rsv", "type": "HAS_DATASET", "target": "dataset_cold_weather_rsv"},
        {"source": "signal_cold_weather_anomaly_rsv", "type": "SUPPORTED_BY", "target": "paper_rsv_weather"},
        {"source": "signal_cold_weather_anomaly_rsv", "type": "POSSIBLE_DRIVER_OF", "target": "eq_rsv_pediatric_base"},

        {"source": "eq_covid_hosp_base", "type": "MODELS", "target": "disease_covid19"},
        {"source": "eq_covid_hosp_base", "type": "APPLIES_TO", "target": "region_northeast_us"},
        {"source": "eq_covid_hosp_base", "type": "USES_VARIABLE", "target": "state_i_covid"},
        {"source": "eq_covid_hosp_base", "type": "USES_PARAMETER", "target": "param_beta_covid"},

        {"source": "signal_covid_hosp", "type": "APPLIES_TO", "target": "region_northeast_us"},
        {"source": "signal_covid_hosp", "type": "MODELS", "target": "disease_covid19"},
        {"source": "signal_covid_hosp", "type": "HAS_DATASET", "target": "dataset_covid_hosp"},

        {"source": "signal_variant_growth_covid", "type": "APPLIES_TO", "target": "region_variant_surveillance_network"},
        {"source": "signal_variant_growth_covid", "type": "MODELS", "target": "disease_covid19"},
        {"source": "signal_variant_growth_covid", "type": "HAS_CONTEXT", "target": "context_variant_growth"},
        {"source": "signal_variant_growth_covid", "type": "HAS_DATASET", "target": "dataset_variant_growth_covid"},
        {"source": "signal_variant_growth_covid", "type": "SUPPORTED_BY", "target": "paper_covid_variant_growth"},
        {"source": "signal_variant_growth_covid", "type": "LEADING_INDICATOR_FOR", "target": "signal_covid_hosp"},
        {"source": "signal_variant_growth_covid", "type": "IMPORTATION_LINK", "target": "eq_covid_hosp_base"},
        {"source": "signal_variant_growth_covid", "type": "POSSIBLE_DRIVER_OF", "target": "eq_covid_hosp_base"},

        {"source": "signal_wastewater_surge_covid", "type": "APPLIES_TO", "target": "region_northeast_us"},
        {"source": "signal_wastewater_surge_covid", "type": "MODELS", "target": "disease_covid19"},
        {"source": "signal_wastewater_surge_covid", "type": "HAS_CONTEXT", "target": "context_wastewater_surveillance"},
        {"source": "signal_wastewater_surge_covid", "type": "HAS_DATASET", "target": "dataset_wastewater_covid"},
        {"source": "signal_wastewater_surge_covid", "type": "SUPPORTED_BY", "target": "paper_covid_wastewater"},
        {"source": "signal_wastewater_surge_covid", "type": "LEADING_INDICATOR_FOR", "target": "signal_covid_hosp"},
        {"source": "signal_wastewater_surge_covid", "type": "POSSIBLE_DRIVER_OF", "target": "eq_covid_hosp_base"},

        {"source": "signal_mobility_rebound_covid", "type": "APPLIES_TO", "target": "region_northeast_us"},
        {"source": "signal_mobility_rebound_covid", "type": "MODELS", "target": "disease_covid19"},
        {"source": "signal_mobility_rebound_covid", "type": "HAS_CONTEXT", "target": "context_covid_mobility"},
        {"source": "signal_mobility_rebound_covid", "type": "HAS_DATASET", "target": "dataset_mobility_rebound_covid"},
        {"source": "signal_mobility_rebound_covid", "type": "SUPPORTED_BY", "target": "paper_covid_mobility"},
        {"source": "signal_mobility_rebound_covid", "type": "IMPORTATION_LINK", "target": "eq_covid_hosp_base"},
        {"source": "signal_mobility_rebound_covid", "type": "POSSIBLE_DRIVER_OF", "target": "eq_covid_hosp_base"},

        {"source": "signal_immunity_waning_covid", "type": "APPLIES_TO", "target": "region_northeast_us"},
        {"source": "signal_immunity_waning_covid", "type": "MODELS", "target": "disease_covid19"},
        {"source": "signal_immunity_waning_covid", "type": "HAS_CONTEXT", "target": "context_immunity_waning"},
        {"source": "signal_immunity_waning_covid", "type": "HAS_DATASET", "target": "dataset_immunity_waning_covid"},
        {"source": "signal_immunity_waning_covid", "type": "SUPPORTED_BY", "target": "paper_covid_immunity"},
        {"source": "signal_immunity_waning_covid", "type": "POSSIBLE_DRIVER_OF", "target": "eq_covid_hosp_base"},
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
