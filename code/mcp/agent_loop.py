
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "src"))

from execute_tool import SAFETY_ERROR, execute_tool  # noqa: E402

DEFAULT_LOG = REPO / "reports" / "hw05" / "raw" / "agent_runs.jsonl"
MAX_STEPS = 4

SYSTEM_PROMPT = """You are a grocery-recall assistant for domain s6491_rel.
You may use exactly these tools via execute_tool:
- search_recalls with inputs {"query": "<text>", "limit": <int>}
- get_recall_detail with inputs {"recall_id": <int>}
- aggregate_recalls_by_supplier with inputs {"min_units": <int>}

Reply with ONLY one JSON object, no markdown:
{"action":"tool","name":"<tool name>","inputs":{...}}
or
{"action":"stop","answer":"<final answer for the user>"}

Never search by a person's email. After you have enough tool results, stop.
"""


@dataclass
class MockTurn:
    content: str
    usage: Any = None
    latency_ms: int = 0
    raw: Any = None


class MockModel:

    def complete(self, messages, tools=None):
        return MockTurn(
            content=json.dumps(
                {
                    "action": "tool",
                    "name": "search_recalls",
                    "inputs": {"query": "Blueberries", "limit": 5},
                }
            )
        )


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("model did not return JSON")
    return json.loads(text[start : end + 1])


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record) + "\n")


def run_agent(
    user_input: str,
    *,
    model: Any = None,
    max_steps: int = MAX_STEPS,
    execute_fn: Callable[..., str] = execute_tool,
    backends: dict | None = None,
    log_path: str | os.PathLike | None = DEFAULT_LOG,
) -> dict[str, Any]:
    if model is None:
        from model_client import ModelClient

        model = ModelClient()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]
    steps: list[dict[str, Any]] = []
    tool_call_count = 0
    stop_reason = "max_steps"
    final_answer = None
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")

    for step_no in range(1, max_steps + 1):
        completion = model.complete(messages)
        content = getattr(completion, "content", "") or ""
        step_record: dict[str, Any] = {
            "step": step_no,
            "model_output": content,
        }
        try:
            parsed = _extract_json(content)
        except Exception as exc:
            stop_reason = "normal_completion"
            final_answer = content or str(exc)
            step_record["parse_error"] = str(exc)
            steps.append(step_record)
            break

        action = parsed.get("action")
        if action == "stop":
            stop_reason = "normal_completion"
            final_answer = parsed.get("answer", "")
            step_record["action"] = "stop"
            steps.append(step_record)
            break

        if action == "tool":
            name = parsed.get("name", "")
            inputs = parsed.get("inputs") or {}
            raw = execute_fn(name, inputs, backends=backends) if backends is not None else execute_fn(name, inputs)
            result = json.loads(raw)
            tool_call_count += 1
            step_record.update(
                {
                    "action": "tool",
                    "tool": name,
                    "tool_input": inputs,
                    "tool_result": result,
                }
            )
            steps.append(step_record)
            if result.get("ok") is False and result.get("error") == SAFETY_ERROR:
                stop_reason = "safety_rule_block"
                final_answer = result["error"]
                break
            messages.append({"role": "assistant", "content": content})
            messages.append(
                {
                    "role": "user",
                    "content": "Tool result: " + raw + " If you can answer, stop. Else call another tool.",
                }
            )
            continue

        stop_reason = "normal_completion"
        final_answer = content
        steps.append(step_record)
        break
    else:
        stop_reason = "max_steps"
        final_answer = "Stopped: reached max_steps without a final answer."

    summary = {
        "run_id": run_id,
        "user_input": user_input,
        "max_steps": max_steps,
        "step_count": len(steps),
        "tool_call_count": tool_call_count,
        "stop_reason": stop_reason,
        "final_answer": final_answer,
        "steps": steps,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if log_path is not None:
        _append_jsonl(Path(log_path), summary)
    return summary
