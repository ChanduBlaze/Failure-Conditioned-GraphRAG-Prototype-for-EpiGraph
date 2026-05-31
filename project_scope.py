PROJECT_NAME = "Failure-Conditioned GraphRAG Prototype for EpiGraph"

# Core failure scenario
TARGET_DISEASE = "Influenza"
TARGET_REGION = "US"
FAILURE_TYPE = "underprediction"
FAILURE_PATTERN = "missed_peak"
TARGET_SIGNAL = "signal_us_hosp"
ERROR_DIRECTION = "actual_above_prediction"

# Candidate-driver framing
CANDIDATE_DRIVER_FAMILY = "southern_hemisphere_influenza_signals"
EXPECTED_HIDDEN_DRIVER = "signal_chile_flu"

# Expected system output
EXPECTED_MINIMAL_EDIT = "add_lagged_importation_signal"
OUTPUT_GOAL = "rank_candidate_drivers_and_propose_a_minimal_graph_edit"

# Prototype framing
PROJECT_SCOPE = (
    "Build a Neo4j-backed failure-conditioned GraphRAG prototype for EpiGraph. "
    "Given a forecasting failure in a US influenza mechanism, the system retrieves "
    "and ranks plausible hidden drivers from a graph, validates the top candidate, "
    "and proposes a minimal graph or mechanism edit."
)

# Backend / graph settings
GRAPH_BACKEND = "neo4j"
GRAPH_NAME = "epigraph_failure_demo"
USE_NEO4J = True

# Demo target
DEMO_QUESTION = (
    "When the US influenza mechanism underpredicts a missed hospitalization peak, "
    "which connected hidden driver best explains the failure?"
)


def get_project_scope():
    return {
        "project_name": PROJECT_NAME,
        "project_scope": PROJECT_SCOPE,
        "target_disease": TARGET_DISEASE,
        "target_region": TARGET_REGION,
        "failure_type": FAILURE_TYPE,
        "failure_pattern": FAILURE_PATTERN,
        "target_signal": TARGET_SIGNAL,
        "error_direction": ERROR_DIRECTION,
        "candidate_driver_family": CANDIDATE_DRIVER_FAMILY,
        "expected_hidden_driver": EXPECTED_HIDDEN_DRIVER,
        "expected_minimal_edit": EXPECTED_MINIMAL_EDIT,
        "output_goal": OUTPUT_GOAL,
        "graph_backend": GRAPH_BACKEND,
        "graph_name": GRAPH_NAME,
        "use_neo4j": USE_NEO4J,
        "demo_question": DEMO_QUESTION,
    }


def print_project_scope():
    scope = get_project_scope()
    print("Project Scope Summary")
    print("-" * 40)
    for key, value in scope.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    print_project_scope()