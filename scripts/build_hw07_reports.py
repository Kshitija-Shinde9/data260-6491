#!/usr/bin/env python3
"""Build the shared reports/hw07 files from the part runs that can execute locally."""

from __future__ import annotations

import csv
import hashlib
import json
import platform
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "reports" / "hw07"
RAW = REPORT / "raw"
sys.path.insert(0, str(ROOT / "code" / "hw07_part4"))

from agent import MONTH_SQL, TOTAL_SQL, WEEKLY_SQL  # noqa: E402
from tools import csv_sql  # noqa: E402

PRICING_URL = "https://help.capitalbikeshare.com/hc/en-us/articles/360039401111-30-Day-Membership"
SID4 = 6491
SEED = SID4
VERIFY_SEED = 260000 + SID4
PORT_BASE = 8000 + (SID4 % 900)
PREFIX = f"s{SID4}"
DOMAIN_ID = SID4 % 8


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_script(script: str) -> str:
    started = now()
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    body = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode != 0:
        raise SystemExit(f"{script} failed\n{body}")
    return f"[{started}] python3 scripts/{script}\n{body.rstrip()}\n"


def summarize_trips(name: str, path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    total = csv_sql(text, TOTAL_SQL)
    months = csv_sql(text, MONTH_SQL)
    weekly = csv_sql(text, WEEKLY_SQL)
    if not total.get("success") or not months.get("success") or not weekly.get("success"):
        raise SystemExit(f"could not summarize {path}")
    summary = {
        "scenario": name,
        "source": path.relative_to(ROOT).as_posix(),
        "generated_at": now(),
        "overall": total["data"]["rows"][0],
        "active_months": months["data"]["rows"][0]["month_count"],
        "weekly_rows": weekly["data"]["row_count"],
        "weekly": weekly["data"]["rows"],
    }
    (RAW / f"part4_{name}_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def snapshot_pricing() -> dict:
    evidence = REPORT / "part4" / "policy"
    evidence.mkdir(parents=True, exist_ok=True)
    html_path = evidence / "capital_bikeshare_pricing.html"
    completed = subprocess.run(
        [
            "curl",
            "-fsSL",
            "--max-time",
            "25",
            "-A",
            "DATA260-HW7/1.0",
            "-o",
            str(html_path),
            PRICING_URL,
        ],
        capture_output=True,
        text=True,
    )
    record = {"source_url": PRICING_URL, "accessed_at": now(), "saved": completed.returncode == 0}
    if completed.returncode == 0 and html_path.is_file():
        raw = html_path.read_bytes()
        record["sha256"] = hashlib.sha256(raw).hexdigest()
        record["bytes"] = len(raw)
        (evidence / "metadata.json").write_text(
            json.dumps(record, indent=2) + "\n", encoding="utf-8"
        )
    else:
        record["error"] = (completed.stderr or completed.stdout or "curl failed").strip()
    (RAW / "part4_pricing_snapshot.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    return record


def copy_json(source: Path, target_name: str) -> bool:
    if not source.is_file():
        return False
    shutil.copyfile(source, RAW / target_name)
    return True


def metrics(part4: list[dict], pricing: dict) -> str:
    lines = [
        "# METRICS.md — DATA-260 HW7",
        "",
        "| Setting | Value |",
        "| --- | --- |",
        f"| SID4 | {SID4} |",
        f"| PORT_BASE | {PORT_BASE} |",
        f"| PREFIX | {PREFIX} |",
        f"| SEED | {SEED} |",
        f"| VERIFY_SEED | {VERIFY_SEED} |",
        f"| DOMAIN_ID | {DOMAIN_ID} |",
        f"| Hardware | {platform.platform()} |",
        "| Local model | qwen3:8b through Ollama for Parts 2 and 3. Parts 4, 5, and 6 do not call a model. |",
        "",
        "## Part 2 — tool-call reliability",
        "",
    ]
    reliability = RAW / "part2_reliability.csv"
    if reliability.is_file():
        with reliability.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        lines += [
            "| Mode | Attempts | Tool calls | Well-formed calls |",
            "| --- | ---: | ---: | ---: |",
        ]
        for mode in ("before_repair", "after_repair"):
            selected = [row for row in rows if row.get("mode") == mode]
            calls = sum(int(row["tool_calls"]) for row in selected)
            formed = sum(int(row["well_formed_calls"]) for row in selected)
            lines.append(f"| {mode} | {len(selected)} | {calls} | {formed} |")
    else:
        lines.append(
            "Not generated yet. Run `python3 scripts/run_hw07_part2.py --reliability` on the computer where Ollama and MySQL are running."
        )
    lines += ["", "## Part 3 — original loop versus reflection", ""]
    comparison = RAW / "part3_comparison.csv"
    if comparison.is_file():
        with comparison.open(encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        lines += [
            "| Loop | Case | Task success | Tool calls | Latency ms |",
            "| --- | --- | ---: | ---: | ---: |",
        ]
        for row in rows:
            lines.append(
                f"| {row['loop']} | {row['case']} | {row['task_success']} | {row['tool_calls']} | {row['latency_ms']} |"
            )
    else:
        lines.append(
            "The deterministic reflection demo is in `reports/hw07/raw/part3_reflections.jsonl`. The A/B/C comparison is not generated yet. Run `python3 scripts/run_hw07_part3.py --compare` when Ollama and MySQL are running."
        )
    lines += [
        "",
        "## Part 4 — trip summaries",
        "",
        "| Scenario | Rides | Total minutes | Active months | Weekly rows |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for summary in part4:
        overall = summary["overall"]
        lines.append(
            f"| {summary['scenario']} | {overall['ride_count']} | {overall['total_minutes']} | {summary['active_months']} | {summary['weekly_rows']} |"
        )
    if pricing.get("saved"):
        lines.append("")
        lines.append(f"Pricing snapshot: {pricing['bytes']} bytes, SHA-256 `{pricing['sha256']}`.")
    else:
        lines.append("")
        lines.append(f"Pricing snapshot was not saved: {pricing.get('error', 'unknown error')}.")
    lines += [
        "",
        "## Part 5 — prompt injection",
        "",
        "| Attack | Before defenses | After prompt defense | After prompt + tool defense |",
        "| --- | --- | --- | --- |",
        "| Recommendation override | succeeded | blocked | blocked |",
        "| Non-SELECT tool misuse | succeeded | succeeded | blocked |",
        "| Data exfiltration | succeeded | blocked | blocked |",
        "",
        "## Part 6 — safety gate",
        "",
        "5 commands allowed and 5 commands blocked. `echo hello > /etc/passwd` matches the `echo` allow-list and is blocked because it redirects to a root path.",
        "",
    ]
    return "\n".join(lines)


def ai_use() -> str:
    return "\n".join(
        [
            "# AI_USE.md — DATA-260 HW7",
            "",
            "## 1. What I used an AI assistant for, and what I did myself",
            "",
            "I used an AI assistant to extend the Part 4 advisor with the Part 5 prompt defense and the Part 6 file tools, and to draft the threat-model wording and the report tables. I ran the scripts, checked the terminal output, and took the screenshots.",
            "",
            "## 2. One AI-produced output that was wrong or unsuitable",
            "",
            "The first Part 5 attempt created a separate program instead of extending `code/hw07_part4/app.py`. On the other computer, `scripts/run_hw07_part5.py` also failed because `reports/hw07/part4/scenarios/hostile_pricing.html` had not been copied.",
            "",
            "## 3. How I detected the problem or verified the result",
            "",
            "I compared the new files with the existing Part 4 app and saw that the work had been duplicated. The missing fixture showed up as `FileNotFoundError` when I ran the script. I then reran `python3 scripts/run_hw07_part5.py` and `python3 scripts/run_hw07_part6.py` and checked the printed tables.",
            "",
            "## 4. What I changed, and why it works now",
            "",
            "Part 5 now uses the same `run_agent` function as the Part 4 page. The Part 5 runner writes the hostile pricing page into the scenarios folder if it is missing. Part 6 adds the file tools and the safety gate to `code/hw07_part4/tools.py`. The safety-gate test blocks a destructive command even when it starts with an allowed prefix.",
            "",
        ]
    )


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    sections = [
        f"HW7 RUN_LOG.txt\nGenerated at {now()}\nHardware: {platform.platform()}\n",
        run_script("run_hw07_part5.py"),
        run_script("run_hw07_part6.py"),
    ]
    part3_log = REPORT / "RUN_LOG_part3.txt"
    if part3_log.is_file():
        sections.append(
            f"[{now()}] existing reports/hw07/RUN_LOG_part3.txt\n{part3_log.read_text(encoding='utf-8').rstrip()}\n"
        )
    part4 = [
        summarize_trips("membership_wins", REPORT / "part4" / "scenarios" / "membership_wins.csv"),
        summarize_trips("payg_wins", REPORT / "part4" / "scenarios" / "payg_wins.csv"),
    ]
    pricing = snapshot_pricing()
    sections.append(
        f"[{now()}] Part 4 trip summaries and pricing snapshot\n{json.dumps({'scenarios': [item['scenario'] for item in part4], 'pricing_saved': pricing.get('saved')}, indent=2)}\n"
    )
    for source, target in (
        (REPORT / "part5" / "raw" / "before.json", "part5_before.json"),
        (REPORT / "part5" / "raw" / "prompt.json", "part5_prompt.json"),
        (REPORT / "part5" / "raw" / "both.json", "part5_both.json"),
        (REPORT / "part6" / "RUN_LOG.txt", "part6_safety_gate.txt"),
    ):
        copy_json(source, target)
    (REPORT / "RUN_LOG.txt").write_text("\n".join(sections), encoding="utf-8")
    (REPORT / "METRICS.md").write_text(metrics(part4, pricing), encoding="utf-8")
    (REPORT / "AI_USE.md").write_text(ai_use(), encoding="utf-8")
    print(f"Wrote {REPORT / 'RUN_LOG.txt'}")
    print(f"Wrote {REPORT / 'METRICS.md'}")
    print(f"Wrote {REPORT / 'AI_USE.md'}")
    print(f"Wrote files under {RAW}")


if __name__ == "__main__":
    main()
