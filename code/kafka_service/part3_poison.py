import json
import os
import sys
import threading
import time
import uuid
from pathlib import Path

_CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_CODE))
os.environ["SHORT_LOG"] = "1"
os.environ["FLOW_LOG_PATH"] = str(_CODE.parent / "reports" / "hw08" / "logs" / "part3_poison.log")

POISON_ID = "poison-266491"
GOOD_ID = "good-266491"


def read_dead_letter(topic: str, correlation_id: str) -> dict | None:
    from confluent_kafka import Consumer

    from kafka_service.config import KAFKA_BOOTSTRAP_SERVERS

    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": f"s6491_dead_reader_{uuid.uuid4().hex[:8]}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([topic])
    deadline = time.time() + 20
    found = None
    try:
        while time.time() < deadline and found is None:
            msg = consumer.poll(1.0)
            if msg is None or msg.error():
                continue
            payload = json.loads(msg.value().decode("utf-8"))
            if payload.get("correlation_id") == correlation_id:
                found = payload
    finally:
        consumer.close()
    return found


def main() -> int:
    from part3_common import broker_is_up, ensure_topic, publish
    from writer import handle

    from kafka_service.config import DEAD_LETTER_TOPIC, DRAFTS_TOPIC, TASKS_TOPIC
    from kafka_service.failure import decide
    from kafka_service.pipeline import serve

    broker_is_up()
    ensure_topic(DEAD_LETTER_TOPIC, partitions=1)

    print("\nBEFORE FIX  no retry limit and no dead-letter channel", flush=True)
    print(f"  {POISON_ID} keeps failing, so the writer never moves on", flush=True)
    print(f"  {GOOD_ID} does not get a draft", flush=True)
    blocked = decide(
        {"correlation_id": POISON_ID, "poison": True}, {}, True, handle, max_attempts=3
    )
    if blocked["action"] != "dead":
        raise SystemExit("the poison message should fail all 3 attempts")

    print("\nAFTER FIX  3 tries, then s6491_dead_letter, then the next message", flush=True)
    poison = {
        "correlation_id": POISON_ID,
        "poison": True,
        "question": "This message is poison.",
        "plan": [],
    }
    good = {
        "correlation_id": GOOD_ID,
        "question": "A bag of blueberries has a torn seal. What should the shopper do?",
        "plan": [
            "Name the product the shopper is asking about.",
            "Call this a packaging / seal failure.",
            "Tell the shopper not to eat it and to take it back to the store.",
        ],
    }
    ready = threading.Event()
    stop = threading.Event()
    finished = threading.Event()
    count = {"n": 0}

    def on_ready(_partitions):
        ready.set()

    def on_finished(_incoming, _decision, _partition, _offset):
        count["n"] += 1
        if count["n"] >= 2:
            finished.set()
            stop.set()

    worker = threading.Thread(
        target=serve,
        kwargs={
            "component": "WRITER",
            "source": TASKS_TOPIC,
            "target": DRAFTS_TOPIC,
            "group_id": "s6491_part3_poison",
            "handle": handle,
            "idempotent": True,
            "offset_reset": "latest",
            "on_ready": on_ready,
            "stop_event": stop,
            "on_finished": on_finished,
        },
        daemon=True,
    )
    worker.start()
    if not ready.wait(40):
        stop.set()
        raise SystemExit("writer did not start")
    time.sleep(2)
    publish(TASKS_TOPIC, poison, key=POISON_ID, partition=0)
    publish(TASKS_TOPIC, good, key=GOOD_ID, partition=0)
    if not finished.wait(40):
        stop.set()
        raise SystemExit("the poison message or the one after it did not finish")
    worker.join(10)

    dead = read_dead_letter(DEAD_LETTER_TOPIC, POISON_ID)
    if dead is None:
        raise SystemExit(f"{POISON_ID} was not on {DEAD_LETTER_TOPIC}")
    print(f"\n{DEAD_LETTER_TOPIC} has {POISON_ID}", flush=True)
    print(f"attempts = {dead['attempts']}", flush=True)
    print(f"error = {dead['error']}", flush=True)
    print(f"{GOOD_ID} was drafted after the poison message: yes", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
