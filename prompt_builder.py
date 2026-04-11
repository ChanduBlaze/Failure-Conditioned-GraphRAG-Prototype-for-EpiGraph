from failure_case import FAILURE_CASE
from failure_retrieval import retrieve_failure_candidates
from seed_graph import GRAPH
from validator import validate_candidate


def format_subgraph(subgraph):
    lines = []

    lines.append("Support Subgraph Nodes:")
    for node in subgraph["nodes"]:
        lines.append(f"- {node['id']} ({node['type']}): {node['name']}")

    lines.append("")
    lines.append("Support Subgraph Edges:")
    for edge in subgraph["edges"]:
        lines.append(f"- {edge['source']} --{edge['type']}--> {edge['target']}")

    return "\n".join(lines)

def format_candidate_list(candidates, top_k=3):
    lines = []
    lines.append(f"Top {top_k} ranked hidden-driver candidates:")

    for i, candidate in enumerate(candidates[:top_k], start=1):
        lines.append(
            f"{i}. {candidate['candidate_name']} "
            f"({candidate['candidate_id']}) | score={candidate['score']}"
        )
        for item in candidate["evidence"]:
            lines.append(f"   - {item}")
        lines.append("")

    return "\n".join(lines)

def build_failure_analysis_prompt(failure_case, candidates):
    top_candidate = candidates[0]
    ranked_candidate_text = format_candidate_list(candidates, top_k=3)

    prompt = f"""
You are assisting with epidemiological mechanism revision.

A forecasting failure has occurred with the following details:
- Mechanism ID: {failure_case['mechanism_id']}
- Region: {failure_case['region']}
- Disease: {failure_case['disease']}
- Failure Type: {failure_case['failure_type']}
- Failure Pattern: {failure_case['failure_pattern']}
- Target Signal: {failure_case['target_signal']}
- Error Direction: {failure_case['error_direction']}

{ranked_candidate_text}

Detailed support subgraph for the top-ranked candidate:
- Candidate ID: {top_candidate['candidate_id']}
- Candidate Name: {top_candidate['candidate_name']}
- Score: {top_candidate['score']}

{format_subgraph(top_candidate["support_subgraph"])}

Using only the evidence above:
1. Explain why the top-ranked candidate is more plausible than the other candidates.
2. Propose one minimal graph edit or mechanism edit worth testing.
3. Keep the explanation grounded in the provided graph evidence and candidate ranking.
"""

    return prompt


if __name__ == "__main__":
    candidates = retrieve_failure_candidates(GRAPH, FAILURE_CASE)

    if not candidates:
        print("No candidates found. Prompt not built.")
    else:
        top_candidate = candidates[0]
        validation_result = validate_candidate(top_candidate, GRAPH)

        if not validation_result["is_valid"]:
            print("Top candidate failed validation. Prompt not built.")
            print("Reasons:")
            for reason in validation_result["reasons"]:
                print(f"- {reason}")
        else:
            prompt = build_failure_analysis_prompt(FAILURE_CASE, candidates)
            print("Prompt built successfully.\n")
            print(prompt)