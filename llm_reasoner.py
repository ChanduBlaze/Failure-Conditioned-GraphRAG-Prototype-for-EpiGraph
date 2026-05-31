import json
import os
from datetime import datetime
from pathlib import Path

from openai import OpenAI

from failure_case import get_failure_case
from failure_retrieval import retrieve_failure_candidates
from prompt_builder import build_failure_analysis_prompt
from seed_graph import GRAPH
from validator import validate_candidate


MODEL_NAME = "gpt-5-mini"
MAX_OUTPUT_TOKENS = 1500
OUTPUT_DIR = Path("demo_outputs")

REQUIRED_KEYS = {
    "chosen_candidate_id",
    "chosen_candidate_name",
    "why_top_candidate_wins",
    "proposed_minimal_edit",
    "caveat",
}


def get_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY is not set. Please add it to your environment before running."
        )
    return OpenAI(api_key=api_key)


def build_json_instruction_suffix():
    return """
Return your answer as valid JSON only.
Do not use markdown fences.
Do not add any text before or after the JSON.

Use exactly this schema:
{
  "chosen_candidate_id": "...",
  "chosen_candidate_name": "...",
  "why_top_candidate_wins": "...",
  "proposed_minimal_edit": "...",
  "caveat": "..."
}
""".strip()


def extract_json_text(raw_text):
    raw_text = raw_text.strip()

    # Best case: the whole response is valid JSON
    try:
        json.loads(raw_text)
        return raw_text
    except json.JSONDecodeError:
        pass

    # Fallback: find the first JSON object inside extra text
    start = raw_text.find("{")
    end = raw_text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        raise ValueError("Could not find a JSON object in the model response.")

    candidate = raw_text[start:end + 1]

    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError as e:
        raise ValueError(f"Found a possible JSON block, but it could not be parsed: {e}")


def parse_llm_json(raw_text):
    json_text = extract_json_text(raw_text)
    return json.loads(json_text)


def validate_llm_output(data):
    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        raise ValueError(f"LLM JSON is missing required keys: {sorted(missing)}")

    for key in REQUIRED_KEYS:
        value = data.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"LLM JSON key '{key}' must be a non-empty string.")

    return True


def save_demo_output(result_dict, raw_text):
    OUTPUT_DIR.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    timestamped_file = OUTPUT_DIR / f"llm_result_{timestamp}.json"
    latest_file = OUTPUT_DIR / "latest_result.json"

    payload = {
        "timestamp": timestamp,
        "model": MODEL_NAME,
        "failure_case": result_dict["failure_case"],
        "result": result_dict,
        "raw_text": raw_text,
    }

    with open(timestamped_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return timestamped_file, latest_file


def pretty_print_result(result):
    print("LLM reasoning completed successfully.\n")
    print("Chosen candidate:")
    print(f"- ID: {result['chosen_candidate_id']}")
    print(f"- Name: {result['chosen_candidate_name']}\n")

    print("Why it wins:")
    print(result["why_top_candidate_wins"])
    print()

    print("Proposed minimal edit:")
    print(result["proposed_minimal_edit"])
    print()

    print("Caveat:")
    print(result["caveat"])
    print()


def generate_llm_analysis():
    failure_case = get_failure_case()
    candidates = retrieve_failure_candidates(GRAPH, failure_case)

    if not candidates:
        raise ValueError("No candidates found. Cannot run LLM reasoning.")

    top_candidate = candidates[0]
    validation_result = validate_candidate(top_candidate, GRAPH)

    if not validation_result["is_valid"]:
        raise ValueError(
            "Top candidate failed validation: "
            + "; ".join(validation_result["reasons"])
        )

    prompt = build_failure_analysis_prompt(failure_case, candidates)
    prompt = prompt + "\n\n" + build_json_instruction_suffix()

    client = get_client()
    response = client.responses.create(
        model=MODEL_NAME,
        instructions=(
            "You are a careful epidemiological reasoning assistant. "
            "Stay grounded in the provided graph evidence. "
            "Return valid JSON only."
        ),
        input=prompt,
        reasoning={"effort": "low"},
        max_output_tokens=MAX_OUTPUT_TOKENS,
    )

    raw_text = response.output_text
    if not raw_text or not raw_text.strip():
        raise ValueError("Model returned no visible text output.")

    parsed = parse_llm_json(raw_text)
    validate_llm_output(parsed)

    result_dict = {
        "backend": "in_memory",
        "failure_case": failure_case,
        "top_candidate_validation": validation_result,
        "llm_output": parsed,
    }

    timestamped_file, latest_file = save_demo_output(result_dict, raw_text)

    pretty_print_result(parsed)

    return {
        "result_dict": result_dict,
        "raw_text": raw_text,
        "parsed": parsed,
        "timestamped_file": timestamped_file,
        "latest_file": latest_file,
    }


if __name__ == "__main__":
    try:
        output = generate_llm_analysis()
        print(f"Saved result to: {output['timestamped_file']}")
        print(f"Updated latest result: {output['latest_file']}")
    except Exception as e:
        print("LLM reasoning failed.")
        print(f"Error: {e}")