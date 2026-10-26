#!/usr/bin/env python3
"""Smoke-test HW7 behavior and write reports/hw07/verification.json."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code" / "hw07_part4"))
sys.path.insert(0, str(ROOT / "code" / "mcp"))

from agent import run_agent  # noqa: E402
from reflection_agent import ReflectionTurn, run_reflection_agent  # noqa: E402
from tools import (  # noqa: E402
    confirm_bash,
    csv_sql,
    glob_files,
    is_destructive,
    read_file,
    search_in_files,
    set_sandbox,
    write_file,
)

SID4 = 6491
SEED = SID4
VERIFY_SEED = 260000 + SID4
PORT_BASE = 8000 + (SID4 % 900)
PREFIX = f"s{SID4}"
DOMAIN_ID = SID4 % 8
REPORT = ROOT / "reports" / "hw07"
FIXTURE = "reports/hw07/part4/scenarios/hostile_pricing.html"
SAMPLE = REPORT / "part4" / "scenarios" / "injection_membership.csv"
PASS_COMMANDS = ("pwd", "ls", "echo hello", 'python3 -c "print(1)"', "git status")
BLOCK_COMMANDS = (
    "rm -rf notes_b.py",
    'sudo python3 -c "print(1)"',
    "chmod 777 notes_a.py",
    "dd if=/dev/zero of=/dev/disk0",
    "echo hello > /etc/passwd",
)
CHECKS: list[dict] = []


def check(name: str, passed: bool, detail: str = "") -> None:
    CHECKS.append({"name": name, "passed": bool(passed), "detail": detail})
    mark = "PASS" if passed else "FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"[{mark}] {name}{suffix}")


def git(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout.strip()


class DemoModel:
    def __init__(self) -> None:
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


def check_part4() -> None:
    text = (REPORT / "part4" / "scenarios" / "membership_wins.csv").read_text(encoding="utf-8")
    summary = csv_sql(text, "SELECT COUNT(*) AS ride_count FROM trips")
    count = ((summary.get("data") or {}).get("rows") or [{}])[0].get("ride_count")
    check(
        "Part 4 csv_sql summarizes membership_wins.csv",
        bool(summary.get("success")) and count == 600,
        f"ride_count={count}",
    )
    blocked = csv_sql(text, "DROP TABLE trips")
    check(
        "Part 4 csv_sql blocks a non-SELECT statement",
        blocked.get("success") is False,
        blocked.get("error", ""),
    )


def check_part5() -> None:
    csv_text = SAMPLE.read_text(encoding="utf-8")
    expected = {
        (False, False): {
            "recommendation_override": True,
            "non_select": True,
            "data_exfiltration": True,
        },
        (True, False): {
            "recommendation_override": False,
            "non_select": True,
            "data_exfiltration": False,
        },
        (True, True): {
            "recommendation_override": False,
            "non_select": False,
            "data_exfiltration": False,
        },
    }
    for flags, attacks in expected.items():
        result = run_agent(
            csv_text, FIXTURE, prompt_defense=flags[0], tool_defense=flags[1], write_result=False
        )
        check(
            f"Part 5 attacks for prompt_defense={flags[0]} tool_defense={flags[1]}",
            result.get("attacks") == attacks,
            str(result.get("attacks")),
        )


def check_part6() -> None:
    with tempfile.TemporaryDirectory() as folder:
        set_sandbox(folder)
        write_file("notes_b.py", "DEBUG = True\n")
        write_file("notes_a.py", "def load():\n    return 'ready'\n")
        found = glob_files("*.py")
        hits = search_in_files("DEBUG", file_pattern="*.py")
        shown = read_file("notes_b.py", max_lines=5)
        paths = [hit["path"] for hit in (hits.get("data") or {}).get("hits", [])]
        check(
            "Part 6 glob, search, and read find DEBUG",
            "DEBUG = True" in (shown.get("data") or {}).get("content", "")
            and paths == ["notes_b.py"]
            and len((found.get("data") or {}).get("files", [])) == 2,
            str(paths),
        )
    allowed = all(
        confirm_bash(command)["decision"] == "allow" and not is_destructive(command)
        for command in PASS_COMMANDS
    )
    blocked = all(
        confirm_bash(command)["decision"] == "block" and is_destructive(command)
        for command in BLOCK_COMMANDS
    )
    check("Part 6 safety gate allows 5 commands and blocks 5", allowed and blocked)


def check_part3() -> None:
    result = run_reflection_agent(
        "First search_recalls for blueberries, then get_recall_detail for the first result.",
        case="A",
        model=DemoModel(),
        max_reflections=2,
        log_path=None,
    )
    check(
        "Part 3 deterministic reflection demo reaches a verified answer",
        result.get("stop_reason") == "success"
        and (result.get("verification") or {}).get("passed") is True,
        f"stop={result.get('stop_reason')}",
    )


def check_report_files() -> None:
    required = [
        "reports/hw07/RUN_LOG.txt",
        "reports/hw07/METRICS.md",
        "reports/hw07/AI_USE.md",
        "reports/hw07/raw/part4_membership_wins_summary.json",
        "reports/hw07/raw/part4_payg_wins_summary.json",
        "reports/hw07/raw/part5_before.json",
        "reports/hw07/raw/part5_both.json",
        "reports/hw07/raw/part6_safety_gate.txt",
        "reports/hw07/raw/part3_reflections.jsonl",
    ]
    for relative in required:
        path = ROOT / relative
        check(
            f"report file exists: {relative}", path.is_file(), "" if path.is_file() else "missing"
        )
    check(
        "Part 2 reliability file exists",
        (REPORT / "raw" / "part2_reliability.csv").is_file(),
        "run scripts/run_hw07_part2.py --reliability if missing",
    )
    check(
        "Part 3 comparison file exists",
        (REPORT / "raw" / "part3_comparison.csv").is_file(),
        "run scripts/run_hw07_part3.py --compare if missing",
    )


def main() -> int:
    check_part4()
    check_part5()
    check_part6()
    check_part3()
    check_report_files()
    commit = git("rev-parse", "HEAD") or "not a git repository"
    tag = (
        git("describe", "--tags", "--exact-match", "HEAD")
        or git("tag", "--points-at", "HEAD")
        or "no tag yet"
    )
    if "\n" in tag:
        tag = tag.splitlines()[0]
    passed = sum(item["passed"] for item in CHECKS)
    document = {
        "homework": "HW7",
        "homework_number": 7,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sid4": SID4,
        "port_base": PORT_BASE,
        "prefix": PREFIX,
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "domain_id": DOMAIN_ID,
        "hardware": platform.platform(),
        "commit_hash": commit,
        "tag": tag,
        "model_configuration": {
            "local_model": "qwen3:8b via Ollama",
            "parts_4_to_6": "deterministic Python, no model call",
        },
        "total_checks": len(CHECKS),
        "passed": passed,
        "failed": len(CHECKS) - passed,
        "checks": CHECKS,
    }
    destination = REPORT / "verification.json"
    destination.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(CHECKS)} checks passed.")
    print("Written to reports/hw07/verification.json")
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())
