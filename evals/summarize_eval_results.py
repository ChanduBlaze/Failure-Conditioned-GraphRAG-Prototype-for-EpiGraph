import csv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
SUMMARY_FILE = RESULTS_DIR / "eval_summary.csv"

RESULT_FILES = [
    ("KG-only", RESULTS_DIR / "kg_only_results.csv"),
    ("LLM-only", RESULTS_DIR / "llm_only_results.csv"),
    ("GraphRAG", RESULTS_DIR / "graphrag_results.csv"),
]


def load_rows(path):
    if not path.exists():
        return None

    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_bool(value):
    return str(value).strip().lower() in {"true", "1", "yes"}


def mean(values):
    return sum(values) / len(values) if values else 0.0


def summarize_method(method_name, rows):
    case_count = len(rows)

    top1_accuracy = mean(
        [1.0 if parse_bool(row.get("top1_correct")) else 0.0 for row in rows]
    )
    avg_evidence_precision = mean(
        [parse_float(row.get("evidence_precision")) for row in rows]
    )
    avg_evidence_recall = mean(
        [parse_float(row.get("evidence_recall")) for row in rows]
    )
    total_hallucinated_evidence_count = sum(
        int(parse_float(row.get("hallucinated_evidence_count"), 0.0))
        for row in rows
    )

    return {
        "method_name": method_name,
        "case_count": case_count,
        "top1_accuracy": top1_accuracy,
        "avg_evidence_precision": avg_evidence_precision,
        "avg_evidence_recall": avg_evidence_recall,
        "total_hallucinated_evidence_count": total_hallucinated_evidence_count,
    }


def collect_summaries():
    summaries = []
    missing_files = []

    for method_name, path in RESULT_FILES:
        rows = load_rows(path)

        if rows is None:
            missing_files.append(path.relative_to(PROJECT_ROOT))
            continue

        summaries.append(summarize_method(method_name, rows))

    return summaries, missing_files


def save_summary(summaries):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "method_name",
        "case_count",
        "top1_accuracy",
        "avg_evidence_precision",
        "avg_evidence_recall",
        "total_hallucinated_evidence_count",
    ]

    with open(SUMMARY_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for summary in summaries:
            writer.writerow(
                {
                    "method_name": summary["method_name"],
                    "case_count": summary["case_count"],
                    "top1_accuracy": f"{summary['top1_accuracy']:.3f}",
                    "avg_evidence_precision": (
                        f"{summary['avg_evidence_precision']:.3f}"
                    ),
                    "avg_evidence_recall": f"{summary['avg_evidence_recall']:.3f}",
                    "total_hallucinated_evidence_count": summary[
                        "total_hallucinated_evidence_count"
                    ],
                }
            )


def print_table(summaries, missing_files):
    if missing_files:
        print("Missing result files skipped:")
        for path in missing_files:
            print(f"- {path}")
        print()

    if not summaries:
        print("No evaluation result files found.")
        return

    headers = [
        "Method",
        "Cases",
        "Top-1 Acc",
        "Evidence P",
        "Evidence R",
        "Hallucinated",
    ]

    rows = [
        [
            summary["method_name"],
            str(summary["case_count"]),
            f"{summary['top1_accuracy']:.3f}",
            f"{summary['avg_evidence_precision']:.3f}",
            f"{summary['avg_evidence_recall']:.3f}",
            str(summary["total_hallucinated_evidence_count"]),
        ]
        for summary in summaries
    ]

    widths = [
        max(len(row[index]) for row in [headers] + rows)
        for index in range(len(headers))
    ]

    header_line = "  ".join(
        headers[index].ljust(widths[index]) for index in range(len(headers))
    )
    divider = "  ".join("-" * width for width in widths)

    print("Evaluation Summary")
    print("-" * 40)
    print(header_line)
    print(divider)

    for row in rows:
        print(
            "  ".join(
                row[index].ljust(widths[index]) for index in range(len(headers))
            )
        )

    print()
    print(f"Summary saved to: {SUMMARY_FILE.relative_to(PROJECT_ROOT)}")


def main():
    summaries, missing_files = collect_summaries()
    save_summary(summaries)
    print_table(summaries, missing_files)


if __name__ == "__main__":
    main()
