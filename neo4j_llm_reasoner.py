from failure_case import get_failure_case
from neo4j_retrieval import (
    get_driver,
    retrieve_failure_candidates_from_neo4j,
    get_top_candidate_support_subgraph,
    NEO4J_DATABASE,
)
from neo4j_validator import validate_candidate_neo4j
from neo4j_signal_summary import (
    fetch_signal_summary as fetch_us_signal_summary,
    SIGNAL_ID as US_SIGNAL_ID,
)
from neo4j_chile_signal_summary import (
    fetch_signal_summary as fetch_chile_signal_summary,
    SIGNAL_ID as CHILE_SIGNAL_ID,
)
from neo4j_prompt_with_data_demo import (
    build_failure_analysis_prompt_with_real_data,
    compute_lag_context,
)

from llm_reasoner import (
    get_client,
    build_json_instruction_suffix,
    parse_llm_json,
    validate_llm_output,
    save_demo_output,
    pretty_print_result,
)


MODEL_NAME = "gpt-5-mini"
REASONING_EFFORT = "low"
MAX_OUTPUT_TOKENS = 1500


def attach_top_support_subgraph(driver, candidates, failure_case):
    if not candidates:
        return candidates

    top_candidate = candidates[0]
    support_subgraph = get_top_candidate_support_subgraph(
        driver,
        top_candidate["candidate_id"],
        failure_case,
    )
    top_candidate["support_subgraph"] = support_subgraph
    return candidates


def generate_neo4j_llm_analysis():
    failure_case = get_failure_case()
    driver = get_driver()

    try:
        candidates = retrieve_failure_candidates_from_neo4j(driver, failure_case)

        if not candidates:
            print("No candidates found. LLM analysis will not be generated.")
            return None

        candidates = attach_top_support_subgraph(driver, candidates, failure_case)

        validation = validate_candidate_neo4j(driver, candidates[0])
        if not validation["passed"]:
            print("Top candidate failed validation. LLM analysis will not be generated.")
            for reason in validation["reasons"]:
                print(f"- {reason}")
            return None

        with driver.session(database=NEO4J_DATABASE) as session:
            us_signal_summary = session.execute_read(
                fetch_us_signal_summary,
                US_SIGNAL_ID,
            )
            chile_signal_summary = session.execute_read(
                fetch_chile_signal_summary,
                CHILE_SIGNAL_ID,
            )

        lag_context = compute_lag_context(driver)

        prompt = build_failure_analysis_prompt_with_real_data(
            failure_case,
            candidates,
            us_signal_summary,
            chile_signal_summary,
            lag_context,
        )
        full_prompt = prompt + "\n\n" + build_json_instruction_suffix()

        client = get_client()
        response = client.responses.create(
            model=MODEL_NAME,
            reasoning={"effort": REASONING_EFFORT},
            max_output_tokens=MAX_OUTPUT_TOKENS,
            input=full_prompt,
        )

        raw_text = response.output_text
        if not raw_text or not raw_text.strip():
            raise ValueError("Model returned no visible text output.")

        parsed = parse_llm_json(raw_text)
        validate_llm_output(parsed)

        result_dict = {
            "backend": "neo4j",
            "failure_case": failure_case,
            "top_candidate_validation": validation,
            "target_signal_summary": us_signal_summary,
            "driver_signal_summary": chile_signal_summary,
            "lag_context": lag_context,
            "llm_output": parsed,
        }

        save_demo_output(result_dict, raw_text)
        pretty_print_result(parsed)

        return {
            "result_dict": result_dict,
            "raw_text": raw_text,
            "parsed": parsed,
        }

    finally:
        driver.close()


if __name__ == "__main__":
    generate_neo4j_llm_analysis()