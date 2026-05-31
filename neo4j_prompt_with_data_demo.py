from failure_case import get_failure_case
from prompt_builder import build_failure_analysis_prompt
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


def format_us_target_summary(summary):
    peak = summary["peak_row"]
    latest = summary["latest_row"]

    return f"""
Real target-signal summary from Neo4j:
- Signal ID: {US_SIGNAL_ID}
- Total observed weeks: {summary['total_weeks']}
- Peak weekly hospitalization rate: {peak['weekly_rate']}
- Peak week: {peak['season']} | {peak['calendar_year']}-W{int(peak['mmwr_week']):02d}
- Latest cumulative hospitalization rate: {latest['cumulative_rate']}
- Latest observed week: {latest['season']} | {latest['calendar_year']}-W{int(latest['mmwr_week']):02d}
""".strip()


def format_chile_driver_summary(summary):
    peak = summary["peak_row"]
    latest = summary["latest_row"]

    return f"""
Real candidate-driver summary from Neo4j:
- Signal ID: {CHILE_SIGNAL_ID}
- Total observed weeks: {summary['total_weeks']}
- Peak positivity: {peak['positivity']:.4f}
- Peak week: {peak['iso_year']}-W{int(peak['iso_week']):02d}
- Peak positive specimens: {peak['inf_all']} out of {peak['spec_processed_nb']}
- Latest positivity: {latest['positivity']:.4f}
- Latest observed week: {latest['iso_year']}-W{int(latest['iso_week']):02d}
""".strip()


def build_failure_analysis_prompt_with_real_data(
    failure_case,
    candidates,
    us_signal_summary,
    chile_signal_summary,
):
    base_prompt = build_failure_analysis_prompt(failure_case, candidates)

    us_block = format_us_target_summary(us_signal_summary)
    chile_block = format_chile_driver_summary(chile_signal_summary)

    instructions = """
Use these summaries only as supporting context.
Do not invent additional observations beyond the provided graph evidence and summaries.
Prefer explanations that connect the candidate-driver signal to the observed target behavior in a grounded way.
""".strip()

    return base_prompt + "\n\n" + us_block + "\n\n" + chile_block + "\n\n" + instructions


def print_prompt_header():
    print("Neo4j grounded prompt with real target + driver data")
    print("-" * 40)


if __name__ == "__main__":
    failure_case = get_failure_case()
    driver = get_driver()

    try:
        candidates = retrieve_failure_candidates_from_neo4j(driver, failure_case)

        if not candidates:
            print("No candidates found. Prompt will not be built.")
        else:
            candidates = attach_top_support_subgraph(driver, candidates, failure_case)

            validation = validate_candidate_neo4j(driver, candidates[0])

            if not validation["passed"]:
                print("Top candidate failed validation. Prompt will not be built.")
                for reason in validation["reasons"]:
                    print(f"- {reason}")
            else:
                with driver.session(database=NEO4J_DATABASE) as session:
                    us_signal_summary = session.execute_read(
                        fetch_us_signal_summary,
                        US_SIGNAL_ID,
                    )
                    chile_signal_summary = session.execute_read(
                        fetch_chile_signal_summary,
                        CHILE_SIGNAL_ID,
                    )

                prompt = build_failure_analysis_prompt_with_real_data(
                    failure_case,
                    candidates,
                    us_signal_summary,
                    chile_signal_summary,
                )

                print_prompt_header()
                print(prompt)

    finally:
        driver.close()