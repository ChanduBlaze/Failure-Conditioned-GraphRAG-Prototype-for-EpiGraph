"""
Build manual/Codex-fillable output templates for empirical hard-pilot prompts.

This does not call an LLM.

It reads prompt JSON files from:
    evals/empirical_hard_pilot/prompts/

and writes CSV templates to:
    evals/empirical_hard_pilot/model_outputs/

Each template includes:
    case_id, method, case_type, query, prompt, answer

The answer column is blank so outputs can be filled manually, through ChatGPT,
through Codex, or by a future API runner.

The scorer only requires:
    case_id, method, answer

so the extra query/prompt columns are for traceability.
"""
import argparse
import csv
import json
from pathlib import Path
from typing import Any


DEFAULT_PROMPT_DIR = Path("evals/empirical_hard_pilot/prompts")
DEFAULT_OUTPUT_DIR = Path("evals/empirical_hard_pilot/model_outputs")

PROMPT_FILES = {
    "empirical_llm_only": "empirical_llm_only_prompts.json",
    "empirical_text_rag_clean": "empirical_text_rag_clean_prompts.json",
    "empirical_text_rag_blended": "empirical_text_rag_blended_prompts.json",
    "empirical_graphrag_context": "empirical_graphrag_context_prompts.json",
}


FIELDNAMES = [
    "case_id",
    "method",
    "case_type",
    "target_signal",
    "query",
    "prompt",
    "answer",
]


def read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def prompt_to_template_row(prompt_row: dict[str, Any]) -> dict[str, str]:
    return {
        "case_id": str(prompt_row.get("case_id", "")),
        "method": str(prompt_row.get("method", "")),
        "case_type": str(prompt_row.get("case_type", "")),
        "target_signal": str(prompt_row.get("target_signal", "")),
        "query": str(prompt_row.get("query", "")),
        "prompt": str(prompt_row.get("prompt", "")),
        "answer": "",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-dir", default=str(DEFAULT_PROMPT_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    prompt_dir = Path(args.prompt_dir)
    output_dir = Path(args.output_dir)

    all_rows: list[dict[str, str]] = []

    for method, filename in PROMPT_FILES.items():
        prompt_path = prompt_dir / filename
        if not prompt_path.is_file():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")

        prompts = read_json(prompt_path)
        if not isinstance(prompts, list):
            raise ValueError(f"Prompt file must contain a list: {prompt_path}")

        rows = [prompt_to_template_row(row) for row in prompts]
        all_rows.extend(rows)

        out_path = output_dir / f"{method}_outputs_template.csv"
        write_csv(out_path, rows)
        print(f"Wrote {len(rows)} rows: {out_path}")

    combined_path = output_dir / "empirical_hard_pilot_model_outputs_template.csv"
    write_csv(combined_path, all_rows)
    print(f"Wrote {len(all_rows)} combined rows: {combined_path}")

    print("")
    print("Next manual/Codex workflow:")
    print("1. Open one of the *_outputs_template.csv files.")
    print("2. For each row, send the prompt to ChatGPT/Codex or another model.")
    print("3. Paste the model answer into the answer column.")
    print("4. Save a filled output CSV.")
    print("5. Score it with score_empirical_hard_pilot_outputs.py.")


if __name__ == "__main__":
    main()
