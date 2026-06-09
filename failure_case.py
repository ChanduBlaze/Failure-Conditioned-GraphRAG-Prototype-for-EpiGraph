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

FAILURE_CASES_BY_ID = {
    FAILURE_CASE["id"]: FAILURE_CASE,
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


def print_failure_case(failure_case: dict) -> None:
    print("Failure Case")
    print("-" * 40)
    for key, value in failure_case.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    case = get_failure_case()
    print_failure_case(case)
