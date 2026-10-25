#!/usr/bin/env python3
"""Run HW7 Part 2 fixed cases, recovery case, and reliability measurements."""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code" / "mcp"))
sys.path.insert(0, str(ROOT / "src"))

from agent_loop import run_agent  # noqa: E402

REPORT = ROOT / "reports" / "hw07"
CASES = REPORT / "cases"
RAW = REPORT / "raw"
RUN_LOG = REPORT / "RUN_LOG.txt"
RELIABILITY = RAW / "part2_reliability.csv"
METRICS = REPORT / "METRICS.md"

FIXED_CASES = [
    (
        "A_search_then_detail",
        "You must make at least two tool calls. First call search_recalls for blueberries. "
        "Then use the id of the first search result in get_recall_detail. Do not answer after "
        "the search; answer only after the detail lookup.",
        2,
    ),
    (
        "B_aggregate_then_supporting_example",
        "First call aggregate_recalls_by_supplier with min_units=0. "
        "Then call search_recalls for blueberries to find one supporting recall example. "
        "Do not answer until both calls return results.",
        2,
    ),
    (
        "C_compare_two_entities",
        "You must make at least three tool calls. First call search_recalls for Signature. "
        "Then call get_recall_detail for each of the first two result ids. Do not answer "
        "until the search and both detail lookups are complete.",
        3,
    ),
]


def write_cases() -> None:
    CASES.mkdir(parents=True, exist_ok=True)
    for name, prompt, minimum_calls in FIXED_CASES:
        (CASES / f"{name}.json").write_text(
            json.dumps(
                {"name": name, "prompt": prompt, "minimum_tool_calls": minimum_calls},
                indent=2,
            )
            + "\n"
        )
    (CASES / "D_nonexistent_id.json").write_text(
        json.dumps(
            {
                "name": "D_nonexistent_id",
                "prompt": "Look up the full details for recall id 99999 and explain the result without crashing.",
                "expected": "useful not-found response",
            },
            indent=2,
        )
        + "\n"
    )


def classify(summary: dict, minimum_calls: int) -> list[str]:
    failures: list[str] = []
    for step in summary.get("steps", []):
        if step.get("parse_error"):
            failures.append("text_when_tool_required")
        if step.get("schema_error"):
            if "unknown tool" in step["schema_error"]:
                failures.append("unknown_tool")
            else:
                failures.append("malformed_arguments")
        result = step.get("tool_result") or {}
        error = str(result.get("error") or "")
        if error and "unknown tool" in error:
            failures.append("unknown_tool")
        elif error and any(word in error for word in ("must", "required", "integer", "object")):
            failures.append("malformed_arguments")
    if summary.get("tool_call_count", 0) < minimum_calls:
        failures.append("lost_multi_step_chain")
    return sorted(set(failures))


def run_one(name: str, prompt: str, minimum_calls: int, *, max_repairs: int) -> dict:
    started = time.perf_counter()
    summary = run_agent(
        prompt,
        max_steps=6,
        max_repairs=max_repairs,
        log_path=None,
    )
    summary["case"] = name
    summary["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
    summary["minimum_tool_calls"] = minimum_calls
    summary["failures"] = classify(summary, minimum_calls)
    return summary


def print_summary(summary: dict) -> None:
    print(
        f"case={summary['case']} tools={summary['tool_call_count']} "
        f"repairs={summary.get('repair_count', 0)} stop={summary['stop_reason']}"
    )
    for step in summary.get("steps", []):
        if step.get("action") == "tool":
            print(f"  tool={step.get('tool')} inputs={step.get('tool_input')}")
            print(f"  result={json.dumps(step.get('tool_result'), sort_keys=True)[:500]}")
    print(f"  answer={(summary.get('final_answer') or '')[:500]}")
    print(f"  failures={summary['failures']}\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--case",
        choices=["A", "B", "C", "error", "all"],
        default="all",
        help="run one screenshot case, or all fixed cases",
    )
    parser.add_argument(
        "--reliability",
        action="store_true",
        help="run the 20-before and 20-after reliability measurement",
    )
    args = parser.parse_args()
    write_cases()
    REPORT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    log_lines: list[str] = ["HW7 Part 2 agent run log", ""]

    selected_cases = [] if args.case == "error" else FIXED_CASES
    if args.case in {"A", "B", "C"}:
        selected_cases = [FIXED_CASES[ord(args.case) - ord("A")]]

    print("Running fixed verification case(s) with one repair allowed.\n")
    fixed_summaries = []
    for name, prompt, minimum_calls in selected_cases:
        summary = run_one(name, prompt, minimum_calls, max_repairs=1)
        fixed_summaries.append(summary)
        print_summary(summary)
        log_lines.append(json.dumps(summary, indent=2))

    if args.case in {"error", "all"}:
        recovery = run_one(
            "D_nonexistent_id",
            "Look up the full details for recall id 99999 and explain the result without crashing.",
            1,
            max_repairs=1,
        )
        print("Error-recovery case:")
        print_summary(recovery)
        log_lines.append(json.dumps(recovery, indent=2))

    if not args.reliability:
        RUN_LOG.write_text("\n\n".join(log_lines) + "\n")
        print("\nWrote:")
        print(RUN_LOG)
        print("Cases:", CASES)
        return

    rows: list[dict] = []
    print("Running 20 baseline attempts and 20 repaired attempts...")
    for mode, repairs in (("before_repair", 0), ("after_repair", 1)):
        for attempt in range(1, 21):
            name, prompt, minimum_calls = FIXED_CASES[(attempt - 1) % len(FIXED_CASES)]
            summary = run_one(name, prompt, minimum_calls, max_repairs=repairs)
            rows.append(
                {
                    "mode": mode,
                    "attempt": attempt,
                    "case": name,
                    "tool_calls": summary["tool_call_count"],
                    "repairs": summary.get("repair_count", 0),
                    "well_formed_calls": summary["tool_call_count"]
                    - sum(failure == "malformed_arguments" for failure in summary["failures"]),
                    "stop_reason": summary["stop_reason"],
                    "failures": ",".join(summary["failures"]),
                    "elapsed_ms": summary["elapsed_ms"],
                }
            )
            print(
                f"{mode} attempt {attempt}/20: {name} tools={summary['tool_call_count']} failures={summary['failures']}"
            )

    with RELIABILITY.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    def metrics(mode: str) -> tuple[int, int, int, dict[str, int]]:
        selected = [row for row in rows if row["mode"] == mode]
        calls = sum(int(row["tool_calls"]) for row in selected)
        formed = sum(int(row["well_formed_calls"]) for row in selected)
        failure_counts: dict[str, int] = {}
        for row in selected:
            for failure in filter(None, row["failures"].split(",")):
                failure_counts[failure] = failure_counts.get(failure, 0) + 1
        return len(selected), calls, formed, failure_counts

    metric_lines = [
        "# HW7 Part 2 Reliability Results",
        "",
        "The same three fixed prompts were rotated across 20 baseline and 20 repaired attempts.",
        "Model settings: the HW1 adapter default model and temperature 0.0; max steps 6.",
        "",
        "| Mode | Attempts | Tool calls | Well-formed calls | Well-formed rate | Failure counts |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for mode in ("before_repair", "after_repair"):
        attempts, calls, formed, failure_counts = metrics(mode)
        rate = f"{formed / calls:.1%}" if calls else "n/a"
        metric_lines.append(
            f"| {mode} | {attempts} | {calls} | {formed} | {rate} | {failure_counts or 'none'} |"
        )
    metric_lines += ["", f"Raw per-attempt data: `{RELIABILITY.relative_to(ROOT)}`", ""]
    METRICS.write_text("\n".join(metric_lines))
    RUN_LOG.write_text("\n\n".join(log_lines) + "\n")

    print("\nWrote:")
    print(RUN_LOG)
    print(METRICS)
    print(RELIABILITY)


if __name__ == "__main__":
    main()
