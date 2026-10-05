#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import math
import os
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
MCP_DIR = os.path.join(REPO, "code", "mcp")
RAW = os.path.join(REPO, "reports", "hw05", "raw")
REPORTS = os.path.join(REPO, "reports", "hw05")

sys.path.insert(0, MCP_DIR)

from domain_server import _db_search, run_storage  # noqa: E402
from resilient_storage import VERIFY_SEED, make_experiment_rng  # noqa: E402

RATES = [0.0, 0.20, 0.50]
CALLS_PER_RATE = 50
TOOL = "search_recalls"
QUERY = "a"


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def run_one(rate: float, call_index: int) -> dict:
    rng = make_experiment_rng(rate, call_index)
    started = time.perf_counter()
    result = run_storage(
        lambda: _db_search(QUERY, 5),
        failure_rate=rate,
        rng=rng,
    )
    wall_ms = (time.perf_counter() - started) * 1000
    return {
        "call_index": call_index,
        "failure_rate": rate,
        "tool": TOOL,
        "query": QUERY,
        "ok": result.ok,
        "error": result.error,
        "attempts": result.attempts,
        "latency_ms": round(result.latency_ms, 3),
        "wall_latency_ms": round(wall_ms, 3),
        "injected_failures": sum(1 for t in result.trace if t.injected_failure),
        "verify_seed": VERIFY_SEED,
        "trace": [
            {
                "attempt": t.attempt,
                "injected_failure": t.injected_failure,
                "error": t.error,
                "latency_ms": round(t.latency_ms, 3),
            }
            for t in result.trace
        ],
    }


def summarize(records: list[dict], rate: float) -> dict:
    subset = [r for r in records if r["failure_rate"] == rate]
    successes = [r for r in subset if r["ok"]]
    latencies = sorted(r["latency_ms"] for r in subset)
    mean_lat = sum(latencies) / len(latencies) if latencies else 0.0
    return {
        "injected_failure_rate": rate,
        "n": len(subset),
        "successes": len(successes),
        "success_rate": len(successes) / len(subset) if subset else 0.0,
        "mean_latency_ms": mean_lat,
        "p99_latency_ms": percentile(latencies, 0.99),
    }


def write_metrics(summaries: list[dict]):
    path = os.path.join(REPORTS, "METRICS.md")
    lines = [
        "# HW5 Part 3 — Fault injection metrics",
        "",
        f"VERIFY_SEED = {VERIFY_SEED}",
        f"Tool under test = `{TOOL}` (storage path with timeout + exponential backoff, max 3 attempts)",
        f"Calls = {CALLS_PER_RATE} per rate × {len(RATES)} rates = {CALLS_PER_RATE * len(RATES)} total",
        "",
        "| Injected failure rate | Success rate | Mean latency (ms) | p99 latency (ms) |",
        "|---|---|---|---|",
    ]
    for s in summaries:
        lines.append(
            f"| {int(s['injected_failure_rate'] * 100)}% "
            f"| {s['success_rate'] * 100:.1f}% "
            f"| {s['mean_latency_ms']:.2f} "
            f"| {s['p99_latency_ms']:.2f} |"
        )
    lines.append("")
    os.makedirs(REPORTS, exist_ok=True)
    with open(path, "w") as f:
        f.write("\n".join(lines))
    print("Wrote", path)


def main():
    os.makedirs(RAW, exist_ok=True)
    print(f"VERIFY_SEED={VERIFY_SEED}  starting {CALLS_PER_RATE * len(RATES)} calls…")
    started_at = datetime.now(timezone.utc).isoformat()

    records: list[dict] = []
    for rate in RATES:
        print(f"\n--- failure_rate={rate:.0%} ---")
        for i in range(1, CALLS_PER_RATE + 1):
            rec = run_one(rate, i)
            records.append(rec)
            flag = "OK" if rec["ok"] else "FAIL"
            print(
                f"  [{i:02d}/{CALLS_PER_RATE}] {flag} attempts={rec['attempts']} "
                f"latency_ms={rec['latency_ms']:.1f}"
            )

    csv_path = os.path.join(RAW, "task20_fault_injection.csv")
    fields = [
        "call_index",
        "failure_rate",
        "tool",
        "query",
        "ok",
        "error",
        "attempts",
        "latency_ms",
        "wall_latency_ms",
        "injected_failures",
        "verify_seed",
    ]
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in records:
            writer.writerow({k: r.get(k) for k in fields})

    json_path = os.path.join(RAW, "task20_fault_injection.json")
    with open(json_path, "w") as f:
        json.dump(
            {
                "started_at": started_at,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "verify_seed": VERIFY_SEED,
                "calls_per_rate": CALLS_PER_RATE,
                "rates": RATES,
                "records": records,
            },
            f,
            indent=2,
        )

    summaries = [summarize(records, rate) for rate in RATES]
    summary_path = os.path.join(RAW, "task20_summary.json")
    with open(summary_path, "w") as f:
        json.dump({"verify_seed": VERIFY_SEED, "summaries": summaries}, f, indent=2)

    write_metrics(summaries)
    print("\nWrote", csv_path)
    print("Wrote", json_path)
    print("Wrote", summary_path)
    print("\nSummary:")
    for s in summaries:
        print(
            f"  rate={s['injected_failure_rate']:.0%}  "
            f"success={s['success_rate']*100:.1f}%  "
            f"mean={s['mean_latency_ms']:.2f}ms  "
            f"p99={s['p99_latency_ms']:.2f}ms"
        )


if __name__ == "__main__":
    main()
