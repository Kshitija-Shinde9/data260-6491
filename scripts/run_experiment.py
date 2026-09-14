import argparse
import csv
import json
import os
import statistics
import time

import sys

# My graph code lives in code/agent_graph and src/model_client.py at the repo root,
# so I add both to the path before importing.
HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.join(HERE, "..")
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "code", "agent_graph"))

from workflow import build_initial_state, build_workflow

REPORTS = os.path.join(HERE, "..", "reports", "hw02")
CASES = os.path.join(REPORTS, "cases")
RAW = os.path.join(REPORTS, "raw")

FIELDS = ["run", "ceiling", "attempts", "schema_failures", "schema_valid", "turns_used",
          "latency_ms", "outcome", "tags", "schema_error"]


# Reads my frozen input file so every run uses exactly the same text.
def load_case(name):
    with open(os.path.join(CASES, name)) as f:
        return json.load(f)


# Sorts one finished run into one of the four buckets the assignment asks for.
def classify(final, ceiling):
    # The four buckets are about schema retries, so I count how many times the
    # answer broke my rules, not how many times the Reviewer sent it back.
    failures = final.get("schema_failures", 0)
    valid = final.get("schema_valid", False)
    turns = final.get("turn_count", 0)

    # A run that ran out of turns is abandoned, whatever else happened.
    if turns >= ceiling or not valid:
        return "hit turn ceiling"
    if failures == 0:
        return "valid first attempt"
    if failures == 1:
        return "valid after 1 retry"
    return "valid after 2+ retries"


# Runs the graph once and reports what happened.
def run_once(graph, case, ceiling, run_number):
    state = build_initial_state(case["title"], case["content"], case["email"], ceiling)

    start = time.time()
    final = {}
    try:
        for step in graph.stream(state, {"recursion_limit": 60}):
            for node_name, update in step.items():
                final.update(update)
    except Exception as error:
        print(f"   run {run_number} stopped early: {error}")
    latency_ms = int((time.time() - start) * 1000)

    outcome = classify(final, ceiling)
    tags = final.get("planner_proposal", {}).get("data", {}).get("tags", [])

    return {
        "run": run_number,
        "ceiling": ceiling,
        "attempts": final.get("planner_attempts", 0),
        "schema_failures": final.get("schema_failures", 0),
        "schema_valid": final.get("schema_valid", False),
        "turns_used": final.get("turn_count", 0),
        "latency_ms": latency_ms,
        "outcome": outcome,
        "tags": " | ".join(tags),
        "schema_error": final.get("schema_error", ""),
    }


# Runs the graph n times and writes every run to a CSV as it goes.
def run_many(case, ceiling, n, csv_name, label):
    os.makedirs(RAW, exist_ok=True)
    graph = build_workflow()
    path = os.path.join(RAW, csv_name)
    rows = []

    print("=" * 64)
    print(f"{label}: {n} runs, turn ceiling {ceiling}")
    print(f"input : {case['title']}")
    print(f"saving: reports/hw02/raw/{csv_name}")
    print("=" * 64)

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()

        for i in range(1, n + 1):
            print(f"\n--- run {i} of {n} ---")
            row = run_once(graph, case, ceiling, i)
            writer.writerow(row)
            f.flush()          # write each run straight away, so nothing is lost if I stop it
            rows.append(row)
            print(f"   => {row['outcome']}  ({row['latency_ms']} ms, {row['attempts']} attempt(s), {row['schema_failures']} schema failure(s))")

    return rows


# Prints the results table the assignment gives me.
def print_outcome_table(rows, title):
    buckets = ["valid first attempt", "valid after 1 retry",
               "valid after 2+ retries", "hit turn ceiling"]

    print()
    print("=" * 64)
    print(title)
    print("=" * 64)
    print(f"{'Outcome':<26}{'Count':>8}{'Mean latency (ms)':>22}")
    print("-" * 64)
    for bucket in buckets:
        matching = [r for r in rows if r["outcome"] == bucket]
        if matching:
            mean = int(statistics.mean(r["latency_ms"] for r in matching))
            print(f"{bucket:<26}{len(matching):>8}{mean:>22,}")
        else:
            print(f"{bucket:<26}{0:>8}{'-':>22}")
    print("-" * 64)
    print(f"{'TOTAL':<26}{len(rows):>8}")


# Task 4 compares two turn ceilings side by side.
def print_ceiling_comparison(rows2, rows10):
    print()
    print("=" * 64)
    print("TASK 4 - comparing turn ceilings of 2 and 10")
    print("=" * 64)
    print(f"{'Ceiling':<12}{'Runs':>8}{'Completed':>12}{'Rate':>10}{'Mean latency (ms)':>22}")
    print("-" * 64)
    for ceiling, rows in (("2", rows2), ("10", rows10)):
        # A run only counts as completed if it finished properly, meaning it did
        # not run out of turns. A valid answer that was cut off still counts as
        # abandoned, because the reviewer never got to approve it.
        done = [r for r in rows if r["outcome"] != "hit turn ceiling"]
        rate = (len(done) / len(rows) * 100) if rows else 0
        mean = int(statistics.mean(r["latency_ms"] for r in rows)) if rows else 0
        print(f"{ceiling:<12}{len(rows):>8}{len(done):>12}{rate:>9.0f}%{mean:>22,}")
    print("-" * 64)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", type=int, required=True, choices=[3, 4, 5],
                    help="3 = 30 runs, 4 = ceilings 2 vs 10, 5 = adversarial input")
    ap.add_argument("--runs", type=int, default=None, help="override how many runs, useful for a quick test")
    args = ap.parse_args()

    if args.task == 3:
        case = load_case("schema_input.json")
        n = args.runs or 30
        rows = run_many(case, 10, n, "task3_schema_runs.csv", "TASK 3")
        print_outcome_table(rows, f"TASK 3 - outcome over {n} runs")

    elif args.task == 4:
        case = load_case("schema_input.json")
        n = args.runs or 20
        rows2 = run_many(case, 2, n, "task4_ceiling_2.csv", "TASK 4a - ceiling 2")
        rows10 = run_many(case, 10, n, "task4_ceiling_10.csv", "TASK 4b - ceiling 10")
        print_ceiling_comparison(rows2, rows10)

    elif args.task == 5:
        case = load_case("adversarial_input.json")
        n = args.runs or 5
        rows = run_many(case, 10, n, "task5_adversarial.csv", "TASK 5 - adversarial input")
        print_outcome_table(rows, f"TASK 5 - outcome over {n} adversarial runs")
        hit = len([r for r in rows if r["outcome"] == "hit turn ceiling"])
        print(f"\nreached the ceiling in {hit} of {n} runs")


if __name__ == "__main__":
    main()
