PROJECT_NAME = "Failure-Conditioned GraphRAG Prototype for EpiGraph"

TARGET_DISEASE = "Influenza"
TARGET_REGION = "US"
FAILURE_TYPE = "underprediction"
FAILURE_PATTERN = "missed_peak"
TARGET_SIGNAL = "us_hospitalizations"
ERROR_DIRECTION = "actual_above_prediction"

CANDIDATE_DRIVER_FAMILY = "southern_hemisphere_influenza_signals"
EXPECTED_HIDDEN_DRIVER = "chile_influenza_activity"

EXPECTED_MINIMAL_EDIT = "add_lagged_importation_signal"
OUTPUT_GOAL = "rank_candidate_drivers_and_propose_a_minimal_graph_edit"

if __name__ == "__main__":
    print("Project Name:", PROJECT_NAME)
    print("Target Disease:", TARGET_DISEASE)
    print("Target Region:", TARGET_REGION)
    print("Failure Type:", FAILURE_TYPE)
    print("Failure Pattern:", FAILURE_PATTERN)
    print("Target Signal:", TARGET_SIGNAL)
    print("Error Direction:", ERROR_DIRECTION)
    print("Candidate Driver Family:", CANDIDATE_DRIVER_FAMILY)
    print("Expected Hidden Driver:", EXPECTED_HIDDEN_DRIVER)
    print("Expected Minimal Edit:", EXPECTED_MINIMAL_EDIT)
    print("Output Goal:", OUTPUT_GOAL)