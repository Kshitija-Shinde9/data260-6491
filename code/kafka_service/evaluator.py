"""Score one Planner, Writer, and Reviewer journey that shares a correlation_id.

The judge is a local GEval: each criterion has evaluation steps, and the local
model returns a score from 1 (very poor) to 5 (excellent) plus a one-sentence
reason. A missing message or a judge that does not answer in time ends the run
instead of waiting.
"""

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from kafka_service.flow_log import saved_flow_logs
from kafka_service.ops_metrics import parse_flow_line

JUDGE_TIMEOUT_SEC = 30
DEFAULT_TRACE = "2b83f4a7-e6f0-46cc-b334-409b5205daa4"
RESULT_NAME = "part2_evaluation.json"

_SEND = {
    ("PLANNER", "SEND"): "plan",
    ("WRITER", "SEND"): "draft",
    ("REVIEWER", "SEND"): "final",
}

CRITERIA = {
    "plan_quality": {
        "name": "Plan quality",
        "steps": [
            "Check that the plan names the product or the problem in the question.",
            "Check that it names the recall type and tells the writer what the shopper should do.",
            "Score how useful that plan is for writing the answer.",
        ],
    },
    "writer_helpfulness": {
        "name": "Writer helpfulness",
        "steps": [
            "Check that the draft follows the plan.",
            "Check that it tells the shopper not to eat the product and what to do next.",
            "Score whether the draft is accurate and useful.",
        ],
    },
    "final_answer_helpfulness": {
        "name": "Final answer helpfulness",
        "steps": [
            "Check that the answer is about the shopper's question.",
            "Check that a shopper can act on it.",
            "Score how helpful and relevant the final answer is.",
        ],
    },
}


class EvaluationError(RuntimeError):
    """The journey is incomplete, or the judge did not return a usable score."""


def judge_model_name() -> str:
    return os.environ.get("JUDGE_MODEL") or os.environ.get("SMOL_MODEL") or "llama3.2:3b"


def ollama_url() -> str:
    return os.environ.get("OLLAMA_URL", "http://localhost:11434").rstrip("/")


def load_joined(root: Path, correlation_id: str) -> dict:
    """Load the plan, draft, and final payloads that share this correlation_id."""
    found: dict[str, dict] = {}
    for path in saved_flow_logs(root):
        if path.suffix != ".log":
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            event = parse_flow_line(line, path.name)
            if event is None or event.correlation_id != correlation_id or not event.payload:
                continue
            slot = _SEND.get((event.component, event.raw_stage))
            if slot is None:
                continue
            found[slot] = {
                "source": path.name,
                "timestamp": event.ts.isoformat(),
                "component": event.component,
                "stage": event.raw_stage,
                "message": event.payload,
            }
    missing = [name for name in ("plan", "draft", "final") if name not in found]
    if missing:
        raise EvaluationError(
            f"{correlation_id} is missing {', '.join(missing)}. "
            "The evaluator only scores a journey that has a plan, a draft, and a final answer."
        )
    plan = found["plan"]["message"]
    draft = found["draft"]["message"]
    final = found["final"]["message"]
    if not isinstance(plan.get("plan"), list) or not str(draft.get("draft", "")).strip():
        raise EvaluationError(
            f"{correlation_id} has a plan or draft message the judge cannot score."
        )
    if not str(final.get("answer", "")).strip():
        raise EvaluationError(f"{correlation_id} has no final answer.")
    return {
        "trace_id": correlation_id,
        "question": str(plan.get("question") or draft.get("question") or ""),
        "plan": found["plan"],
        "draft": found["draft"],
        "final": found["final"],
    }


def _ask_judge(model: str, prompt: str) -> str:
    body = json.dumps(
        {
            "model": model,
            "stream": False,
            "think": False,
            "options": {"temperature": 0},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a GEval judge. Reply with one JSON object only: "
                        '{"score": <integer 1 to 5>, "reason": "<one sentence>"}. '
                        "1 means very poor and 5 means excellent."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{ollama_url()}/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=JUDGE_TIMEOUT_SEC) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise EvaluationError(
            f"The local judge ({model}) did not answer within {JUDGE_TIMEOUT_SEC}s: {exc}"
        ) from exc
    content = payload.get("message", {}).get("content", "")
    if not str(content).strip():
        raise EvaluationError(f"The local judge ({model}) returned an empty score.")
    return str(content)


def _parse_verdict(text: str) -> tuple[int, str]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        raise EvaluationError("The judge reply was not JSON.")
    try:
        data = json.loads(text[start : end + 1])
        score = int(data["score"])
        reason = str(data["reason"]).strip()
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise EvaluationError("The judge reply had no score and reason.") from exc
    if score < 1 or score > 5 or not reason:
        raise EvaluationError(f"The judge score {score} is outside 1-5 or has no reason.")
    return score, reason


def score_criterion(model: str, name: str, steps: list[str], material: str) -> dict:
    numbered = "\n".join(f"{index}. {step}" for index, step in enumerate(steps, start=1))
    prompt = f"Criterion: {name}\nEvaluation steps:\n{numbered}\n\nMaterial:\n{material}"
    score, reason = _parse_verdict(_ask_judge(model, prompt))
    return {"score": score, "reason": reason}


def improvement_note(draft: str, final: str, draft_score: int, final_score: int) -> str:
    difference = final_score - draft_score
    if draft.strip() == final.strip():
        return (
            f"The reviewer returned the writer's draft unchanged, so the final answer "
            f"did not improve. The judge scored that same text {draft_score} as the draft "
            f"and {final_score} as the final answer (difference {difference}). "
            "That gap is the judge scoring one answer twice, not a change by the reviewer."
        )
    if difference <= 0:
        return (
            f"The final answer scored {final_score} and the draft scored {draft_score} "
            f"(difference {difference}). On this question the reviewer pass did not make "
            "the answer more helpful."
        )
    return (
        f"The final answer scored {difference} above the draft "
        f"({draft_score} to {final_score}). That gap is the reviewer changing the draft "
        "before it is returned."
    )


def evaluate_joined(joined: dict, model: str | None = None) -> dict:
    model = model or judge_model_name()
    question = joined["question"]
    plan = joined["plan"]["message"]["plan"]
    draft = str(joined["draft"]["message"]["draft"])
    final = str(joined["final"]["message"]["answer"])
    plan_score = score_criterion(
        model,
        CRITERIA["plan_quality"]["name"],
        CRITERIA["plan_quality"]["steps"],
        f"Question: {question}\nPlan:\n" + "\n".join(f"- {step}" for step in plan),
    )
    draft_score = score_criterion(
        model,
        CRITERIA["writer_helpfulness"]["name"],
        CRITERIA["writer_helpfulness"]["steps"],
        f"Question: {question}\nPlan:\n"
        + "\n".join(f"- {step}" for step in plan)
        + f"\nDraft: {draft}",
    )
    final_score = score_criterion(
        model,
        CRITERIA["final_answer_helpfulness"]["name"],
        CRITERIA["final_answer_helpfulness"]["steps"],
        f"Question: {question}\nFinal answer: {final}",
    )
    difference = final_score["score"] - draft_score["score"]
    note = improvement_note(draft, final, draft_score["score"], final_score["score"])
    return {
        "case_id": "part2-end-to-end",
        "trace_id": joined["trace_id"],
        "correlation_id": joined["trace_id"],
        "question": question,
        "plan": plan,
        "plan_quality": plan_score["score"],
        "plan_reason": plan_score["reason"],
        "draft": draft,
        "writer_helpfulness": draft_score["score"],
        "draft_score": draft_score["score"],
        "draft_reason": draft_score["reason"],
        "final_answer": final,
        "final_answer_helpfulness": final_score["score"],
        "final_score": final_score["score"],
        "final_reason": final_score["reason"],
        "improvement": difference,
        "improvement_interpretation": note,
        "messages": {
            "plan": joined["plan"],
            "draft": joined["draft"],
            "final": joined["final"],
        },
    }


def result_document(case: dict, model: str) -> dict:
    return {
        "judge": {
            "method": "GEval",
            "model": model,
            "provider": f"local Ollama at {ollama_url()}",
            "scale": "1 very poor, 5 excellent",
            "timeout_sec": JUDGE_TIMEOUT_SEC,
        },
        "interpretation": case["improvement_interpretation"],
        "cases": [case],
    }


def write_result(root: Path, document: dict) -> Path:
    path = root / "reports" / "hw10" / RESULT_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    return path


def score_writer_draft(question: str, plan: list, draft: str, model: str | None = None) -> dict:
    """Score one frozen writer draft with the same GEval criterion used in Part 2."""
    model = model or judge_model_name()
    steps = "\n".join(f"- {step}" for step in plan)
    return score_criterion(
        model,
        CRITERIA["writer_helpfulness"]["name"],
        CRITERIA["writer_helpfulness"]["steps"],
        f"Question: {question}\nPlan:\n{steps}\nDraft: {draft}",
    )


def _average_ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(values):
        end = start
        while end + 1 < len(values) and values[order[end + 1]] == values[order[start]]:
            end += 1
        average = (start + end) / 2 + 1
        for index in range(start, end + 1):
            ranks[order[index]] = average
        start = end + 1
    return ranks


def _pearson(left: list[float], right: list[float]) -> float | None:
    count = len(left)
    mean_left = sum(left) / count
    mean_right = sum(right) / count
    numerator = sum((x - mean_left) * (y - mean_right) for x, y in zip(left, right))
    left_scale = sum((x - mean_left) ** 2 for x in left) ** 0.5
    right_scale = sum((y - mean_right) ** 2 for y in right) ** 0.5
    if left_scale == 0 or right_scale == 0:
        return None
    return numerator / (left_scale * right_scale)


def spearman(human: list[float], judge: list[float]) -> float | None:
    if len(human) != len(judge) or len(human) < 2:
        return None
    return _pearson(_average_ranks(human), _average_ranks(judge))


def mean_absolute_difference(human: list[float], judge: list[float]) -> float:
    gaps = [abs(left - right) for left, right in zip(human, judge)]
    return sum(gaps) / len(gaps)
