# part 3 - non-determinism experiment.
# fires the same fixed input through agents_demo.py's pipeline 20x at temp 0.7
# and 20x at temp 0.0, dumps the raw tags/latency for every run into
# reports/hw01/raw/, then works out the distinct-tag-set/intersection/percentile

import csv
import json
import os
import sys
import time

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(REPO_ROOT, "code", "web_application"))

import numpy as np

from agents_demo import build_llm, run_pipeline

HW01_DIR = os.path.join(REPO_ROOT, "reports", "hw01")
INPUT_PATH = os.path.join(HW01_DIR, "cases", "nondeterminism_input.json")
RAW_DIR = os.path.join(HW01_DIR, "raw")
RUNS_PER_TEMP = 20
TEMPERATURES = [0.7, 0.0]
MODEL = os.environ.get("SMOL_MODEL", "qwen3:8b")
BASE_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


def main():
    with open(INPUT_PATH) as f:
        fixed_input = json.load(f)

    os.makedirs(RAW_DIR, exist_ok=True)
    csv_path = os.path.join(RAW_DIR, "nondeterminism_runs.csv")
    json_path = os.path.join(RAW_DIR, "nondeterminism_runs.json")

    fieldnames = [
        "run_index", "temperature", "tag1", "tag2", "tag3", "summary",
        "planner_ms", "reviewer_ms", "finalizer_ms", "total_ms", "timestamp",
    ]
    all_rows = []

    with open(csv_path, "w", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()

        for temperature in TEMPERATURES:
            llm = build_llm(MODEL, BASE_URL, temperature)
            for i in range(1, RUNS_PER_TEMP + 1):
                t_start = time.time()
                result = run_pipeline(
                    llm,
                    fixed_input["title"],
                    fixed_input["content"],
                    fixed_input.get("email", "student@example.com"),
                )
                tags = result["package"]["agents"]["final"].get("tags", [])
                tags = (tags + ["", "", ""])[:3]
                summary = result["package"]["agents"]["final"].get("summary", "")
                row = {
                    "run_index": i,
                    "temperature": temperature,
                    "tag1": tags[0],
                    "tag2": tags[1],
                    "tag3": tags[2],
                    "summary": summary,
                    "planner_ms": result["latency_ms"]["planner"],
                    "reviewer_ms": result["latency_ms"]["reviewer"],
                    "finalizer_ms": result["latency_ms"]["finalizer"],
                    "total_ms": result["latency_ms"]["total"],
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
                writer.writerow(row)
                csvfile.flush()
                all_rows.append(row)
                print(
                    f"[temp={temperature} run={i}/{RUNS_PER_TEMP}] tags={tags} "
                    f"total_ms={row['total_ms']} elapsed={time.time() - t_start:.1f}s",
                    flush=True,
                )

    with open(json_path, "w") as f:
        json.dump(all_rows, f, indent=2)

    metrics = {}
    for temperature in TEMPERATURES:
        rows = [r for r in all_rows if r["temperature"] == temperature]
        tag_sets = [frozenset(t for t in (r["tag1"], r["tag2"], r["tag3"]) if t) for r in rows]
        distinct_sets = len(set(tag_sets))

        tag_counts = {}
        for ts in tag_sets:
            for tag in ts:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        in_all = sorted(t for t, c in tag_counts.items() if c == len(rows))
        in_exactly_one = sorted(t for t, c in tag_counts.items() if c == 1)

        latencies = [r["total_ms"] for r in rows]
        metrics[str(temperature)] = {
            "n_runs": len(rows),
            "distinct_tag_sets": distinct_sets,
            "tags_in_all_runs": in_all,
            "tags_in_exactly_one_run": in_exactly_one,
            "latency_p50_ms": float(np.percentile(latencies, 50)),
            "latency_p95_ms": float(np.percentile(latencies, 95)),
            "latency_p99_ms": float(np.percentile(latencies, 99)),
        }

    metrics_path = os.path.join(RAW_DIR, "nondeterminism_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)

    print("\n=== METRICS SUMMARY ===")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
