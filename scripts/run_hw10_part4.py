import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))

from kafka_service.evaluator import (  # noqa: E402
    EvaluationError,
    judge_model_name,
    score_writer_draft,
)
from kafka_service.failure import PoisonMessage  # noqa: E402
from kafka_service.flow_log import span_log_path, write_span  # noqa: E402
from kafka_service.planner import make_plan  # noqa: E402
from kafka_service.reviewer import review_draft  # noqa: E402
from kafka_service.writer import handle as write_message  # noqa: E402

OUT = REPO / "reports" / "hw10" / "part4_latency.json"
MISS_COUNT = 50
TABLE_STAGES = (
    ("cache_lookup", "Cache lookup"),
    ("planner", "Planner"),
    ("writer", "Writer"),
    ("reviewer", "Reviewer"),
    ("queue_wait", "Queue wait (total)"),
    ("evaluation", "Evaluation"),
)


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    rank = (len(ordered) - 1) * (pct / 100)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


class ExactStore:
    """Used only when Redis is down. A repeated question is a hit. A new one is a miss."""

    def __init__(self) -> None:
        self.saved: dict[str, str] = {}

    def lookup(self, question: str) -> str | None:
        return self.saved.get(question)

    def store(self, question: str, answer: str) -> None:
        self.saved[question] = answer


def span(
    trace_id: str,
    stage: str,
    start: datetime,
    end: datetime,
    status: str,
    error: str = "",
    cache: str | None = None,
) -> float:
    write_span(trace_id, stage, start, end, status, error, cache=cache)
    return (end - start).total_seconds() * 1000


def run_stage(trace_id: str, stage: str, work, cache: str | None = None) -> tuple[object, float]:
    start = datetime.now(timezone.utc)
    try:
        value = work()
    except Exception as exc:
        span(trace_id, stage, start, datetime.now(timezone.utc), "error", str(exc), cache)
        raise
    duration = span(trace_id, stage, start, datetime.now(timezone.utc), "ok", cache=cache)
    return value, duration


def miss_journey(store: ExactStore, question: str, trace_id: str, judge: str) -> dict:
    durations = {}
    gaps = []
    previous = datetime.now(timezone.utc)

    def mark_end() -> None:
        nonlocal previous
        previous = datetime.now(timezone.utc)

    def handoff() -> None:
        nonlocal previous
        now = datetime.now(timezone.utc)
        gaps.append((now - previous).total_seconds() * 1000)
        previous = now

    found, durations["cache_lookup"] = run_stage(
        trace_id, "cache_lookup", lambda: store.lookup(question), cache="miss"
    )
    if found is not None:
        raise EvaluationError(f"{trace_id} was served from the cache")
    mark_end()
    handoff()
    run_stage(trace_id, "inbox", lambda: question)
    mark_end()
    plan, durations["planner"] = run_stage(trace_id, "planner", lambda: make_plan(question))
    mark_end()
    handoff()
    drafted, durations["writer"] = run_stage(
        trace_id,
        "writer",
        lambda: write_message({"correlation_id": trace_id, "question": question, "plan": plan}),
    )
    mark_end()
    handoff()
    reviewed, durations["reviewer"] = run_stage(
        trace_id, "reviewer", lambda: review_draft(drafted["draft"])
    )
    _status, answer = reviewed
    run_stage(trace_id, "final", lambda: answer)
    total_wait = round(sum(gaps), 3)
    wait_start = datetime.now(timezone.utc)
    wait_end = wait_start + timedelta(milliseconds=total_wait)
    span(trace_id, "queue_wait", wait_start, wait_end, "ok")
    durations["queue_wait"] = total_wait
    verdict, durations["evaluation"] = run_stage(
        trace_id,
        "evaluation",
        lambda: score_writer_draft(question, plan, drafted["draft"], judge),
    )
    store.store(question, answer)
    durations["e2e"] = round(sum(durations[name] for name, _label in TABLE_STAGES), 3)
    return durations | {"answer": answer, "score": verdict["score"]}


def hit_journey(store: ExactStore, question: str, trace_id: str) -> float:
    started = datetime.now(timezone.utc)
    found = store.lookup(question)
    ended = datetime.now(timezone.utc)
    if not found:
        raise EvaluationError("the cache-hit example was not stored")
    return span(trace_id, "cache_lookup", started, ended, "ok", cache="hit")


def failed_journey(trace_id: str) -> str:
    question = "This message is marked poison and the writer should stop."
    run_stage(trace_id, "cache_lookup", lambda: None, cache="miss")
    run_stage(trace_id, "inbox", lambda: question)
    plan = make_plan(question)
    run_stage(trace_id, "planner", lambda: plan)
    try:
        run_stage(
            trace_id,
            "writer",
            lambda: write_message(
                {"correlation_id": trace_id, "question": question, "plan": plan, "poison": True}
            ),
        )
    except PoisonMessage as exc:
        return str(exc)
    raise EvaluationError("the poison message did not fail")


def summarize(rows: list[dict]) -> list[dict]:
    table = []
    for key, label in TABLE_STAGES:
        values = [row[key] for row in rows]
        shares = [row[key] / row["e2e"] * 100 for row in rows if row["e2e"]]
        table.append(
            {
                "stage": label,
                "p50_ms": round(percentile(values, 50), 3),
                "p95_ms": round(percentile(values, 95), 3),
                "percent_of_e2e": round(sum(shares) / len(shares), 1),
            }
        )
    return table


def main() -> int:
    judge = judge_model_name()
    store = ExactStore()
    span_log_path().parent.mkdir(parents=True, exist_ok=True)
    span_log_path().write_text("", encoding="utf-8")
    print(f"judge = {judge}", flush=True)
    print(
        "cache = exact-question store (Redis is not running). New questions are misses.", flush=True
    )
    miss_id = str(uuid.uuid4())
    hit_id = str(uuid.uuid4())
    fail_id = str(uuid.uuid4())
    example_question = (
        "A shopper found a torn bag of frozen berries, example for the cache-miss trace. "
        "What should they do?"
    )
    try:
        miss_journey(store, example_question, miss_id, judge)
        hit_ms = hit_journey(store, example_question, hit_id)
        failure = failed_journey(fail_id)
        measured = []
        for index in range(1, MISS_COUNT + 1):
            question = (
                f"Uncached recall question {index}: a new bag no one has asked about, "
                f"seal torn, lot {index}."
            )
            trace_id = str(uuid.uuid4())
            measured.append(miss_journey(store, question, trace_id, judge))
            if index % 10 == 0:
                print(f"measured {index}/{MISS_COUNT}", flush=True)
    except (EvaluationError, PoisonMessage) as exc:
        print(f"part 4 stopped: {exc}", flush=True)
        return 1

    if any(row.get("served_from_cache") for row in measured):
        print("part 4 stopped: a measured request was served from the cache", flush=True)
        return 1
    table = summarize(measured)
    dominant = max(table, key=lambda row: row["p50_ms"])
    document = {
        "cache_backend": "exact-question store because Redis was not running",
        "kafka": "not running; planner, writer, reviewer, and the judge ran in-process",
        "judge": judge,
        "miss_count": MISS_COUNT,
        "all_confirmed_misses": True,
        "window": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "traces": {
            "cache_hit": hit_id,
            "cache_miss": miss_id,
            "failed": fail_id,
            "failed_stage": "writer",
            "failed_error": failure,
        },
        "cache_hit_latency_ms": {"p50": round(hit_ms, 3), "p95": round(hit_ms, 3)},
        "stages": table,
        "dominant_stage": dominant["stage"],
        "optimize_first": (
            f"{dominant['stage']} is the largest share of a cache miss "
            f"(p50 {dominant['p50_ms']} ms, {dominant['percent_of_e2e']}% of end-to-end). "
            "I would take that stage off the shopper's wait, or make it cheaper, before tuning the others."
        ),
    }
    OUT.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"hit {hit_id}", flush=True)
    print(f"miss {miss_id}", flush=True)
    print(f"failed {fail_id} writer: {failure}", flush=True)
    for row in table:
        print(
            f"{row['stage']}: p50 {row['p50_ms']} ms, p95 {row['p95_ms']} ms, {row['percent_of_e2e']}%",
            flush=True,
        )
    print(document["optimize_first"], flush=True)
    print(f"wrote {OUT.relative_to(REPO)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
