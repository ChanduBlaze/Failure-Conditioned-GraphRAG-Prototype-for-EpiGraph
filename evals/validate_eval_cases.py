import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_FILE = PROJECT_ROOT / "evals" / "eval_cases.json"

REQUIRED_FIELDS = {
    "id",
    "task_type",
    "question",
    "expected_candidate_id",
}


def load_cases():
    if not EVAL_FILE.exists():
        raise FileNotFoundError(
            f"Could not find {EVAL_FILE.relative_to(PROJECT_ROOT)}"
        )

    try:
        with open(EVAL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"{EVAL_FILE.relative_to(PROJECT_ROOT)} is not valid JSON: "
            f"{exc.msg} at line {exc.lineno}, column {exc.colno}."
        ) from exc

    if not isinstance(data, list):
        raise ValueError("eval_cases.json must contain a JSON list.")

    return data


def validate_case(case, index):
    if not isinstance(case, dict):
        raise ValueError(f"Case at index {index} must be a JSON object.")

    missing = REQUIRED_FIELDS - set(case.keys())
    if missing:
        raise ValueError(
            f"Case at index {index} is missing required fields: {sorted(missing)}"
        )

    if not isinstance(case["id"], str) or not case["id"].strip():
        raise ValueError(f"Case at index {index} has invalid id.")

    if not isinstance(case["question"], str) or not case["question"].strip():
        raise ValueError(f"Case {case['id']} has invalid question.")

    if not isinstance(case["expected_candidate_id"], str):
        raise ValueError(f"Case {case['id']} has invalid expected_candidate_id.")

    if "expected_evidence_edges" in case:
        if not isinstance(case["expected_evidence_edges"], list):
            raise ValueError(
                f"Case {case['id']} expected_evidence_edges must be a list."
            )

    return True


def main():
    try:
        cases = load_cases()
    except (FileNotFoundError, ValueError) as exc:
        print(f"Validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    for index, case in enumerate(cases):
        try:
            validate_case(case, index)
        except ValueError as exc:
            print(f"Validation failed: {exc}", file=sys.stderr)
            raise SystemExit(1) from exc

    print("eval_cases.json validation passed.")
    print("-" * 40)
    print(f"Total cases: {len(cases)}")

    task_counts = {}
    for case in cases:
        task_type = case.get("task_type", "unknown")
        task_counts[task_type] = task_counts.get(task_type, 0) + 1

    print("\nTask types:")
    for task_type, count in sorted(task_counts.items()):
        print(f"- {task_type}: {count}")


if __name__ == "__main__":
    main()
