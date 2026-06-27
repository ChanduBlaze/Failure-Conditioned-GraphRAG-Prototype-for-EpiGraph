"""Run deterministic artifact-level evaluation for the real-data extension.

This runner compares already-generated Text-RAG and GraphRAG context artifacts.
It does not call an LLM. Its purpose is to validate real-data information
parity before any LLM-based real Text-RAG or GraphRAG evaluation is added.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_CASES = Path("evals/real_eval_cases.json")
DEFAULT_TEXT_CORPUS = Path(
    "data/real_processed/real_text_rag_corpus.json"
)
DEFAULT_GRAPH_CONTEXT = Path(
    "data/real_processed/real_graph_context.json"
)
DEFAULT_OUTPUT_DIR = Path("evals/results_real")

TEXT_RESULTS_NAME = "real_text_rag_results.csv"
GRAPH_RESULTS_NAME = "real_graphrag_context_results.csv"
SUMMARY_NAME = "real_summary.csv"

RESULT_COLUMNS = [
    "case_id",
    "method",
    "predicted_candidate_id",
    "candidate_correct",
    "mentioned_evidence_edges",
    "identified_missing_edges",
    "status_correct",
    "present_edge_recall",
    "missing_edge_recall",
    "lag_correct",
    "score_meets_minimum",
    "must_not_include_violations",
    "notes",
]

SUMMARY_COLUMNS = [
    "method",
    "case_count",
    "candidate_accuracy",
    "avg_present_edge_recall",
    "avg_missing_edge_recall",
    "status_accuracy",
    "lag_accuracy",
    "score_threshold_accuracy",
    "total_must_not_include_violations",
]

MISSING_STATUSES = {"missing", "insufficient_data"}
NUMBER_PATTERN = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
SCORE_PATTERN = re.compile(
    rf"\bscore\s*[:=]\s*({NUMBER_PATTERN})",
    re.IGNORECASE,
)
LAG_PATTERN = re.compile(
    r"(?:\blag\s+weeks\s*:|\bbest\s+lag\s*=)\s*([-+]?\d+)",
    re.IGNORECASE,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Deterministically evaluate real Text-RAG and GraphRAG artifacts "
            "without an LLM or a Neo4j connection."
        )
    )
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument(
        "--text-corpus",
        type=Path,
        default=DEFAULT_TEXT_CORPUS,
    )
    parser.add_argument(
        "--graph-context",
        type=Path,
        default=DEFAULT_GRAPH_CONTEXT,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def load_json(path: Path, expected_type: type, description: str) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"{description} not found: {path}")
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


def validate_output_dir(output_dir: Path) -> Path:
    """Allow writes only below evals/results_real and never evals/results."""
    allowed_root = (Path.cwd() / DEFAULT_OUTPUT_DIR).resolve()
    forbidden_root = (Path.cwd() / "evals" / "results").resolve()
    resolved_output = output_dir.resolve()

    try:
        resolved_output.relative_to(forbidden_root)
    except ValueError:
        pass
    else:
        raise ValueError("Refusing to write real evaluation under evals/results/.")

    try:
        resolved_output.relative_to(allowed_root)
    except ValueError as exc:
        raise ValueError(
            "Real evaluation output must be under evals/results_real/."
        ) from exc
    return resolved_output


def normalize_string_set(values: Any) -> set[str]:
    if not isinstance(values, list):
        return set()
    return {
        str(value)
        for value in values
        if value is not None and str(value)
    }


def edge_recall(expected: set[str], observed: set[str]) -> float:
    return 1.0 if expected.issubset(observed) else 0.0


def forbidden_phrase_count(text: str, phrases: Any) -> int:
    lowered_text = text.lower()
    if not isinstance(phrases, list):
        return 0
    return sum(
        1
        for phrase in phrases
        if phrase is not None
        and str(phrase).strip()
        and str(phrase).strip().lower() in lowered_text
    )


def extract_scores(text: str) -> list[float]:
    scores: list[float] = []
    for match in SCORE_PATTERN.finditer(text):
        try:
            scores.append(float(match.group(1)))
        except ValueError:
            continue
    return scores


def text_contains_expected_lag(text: str, expected_lag: Any) -> bool:
    try:
        expected = int(expected_lag)
    except (TypeError, ValueError):
        return False
    return any(int(match.group(1)) == expected for match in LAG_PATTERN.finditer(text))


def chunk_match_rank(
    chunk: dict[str, Any],
    case_id: str,
    failure_case_id: str,
) -> int | None:
    chunk_case_id = str(chunk.get("case_id", ""))
    if chunk_case_id == failure_case_id:
        return 0
    if chunk_case_id == case_id:
        return 1

    chunk_id = str(chunk.get("chunk_id", ""))
    if failure_case_id and failure_case_id in chunk_id:
        return 2
    if case_id and case_id in chunk_id:
        return 3
    return None


def find_matching_chunks(
    case: dict[str, Any],
    corpus: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    case_id = str(case.get("id", ""))
    failure_case_id = str(case.get("failure_case_id", ""))
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for chunk in corpus:
        if not isinstance(chunk, dict):
            continue
        rank = chunk_match_rank(chunk, case_id, failure_case_id)
        if rank is not None:
            ranked.append((rank, str(chunk.get("chunk_id", "")), chunk))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in ranked]


def base_result(
    case: dict[str, Any],
    method: str,
    predicted_candidate_id: str,
    mentioned_edges: set[str],
    missing_edges: set[str],
    status_correct: bool,
    lag_correct: bool,
    score_meets_minimum: bool,
    violations: int,
    notes: str | None = None,
) -> dict[str, Any]:
    expected_present = normalize_string_set(
        case.get("expected_present_edges", [])
    )
    expected_missing = normalize_string_set(
        case.get("expected_missing_edges", [])
    )
    return {
        "case_id": str(case.get("id", "")),
        "method": method,
        "predicted_candidate_id": predicted_candidate_id,
        "candidate_correct": (
            predicted_candidate_id
            == str(case.get("expected_candidate_id", ""))
        ),
        "mentioned_evidence_edges": ";".join(sorted(mentioned_edges)),
        "identified_missing_edges": ";".join(sorted(missing_edges)),
        "status_correct": status_correct,
        "present_edge_recall": edge_recall(
            expected_present,
            mentioned_edges,
        ),
        "missing_edge_recall": edge_recall(
            expected_missing,
            missing_edges,
        ),
        "lag_correct": lag_correct,
        "score_meets_minimum": score_meets_minimum,
        "must_not_include_violations": violations,
        "notes": notes if notes is not None else str(case.get("notes", "")),
    }


def evaluate_text_case(
    case: dict[str, Any],
    corpus: list[dict[str, Any]],
) -> dict[str, Any]:
    matching_chunks = find_matching_chunks(case, corpus)
    if not matching_chunks:
        return base_result(
            case,
            "text_rag",
            "",
            set(),
            set(),
            False,
            False,
            False,
            0,
            "No matching Text-RAG chunks found.",
        )

    top_chunk = matching_chunks[0]
    predicted_candidate_id = str(top_chunk.get("candidate_id", ""))
    candidate_chunks = [
        chunk
        for chunk in matching_chunks
        if str(chunk.get("candidate_id", "")) == predicted_candidate_id
    ]
    if not candidate_chunks:
        candidate_chunks = [top_chunk]

    mentioned_edges = {
        str(chunk.get("edge_type"))
        for chunk in candidate_chunks
        if str(chunk.get("status", "")) == "present"
        and chunk.get("edge_type")
    }
    missing_edges = {
        str(chunk.get("edge_type"))
        for chunk in candidate_chunks
        if str(chunk.get("status", "")) in MISSING_STATUSES
        and chunk.get("edge_type")
    }
    expected_status = str(case.get("expected_status", ""))
    status_correct = any(
        str(chunk.get("status", "")) == expected_status
        for chunk in candidate_chunks
    )

    combined_text = "\n".join(
        str(chunk.get("text", "")) for chunk in candidate_chunks
    )
    lag_correct = text_contains_expected_lag(
        combined_text,
        case.get("expected_lag_weeks"),
    )
    scores = extract_scores(combined_text)
    try:
        minimum_score = float(case.get("minimum_expected_score"))
    except (TypeError, ValueError):
        minimum_score = None
    score_meets_minimum = (
        minimum_score is not None
        and bool(scores)
        and max(scores) >= minimum_score
    )
    violations = forbidden_phrase_count(
        combined_text,
        case.get("must_not_include", []),
    )

    return base_result(
        case,
        "text_rag",
        predicted_candidate_id,
        mentioned_edges,
        missing_edges,
        status_correct,
        lag_correct,
        score_meets_minimum,
        violations,
    )


def numeric_score(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def evaluate_graph_case(
    case: dict[str, Any],
    graph_context: dict[str, Any],
) -> dict[str, Any]:
    valid_case_ids = {
        str(case.get("id", "")),
        str(case.get("failure_case_id", "")),
    }
    if str(graph_context.get("case_id", "")) not in valid_case_ids:
        return base_result(
            case,
            "graphrag_context",
            "",
            set(),
            set(),
            False,
            False,
            False,
            0,
            "Graph context does not match this evaluation case.",
        )

    candidates = [
        candidate
        for candidate in graph_context.get("candidates", [])
        if isinstance(candidate, dict)
    ]
    candidates.sort(
        key=lambda candidate: (
            -numeric_score(candidate.get("score")),
            str(candidate.get("candidate_id", "")),
        )
    )
    if not candidates:
        return base_result(
            case,
            "graphrag_context",
            "",
            set(),
            set(),
            False,
            False,
            False,
            0,
            "No candidates found in GraphRAG context.",
        )

    top_candidate = candidates[0]
    predicted_candidate_id = str(top_candidate.get("candidate_id", ""))
    evidence_edges = [
        edge
        for edge in top_candidate.get("evidence_edges", [])
        if isinstance(edge, dict)
    ]
    evidence_edges.sort(
        key=lambda edge: str(edge.get("evidence_claim_id", ""))
    )

    mentioned_edges = {
        str(edge.get("edge_type"))
        for edge in evidence_edges
        if str(edge.get("status", "")) == "present"
        and edge.get("edge_type")
    }
    missing_edges = {
        str(edge.get("edge_type"))
        for edge in evidence_edges
        if str(edge.get("status", "")) in MISSING_STATUSES
        and edge.get("edge_type")
    }
    expected_status = str(case.get("expected_status", ""))
    status_correct = any(
        str(edge.get("status", "")) == expected_status
        for edge in evidence_edges
    )

    try:
        expected_lag = int(case.get("expected_lag_weeks"))
    except (TypeError, ValueError):
        expected_lag = None
    observed_lags: list[int] = []
    for edge in evidence_edges:
        try:
            observed_lags.append(int(edge["lag_weeks"]))
        except (KeyError, TypeError, ValueError):
            continue
    lag_correct = (
        expected_lag is not None and expected_lag in observed_lags
    )

    try:
        minimum_score = float(case.get("minimum_expected_score"))
    except (TypeError, ValueError):
        minimum_score = None
    evidence_scores = [
        numeric_score(edge.get("score"))
        for edge in evidence_edges
        if edge.get("score") is not None
    ]
    if not evidence_scores and top_candidate.get("score") is not None:
        evidence_scores.append(numeric_score(top_candidate.get("score")))
    score_meets_minimum = (
        minimum_score is not None
        and bool(evidence_scores)
        and max(evidence_scores) >= minimum_score
    )

    evidence_text = "\n".join(
        part
        for edge in evidence_edges
        for part in (
            str(edge.get("evidence_sentence", "")),
            str(edge.get("limitation", "")),
        )
        if part
    )
    violations = forbidden_phrase_count(
        evidence_text,
        case.get("must_not_include", []),
    )

    return base_result(
        case,
        "graphrag_context",
        predicted_candidate_id,
        mentioned_edges,
        missing_edges,
        status_correct,
        lag_correct,
        score_meets_minimum,
        violations,
    )


def summarize(method: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    case_count = len(rows)

    def average(column: str) -> float:
        if not rows:
            return 0.0
        return sum(float(row[column]) for row in rows) / case_count

    return {
        "method": method,
        "case_count": case_count,
        "candidate_accuracy": average("candidate_correct"),
        "avg_present_edge_recall": average("present_edge_recall"),
        "avg_missing_edge_recall": average("missing_edge_recall"),
        "status_accuracy": average("status_correct"),
        "lag_accuracy": average("lag_correct"),
        "score_threshold_accuracy": average("score_meets_minimum"),
        "total_must_not_include_violations": sum(
            int(row["must_not_include_violations"]) for row in rows
        ),
    }


def write_csv(
    path: Path,
    columns: list[str],
    rows: list[dict[str, Any]],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=columns,
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def run_evaluation(
    cases: list[dict[str, Any]],
    text_corpus: list[dict[str, Any]],
    graph_context: dict[str, Any],
    output_dir: Path,
) -> tuple[Path, Path, Path]:
    if not cases:
        raise ValueError("Real evaluation case list is empty.")
    if any(not isinstance(case, dict) for case in cases):
        raise ValueError("Every real evaluation case must be a JSON object.")

    resolved_output = validate_output_dir(output_dir)
    text_rows = [
        evaluate_text_case(case, text_corpus) for case in cases
    ]
    graph_rows = [
        evaluate_graph_case(case, graph_context) for case in cases
    ]
    summary_rows = [
        summarize("text_rag", text_rows),
        summarize("graphrag_context", graph_rows),
    ]

    resolved_output.mkdir(parents=True, exist_ok=True)
    text_path = resolved_output / TEXT_RESULTS_NAME
    graph_path = resolved_output / GRAPH_RESULTS_NAME
    summary_path = resolved_output / SUMMARY_NAME
    write_csv(text_path, RESULT_COLUMNS, text_rows)
    write_csv(graph_path, RESULT_COLUMNS, graph_rows)
    write_csv(summary_path, SUMMARY_COLUMNS, summary_rows)
    return text_path, graph_path, summary_path


def main() -> int:
    args = parse_args()
    try:
        cases = load_json(args.cases, list, "Evaluation cases")
        text_corpus = load_json(args.text_corpus, list, "Text-RAG corpus")
        graph_context = load_json(
            args.graph_context,
            dict,
            "GraphRAG context",
        )
        output_paths = run_evaluation(
            cases,
            text_corpus,
            graph_context,
            args.output_dir,
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"Real evaluation failed: {exc}", file=sys.stderr)
        return 1

    print("Deterministic real-data evaluation complete.")
    print(f"Cases evaluated: {len(cases)}")
    for output_path in output_paths:
        print(f"Output: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
