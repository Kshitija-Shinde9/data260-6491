"""Part 4 over Kafka: one trace_id from the semantic cache, through the topics, to the judge.

Needs Redis Stack, the Kafka broker, planner.py, writer.py, reviewer.py, and Ollama running.
A cache miss is looked up in Redis, published to s6491_inbox with the same id, followed through
the planner, writer, and reviewer processes, and scored by the Part 2 evaluator. A cache hit
stops after the lookup. The failed trace publishes a poison message to s6491_tasks.
"""

import itertools
import json
import os
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))

from kafka_service.config import FINAL_TOPIC, INBOX_TOPIC, TASKS_TOPIC  # noqa: E402
from kafka_service.evaluator import (  # noqa: E402
    EvaluationError,
    evaluate_joined,
    judge_model_name,
    load_joined,
)
from kafka_service.flow_log import (  # noqa: E402
    log_flow,
    read_flow_lines,
    span_log_path,
    write_span,
)
from kafka_service.kafka_io import build_producer, send_json, wait_for_broker  # noqa: E402
from kafka_service.ops_metrics import parse_flow_line  # noqa: E402
from kafka_service.pipeline import FinalWaiter, new_correlation_id  # noqa: E402
from kafka_service.semantic_cache import SemanticCache  # noqa: E402

OUT = REPO / "reports" / "hw10" / "part4_latency.json"
THRESHOLD = float(os.getenv("QA_THRESHOLD", "0.95"))
MISS_TARGET = 50
HIT_SAMPLES = 10
MAX_EXCLUDED = 5
FINAL_TIMEOUT_SEC = 30
POISON_TIMEOUT_SEC = 40
EXAMPLE_QUESTION = (
    "A shopper found a torn bag of frozen berries, example for the cache-miss trace. "
    "What should they do?"
)
POISON_QUESTION = "This message is marked poison and the writer should stop."
TABLE_STAGES = (
    ("cache_lookup", "Cache lookup"),
    ("planner", "Planner"),
    ("writer", "Writer"),
    ("reviewer", "Reviewer"),
    ("queue_wait", "Queue wait (total)"),
    ("evaluation", "Evaluation"),
)
PRODUCTS = (
    "Sunridge granola bars, 12 count",
    "Bayview oat milk, 32oz carton",
    "Harvest Table canned chickpeas, 15oz",
    "Northfield sharp cheddar, 8oz block",
    "Golden Acre white bread loaf",
    "Marlow Farms baby carrots, 1lb bag",
    "Cedar Bay smoked salmon, 6oz pack",
    "Pinecrest peanut butter, 16oz jar",
    "Orchard Lane apple juice, 64oz bottle",
    "Brightleaf romaine hearts, 3 pack",
    "Millstone whole wheat pasta, 16oz box",
    "Redwood Creek tomato soup, 18oz can",
    "Seaside shrimp cocktail tray",
    "Larkspur vanilla yogurt, 32oz tub",
    "Ironwood beef jerky, 3oz bag",
    "Willow Run free-range eggs, one dozen",
    "Summit Peak frozen pizza, pepperoni",
    "Clover Hill cottage cheese, 16oz",
    "Driftwood coconut water, 6 pack",
    "Tidewater canned tuna, 5oz",
)
PROBLEMS = (
    "The lid is cracked and some of it leaked.",
    "It has a strange chemical smell.",
    "The date on the label is smudged.",
    "A piece of plastic was inside.",
    "The label does not list milk but the small print mentions it.",
    "It was left out of the fridge overnight.",
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def milliseconds(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() * 1000


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    rank = (len(ordered) - 1) * (pct / 100)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] * (1 - (rank - low)) + ordered[high] * (rank - low)


def question_pool() -> list[str]:
    pairs = list(itertools.product(PRODUCTS, PROBLEMS))
    random.Random(266491).shuffle(pairs)
    return [f"{product}: {problem} What should the shopper do?" for product, problem in pairs]


def lookup(
    cache: SemanticCache, trace_id: str, question: str
) -> tuple[bool, dict | None, datetime, datetime]:
    start = now()
    found = cache.search(question)
    end = now()
    similarity = 0.0 if found is None else found["similarity"]
    hit = found is not None and similarity >= THRESHOLD
    label = "hit" if hit else "miss"
    detail = f"cache {label} similarity={similarity:.4f} is_cached={str(hit).lower()}"
    log_flow("CACHE", "LOOKUP", f"corr={trace_id} {detail}")
    write_span(trace_id, "cache_lookup", start, end, "ok", cache=label, detail=detail)
    return hit, found, start, end


def read_spans(trace_id: str) -> dict[str, dict]:
    found: dict[str, dict] = {}
    path = span_log_path()
    if not path.is_file():
        return found
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if trace_id not in line:
            continue
        try:
            span = json.loads(line)
        except json.JSONDecodeError:
            continue
        if span.get("trace_id") == trace_id:
            found[span["stage"]] = span
    return found


def wait_for_spans(trace_id: str, stages: tuple[str, ...]) -> dict[str, dict]:
    for _ in range(40):
        found = read_spans(trace_id)
        if all(stage in found for stage in stages):
            return found
        time.sleep(0.25)
    raise EvaluationError(f"{trace_id} has no span from {', '.join(stages)} in {span_log_path()}.")


def hop_times(trace_id: str) -> dict[tuple[str, str], datetime]:
    wanted = {
        ("PLANNER", "RECEIVE"),
        ("PLANNER", "SEND"),
        ("WRITER", "RECEIVE"),
        ("WRITER", "SEND"),
        ("REVIEWER", "RECEIVE"),
        ("REVIEWER", "SEND"),
    }
    for _ in range(40):
        times = {}
        for line in read_flow_lines(trace_id):
            event = parse_flow_line(line, "flow")
            if event is not None:
                times.setdefault((event.component, event.raw_stage), event.ts)
        if wanted <= set(times):
            return times
        time.sleep(0.25)
    raise EvaluationError(
        f"{trace_id} is missing planner, writer, or reviewer lines in the flow log."
    )


def queue_wait_ms(times: dict, inbox_end: datetime, received: datetime) -> float:
    gaps = [
        times[("PLANNER", "RECEIVE")] - inbox_end,
        times[("WRITER", "RECEIVE")] - times[("PLANNER", "SEND")],
        times[("REVIEWER", "RECEIVE")] - times[("WRITER", "SEND")],
        received - times[("REVIEWER", "SEND")],
    ]
    return sum(max(0.0, gap.total_seconds() * 1000) for gap in gaps)


def span_ms(span: dict) -> float:
    return milliseconds(datetime.fromisoformat(span["start"]), datetime.fromisoformat(span["end"]))


def kafka_journey(
    cache: SemanticCache,
    producer,
    waiter: FinalWaiter,
    question: str,
    judge: str,
    trace_id: str,
) -> dict | None:
    hit, _found, lookup_start, _lookup_end = lookup(cache, trace_id, question)
    if hit:
        return None

    message = {"correlation_id": trace_id, "question": question}
    inbox_start = now()
    log_flow("YOU", "SEND", f"corr={trace_id} -> {INBOX_TOPIC}", message)
    send_json(producer, INBOX_TOPIC, trace_id, message)
    inbox_end = now()
    write_span(trace_id, "inbox", inbox_start, inbox_end, "ok")

    final = waiter.wait(trace_id, FINAL_TIMEOUT_SEC)
    received = now()
    if final is None:
        raise EvaluationError(
            f"No answer for {trace_id}. Check that planner.py, writer.py, and reviewer.py are running."
        )
    log_flow("YOU", "FINAL", f"corr={trace_id} status={final.get('status')}", final)

    agent = wait_for_spans(trace_id, ("planner", "writer", "reviewer"))
    times = hop_times(trace_id)
    wait_ms = queue_wait_ms(times, inbox_end, received)
    write_span(trace_id, "final", times[("REVIEWER", "SEND")], received, "ok")
    write_span(trace_id, "queue_wait", inbox_end, inbox_end + timedelta(milliseconds=wait_ms), "ok")

    evaluation_start = now()
    try:
        verdict = evaluate_joined(load_joined(REPO, trace_id), judge)
    except EvaluationError as exc:
        write_span(trace_id, "evaluation", evaluation_start, now(), "error", str(exc))
        raise
    evaluation_end = now()
    write_span(trace_id, "evaluation", evaluation_start, evaluation_end, "ok")

    cache_span = read_spans(trace_id)["cache_lookup"]
    return {
        "trace_id": trace_id,
        "answer": str(final.get("answer", "")),
        "cache_lookup": span_ms(cache_span),
        "planner": span_ms(agent["planner"]),
        "writer": span_ms(agent["writer"]),
        "reviewer": span_ms(agent["reviewer"]),
        "queue_wait": wait_ms,
        "evaluation": milliseconds(evaluation_start, evaluation_end),
        "e2e": milliseconds(lookup_start, evaluation_end),
        "plan_quality": verdict["plan_quality"],
    }


def failed_journey(cache: SemanticCache, producer) -> tuple[str, str]:
    trace_id = new_correlation_id()
    hit, _found, _start, _end = lookup(cache, trace_id, POISON_QUESTION)
    if hit:
        raise EvaluationError("The poison question was served from the cache.")
    message = {"correlation_id": trace_id, "question": POISON_QUESTION, "plan": [], "poison": True}
    log_flow("YOU", "SEND", f"corr={trace_id} -> {TASKS_TOPIC}", message)
    send_json(producer, TASKS_TOPIC, trace_id, message)

    deadline = time.time() + POISON_TIMEOUT_SEC
    while time.time() < deadline:
        for line in read_flow_lines(trace_id):
            event = parse_flow_line(line, "flow")
            if event is not None and event.component == "WRITER" and event.raw_stage == "DEAD":
                spans = wait_for_spans(trace_id, ("writer",))
                return trace_id, spans["writer"].get("error") or "poison message"
        time.sleep(0.5)
    raise EvaluationError(
        "The writer did not dead-letter the poison message. Is writer.py running?"
    )


def summarize(rows: list[dict]) -> tuple[list[dict], float]:
    table = []
    for key, label in TABLE_STAGES:
        values = [row[key] for row in rows]
        shares = [row[key] / row["e2e"] * 100 for row in rows]
        table.append(
            {
                "stage": label,
                "p50_ms": round(percentile(values, 50), 3),
                "p95_ms": round(percentile(values, 95), 3),
                "percent_of_e2e": round(sum(shares) / len(shares), 1),
            }
        )
    other = [100 - sum(row[key] for key, _label in TABLE_STAGES) / row["e2e"] * 100 for row in rows]
    return table, round(sum(other) / len(other), 1)


def optimize_first(dominant: dict) -> str:
    advice = {
        "Evaluation": "run the judge after the answer is returned, or use a cheaper judge call",
        "Queue wait (total)": "look at consumer poll and fetch settings on the topics",
    }.get(dominant["stage"], "look at that stage's own code")
    return (
        f"{dominant['stage']} is the largest share of a cache miss "
        f"(p50 {dominant['p50_ms']} ms, {dominant['percent_of_e2e']}% of end-to-end). "
        f"I would {advice} before tuning the others."
    )


def main() -> int:
    judge = judge_model_name()
    print(f"judge = {judge}, cache threshold = {THRESHOLD}", flush=True)
    cache = SemanticCache()
    cache.search("warm up the embedding model")
    wait_for_broker()
    producer = build_producer()
    waiter = FinalWaiter(FINAL_TOPIC)
    cache.delete(cache.key_for(EXAMPLE_QUESTION))
    measured: list[dict] = []
    excluded: list[str] = []
    skipped_hits = 0
    try:
        miss_id = new_correlation_id()
        example = kafka_journey(cache, producer, waiter, EXAMPLE_QUESTION, judge, miss_id)
        if example is None:
            print("The example question was already cached. Rerun the script.", flush=True)
            return 1
        cache.store(EXAMPLE_QUESTION, example["answer"], "0", "")
        print(f"miss {miss_id}", flush=True)

        hit_ids = []
        hit_ms = []
        for _ in range(HIT_SAMPLES):
            hit_id = new_correlation_id()
            hit, _found, start, end = lookup(cache, hit_id, EXAMPLE_QUESTION)
            if not hit:
                print("The stored question was not found again.", flush=True)
                return 1
            hit_ids.append(hit_id)
            hit_ms.append(milliseconds(start, end))
        print(f"hit {hit_ids[0]}", flush=True)

        failed_id, failed_error = failed_journey(cache, producer)
        print(f"failed {failed_id} writer: {failed_error}", flush=True)

        for question in question_pool():
            if len(measured) >= MISS_TARGET:
                break
            try:
                row = kafka_journey(cache, producer, waiter, question, judge, new_correlation_id())
            except EvaluationError as exc:
                excluded.append(str(exc))
                print(f"excluded: {exc}", flush=True)
                if len(excluded) > MAX_EXCLUDED:
                    print(
                        "Too many failed requests. Check Ollama and the three agents.", flush=True
                    )
                    return 1
                continue
            if row is None:
                skipped_hits += 1
                continue
            measured.append(row)
            if len(measured) % 10 == 0:
                print(f"measured {len(measured)}/{MISS_TARGET}", flush=True)
    finally:
        cache.delete(cache.key_for(EXAMPLE_QUESTION))
        producer.flush(5)
        waiter.close()

    if len(measured) < MISS_TARGET:
        print(f"Only {len(measured)} confirmed misses were measured.", flush=True)
        return 1

    table, other_percent = summarize(measured)
    dominant = max(table, key=lambda row: row["p50_ms"])
    document = {
        "cache_backend": f"Redis semantic cache, all-MiniLM-L6-v2, threshold {THRESHOLD}",
        "kafka": (
            "planner, writer, and reviewer ran as separate processes on "
            "s6491_inbox, s6491_tasks, s6491_drafts, and s6491_final"
        ),
        "judge": judge,
        "miss_count": len(measured),
        "all_confirmed_misses": True,
        "window": now().strftime("%Y-%m-%d"),
        "traces": {
            "cache_hit": hit_ids[0],
            "cache_miss": miss_id,
            "failed": failed_id,
            "failed_stage": "writer",
            "failed_error": failed_error,
        },
        "cache_hit_latency_ms": {
            "p50": round(percentile(hit_ms, 50), 3),
            "p95": round(percentile(hit_ms, 95), 3),
            "samples": len(hit_ms),
        },
        "stages": table,
        "other_percent_of_e2e": other_percent,
        "excluded_requests": len(excluded),
        "skipped_cache_hits": skipped_hits,
        "dominant_stage": dominant["stage"],
        "optimize_first": optimize_first(dominant),
    }
    OUT.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    for row in table:
        print(
            f"{row['stage']}: p50 {row['p50_ms']} ms, p95 {row['p95_ms']} ms, "
            f"{row['percent_of_e2e']}%",
            flush=True,
        )
    print(document["optimize_first"], flush=True)
    print(f"wrote {OUT.relative_to(REPO)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
