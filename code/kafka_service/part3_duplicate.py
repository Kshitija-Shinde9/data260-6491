import os
import sys
import threading
import time
from pathlib import Path

_CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_CODE))
os.environ["SHORT_LOG"] = "1"
os.environ["FLOW_LOG_PATH"] = str(
    _CODE.parent / "reports" / "hw08" / "logs" / "part3_duplicate.log"
)

MESSAGE = {
    "correlation_id": "dup-266491",
    "question": "A bag of blueberries has a torn seal. What should the shopper do?",
    "plan": [
        "Name the product the shopper is asking about.",
        "Call this a packaging / seal failure.",
        "Tell the shopper not to eat it and to take it back to the store.",
    ],
}


def run_phase(title: str, group_id: str, idempotent: bool) -> None:
    from part3_common import publish
    from writer import handle

    from kafka_service.config import DRAFTS_TOPIC, TASKS_TOPIC
    from kafka_service.pipeline import serve

    print(f"\n{title}", flush=True)
    print(f"idempotent = {idempotent}   correlation_id = {MESSAGE['correlation_id']}", flush=True)
    ready = threading.Event()
    stop = threading.Event()
    finished = threading.Event()
    seen = {"n": 0}

    def on_ready(_partitions):
        ready.set()

    def on_finished(_incoming, _decision, _partition, _offset):
        seen["n"] += 1
        if seen["n"] >= 2:
            finished.set()
            stop.set()

    worker = threading.Thread(
        target=serve,
        kwargs={
            "component": "WRITER",
            "source": TASKS_TOPIC,
            "target": DRAFTS_TOPIC,
            "group_id": group_id,
            "handle": handle,
            "idempotent": idempotent,
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
        raise SystemExit("writer did not start. Is s6491_kafka still healthy?")
    time.sleep(2)
    publish(TASKS_TOPIC, MESSAGE, key=MESSAGE["correlation_id"], partition=0)
    publish(TASKS_TOPIC, MESSAGE, key=MESSAGE["correlation_id"], partition=0)
    if not finished.wait(40):
        stop.set()
        raise SystemExit(
            "both copies did not finish. Leave the three Part 2 terminals stopped and run this again."
        )
    worker.join(10)


def main() -> int:
    from part3_common import broker_is_up

    broker_is_up()
    run_phase("BEFORE FIX  same id, no idempotency", "s6491_part3_dup_before", False)
    run_phase("AFTER FIX  same id, idempotency on", "s6491_part3_dup_after", True)
    print(
        "\nBefore: two SEND lines. After: one SEND and one DUPLICATE, no second draft.", flush=True
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
