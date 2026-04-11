from seed_graph import GRAPH
from failure_case import FAILURE_CASE


DRIVER_EDGE_TYPES = {
    "POSSIBLE_DRIVER_OF",
    "IMPORTATION_LINK",
    "LEADING_INDICATOR_FOR"
}


def get_node_by_id(graph, node_id):
    for node in graph["nodes"]:
        if node["id"] == node_id:
            return node
    return None


def get_edges_by_type(graph, edge_types):
    return [edge for edge in graph["edges"] if edge["type"] in edge_types]


def score_candidate(graph, candidate_node_id, failure_case):
    score = 0
    evidence = []

    mechanism_id = failure_case["mechanism_id"]
    target_signal = failure_case["target_signal"]

    for edge in graph["edges"]:
        if edge["source"] == candidate_node_id and edge["target"] == mechanism_id:
            if edge["type"] == "POSSIBLE_DRIVER_OF":
                score += 2
                evidence.append("POSSIBLE_DRIVER_OF -> mechanism (+2)")

            elif edge["type"] == "IMPORTATION_LINK":
                score += 2
                evidence.append("IMPORTATION_LINK -> mechanism (+2)")

        if edge["source"] == candidate_node_id and edge["target"] == target_signal:
            if edge["type"] == "LEADING_INDICATOR_FOR":
                score += 3
                evidence.append("LEADING_INDICATOR_FOR -> target signal (+3)")

    return score, evidence

def build_candidate_support_subgraph(graph, candidate_node_id, failure_case):
    mechanism_id = failure_case["mechanism_id"]
    target_signal = failure_case["target_signal"]

    supporting_edges = []
    supporting_node_ids = {candidate_node_id, mechanism_id, target_signal}

    for edge in graph["edges"]:
        if edge["source"] == candidate_node_id and edge["target"] in {mechanism_id, target_signal}:
            if edge["type"] in DRIVER_EDGE_TYPES:
                supporting_edges.append(edge)
                supporting_node_ids.add(edge["target"])

    supporting_nodes = [
        node for node in graph["nodes"]
        if node["id"] in supporting_node_ids
    ]

    return {
        "nodes": supporting_nodes,
        "edges": supporting_edges
    }

def print_support_subgraph(candidate):
    print("\nTop candidate support subgraph:")
    print(f"Candidate: {candidate['candidate_name']}")
    
    print("\n  Nodes:")
    for node in candidate["support_subgraph"]["nodes"]:
        print(f"  - {node['id']} ({node['type']})")

    print("\n  Edges:")
    for edge in candidate["support_subgraph"]["edges"]:
        print(f"  - {edge['source']} --{edge['type']}--> {edge['target']}")

def retrieve_failure_candidates(graph, failure_case):
    candidates = []

    for node in graph["nodes"]:
        if node["type"] != "Signal":
            continue

        score, evidence = score_candidate(graph, node["id"], failure_case)

        if score > 0:
            support_subgraph = build_candidate_support_subgraph(
                graph, node["id"], failure_case
            )

            candidates.append({
                "candidate_id": node["id"],
                "candidate_name": node["name"],
                "score": score,
                "evidence": evidence,
                "support_subgraph": support_subgraph
            })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates


if __name__ == "__main__":
    candidates = retrieve_failure_candidates(GRAPH, FAILURE_CASE)

    print("Failure-conditioned retrieval complete.")
    print(f"Number of candidates found: {len(candidates)}")

    print("\nRanked candidates:")
    for candidate in candidates:
        print(
            f"- {candidate['candidate_id']} | "
            f"{candidate['candidate_name']} | "
            f"score={candidate['score']}"
        )
        for item in candidate["evidence"]:
            print(f"    evidence: {item}")
        print(
            f"    support_subgraph: "
            f"{len(candidate['support_subgraph']['nodes'])} nodes, "
            f"{len(candidate['support_subgraph']['edges'])} edges"
        )
    if candidates:
        print_support_subgraph(candidates[0])