"""
Combine empirical hard-pilot scored outputs across methods.

Inputs:
    evals/empirical_hard_pilot/empirical_llm_only_scored.csv
    evals/empirical_hard_pilot/empirical_text_rag_clean_scored.csv
    evals/empirical_hard_pilot/empirical_text_rag_blended_scored.csv
    evals/empirical_hard_pilot/empirical_graphrag_context_scored.csv

Output:
    evals/empirical_hard_pilot/empirical_hard_pilot_scored.csv

This script does not call an LLM.
"""
import argparse
import csv
from pathlib import Path


DEFAULT_INPUTS = [
    Path("evals/empirical_hard_pilot/empirical_llm_only_scored.csv"),
    Path("evals/empirical_hard_pilot/empirical_text_rag_clean_scored.csv"),
    Path("evals/empirical_hard_pilot/empirical_text_rag_blended_scored.csv"),
    Path("evals/empirical_hard_pilot/empirical_graphrag_context_scored.csv"),
]

DEFAULT_OUT = Path("evals/empirical_hard_pilot/empirical_hard_pilot_scored.csv")


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing scored file: {path}")

    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise ValueError(f"No header found in {path}")
        return fieldnames, list(reader)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    all_rows: list[dict[str, str]] = []
    expected_fieldnames: list[str] | None = None

    for path in DEFAULT_INPUTS:
        fieldnames, rows = read_rows(path)

        if expected_fieldnames is None:
            expected_fieldnames = fieldnames
        elif fieldnames != expected_fieldnames:
            raise ValueError(
                f"Column mismatch in {path}. "
                f"Expected {expected_fieldnames}, found {fieldnames}"
            )

        all_rows.extend(rows)

    if expected_fieldnames is None:
        raise ValueError("No input rows found.")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=expected_fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Wrote {len(all_rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
