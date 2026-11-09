import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))
sys.path.insert(0, str(REPO / "code" / "web_application"))
sys.path.insert(0, str(REPO / "src"))

from dotenv import load_dotenv

load_dotenv(REPO / "code" / "web_application" / ".env")

from kafka_service.config import PREFIX, QA_THRESHOLD  # noqa: E402
from kafka_service.qa_ingress import answer_question, load_records  # noqa: E402
from kafka_service.semantic_cache import SemanticCache, embed_text  # noqa: E402

QUERIES = [
    ("new", "What is the recall type for Trader Joe's Organic Frozen Blueberries, 16oz?"),
    ("exact", "What is the recall type for Trader Joe's Organic Frozen Blueberries, 16oz?"),
    ("paraphrase", "What recall type applies to Trader Joe's Organic Frozen Blueberries, 16oz?"),
    ("new", "What is the recall type for Kirkland Signature Trail Mix, 4lb?"),
    ("exact", "What is the recall type for Kirkland Signature Trail Mix, 4lb?"),
    ("paraphrase", "What recall type applies to Kirkland Signature Trail Mix, 4lb?"),
    (
        "new",
        "What should a shopper do with the Safeway Signature Rotisserie Chicken that was lukewarm?",
    ),
    (
        "exact",
        "What should a shopper do with the Safeway Signature Rotisserie Chicken that was lukewarm?",
    ),
    ("new", "What is the recall type for Trader Joe's Organic Frozen Strawberries, 16oz?"),
    ("new", "What is the capital of France?"),
    ("new", "Which undeclared allergen is in the Kirkland Signature Trail Mix, 4lb recall?"),
    (
        "paraphrase",
        "What undeclared allergen does the Kirkland Signature Trail Mix, 4lb recall involve?",
    ),
]


def _avg(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def main() -> None:
    print(f"prefix: {PREFIX}")
    print("part: 2 semantic cache")
    print(f"threshold: {QA_THRESHOLD}")
    print("A miss follows planner -> src/model_client.py -> reviewer.")
    print(flush=True)

    embed_text("warmup")
    records = load_records()
    cache = SemanticCache()
    cache.reset()

    rows = []
    for index, (kind, question) in enumerate(QUERIES, start=1):
        print(f"[{index}] kind={kind}")
        print(f"Q: {question}")
        result = answer_question(question, cache, records, QA_THRESHOLD)
        print(f"A: {result['answer']}")
        print(
            f"is_cached={str(result['is_cached']).lower()} "
            f"similarity={result['similarity']:.4f} latency_ms={result['latency_ms']:.1f}"
        )
        print(flush=True)
        rows.append(result)

    hits = [row for row in rows if row["is_cached"]]
    misses = [row for row in rows if not row["is_cached"]]
    hit_rate = 100.0 * len(hits) / len(rows)
    print("=== Cache summary ===")
    print(f"queries: {len(rows)}")
    print(f"cache hits: {len(hits)}")
    print(f"cache misses: {len(misses)}")
    print(f"cache hit rate: {hit_rate:.1f}%")
    print(f"average latency cached ms: {_avg([row['latency_ms'] for row in hits]):.1f}")
    print(f"average latency non-cached ms: {_avg([row['latency_ms'] for row in misses]):.1f}")


if __name__ == "__main__":
    main()
