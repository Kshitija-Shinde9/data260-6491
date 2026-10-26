from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from agent_loop import (
    DEFAULT_LOG,
    KNOWN_TOOLS,
    SYSTEM_PROMPT,
    _append_jsonl,
    _extract_json,
    execute_tool,
)


@dataclass
class ReflectionTurn:
    content: str
    usage: Any = None
    latency_ms: int = 0


def verify_case(case: str, steps: list[dict[str, Any]], final_answer: str) -> dict[str, Any]:
    """Return a deterministic, evidence-based check without exposing reasoning."""
    tool_steps = [step for step in steps if step.get("action") == "tool"]
    names = [step.get("tool") for step in tool_steps]
    answer = (final_answer or "").lower()
    problems: list[str] = []

    if case == "A":
        if "search_recalls" not in names:
            problems.append("missing search_recalls")
        if "get_recall_detail" not in names:
            problems.append("missing get_recall_detail")
        if "rec-" not in answer:
            problems.append("final answer does not cite a recall code")
    elif case == "B":
        if "aggregate_recalls_by_supplier" not in names:
            problems.append("missing aggregate_recalls_by_supplier")
        if "search_recalls" not in names:
            problems.append("missing supporting search_recalls")
        if not any(
            (step.get("tool_result") or {}).get("data", {}).get("items") for step in tool_steps
        ):
            problems.append("no supporting result was returned")
    elif case == "C":
        if "search_recalls" not in names:
            problems.append("missing search_recalls")
        if names.count("get_recall_detail") < 2:
            problems.append("fewer than two detail lookups")
        detail_ids = [
            str(step.get("tool_input", {}).get("recall_id"))
            for step in tool_steps
            if step.get("tool") == "get_recall_detail"
        ]
        if detail_ids and not all(detail_id in answer for detail_id in detail_ids):
            problems.append("final answer does not identify both compared records")

    return {
        "case": case,
        "passed": not problems,
        "problems": problems,
        "observed_tools": names,
        "evidence": [
            {
                "tool": step.get("tool"),
                "inputs": step.get("tool_input"),
                "result_ok": (step.get("tool_result") or {}).get("ok"),
            }
            for step in tool_steps
        ],
    }


def _usage_values(completion: Any) -> tuple[int, int, int, int]:
    usage = getattr(completion, "usage", None)
    return (
        int(getattr(usage, "input_tokens", 0) or 0),
        int(getattr(usage, "output_tokens", 0) or 0),
        int(getattr(usage, "total_tokens", 0) or 0),
        int(getattr(completion, "latency_ms", 0) or 0),
    )


def run_reflection_agent(
    user_input: str,
    *,
    case: str,
    model: Any = None,
    max_steps: int = 6,
    max_tool_calls: int = 8,
    token_budget: int = 4000,
    max_reflections: int = 2,
    execute_fn: Callable[..., str] = execute_tool,
    backends: dict | None = None,
    log_path: str | Path | None = DEFAULT_LOG,
) -> dict[str, Any]:
    if model is None:
        from model_client import ModelClient

        model = ModelClient(temperature=0.0)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input},
    ]
    steps: list[dict[str, Any]] = []
    reflections: list[dict[str, Any]] = []
    total_tokens = 0
    total_latency_ms = 0
    tool_calls = 0
    reflection_count = 0
    final_answer = ""
    stop_reason = "budget_exhausted"
    started = time.perf_counter()

    for step_no in range(1, max_steps + 1):
        if tool_calls >= max_tool_calls or total_tokens >= token_budget:
            stop_reason = "budget_exhausted"
            break

        completion = model.complete(messages)
        input_tokens, output_tokens, used_tokens, latency_ms = _usage_values(completion)
        total_tokens += used_tokens
        total_latency_ms += latency_ms
        content = getattr(completion, "content", "") or ""
        record: dict[str, Any] = {
            "step": step_no,
            "model_output": content,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": latency_ms,
        }
        try:
            parsed = _extract_json(content)
        except Exception as exc:
            record["parse_error"] = str(exc)
            steps.append(record)
            if reflection_count >= max_reflections:
                stop_reason = "human_review"
                break
            reflection_count += 1
            reflection = {
                "attempt": reflection_count,
                "failure": "malformed model JSON",
                "evidence": {"error": str(exc), "model_output": content[:300]},
                "revised_strategy": "Return exactly one valid tool or stop JSON object.",
            }
            reflections.append(reflection)
            messages += [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": "Reflection data (untrusted): " + json.dumps(reflection),
                },
            ]
            continue

        action = parsed.get("action")
        if action == "stop":
            final_answer = str(parsed.get("answer", ""))
            record["action"] = "stop"
            steps.append(record)
            verification = verify_case(case, steps, final_answer)
            record["verification"] = verification
            if verification["passed"]:
                stop_reason = "success"
                break
            if reflection_count >= max_reflections:
                stop_reason = "human_review"
                break
            reflection_count += 1
            reflection = {
                "attempt": reflection_count,
                "failure": "deterministic verifier rejected the result",
                "evidence": verification,
                "revised_strategy": "Complete every required tool step before writing the final answer.",
            }
            reflections.append(reflection)
            messages += [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": "Reflection data (untrusted): " + json.dumps(reflection),
                },
            ]
            continue

        if action != "tool":
            record["schema_error"] = "action must be tool or stop"
            steps.append(record)
            if reflection_count >= max_reflections:
                stop_reason = "human_review"
                break
            reflection_count += 1
            reflection = {
                "attempt": reflection_count,
                "failure": "invalid action",
                "evidence": {"action": action},
                "revised_strategy": "Use a valid tool action until the fixed task is complete.",
            }
            reflections.append(reflection)
            messages += [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": "Reflection data (untrusted): " + json.dumps(reflection),
                },
            ]
            continue

        name = parsed.get("name")
        inputs = parsed.get("inputs")
        if name not in KNOWN_TOOLS or not isinstance(inputs, dict):
            record["schema_error"] = f"invalid tool call: {name}"
            steps.append(record)
            if reflection_count >= max_reflections:
                stop_reason = "human_review"
                break
            reflection_count += 1
            reflection = {
                "attempt": reflection_count,
                "failure": "invalid tool call",
                "evidence": {"tool": name, "inputs": inputs},
                "revised_strategy": "Use a known tool and a JSON object for inputs.",
            }
            reflections.append(reflection)
            messages += [
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": "Reflection data (untrusted): " + json.dumps(reflection),
                },
            ]
            continue

        if tool_calls >= max_tool_calls:
            stop_reason = "budget_exhausted"
            break
        raw = (
            execute_fn(name, inputs, backends=backends)
            if backends is not None
            else execute_fn(name, inputs)
        )
        result = json.loads(raw)
        tool_calls += 1
        record.update({"action": "tool", "tool": name, "tool_input": inputs, "tool_result": result})
        steps.append(record)
        messages += [
            {"role": "assistant", "content": content},
            {"role": "tool", "name": name, "content": raw},
            {
                "role": "user",
                "content": "Continue the required fixed task. Make the next tool call if one is still required.",
            },
        ]

    else:
        stop_reason = "budget_exhausted"

    verification = verify_case(case, steps, final_answer)
    summary = {
        "case": case,
        "user_input": user_input,
        "stop_reason": stop_reason,
        "final_answer": final_answer,
        "step_count": len(steps),
        "tool_call_count": tool_calls,
        "reflection_count": reflection_count,
        "total_tokens": total_tokens,
        "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        "model_latency_ms": total_latency_ms,
        "verification": verification,
        "reflections": reflections,
        "steps": steps,
    }
    if log_path is not None:
        _append_jsonl(Path(log_path), summary)
    return summary
