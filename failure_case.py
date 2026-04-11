FAILURE_CASE = {
    "mechanism_id": "eq_us_flu_base",
    "region": "US",
    "disease": "Influenza",
    "failure_type": "underprediction",
    "failure_pattern": "missed_peak",
    "target_signal": "signal_us_hosp",
    "error_direction": "actual_above_prediction",
    "candidate_driver_family": "southern_hemisphere_influenza_signals"
}


if __name__ == "__main__":
    print("Failure case loaded successfully.")
    for key, value in FAILURE_CASE.items():
        print(f"{key}: {value}")