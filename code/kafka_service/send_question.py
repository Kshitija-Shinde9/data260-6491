import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DEFAULT_QUESTION = (
    "A 16oz bag of Trader Joe's organic frozen blueberries has a tear at the top seal "
    "and frost on the berries near the opening. What should the shopper do?"
)


def main() -> int:
    from kafka_service.config import FINAL_TOPIC, INBOX_TOPIC
    from kafka_service.flow_log import log_flow
    from kafka_service.kafka_io import build_producer, send_json
    from kafka_service.pipeline import FinalWaiter, journey_lines, new_correlation_id

    question = " ".join(sys.argv[1:]).strip() or DEFAULT_QUESTION
    correlation_id = new_correlation_id()
    message = {"correlation_id": correlation_id, "question": question}

    print(f"correlation_id = {correlation_id}", flush=True)
    print(f"question = {question}", flush=True)

    waiter = FinalWaiter(FINAL_TOPIC)
    producer = build_producer()
    try:
        log_flow("YOU", "SEND", f"corr={correlation_id} -> {INBOX_TOPIC}", message)
        send_json(producer, INBOX_TOPIC, correlation_id, message)
        print(f"sent to {INBOX_TOPIC}. Waiting for {FINAL_TOPIC}.", flush=True)
        final = waiter.wait(correlation_id, timeout_sec=30)
    finally:
        producer.flush(5)
        waiter.close()

    if final is None:
        print(
            "No answer arrived. Check that planner.py, writer.py, and reviewer.py are still running.",
            flush=True,
        )
        return 1

    log_flow("YOU", "FINAL", f"corr={correlation_id} status={final.get('status')}", final)
    print("\nFINAL JSON:", flush=True)
    print(json.dumps(final, indent=2), flush=True)
    kept = final.get("correlation_id") == correlation_id
    print(f"correlation_id preserved = {kept}", flush=True)

    print("\nJOURNEY (inbox -> tasks -> drafts -> final):", flush=True)
    for line in journey_lines(correlation_id):
        print(line, flush=True)
    return 0 if kept and final.get("status") and final.get("answer") else 1


if __name__ == "__main__":
    sys.exit(main())
