#!/usr/bin/env python3
"""Run HW7 Part 3 reflection checks and the original-vs-reflection comparison."""

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
from reflection_agent import ReflectionTurn, run_reflection_agent, verify_case  # noqa: E402

REPORT = ROOT / "reports" / "hw07"
RAW = REPORT / "raw"
RUN_LOG = REPORT / "RUN_LOG_part3.txt"
REFLECTIONS = RAW / "part3_reflections.jsonl"
COMPARISON = RAW / "part3_comparison.csv"
TABLE = REPORT / "PART3_COMPARISON.md"

CASES = {
    "A": "You must make at least two tool calls. First search_recalls for blueberries, then get_recall_detail for the first result. Do not answer early.",
    "B": "You must make at least two tool calls. First aggregate_recalls_by_supplier with min_units=0, then search_recalls for blueberries for one supporting example. Do not answer early.",
    "C": "You must make at least three tool calls. First search_recalls for Signature, then get_recall_detail for each of the first two results. Do not answer early.",
}


class ReflectionDemoModel:
    """Deterministic local model used only to show one failed-then-retried reflection."""

    def __init__(self):
        self.calls = 0

    def complete(self, messages, tools=None):
        self.calls += 1
        if self.calls == 1:
            return ReflectionTurn('{"action":"stop","answer":"I checked one result."}')
        if self.calls == 2:
            return ReflectionTurn(
                '{"action":"tool","name":"search_recalls","inputs":{"query":"Blueberries","limit":1}}'
            )
        if self.calls == 3:
            return ReflectionTurn(
                '{"action":"tool","name":"get_recall_detail","inputs":{"recall_id":1}}'
            )
        return ReflectionTurn(
            '{"action":"stop","answer":"Recall ID 1 is REC-0001, Trader Joe\'s Organic Frozen Blueberries, 16oz."}'
        )


def print_result(label: str, result: dict) -> None:
    print(f"{label}: case={result.get('case')} stop={result.get('stop_reason')} ")
    print(
        f"  tools={result.get('tool_call_count', 0)} "
        f"reflections={result.get('reflection_count', 0)} "
        f"tokens={result.get('total_tokens', 0)} latency_ms={result.get('latency_ms', 0)}"
    )
    if result.get("reflections"):
        print("  reflections:")
        for reflection in result["reflections"]:
            print("   ", json.dumps(reflection, sort_keys=True))
    verification = result.get("verification") or {}
    print(
        f"  verifier_passed={verification.get('passed')} problems={verification.get('problems', [])}"
    )
    print(f"  answer={(result.get('final_answer') or '')[:500]}\n")


def write_reflection_records(results: list[dict]) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    with REFLECTIONS.open("w") as handle:
        for result in results:
            for reflection in result.get("reflections", []):
                handle.write(json.dumps({"case": result["case"], **reflection}) + "\n")


def original_metrics(case: str, prompt: str) -> dict:
    started = time.perf_counter()
    result = run_agent(prompt, max_steps=6, max_repairs=1, log_path=None)
    verification = verify_case(case, result.get("steps", []), result.get("final_answer", ""))
    return {
        "loop": "original",
        "case": case,
        "task_success": int(verification["passed"]),
        "unsupported_claims": int(not verification["passed"]),
        "retry_rate": 0,
        "tool_calls": result.get("tool_call_count", 0),
        "tokens": result.get("total_tokens", 0),
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "verifier_false_rejections": 0,
    }


def reflection_metrics(case: str, prompt: str) -> dict:
    result = run_reflection_agent(prompt, case=case, max_reflections=2, log_path=None)
    return {
        "loop": "reflection",
        "case": case,
        "task_success": int(result["stop_reason"] == "success"),
        "unsupported_claims": int(not result["verification"]["passed"]),
        "retry_rate": int(result["reflection_count"] > 0),
        "tool_calls": result["tool_call_count"],
        "tokens": result["total_tokens"],
        "latency_ms": result["latency_ms"],
        "verifier_false_rejections": 0,
    }


def run_compare() -> None:
    rows = []
    for case, prompt in CASES.items():
        print(f"Comparing case {case} with the original loop...")
        rows.append(original_metrics(case, prompt))
        print(f"Comparing case {case} with the reflection loop...")
        rows.append(reflection_metrics(case, prompt))

    RAW.mkdir(parents=True, exist_ok=True)
    with COMPARISON.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    lines = [
        "# HW7 Part 3 Original-vs-Reflection Comparison",
        "",
        "| Metric | Original loop | Reflection loop |",
        "|---|---:|---:|",
    ]
    for metric, label in (
        ("task_success", "Task success"),
        ("unsupported_claims", "Unsupported claims"),
        ("retry_rate", "Retry rate"),
        ("tool_calls", "Tool calls"),
        ("tokens", "Tokens"),
        ("latency_ms", "Latency (ms)"),
        ("verifier_false_rejections", "Verifier false rejections"),
    ):
        original = sum(row[metric] for row in rows if row["loop"] == "original")
        reflection = sum(row[metric] for row in rows if row["loop"] == "reflection")
        lines.append(f"| {label} | {original} | {reflection} |")
    lines += ["", f"Raw data: `{COMPARISON.relative_to(ROOT)}`", ""]
    TABLE.write_text("\n".join(lines))
    print(f"Wrote {TABLE}")
    print(f"Wrote {COMPARISON}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=["A", "B", "C", "all"], default="all")
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--demo-reflection", action="store_true")
    args = parser.parse_args()

    REPORT.mkdir(parents=True, exist_ok=True)
    selected = list(CASES.items()) if args.case == "all" else [(args.case, CASES[args.case])]
    results = []
    log_lines = ["HW7 Part 3 reflection run log", ""]

    if args.demo_reflection:
        result = run_reflection_agent(
            CASES["A"],
            case="A",
            model=ReflectionDemoModel(),
            max_reflections=2,
            log_path=None,
        )
        results.append(result)
        print_result("DEMO REFLECTION", result)
        log_lines.append(json.dumps(result, indent=2))
    else:
        for case, prompt in selected:
            result = run_reflection_agent(prompt, case=case, max_reflections=2, log_path=None)
            results.append(result)
            print_result(f"REFLECTION CASE {case}", result)
            log_lines.append(json.dumps(result, indent=2))

    write_reflection_records(results)
    RUN_LOG.write_text("\n\n".join(log_lines) + "\n")
    print(f"Wrote {RUN_LOG}")
    print(f"Wrote {REFLECTIONS}")

    if args.compare:
        run_compare()


if __name__ == "__main__":
    main()
