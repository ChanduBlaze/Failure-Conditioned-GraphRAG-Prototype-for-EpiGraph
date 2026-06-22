FAILURE_CASE = {
    "id": "failure_case_us_flu_missed_peak_001",
    "mechanism_id": "eq_us_flu_base",
    "region": "US",
    "disease": "Influenza",
    "failure_type": "underprediction",
    "failure_pattern": "missed_peak",
    "target_signal": "signal_us_hosp",
    "error_direction": "actual_above_prediction",
    "candidate_driver_family": "southern_hemisphere_influenza_signals",
    "summary": "US influenza mechanism underpredicted a missed hospitalization peak.",
}

DENGUE_FAILURE_CASE = {
    "id": "failure_case_dengue_regional_outbreak_001",
    "mechanism_id": "eq_dengue_base",
    "region": "Puerto Rico",
    "disease": "Dengue",
    "failure_type": "underprediction",
    "failure_pattern": "missed_peak",
    "target_signal": "signal_pr_dengue_cases",
    "error_direction": "actual_above_prediction",
    "candidate_driver_family": "climate_vector_surveillance_and_importation_signals",
    "summary": "Puerto Rico dengue mechanism underpredicted a regional outbreak peak.",
}


RSV_FAILURE_CASE = {
    "id": "failure_case_rsv_pediatric_hosp_underprediction_001",
    "mechanism_id": "eq_rsv_pediatric_base",
    "region": "Southeast US",
    "disease": "RSV",
    "failure_type": "underprediction",
    "failure_pattern": "missed_peak",
    "target_signal": "signal_rsv_pediatric_hosp",
    "error_direction": "actual_above_prediction",
    "candidate_driver_family": "rsv_surveillance_contact_mobility_and_weather_signals",
    "summary": "Southeast US pediatric RSV mechanism underpredicted a hospitalization peak.",
}

FAILURE_CASES_BY_ID = {
    FAILURE_CASE["id"]: FAILURE_CASE,
    DENGUE_FAILURE_CASE["id"]: DENGUE_FAILURE_CASE,
    RSV_FAILURE_CASE["id"]: RSV_FAILURE_CASE,
}

FAILURE_CASE_CANDIDATES_BY_ID = {
    FAILURE_CASE["id"]: [
        {
            "candidate_id": "signal_chile_flu",
            "candidate_name": "Chile Influenza Activity",
        },
        {
            "candidate_id": "signal_australia_flu",
            "candidate_name": "Australia Influenza Activity",
        },
        {
            "candidate_id": "signal_travel_pressure",
            "candidate_name": "Travel Importation Pressure",
        },
        {
            "candidate_id": "signal_humidity_drop",
            "candidate_name": "Humidity Drop Anomaly",
        },
    ],
    DENGUE_FAILURE_CASE["id"]: [
        {
            "candidate_id": "signal_rainfall_anomaly",
            "candidate_name": "Rainfall Anomaly",
        },
        {
            "candidate_id": "signal_temperature_anomaly",
            "candidate_name": "Temperature Anomaly",
        },
        {
            "candidate_id": "signal_vector_index",
            "candidate_name": "Mosquito Vector Index",
        },
        {
            "candidate_id": "signal_travel_importation_dengue",
            "candidate_name": "Dengue Travel Importation Pressure",
        },
    ],
    RSV_FAILURE_CASE["id"]: [
        {
            "candidate_id": "signal_regional_rsv_early",
            "candidate_name": "Regional RSV Early Signal",
        },
        {
            "candidate_id": "signal_school_reopening_pressure",
            "candidate_name": "School Reopening Contact Pressure",
        },
        {
            "candidate_id": "signal_mobility_pressure_rsv",
            "candidate_name": "RSV Mobility Pressure",
        },
        {
            "candidate_id": "signal_cold_weather_anomaly_rsv",
            "candidate_name": "Cold Weather Anomaly",
        },
    ],
}


REQUIRED_FAILURE_FIELDS = {
    "id",
    "mechanism_id",
    "region",
    "disease",
    "failure_type",
    "failure_pattern",
    "target_signal",
    "error_direction",
    "candidate_driver_family",
    "summary",
}


def validate_failure_case(failure_case: dict) -> None:
    missing = REQUIRED_FAILURE_FIELDS - set(failure_case.keys())
    if missing:
        raise ValueError(
            f"Failure case is missing required fields: {sorted(missing)}"
        )


def get_failure_case() -> dict:
    validate_failure_case(FAILURE_CASE)
    return FAILURE_CASE


def get_failure_case_by_id(failure_case_id: str) -> dict:
    if not failure_case_id:
        return get_failure_case()

    failure_case = FAILURE_CASES_BY_ID.get(failure_case_id)

    if failure_case is None:
        raise ValueError(f"Unknown failure_case_id: {failure_case_id}")

    validate_failure_case(failure_case)
    return failure_case


def get_candidates_for_failure_case(failure_case_id: str) -> list[dict]:
    failure_case = get_failure_case_by_id(failure_case_id)
    candidates = FAILURE_CASE_CANDIDATES_BY_ID.get(failure_case["id"])

    if candidates is None:
        raise ValueError(
            f"No candidates configured for failure_case_id: {failure_case['id']}"
        )

    return [dict(candidate) for candidate in candidates]


def print_failure_case(failure_case: dict) -> None:
    print("Failure Case")
    print("-" * 40)
    for key, value in failure_case.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    case = get_failure_case()
    print_failure_case(case)
