from failure_case import FAILURE_CASE
from failure_retrieval import retrieve_failure_candidates
from seed_graph import GRAPH


MIN_SCORE_THRESHOLD = 4
MIN_SUPPORT_EDGE_COUNT = 2
MIN_DATASET_LINK_COUNT = 1
MIN_PROVENANCE_LINK_COUNT = 1

def count_candidate_edges(graph, candidate_id, edge_type):
    count = 0
    for edge in graph["edges"]:
        if edge["source"] == candidate_id and edge["type"] == edge_type:
            count += 1
    return count

def validate_candidate(candidate, graph):
    reasons = []

    if candidate["score"] < MIN_SCORE_THRESHOLD:
        reasons.append(
            f"score {candidate['score']} is below threshold {MIN_SCORE_THRESHOLD}"
        )

    support_edge_count = len(candidate["support_subgraph"]["edges"])
    if support_edge_count < MIN_SUPPORT_EDGE_COUNT:
        reasons.append(
            f"support edge count {support_edge_count} is below threshold {MIN_SUPPORT_EDGE_COUNT}"
        )

    dataset_link_count = count_candidate_edges(graph, candidate["candidate_id"], "HAS_DATASET")
    if dataset_link_count < MIN_DATASET_LINK_COUNT:
        reasons.append(
            f"dataset link count {dataset_link_count} is below threshold {MIN_DATASET_LINK_COUNT}"
        )

    provenance_link_count = count_candidate_edges(graph, candidate["candidate_id"], "SUPPORTED_BY")
    if provenance_link_count < MIN_PROVENANCE_LINK_COUNT:
        reasons.append(
            f"provenance link count {provenance_link_count} is below threshold {MIN_PROVENANCE_LINK_COUNT}"
        )

    is_valid = len(reasons) == 0

    return {
        "candidate_id": candidate["candidate_id"],
        "candidate_name": candidate["candidate_name"],
        "is_valid": is_valid,
        "reasons": reasons
    }


if __name__ == "__main__":
    candidates = retrieve_failure_candidates(GRAPH, FAILURE_CASE)

    if not candidates:
        print("No candidates found.")
    else:
        top_candidate = candidates[0]
        result = validate_candidate(top_candidate, GRAPH)

        print("Validation result:")
        print(f"Candidate: {result['candidate_name']} ({result['candidate_id']})")
        print(f"Valid: {result['is_valid']}")

        if result["reasons"]:
            print("Reasons:")
            for reason in result["reasons"]:
                print(f"- {reason}")
        else:
            print("Reasons:")
            print("- candidate passed all validation checks")