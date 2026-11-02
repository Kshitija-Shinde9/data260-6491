import json
import threading
import uuid

from confluent_kafka import Consumer, KafkaError, TopicPartition

from kafka_service.config import (
    CLIENT_GROUP_PREFIX,
    KAFKA_BOOTSTRAP_SERVERS,
    REQUEST_TIMEOUT_SEC,
    REQUEST_TOPIC,
    RESPONSE_TOPIC,
)
from kafka_service.flow_log import log_flow
from kafka_service.kafka_io import build_producer, ensure_topics, send_json


def new_correlation_id() -> str:
    return str(uuid.uuid4())


def build_request(operation: str, data: dict, correlation_id: str) -> dict:
    return {
        "correlation_id": correlation_id,
        "reply_to": RESPONSE_TOPIC,
        "operation": operation,
        "data": data,
    }


class RecallKafkaClient:
    def __init__(
        self,
        component: str = "CLIENT",
        bootstrap: str = KAFKA_BOOTSTRAP_SERVERS,
        timeout_sec: float = REQUEST_TIMEOUT_SEC,
    ):
        self.component = component
        self.bootstrap = bootstrap
        self.timeout_sec = timeout_sec
        self._pending: dict[str, dict] = {}
        self._lock = threading.Lock()
        self._send_lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None
        self._producer = None
        self._consumer = None

    def start(self) -> "RecallKafkaClient":
        if self._running:
            return self
        ensure_topics(self.bootstrap)
        self._producer = build_producer(self.bootstrap)
        self._consumer = Consumer(
            {
                "bootstrap.servers": self.bootstrap,
                "group.id": f"{CLIENT_GROUP_PREFIX}_{uuid.uuid4().hex[:8]}",
                "enable.auto.commit": False,
            }
        )

        partitions = (
            self._consumer.list_topics(RESPONSE_TOPIC, timeout=10).topics[RESPONSE_TOPIC].partitions
        )
        assignments = []
        for partition_id in partitions:
            _low, high = self._consumer.get_watermark_offsets(
                TopicPartition(RESPONSE_TOPIC, partition_id), timeout=10
            )
            assignments.append(TopicPartition(RESPONSE_TOPIC, partition_id, high))
        self._consumer.assign(assignments)
        self._running = True
        self._thread = threading.Thread(target=self._read_responses, daemon=True)
        self._thread.start()
        log_flow(self.component, "READY", f"listening on {RESPONSE_TOPIC} at {self.bootstrap}")
        return self

    def _read_responses(self) -> None:
        while self._running:
            msg = self._consumer.poll(0.5)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    print(f"{self.component} consumer error: {msg.error()}", flush=True)
                continue
            try:
                response = json.loads(msg.value().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            correlation_id = response.get("correlation_id") if isinstance(response, dict) else None
            with self._lock:
                waiter = self._pending.get(correlation_id)
            if waiter is None:
                continue
            waiter["location"] = f"{msg.topic()}[{msg.partition()}]@{msg.offset()}"
            waiter["response"] = response
            waiter["event"].set()

    def request(self, operation: str, data: dict, correlation_id: str | None = None) -> dict:
        if not self._running:
            self.start()
        correlation_id = correlation_id or new_correlation_id()
        message = build_request(operation, data, correlation_id)
        waiter = {"event": threading.Event(), "response": None, "location": None}
        with self._lock:
            self._pending[correlation_id] = waiter
        try:
            # Logged before producing: the worker may log RECEIVE before the broker ack returns.
            log_flow(
                self.component,
                "SEND",
                f"corr={correlation_id} op={operation} -> {REQUEST_TOPIC}",
                message,
            )
            with self._send_lock:
                send_json(self._producer, REQUEST_TOPIC, correlation_id, message)
            if not waiter["event"].wait(self.timeout_sec):
                timeout_response = {
                    "correlation_id": correlation_id,
                    "operation": operation,
                    "success": False,
                    "error": f"Timed out after {self.timeout_sec:.0f}s waiting for {RESPONSE_TOPIC}",
                }
                log_flow(
                    self.component,
                    "TIMEOUT",
                    f"corr={correlation_id} op={operation}",
                    timeout_response,
                )
                return timeout_response
            response = waiter["response"]
            log_flow(
                self.component,
                "RESPONSE",
                f"corr={correlation_id} op={operation} <- {waiter['location']} "
                f"correlation_preserved={response.get('correlation_id') == correlation_id}",
                response,
            )
            return response
        finally:
            with self._lock:
                self._pending.pop(correlation_id, None)

    def close(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        if self._consumer is not None:
            self._consumer.close()
        if self._producer is not None:
            self._producer.flush(5)

    def __enter__(self) -> "RecallKafkaClient":
        return self.start()

    def __exit__(self, *_exc) -> None:
        self.close()
