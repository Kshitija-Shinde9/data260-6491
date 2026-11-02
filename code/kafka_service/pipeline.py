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

from kafka_service.config import KAFKA_BOOTSTRAP_SERVERS
from kafka_service.flow_log import log_flow, read_flow_lines
from kafka_service.kafka_io import build_producer, send_json


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def serve(component: str, source: str, target: str, group_id: str, handle) -> None:
    """Read one topic, hand each message to handle(), and publish what comes back."""
    producer = build_producer()
    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": group_id,
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
        }
    )
    running = True

    def stop(_signum, _frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def on_assign(_consumer, partitions):
        assigned = ", ".join(f"{p.topic}[{p.partition}]" for p in partitions)
        print(f"{component} is ready and listening on {assigned}", flush=True)
        log_flow(component, "READY", f"listening on {assigned}")

    consumer.subscribe([source], on_assign=on_assign)
    print(f"{component} subscribed to {source}. Waiting for a message.", flush=True)
    try:
        while running:
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
                log_flow(component, "DROP", f"{location} is not JSON")
                consumer.commit(message=msg, asynchronous=False)
                continue
            if not isinstance(incoming, dict) or not incoming.get("correlation_id"):
                log_flow(component, "DROP", f"{location} has no correlation_id")
                consumer.commit(message=msg, asynchronous=False)
                continue

            correlation_id = incoming["correlation_id"]
            log_flow(component, "RECEIVE", f"corr={correlation_id} <- {location}", incoming)
            outgoing = handle(incoming)
            outgoing["correlation_id"] = correlation_id
            send_json(producer, target, correlation_id, outgoing)
            log_flow(component, "SEND", f"corr={correlation_id} -> {target}", outgoing)
            consumer.commit(message=msg, asynchronous=False)
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
