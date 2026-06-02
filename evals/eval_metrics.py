def normalize_list_of_strings(values):
    """Return a cleaned list containing only non-empty string values."""
    normalized = []

    for value in values or []:
        if isinstance(value, str) and value.strip():
            normalized.append(value.strip())

    return normalized


def compute_evidence_metrics(mentioned_edge_types, expected_edge_types):
    """Compute precision, recall, and hallucinated count for evidence edge types."""
    mentioned = set(normalize_list_of_strings(mentioned_edge_types))
    expected = set(normalize_list_of_strings(expected_edge_types))

    if mentioned:
        precision = len(mentioned & expected) / len(mentioned)
    else:
        precision = 1.0 if not expected else 0.0

    if expected:
        recall = len(mentioned & expected) / len(expected)
    else:
        recall = 1.0

    return {
        "evidence_precision": precision,
        "evidence_recall": recall,
        "hallucinated_evidence_count": len(mentioned - expected),
    }


def compute_missing_edge_metrics(
    identified_missing_edges,
    expected_missing_edges,
    mentioned_edge_types=None,
):
    """Score whether expected missing edges were identified and not claimed present."""
    identified_missing = set(normalize_list_of_strings(identified_missing_edges))
    expected_missing = set(normalize_list_of_strings(expected_missing_edges))
    mentioned = set(normalize_list_of_strings(mentioned_edge_types))

    if expected_missing:
        recall = len(identified_missing & expected_missing) / len(expected_missing)
    else:
        recall = 1.0

    false_claims = expected_missing & mentioned

    return {
        "missing_edge_correct": expected_missing.issubset(identified_missing),
        "missing_edge_recall": recall,
        "missing_edge_false_claim_count": len(false_claims),
    }


def compute_support_node_metrics(mentioned_support_nodes, expected_support_nodes):
    """Compute precision, recall, and hallucinated count for support node IDs."""
    mentioned = set(normalize_list_of_strings(mentioned_support_nodes))
    expected = set(normalize_list_of_strings(expected_support_nodes))

    if mentioned:
        precision = len(mentioned & expected) / len(mentioned)
    else:
        precision = 1.0 if not expected else 0.0

    if expected:
        recall = len(mentioned & expected) / len(expected)
    else:
        recall = 1.0

    return {
        "support_node_precision": precision,
        "support_node_recall": recall,
        "hallucinated_support_node_count": len(mentioned - expected),
    }


def parse_bool(value):
    """Parse common truthy values from strings, booleans, and numbers."""
    if isinstance(value, bool):
        return value

    return str(value).strip().lower() in {"true", "1", "yes"}


def parse_float(value, default=0.0):
    """Parse a float value, returning the provided default on missing/bad input."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def mean(values):
    """Return the arithmetic mean of numeric values, or 0.0 for an empty list."""
    values = list(values or [])
    return sum(values) / len(values) if values else 0.0


if __name__ == "__main__":
    print("Evidence metrics:")
    print(
        compute_evidence_metrics(
            ["LEADING_INDICATOR_FOR", "IMPORTATION_LINK"],
            ["LEADING_INDICATOR_FOR", "IMPORTATION_LINK", "POSSIBLE_DRIVER_OF"],
        )
    )

    print("\nMissing-edge metrics:")
    print(
        compute_missing_edge_metrics(
            identified_missing_edges=["IMPORTATION_LINK"],
            expected_missing_edges=["IMPORTATION_LINK"],
            mentioned_edge_types=["LEADING_INDICATOR_FOR"],
        )
    )

    print("\nSupport-node metrics:")
    print(
        compute_support_node_metrics(
            ["signal_chile_flu", "signal_us_hosp"],
            ["signal_chile_flu", "signal_us_hosp", "eq_us_flu_base"],
        )
    )

    print("\nParsing and mean examples:")
    print({"parse_bool": parse_bool("true"), "parse_float": parse_float("1.25")})
    print({"mean": mean([1.0, 0.0, 1.0])})
