import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVALS_DIR = PROJECT_ROOT / "evals"
RESULTS_DIR = EVALS_DIR / "results"
DETAILED_RESULTS_FILE = RESULTS_DIR / "hard_pilot_repeated_results.csv"
SUMMARY_FILE = RESULTS_DIR / "hard_pilot_repeated_summary.csv"

for import_path in [PROJECT_ROOT, EVALS_DIR]:
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

try:
    from eval_metrics import mean, parse_bool, parse_float
    from run_graphrag_hard_pilot_eval import run_eval as run_graphrag_eval
    from run_llm_hard_pilot_eval import run_eval as run_llm_eval
    from run_text_rag_hard_pilot_eval import run_eval as run_text_rag_eval
except ModuleNotFoundError as exc:
    print(
        f"Repeated hard pilot evaluation failed: missing dependency: {exc}",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


METHODS = [
    ("LLM-only", run_llm_eval),
    ("Text-RAG", run_text_rag_eval),
    ("GraphRAG", run_graphrag_eval),
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run main hard-pilot LLM-based methods repeatedly."
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of repeated runs to execute for each method. Default: 3.",
    )
    return parser.parse_args()


def sample_std(values):
    # Sample standard deviation is used, with n - 1 in the denominator.
    values = list(values or [])

    if len(values) < 2:
        return 0.0

    avg = mean(values)
    variance = sum((value - avg) ** 2 for value in values) / (len(values) - 1)
    return variance ** 0.5


def add_run_and_method(rows, run_id, method):
    return [{"run_id": run_id, "method": method, **row} for row in rows]


def run_repeated_eval(run_count):
    if run_count < 1:
        raise ValueError("--runs must be at least 1.")

    print(
        "Warning: this will execute repeated hard-pilot evaluations, including "
        f"{run_count} run(s) for each LLM-based method and multiple LLM calls."
    )

    all_rows = []

    for run_id in range(1, run_count + 1):
        for method, run_eval in METHODS:
            print(f"Starting {method} run {run_id}/{run_count}...")

            try:
                rows = run_eval()
            except Exception as exc:
                print(
                    f"Repeated hard pilot evaluation failed during {method} "
                    f"run {run_id}: {exc}",
                    file=sys.stderr,
                )
                raise SystemExit(1) from exc

            all_rows.extend(add_run_and_method(rows, run_id, method))

    return all_rows


def group_rows_by_run_and_method(rows):
    grouped = defaultdict(list)

    for row in rows:
        grouped[(row["run_id"], row["method"])].append(row)

    return grouped


def summarize_run_method(run_id, method, rows):
    candidate_values = [
        1.0 if parse_bool(row.get("candidate_correct")) else 0.0
        for row in rows
    ]
    stronger_values = [
        1.0 if parse_bool(row.get("stronger_candidate_identified")) else 0.0
        for row in rows
        if row.get("expected_stronger_candidate_id")
    ]
    weak_values = [
        1.0 if parse_bool(row.get("weak_candidate_rejected")) else 0.0
        for row in rows
        if row.get("expected_weak_candidate_id")
    ]

    return {
        "run_id": run_id,
        "method": method,
        "case_count": len(rows),
        "candidate_accuracy": mean(candidate_values),
        "avg_present_edge_precision": mean(
            [parse_float(row.get("present_edge_precision")) for row in rows]
        ),
        "avg_present_edge_recall": mean(
            [parse_float(row.get("present_edge_recall")) for row in rows]
        ),
        "avg_missing_edge_recall": mean(
            [parse_float(row.get("missing_edge_recall")) for row in rows]
        ),
        "total_false_claims": sum(
            int(parse_float(row.get("missing_edge_false_claim_count"), 0.0))
            for row in rows
        ),
        "stronger_candidate_accuracy": mean(stronger_values),
        "weak_candidate_rejection_accuracy": mean(weak_values),
    }


def collect_run_summaries(rows):
    grouped = group_rows_by_run_and_method(rows)

    return [
        summarize_run_method(run_id, method, grouped[(run_id, method)])
        for run_id, method in sorted(grouped)
        if method
    ]


def aggregate_method_summaries(run_summaries):
    grouped = defaultdict(list)

    for summary in run_summaries:
        grouped[summary["method"]].append(summary)

    aggregates = []

    for method in [name for name, _run_eval in METHODS]:
        summaries = grouped.get(method, [])

        if not summaries:
            continue

        case_counts = [summary["case_count"] for summary in summaries]
        aggregate = {
            "method": method,
            "run_count": len(summaries),
            "cases_per_run": mean(case_counts),
        }

        for metric in [
            "candidate_accuracy",
            "avg_present_edge_precision",
            "avg_present_edge_recall",
            "avg_missing_edge_recall",
            "total_false_claims",
            "stronger_candidate_accuracy",
            "weak_candidate_rejection_accuracy",
        ]:
            values = [summary[metric] for summary in summaries]
            aggregate[f"{metric}_mean"] = mean(values)
            aggregate[f"{metric}_std"] = sample_std(values)

        aggregates.append(aggregate)

    return aggregates


def collect_fieldnames(rows):
    fieldnames = ["run_id", "method"]

    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)

    return fieldnames


def save_detailed_results(rows):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if not rows:
        return

    with open(DETAILED_RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=collect_fieldnames(rows))
        writer.writeheader()
        writer.writerows(rows)


def format_metric(value):
    return f"{value:.3f}"


def save_summary(aggregates):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "method",
        "run_count",
        "cases_per_run",
        "candidate_accuracy_mean",
        "candidate_accuracy_std",
        "avg_present_edge_precision_mean",
        "avg_present_edge_precision_std",
        "avg_present_edge_recall_mean",
        "avg_present_edge_recall_std",
        "avg_missing_edge_recall_mean",
        "avg_missing_edge_recall_std",
        "total_false_claims_mean",
        "total_false_claims_std",
        "stronger_candidate_accuracy_mean",
        "stronger_candidate_accuracy_std",
        "weak_candidate_rejection_accuracy_mean",
        "weak_candidate_rejection_accuracy_std",
    ]

    with open(SUMMARY_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for aggregate in aggregates:
            writer.writerow(
                {
                    "method": aggregate["method"],
                    "run_count": aggregate["run_count"],
                    "cases_per_run": format_metric(aggregate["cases_per_run"]),
                    "candidate_accuracy_mean": format_metric(
                        aggregate["candidate_accuracy_mean"]
                    ),
                    "candidate_accuracy_std": format_metric(
                        aggregate["candidate_accuracy_std"]
                    ),
                    "avg_present_edge_precision_mean": format_metric(
                        aggregate["avg_present_edge_precision_mean"]
                    ),
                    "avg_present_edge_precision_std": format_metric(
                        aggregate["avg_present_edge_precision_std"]
                    ),
                    "avg_present_edge_recall_mean": format_metric(
                        aggregate["avg_present_edge_recall_mean"]
                    ),
                    "avg_present_edge_recall_std": format_metric(
                        aggregate["avg_present_edge_recall_std"]
                    ),
                    "avg_missing_edge_recall_mean": format_metric(
                        aggregate["avg_missing_edge_recall_mean"]
                    ),
                    "avg_missing_edge_recall_std": format_metric(
                        aggregate["avg_missing_edge_recall_std"]
                    ),
                    "total_false_claims_mean": format_metric(
                        aggregate["total_false_claims_mean"]
                    ),
                    "total_false_claims_std": format_metric(
                        aggregate["total_false_claims_std"]
                    ),
                    "stronger_candidate_accuracy_mean": format_metric(
                        aggregate["stronger_candidate_accuracy_mean"]
                    ),
                    "stronger_candidate_accuracy_std": format_metric(
                        aggregate["stronger_candidate_accuracy_std"]
                    ),
                    "weak_candidate_rejection_accuracy_mean": format_metric(
                        aggregate["weak_candidate_rejection_accuracy_mean"]
                    ),
                    "weak_candidate_rejection_accuracy_std": format_metric(
                        aggregate["weak_candidate_rejection_accuracy_std"]
                    ),
                }
            )


def mean_std_text(aggregate, metric):
    return (
        f"{format_metric(aggregate[f'{metric}_mean'])}/"
        f"{format_metric(aggregate[f'{metric}_std'])}"
    )


def print_table(aggregates):
    if not aggregates:
        print("No repeated hard-pilot rows found.")
        return

    headers = [
        "Method",
        "Runs",
        "Cases/Run",
        "Cand Acc m/s",
        "Present R m/s",
        "Missing R m/s",
        "Stronger m/s",
        "Weak m/s",
    ]
    rows = [
        [
            aggregate["method"],
            str(aggregate["run_count"]),
            format_metric(aggregate["cases_per_run"]),
            mean_std_text(aggregate, "candidate_accuracy"),
            mean_std_text(aggregate, "avg_present_edge_recall"),
            mean_std_text(aggregate, "avg_missing_edge_recall"),
            mean_std_text(aggregate, "stronger_candidate_accuracy"),
            mean_std_text(aggregate, "weak_candidate_rejection_accuracy"),
        ]
        for aggregate in aggregates
    ]
    widths = [
        max(len(row[index]) for row in [headers] + rows)
        for index in range(len(headers))
    ]

    print("Repeated Hard Pilot Method Summary")
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
    print(f"Detailed results saved to: {DETAILED_RESULTS_FILE.relative_to(PROJECT_ROOT)}")
    print(f"Summary saved to: {SUMMARY_FILE.relative_to(PROJECT_ROOT)}")


def main():
    args = parse_args()

    try:
        rows = run_repeated_eval(args.runs)
    except ValueError as exc:
        print(f"Repeated hard pilot evaluation failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    run_summaries = collect_run_summaries(rows)
    aggregates = aggregate_method_summaries(run_summaries)
    save_detailed_results(rows)
    save_summary(aggregates)
    print_table(aggregates)


if __name__ == "__main__":
    main()
