import csv
import subprocess
from pathlib import Path
from datetime import datetime

RUNS = 5

results_dir = Path("evals/results")
out_path = results_dir / "repeated_hard_pilot_summary.csv"

def run_cmd(cmd):
    print("\n$ " + " ".join(cmd))
    subprocess.run(cmd, check=True)

def read_summary(run_id):
    summary_path = results_dir / "hard_pilot_summary.csv"

    with summary_path.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    enriched = []
    for row in rows:
        row = dict(row)
        row["run_id"] = run_id
        row["timestamp"] = datetime.now().isoformat(timespec="seconds")
        enriched.append(row)

    return enriched

all_rows = []

print("Running deterministic KG-only baseline once...")
run_cmd(["python", "evals/run_hard_pilot_eval.py"])

for run_id in range(1, RUNS + 1):
    print("\n" + "=" * 80)
    print(f"Repeated evaluation run {run_id}/{RUNS}")
    print("=" * 80)

    run_cmd(["python", "evals/run_llm_hard_pilot_eval.py"])
    run_cmd(["python", "evals/run_text_rag_hard_pilot_eval.py"])
    run_cmd(["python", "evals/run_graphrag_hard_pilot_eval.py"])
    run_cmd(["python", "evals/summarize_hard_pilot_results.py"])

    all_rows.extend(read_summary(run_id))

fieldnames = [
    "run_id",
    "timestamp",
    "method_name",
    "case_count",
    "candidate_accuracy",
    "avg_present_edge_precision",
    "avg_present_edge_recall",
    "avg_missing_edge_recall",
    "missing_edge_false_claim_count",
    "stronger_candidate_accuracy",
    "weak_candidate_rejection_accuracy",
]

with out_path.open("w", encoding="utf-8", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in all_rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})

print("\nRepeated evaluation complete.")
print(f"Saved to: {out_path}")
