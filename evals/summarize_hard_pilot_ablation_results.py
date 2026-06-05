import csv
import sys
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "evals" / "results"
INPUT_FILE = RESULTS_DIR / "hard_pilot_ablation_results.csv"
SUMMARY_FILE = RESULTS_DIR / "hard_pilot_ablation_summary.csv"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from eval_metrics import mean, parse_bool, parse_float
except ModuleNotFoundError as exc:
    print(
        f"Hard pilot ablation summary failed: missing dependency: {exc}",
        file=sys.stderr,
    )
    raise SystemExit(1) from exc


def load_rows(path):
    if not path.exists():
        raise FileNotFoundError(f"Could not find {path.relative_to(PROJECT_ROOT)}")

    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def group_rows_by_variant(rows):
    grouped = defaultdict(list)

    for row in rows:
        grouped[row.get("variant_name", "")].append(row)

    return grouped


def summarize_variant(variant_name, rows):
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
        "variant_name": variant_name,
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
        "total_false_edge_claims": sum(
            int(parse_float(row.get("missing_edge_false_claim_count"), 0.0))
            for row in rows
        ),
        "stronger_candidate_accuracy": mean(stronger_values),
        "weak_candidate_rejection_accuracy": mean(weak_values),
    }


def collect_summaries(rows):
    grouped = group_rows_by_variant(rows)

    return [
        summarize_variant(variant_name, grouped[variant_name])
        for variant_name in sorted(grouped)
        if variant_name
    ]


def format_metric(value):
    return f"{value:.3f}"


def save_summary(summaries):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "variant_name",
        "case_count",
        "candidate_accuracy",
        "avg_present_edge_precision",
        "avg_present_edge_recall",
        "avg_missing_edge_recall",
        "total_false_edge_claims",
        "stronger_candidate_accuracy",
        "weak_candidate_rejection_accuracy",
    ]

    with open(SUMMARY_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for summary in summaries:
            writer.writerow(
                {
                    "variant_name": summary["variant_name"],
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
                    "total_false_edge_claims": summary["total_false_edge_claims"],
                    "stronger_candidate_accuracy": format_metric(
                        summary["stronger_candidate_accuracy"]
                    ),
                    "weak_candidate_rejection_accuracy": format_metric(
                        summary["weak_candidate_rejection_accuracy"]
                    ),
                }
            )


def print_table(summaries):
    if not summaries:
        print("No ablation rows found.")
        return

    headers = [
        "Variant",
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
            summary["variant_name"],
            str(summary["case_count"]),
            format_metric(summary["candidate_accuracy"]),
            format_metric(summary["avg_present_edge_precision"]),
            format_metric(summary["avg_present_edge_recall"]),
            format_metric(summary["avg_missing_edge_recall"]),
            str(summary["total_false_edge_claims"]),
            format_metric(summary["stronger_candidate_accuracy"]),
            format_metric(summary["weak_candidate_rejection_accuracy"]),
        ]
        for summary in summaries
    ]

    widths = [
        max(len(row[index]) for row in [headers] + rows)
        for index in range(len(headers))
    ]

    print("Hard Pilot Ablation Summary")
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
    try:
        rows = load_rows(INPUT_FILE)
    except FileNotFoundError as exc:
        print(f"Hard pilot ablation summary failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    summaries = collect_summaries(rows)
    save_summary(summaries)
    print_table(summaries)


if __name__ == "__main__":
    main()
