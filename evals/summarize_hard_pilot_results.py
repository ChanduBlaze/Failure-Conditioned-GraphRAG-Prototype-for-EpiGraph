import csv
from pathlib import Path

from eval_metrics import mean, parse_bool, parse_float


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
SUMMARY_FILE = RESULTS_DIR / "hard_pilot_summary.csv"

RESULT_FILES = [
    ("KG-only", RESULTS_DIR / "hard_pilot_results.csv"),
    ("LLM-only", RESULTS_DIR / "llm_hard_pilot_results.csv"),
    ("Text-RAG", RESULTS_DIR / "text_rag_hard_pilot_results.csv"),
    ("GraphRAG", RESULTS_DIR / "graphrag_hard_pilot_results.csv"),
]


def load_rows(path):
    if not path.exists():
        return None

    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def metric_column(row, preferred, fallback=None):
    if preferred in row:
        return row.get(preferred)

    if fallback and fallback in row:
        return row.get(fallback)

    return ""


def summarize_method(method_name, rows):
    candidate_values = [
        1.0 if parse_bool(row.get("candidate_correct")) else 0.0
        for row in rows
        if row.get("candidate_correct") not in {None, ""}
    ]
    stronger_values = [
        1.0
        if parse_bool(
            metric_column(
                row,
                "stronger_candidate_identified",
                fallback="stronger_candidate_ranks_above",
            )
        )
        else 0.0
        for row in rows
        if row.get("expected_stronger_candidate_id")
    ]
    weak_values = [
        1.0
        if parse_bool(
            metric_column(
                row,
                "weak_candidate_rejected",
                fallback="weak_candidate_not_top",
            )
        )
        else 0.0
        for row in rows
        if row.get("expected_weak_candidate_id")
    ]

    candidate_accuracy = mean(candidate_values) if candidate_values else ""

    return {
        "method_name": method_name,
        "case_count": len(rows),
        "candidate_accuracy": candidate_accuracy,
        "avg_present_edge_precision": mean(
            [parse_float(row.get("present_edge_precision")) for row in rows]
        ),
        "avg_present_edge_recall": mean(
            [parse_float(row.get("present_edge_recall")) for row in rows]
        ),
        "avg_missing_edge_recall": mean(
            [parse_float(row.get("missing_edge_recall")) for row in rows]
        ),
        "total_missing_edge_false_claim_count": sum(
            int(parse_float(row.get("missing_edge_false_claim_count"), 0.0))
            for row in rows
        ),
        "stronger_candidate_identification_accuracy": mean(stronger_values),
        "weak_candidate_rejection_accuracy": mean(weak_values),
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


def format_metric(value):
    if value == "":
        return ""

    return f"{value:.3f}"


def save_summary(summaries):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "method_name",
        "case_count",
        "candidate_accuracy",
        "avg_present_edge_precision",
        "avg_present_edge_recall",
        "avg_missing_edge_recall",
        "total_missing_edge_false_claim_count",
        "stronger_candidate_identification_accuracy",
        "weak_candidate_rejection_accuracy",
    ]

    with open(SUMMARY_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for summary in summaries:
            writer.writerow(
                {
                    "method_name": summary["method_name"],
                    "case_count": summary["case_count"],
                    "candidate_accuracy": format_metric(
                        summary["candidate_accuracy"]
                    ),
                    "avg_present_edge_precision": format_metric(
                        summary["avg_present_edge_precision"]
                    ),
                    "avg_present_edge_recall": format_metric(
                        summary["avg_present_edge_recall"]
                    ),
                    "avg_missing_edge_recall": format_metric(
                        summary["avg_missing_edge_recall"]
                    ),
                    "total_missing_edge_false_claim_count": summary[
                        "total_missing_edge_false_claim_count"
                    ],
                    "stronger_candidate_identification_accuracy": format_metric(
                        summary["stronger_candidate_identification_accuracy"]
                    ),
                    "weak_candidate_rejection_accuracy": format_metric(
                        summary["weak_candidate_rejection_accuracy"]
                    ),
                }
            )


def print_table(summaries, missing_files):
    if missing_files:
        print("Missing hard pilot result files skipped:")
        for path in missing_files:
            print(f"- {path}")
        print()

    if not summaries:
        print("No hard pilot result files found.")
        return

    headers = [
        "Method",
        "Cases",
        "Cand Acc",
        "Present P",
        "Present R",
        "Missing R",
        "False Claims",
        "Stronger Acc",
        "Weak Reject",
    ]

    rows = [
        [
            summary["method_name"],
            str(summary["case_count"]),
            format_metric(summary["candidate_accuracy"]),
            format_metric(summary["avg_present_edge_precision"]),
            format_metric(summary["avg_present_edge_recall"]),
            format_metric(summary["avg_missing_edge_recall"]),
            str(summary["total_missing_edge_false_claim_count"]),
            format_metric(summary["stronger_candidate_identification_accuracy"]),
            format_metric(summary["weak_candidate_rejection_accuracy"]),
        ]
        for summary in summaries
    ]

    widths = [
        max(len(row[index]) for row in [headers] + rows)
        for index in range(len(headers))
    ]

    print("Hard Pilot Evaluation Summary")
    print("-" * 40)
    print(
        "  ".join(
            headers[index].ljust(widths[index]) for index in range(len(headers))
        )
    )
    print("  ".join("-" * width for width in widths))

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
