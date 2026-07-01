"""Build leakage-controlled prompts for an external real-data LLM baseline.

The prompts contain only failure-case identity, target name, candidate names
and IDs, and a classification question. No evidence artifact is sent to an
LLM, and this script does not call an LLM itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


DEFAULT_CASES = Path("evals/real_eval_cases.json")
DEFAULT_GRAPH_CONTEXT = Path(
    "data/real_processed/real_graph_context.json"
)
DEFAULT_OUTPUT = Path("evals/results_real/real_llm_only_prompts.json")

RESTRICTED_PROMPT_TERMS = [
    "score",
    "threshold",
    "lag",
    "lag_weeks",
    "evidence_sentence",
    "evidence sentence",
    "limitation",
    "source_dataset",
    "source dataset",
    "leading_indicator",
    "leading_indicator_for",
    "support_edges",
    "support edges",
    "graph edge",
    "text-rag",
    "graphrag",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Build real-data LLM-only prompts without evidence scores, lags, "
            "provenance, Text-RAG chunks, or graph context."
        )
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument(
        "--graph-context",
        type=Path,
        default=DEFAULT_GRAPH_CONTEXT,
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def read_json(path: Path, expected_type: type, description: str) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"{description} file not found: {path}")
    try:
        with path.open("r", encoding="utf-8") as input_file:
            value = json.load(input_file)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {description} {path}: {exc}") from exc
    if not isinstance(value, expected_type):
        raise ValueError(
            f"{description} must contain a {expected_type.__name__}."
        )
    return value


def candidate_names_by_id(
    graph_context: dict[str, Any],
) -> dict[str, str]:
    names = {
        str(candidate.get("candidate_id", "")): str(
            candidate.get("candidate_name", "")
        )
        for candidate in graph_context.get("candidates", [])
        if isinstance(candidate, dict) and candidate.get("candidate_id")
    }
    for node in graph_context.get("support_nodes", []):
        if (
            isinstance(node, dict)
            and node.get("type") == "CandidateDriver"
            and node.get("id")
        ):
            names.setdefault(str(node["id"]), str(node.get("name", "")))
    return names


def validate_prompt_safety(
    prompt: str,
    restricted_values: tuple[str, ...] = (),
) -> None:
    lowered = prompt.lower()
    found = [term for term in RESTRICTED_PROMPT_TERMS if term in lowered]
    found.extend(
        value
        for value in restricted_values
        if value and value.lower() in lowered
    )
    if found:
        raise ValueError(
            "Generated LLM-only prompt contains restricted evidence fields: "
            + ", ".join(found)
        )


def build_prompts(
    cases: list[dict[str, Any]],
    graph_context: dict[str, Any],
) -> list[dict[str, str]]:
    failure_case = graph_context.get("failure_case")
    target_signal = graph_context.get("target_signal")
    if not isinstance(failure_case, dict) or not failure_case.get("id"):
        raise ValueError("Graph context has no failure_case identity.")
    if not isinstance(target_signal, dict) or not target_signal.get("name"):
        raise ValueError("Graph context has no target_signal name.")

    candidate_names = candidate_names_by_id(graph_context)
    if not candidate_names:
        raise ValueError("Graph context has no candidate names.")

    candidate_lines = [
        f"- {candidate_names[candidate_id]} ({candidate_id})"
        for candidate_id in sorted(candidate_names)
    ]
    candidate_block = "\n".join(candidate_lines)
    failure_case_id = str(failure_case["id"])
    target_name = str(target_signal["name"])
    neutral_failure_description = (
        f"{target_name} forecast underprediction."
    )

    prompts: list[dict[str, str]] = []
    for case in cases:
        if not isinstance(case, dict):
            raise ValueError("Every evaluation case must be a JSON object.")
        case_id = str(case.get("id", ""))
        expected_candidate_id = str(
            case.get("expected_candidate_id", "")
        )
        if not case_id or not expected_candidate_id:
            raise ValueError(
                "Every evaluation case needs id and expected_candidate_id."
            )
        if expected_candidate_id not in candidate_names:
            raise ValueError(
                f"Candidate {expected_candidate_id!r} from case {case_id!r} "
                "is absent from graph context."
            )
        case_failure_id = str(
            case.get("failure_case_id", failure_case_id)
        )
        if case_failure_id != failure_case_id:
            raise ValueError(
                f"Case {case_id!r} does not match graph failure case "
                f"{failure_case_id!r}."
            )

        candidate_name = candidate_names[expected_candidate_id]
        prompt = (
            f"Failure case: {neutral_failure_description}\n"
            f"Target signal: {target_name}\n"
            "Candidates under consideration:\n"
            f"{candidate_block}\n\n"
            f"Candidate to assess: {candidate_name} "
            f"({expected_candidate_id})\n"
            "Using only general domain knowledge, classify whether this "
            "candidate is supported, unsupported, or has missing evidence as "
            "a leading indicator for the target signal. State the candidate "
            "ID and classification clearly. Do not claim that an association "
            "proves causality or that the candidate definitively causes the "
            "target."
        )
        validate_prompt_safety(
            prompt,
            (
                failure_case_id,
                "wastewater_leading_indicator",
            ),
        )
        prompts.append(
            {
                "case_id": case_id,
                "method": "llm_only",
                "failure_case_id": failure_case_id,
                "expected_candidate_id": expected_candidate_id,
                "prompt": prompt,
            }
        )
    return prompts


def validate_output_path(path: Path) -> None:
    forbidden = (Path.cwd() / "evals" / "results").resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(forbidden)
    except ValueError:
        return
    raise ValueError("Refusing to write LLM-only prompts under evals/results/.")


def write_prompts(path: Path, prompts: list[dict[str, str]]) -> None:
    validate_output_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(prompts, output_file, indent=2, ensure_ascii=False)
        output_file.write("\n")


def main() -> int:
    args = parse_args()
    try:
        cases = read_json(args.cases, list, "Evaluation cases")
        graph_context = read_json(
            args.graph_context,
            dict,
            "Graph context",
        )
        prompts = build_prompts(cases, graph_context)
        write_prompts(args.output, prompts)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"LLM-only prompt build failed: {exc}", file=sys.stderr)
        return 1

    print(f"LLM-only prompts built: {len(prompts)}")
    print(f"Output: {args.output}")
    print("No LLM was called.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
