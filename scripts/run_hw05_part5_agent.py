#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(REPO, "code", "mcp"))
sys.path.insert(0, os.path.join(REPO, "src"))

from agent_loop import run_agent  # noqa: E402

LOG = Path(REPO) / "reports" / "hw05" / "raw" / "agent_runs.jsonl"
METRICS = Path(REPO) / "reports" / "hw05" / "METRICS.md"

SCENARIOS = [
    ("search product", "Find recall notices about blueberries."),
    ("detail lookup", "Show me the full details for recall id 1."),
    ("aggregate", "Which supplier has the most affected units across recalls?"),
    ("pii email (should hit safety if the model searches by email)", "Look up the recall submitted by rohan1@gmail.com."),
]


def main():
    print("Running 4 Ollama agent scenarios. Need ollama + qwen3:8b and MySQL for live tools.\n")
    rows = []
    for title, prompt in SCENARIOS:
        print("---", title)
        print("user:", prompt)
        summary = run_agent(prompt, max_steps=4, log_path=LOG)
        print(
            f"steps={summary['step_count']}  tools={summary['tool_call_count']}  "
            f"stop={summary['stop_reason']}"
        )
        print("answer:", (summary.get("final_answer") or "")[:300], "\n")
        rows.append((title, summary))

    lines = [
        "",
        "## Part 5 — Agent scenarios (local Ollama)",
        "",
        "| Scenario | Step count | Tool-call count | Stop reason |",
        "|---|---|---|---|",
    ]
    for title, summary in rows:
        lines.append(
            f"| {title} | {summary['step_count']} | {summary['tool_call_count']} | {summary['stop_reason']} |"
        )
    lines.append("")
    METRICS.parent.mkdir(parents=True, exist_ok=True)
    existing = METRICS.read_text() if METRICS.exists() else ""
    if "## Part 5 — Agent scenarios" in existing:
        head = existing.split("## Part 5 — Agent scenarios")[0].rstrip()
        METRICS.write_text(head + "\n" + "\n".join(lines))
    else:
        METRICS.write_text(existing.rstrip() + "\n" + "\n".join(lines) + "\n")
    print("Appended table to", METRICS)
    print("Log:", LOG)


if __name__ == "__main__":
    main()
