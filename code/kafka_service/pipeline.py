import json
import os
import signal
import sys
import threading
import uuid
from pathlib import Path

_CODE = Path(__file__).resolve().parents[1]
if str(_CODE) not in sys.path:
    sys.path.insert(0, str(_CODE))

_REPO = _CODE.parent
os.environ.setdefault(
    "FLOW_LOG_PATH",
    str(_REPO / "reports" / "hw08" / "logs" / "part2_message_flow.log"),
)

from confluent_kafka import Consumer, KafkaError, TopicPartition

from kafka_service.config import DEAD_LETTER_TOPIC, KAFKA_BOOTSTRAP_SERVERS, MAX_ATTEMPTS
from kafka_service.failure import crash_plan, decide
from kafka_service.flow_log import log_flow, read_flow_lines
from kafka_service.kafka_io import build_producer, send_json


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def _detail_payload(payload: dict | None) -> dict | None:
    if os.getenv("SHORT_LOG") == "1":
        return None
    return payload


def _emit(component: str, stage: str, detail: str, payload: dict | None = None) -> None:
    if os.getenv("ORDER_ONLY") == "1":
        return
    log_flow(component, stage, detail, payload)


def _commit(consumer, msg, component: str, correlation_id: str, detail: str) -> None:
    consumer.commit(message=msg, asynchronous=False)
    if os.getenv("ORDER_ONLY") == "1":
        return
    log_flow(component, "COMMIT", f"corr={correlation_id} {detail}")


def _crash(consumer, producer, component: str, correlation_id: str) -> None:
    log_flow(component, "CRASH", f"corr={correlation_id} writer killed before the work finished")
    consumer.close()
    producer.flush(2)
    os._exit(86)


def serve(
    component: str,
    source: str,
    target: str,
    group_id: str,
    handle,
    *,
    idempotent: bool | None = None,
    offset_reset: str | None = None,
    on_ready=None,
    stop_event: threading.Event | None = None,
    on_finished=None,
) -> None:
    """Read one topic, hand each message to handle(), and publish what comes back.

    The offset is committed only after the message is done. A repeated
    correlation_id does not call handle() again. A message that keeps failing
    goes to the dead-letter topic so the next one can move.
    """
    if idempotent is None:
        idempotent = os.getenv("IDEMPOTENT", "1") != "0"
    if offset_reset is None:
        offset_reset = os.getenv("OFFSET_RESET", "latest")
    steps = crash_plan(
        os.getenv("COMMIT_BEFORE_WORK") == "1",
        os.getenv("CRASH_BEFORE_COMMIT") == "1",
    )
    producer = build_producer()
    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": group_id,
            "auto.offset.reset": offset_reset,
            "enable.auto.commit": False,
        }
    )
    seen: dict = {}
    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    if threading.current_thread() is threading.main_thread():
        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)

    def on_assign(_consumer, partitions):
        assigned = ", ".join(f"{p.topic}[{p.partition}]" for p in partitions)
        print(f"{component} is ready and listening on {assigned}", flush=True)
        _emit(component, "READY", f"listening on {assigned}")
        if on_ready is not None:
            on_ready(partitions)

    consumer.subscribe([source], on_assign=on_assign)
    print(f"{component} subscribed to {source}. Waiting for a message.", flush=True)
    try:
        while running and (stop_event is None or not stop_event.is_set()):
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    print(f"{component} consumer error: {msg.error()}", flush=True)
                continue
            location = f"{msg.topic()}[{msg.partition()}]@{msg.offset()}"
            try:
                incoming = json.loads(msg.value().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                _emit(component, "DROP", f"{location} is not JSON")
                consumer.commit(message=msg, asynchronous=False)
                continue
            if not isinstance(incoming, dict) or not incoming.get("correlation_id"):
                _emit(component, "DROP", f"{location} has no correlation_id")
                consumer.commit(message=msg, asynchronous=False)
                continue

            correlation_id = incoming["correlation_id"]
            _emit(
                component,
                "RECEIVE",
                f"corr={correlation_id} <- {location}",
                _detail_payload(incoming),
            )
            if "EARLY_COMMIT" in steps:
                _commit(
                    consumer, msg, component, correlation_id, "committed before the work finished"
                )
            if "CRASH" in steps:
                _crash(consumer, producer, component, correlation_id)

            def on_retry(attempt, total, exc, _cid=correlation_id):
                _emit(component, "RETRY", f"corr={_cid} attempt={attempt}/{total} {exc}")

            decision = decide(
                incoming,
                seen,
                idempotent,
                handle,
                max_attempts=MAX_ATTEMPTS,
                on_retry=on_retry,
            )
            action = decision["action"]
            if action == "duplicate":
                _emit(
                    component,
                    "DUPLICATE",
                    f"corr={correlation_id} already handled, no second draft",
                )
                _commit(consumer, msg, component, correlation_id, "duplicate skipped")
            elif action == "dead":
                dead_payload = {
                    "correlation_id": correlation_id,
                    "attempts": decision["attempts"],
                    "error": decision["errors"][-1],
                    "original": incoming,
                }
                send_json(producer, DEAD_LETTER_TOPIC, correlation_id, dead_payload)
                _emit(
                    component,
                    "DEAD",
                    f"corr={correlation_id} -> {DEAD_LETTER_TOPIC} attempts={decision['attempts']}",
                    _detail_payload(dead_payload),
                )
                _commit(consumer, msg, component, correlation_id, "dead letter committed")
            else:
                outgoing = decision["outgoing"]
                send_json(producer, target, correlation_id, outgoing)
                _emit(
                    component,
                    "SEND",
                    f"corr={correlation_id} -> {target} partition={msg.partition()}",
                    _detail_payload(outgoing),
                )
                _commit(consumer, msg, component, correlation_id, "committed after success")
            if on_finished is not None:
                on_finished(incoming, decision, msg.partition(), msg.offset())
    finally:
        consumer.close()
        producer.flush(5)
        print(f"{component} stopped", flush=True)


class FinalWaiter:
    """Watch s6491_final for the one answer that matches our correlation_id."""

    def __init__(self, topic: str):
        self.topic = topic
        self._found = {}
        self._events = {}
        self._lock = threading.Lock()
        self._running = True
        self._consumer = Consumer(
            {
                "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
                "group.id": f"s6491_final_reader_{uuid.uuid4().hex[:8]}",
                "enable.auto.commit": False,
            }
        )
        partitions = self._consumer.list_topics(topic, timeout=10).topics[topic].partitions
        assignments = []
        for partition_id in partitions:
            _low, high = self._consumer.get_watermark_offsets(
                TopicPartition(topic, partition_id), timeout=10
            )
            assignments.append(TopicPartition(topic, partition_id, high))
        self._consumer.assign(assignments)
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()

    def _read(self) -> None:
        while self._running:
            msg = self._consumer.poll(0.5)
            if msg is None or msg.error():
                continue
            try:
                payload = json.loads(msg.value().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(payload, dict):
                continue
            correlation_id = payload.get("correlation_id")
            with self._lock:
                event = self._events.get(correlation_id)
            if event is not None:
                self._found[correlation_id] = payload
                event.set()

    def wait(self, correlation_id: str, timeout_sec: float) -> dict | None:
        event = threading.Event()
        with self._lock:
            self._events[correlation_id] = event
        try:
            if not event.wait(timeout_sec):
                return None
            return self._found.get(correlation_id)
        finally:
            with self._lock:
                self._events.pop(correlation_id, None)

    def close(self) -> None:
        self._running = False
        self._thread.join(timeout=2)
        self._consumer.close()


def journey_lines(correlation_id: str) -> list[str]:
    return read_flow_lines(correlation_id)
