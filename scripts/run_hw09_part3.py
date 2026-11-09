import json
import re
import sys
import time
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))
sys.path.insert(0, str(REPO / "code" / "web_application"))
sys.path.insert(0, str(REPO / "src"))

from dotenv import load_dotenv

load_dotenv(REPO / "code" / "web_application" / ".env")

from kafka_service.config import PREFIX  # noqa: E402
from kafka_service.qa_ingress import (  # noqa: E402
    answer_question,
    load_records,
    run_hw8_path,
    set_affected_units,
)
from kafka_service.semantic_cache import SemanticCache, embed_text  # noqa: E402

CASES_PATH = REPO / "reports" / "hw09" / "cache_cases.yaml"
RESULTS_PATH = REPO / "reports" / "hw09" / "part3_results.json"
THRESHOLDS = (0.75, 0.80, 0.85, 0.90, 0.95)
MISS_COST = 8.0
FALSE_HIT_COST = 40.0
HIT_COST = 0.2
SHOULD_MISS = 20
STALE_CODE = "REC-0001"
STALE_UNITS_BEFORE = 120
STALE_UNITS_AFTER = 300
STALE_QUESTION = (
    "How many units were affected in the Trader Joe's Organic Frozen Blueberries, 16oz recall?"
)


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _explain(cached_query: str, incoming: str, score: float) -> str:
    words = re.compile(r"[a-z0-9']+")
    left = set(words.findall(cached_query.lower()))
    right = set(words.findall(incoming.lower()))
    shared = sorted(left & right)
    changed = sorted(right - left)
    shared_text = ", ".join(shared[:12]) or "almost the same words"
    changed_text = ", ".join(changed[:8]) or "a small wording change"
    return (
        f"Cosine similarity was {score:.4f}. The questions share these words: {shared_text}. "
        f"The incoming question changes: {changed_text}. "
        "all-MiniLM-L6-v2 treats that overlap as almost the same question, "
        "but the product is different, so the cached answer is about the wrong recall."
    )


def _load_cases() -> tuple[list[dict], list[dict]]:
    document = yaml.safe_load(CASES_PATH.read_text())
    cases = document["cases"]
    seeds = document["seeds"]
    counts = {}
    for case in cases:
        counts[case["group"]] = counts.get(case["group"], 0) + 1
    expected = {
        "exact_duplicate": 10,
        "paraphrase": 10,
        "superficial": 10,
        "unrelated": 10,
    }
    if counts != expected:
        raise SystemExit(f"cache_cases.yaml must stay 10/10/10/10. Found {counts}.")
    return cases, seeds


def _seed(cache: SemanticCache, seeds: list[dict]) -> tuple[list[dict], float]:
    print("Seeding 10 source questions. Each one calls qwen3:8b once.", flush=True)
    print("cache_cases.yaml is not modified.", flush=True)
    ready = []
    latencies = []
    records = load_records()
    for seed in seeds:
        print(f"seed {seed['id']}", flush=True)
        started = time.perf_counter()
        generated = run_hw8_path(seed["query"], records)
        latency_ms = (time.perf_counter() - started) * 1000
        latencies.append(latency_ms)
        ready.append(
            {
                "query": seed["query"],
                "answer": generated["answer"],
                "data_version": generated["data_version"],
                "recall_code": seed["recall_code"],
                "latency_ms": latency_ms,
            }
        )
        print(f"  stored recall_code={seed['recall_code']} latency_ms={latency_ms:.1f}", flush=True)
    return ready, _avg(latencies)


def _sweep(cache: SemanticCache, cases: list[dict], seeds: list[dict], model_ms: float):
    tables = []
    probes = []
    measured = {}
    records = load_records()
    for threshold in THRESHOLDS:
        cache.reset()
        for seed in seeds:
            cache.store(seed["query"], seed["answer"], seed["data_version"], seed["recall_code"])
        latencies = []
        correct_hits = 0
        false_hits = 0
        print(f"threshold {threshold:.2f}", flush=True)
        for case in cases:
            started = time.perf_counter()
            found = cache.search(case["query"])
            search_ms = (time.perf_counter() - started) * 1000
            similarity = 0.0 if found is None else found["similarity"]
            hit = found is not None and similarity >= threshold
            if hit:
                latency_ms = search_ms
                if case["expect"] == "hit":
                    correct_hits += 1
                else:
                    false_hits += 1
            else:
                if case["id"] not in measured:
                    print(f"  timing miss {case['id']}", flush=True)
                    generated_at = time.perf_counter()
                    run_hw8_path(case["query"], records)
                    measured[case["id"]] = (time.perf_counter() - generated_at) * 1000
                latency_ms = search_ms + measured[case["id"]]
            latencies.append(latency_ms)
            probes.append(
                {
                    "id": case["id"],
                    "group": case["group"],
                    "expect": case["expect"],
                    "threshold": threshold,
                    "hit": hit,
                    "false_hit": hit and case["expect"] == "miss",
                    "similarity": round(similarity, 4),
                    "latency_ms": round(latency_ms, 1),
                    "query": case["query"],
                    "cached_query": "" if not hit else found["query"],
                    "cached_answer": "" if not hit else found["answer"],
                    "correct_answer": case["correct_answer"],
                }
            )
        misses = len(cases) - correct_hits - false_hits
        cost = correct_hits * HIT_COST + misses * MISS_COST + false_hits * FALSE_HIT_COST
        summary = {
            "threshold": threshold,
            "hit_rate": round(100.0 * (correct_hits + false_hits) / len(cases), 1),
            "false_hit_rate": round(100.0 * false_hits / SHOULD_MISS, 1),
            "mean_latency_ms": round(_avg(latencies), 1),
            "correct_hits": correct_hits,
            "false_hits": false_hits,
            "misses": misses,
            "total_cost": round(cost, 1),
        }
        tables.append(summary)
        print(
            f"  hit_rate={summary['hit_rate']}% false_hit_rate={summary['false_hit_rate']}% "
            f"mean_latency_ms={summary['mean_latency_ms']} total_cost={summary['total_cost']}",
            flush=True,
        )
    return tables, probes, model_ms


def _print_table(tables: list[dict], model_ms: float) -> None:
    print()
    print("=== Cost model ===")
    print(f"  correct hit = {HIT_COST}  (a Redis search, not a model call)")
    print(f"  miss = {MISS_COST}  (one local qwen3:8b call; the shopper waits)")
    print(f"  false hit = {FALSE_HIT_COST}  (a wrong recall is worse than a slow correct answer)")
    print("  total = correct_hits * 0.2 + misses * 8 + false_hits * 40")
    print("  hit rate = cached responses / 40")
    print("  false-hit rate = false hits / 20 questions that should miss")
    print(
        f"  mean latency uses the live Redis search. A miss also adds that question's "
        f"own model time, measured once. The 10 seed calls averaged {model_ms:.1f} ms."
    )
    print()
    header = f"{'Threshold':>10} {'Hit rate':>10} {'False-hit rate':>16} {'Mean latency ms':>18} {'Total cost':>12}"
    print(header)
    for row in tables:
        print(
            f"{row['threshold']:>10.2f} {row['hit_rate']:>9.1f}% {row['false_hit_rate']:>15.1f}% "
            f"{row['mean_latency_ms']:>18.1f} {row['total_cost']:>12.1f}"
        )


def _choose(tables: list[dict]) -> dict:
    return min(
        tables, key=lambda row: (row["total_cost"], row["false_hit_rate"], -row["threshold"])
    )


def _false_hit(probes: list[dict]) -> dict | None:
    hits = [row for row in probes if row["false_hit"]]
    if not hits:
        return None
    return max(hits, key=lambda row: (row["threshold"] == 0.85, row["similarity"]))


def _print_false_hit(chosen: dict | None) -> None:
    print()
    print("=== One false hit ===")
    if chosen is None:
        print(
            "No false hit at these five thresholds. The labels in cache_cases.yaml were not changed."
        )
        return
    print(f"threshold: {chosen['threshold']:.2f}")
    print(f"case: {chosen['id']} group={chosen['group']}")
    print(f"cached query: {chosen['cached_query']}")
    print(f"incoming query: {chosen['query']}")
    print(f"similarity: {chosen['similarity']:.4f}")
    print(f"cached answer: {chosen['cached_answer']}")
    print(f"correct answer: {chosen['correct_answer']}")
    print(_explain(chosen["cached_query"], chosen["query"], chosen["similarity"]))


def _stale(cache: SemanticCache) -> dict:
    print()
    print("=== Stale answer ===")
    set_affected_units(STALE_CODE, STALE_UNITS_BEFORE)
    cache.reset()
    first = answer_question(STALE_QUESTION, cache, None, 0.85)
    print(f"first answer (data_version={first['data_version']}): {first['answer']}")
    updated = set_affected_units(STALE_CODE, STALE_UNITS_AFTER)
    print(
        f"updated {STALE_CODE} affected_units={updated['affected_units']} "
        f"data_version={updated['data_version']}"
    )
    stale = answer_question(
        STALE_QUESTION,
        cache,
        None,
        0.85,
        validate_version=False,
        store_miss=False,
    )
    print("cached entry before invalidation:", json.dumps(cache.entry(STALE_QUESTION)))
    print(f"stale hit is_cached={str(stale['is_cached']).lower()} answer: {stale['answer']}")
    fresh = answer_question(STALE_QUESTION, cache, None, 0.85, validate_version=True)
    print("cached entry after invalidation:", json.dumps(cache.entry(STALE_QUESTION)))
    print(f"fresh answer (data_version={fresh['data_version']}): {fresh['answer']}")
    print()
    print(
        "Trade-off: checking data_version on a hit costs one database read, "
        "so a hit is no longer only a Redis lookup. The gain is that a shopper does not "
        "keep the old unit count after the recall row changes. A time-to-live key would "
        "be faster and would stay wrong until it expired."
    )
    return {
        "question": STALE_QUESTION,
        "recall_code": STALE_CODE,
        "first_answer": first["answer"],
        "stale_answer": stale["answer"],
        "fresh_answer": fresh["answer"],
        "updated_units": updated["affected_units"],
        "updated_version": updated["data_version"],
    }


def main() -> None:
    print(f"prefix: {PREFIX}")
    print("part: 3 threshold and stale answers")
    print(f"database: {PREFIX}_rel")
    print(flush=True)

    cases, seeds = _load_cases()
    embed_text("warmup")
    cache = SemanticCache()
    set_affected_units(STALE_CODE, STALE_UNITS_BEFORE)
    ready, model_ms = _seed(cache, seeds)
    tables, probes, model_ms = _sweep(cache, cases, ready, model_ms)
    _print_table(tables, model_ms)
    chosen = _choose(tables)
    print()
    print(
        f"Ship threshold {chosen['threshold']:.2f}. "
        f"It has the lowest total cost ({chosen['total_cost']}). "
        f"Hit rate {chosen['hit_rate']}% and false-hit rate {chosen['false_hit_rate']}%."
    )
    false_hit = _false_hit(probes)
    _print_false_hit(false_hit)
    stale = {}
    try:
        stale = _stale(cache)
    finally:
        restored = set_affected_units(STALE_CODE, STALE_UNITS_BEFORE)
        print(
            f"restored {STALE_CODE} affected_units={restored['affected_units']} "
            f"data_version={restored['data_version']}"
        )

    RESULTS_PATH.write_text(
        json.dumps(
            {
                "thresholds": tables,
                "ship_threshold": chosen["threshold"],
                "false_hit": false_hit,
                "stale": stale,
                "costs": {
                    "hit": HIT_COST,
                    "miss": MISS_COST,
                    "false_hit": FALSE_HIT_COST,
                },
            },
            indent=2,
        )
        + "\n"
    )
    print(f"wrote {RESULTS_PATH}")


if __name__ == "__main__":
    main()
