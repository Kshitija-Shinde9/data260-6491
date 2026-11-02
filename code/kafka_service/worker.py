import json
import signal
import uuid
from datetime import datetime, timezone
from typing import Any

from kafka_service.config import (
    CREATE_OPERATION,
    GET_OPERATION,
    KAFKA_BOOTSTRAP_SERVERS,
    REQUEST_TOPIC,
    RESPONSE_TOPIC,
    WORKER_GROUP_ID,
)
from kafka_service.flow_log import log_flow
from kafka_service.recall_entity import validate_recall_fields

ALLOWED_REPLY_TOPICS = {RESPONSE_TOPIC}


def _response(correlation_id: Any, operation: Any, **body: Any) -> dict:
    return {"correlation_id": correlation_id, "operation": operation, **body}


def create_recall(data: Any, store: dict) -> dict:
    fields, error = validate_recall_fields(data)
    if error:
        return {"success": False, "error": error}
    if any(record["recall_code"] == fields["recall_code"] for record in store.values()):
        return {"success": False, "error": f"recall_code {fields['recall_code']} already exists"}
    recall_id = str(uuid.uuid4())
    store[recall_id] = {
        "recall_id": recall_id,
        **fields,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"success": True, "recall_id": recall_id, "message": "Recall created"}


def get_recall(data: Any, store: dict) -> dict:
    if not isinstance(data, dict):
        return {"success": False, "error": "data must be a JSON object"}
    recall_id = data.get("recall_id")
    if not isinstance(recall_id, str) or not recall_id.strip():
        return {"success": False, "error": "recall_id is required"}
    record = store.get(recall_id.strip())
    if record is None:
        return {"success": False, "error": "Recall not found"}
    return {"success": True, "recall": dict(record)}


def handle_request(message: Any, store: dict) -> tuple[str | None, dict | None]:
    """Turn one request message into (reply topic, response), without touching Kafka.

    Returns (None, None) only when no reply can be correlated: the message is not a
    JSON object or it has no correlation_id.
    """
    if not isinstance(message, dict):
        return None, None
    correlation_id = message.get("correlation_id")
    if not isinstance(correlation_id, str) or not correlation_id.strip():
        return None, None

    operation = message.get("operation")
    reply_to = message.get("reply_to")
    if reply_to not in ALLOWED_REPLY_TOPICS:
        # Still answer on the service's own response topic so the caller is not left waiting.
        return RESPONSE_TOPIC, _response(
            correlation_id,
            operation,
            success=False,
            error=f"reply_to must be {RESPONSE_TOPIC}",
        )
    if "data" not in message:
        return reply_to, _response(
            correlation_id, operation, success=False, error="data is required"
        )

    if operation == CREATE_OPERATION:
        result = create_recall(message["data"], store)
    elif operation == GET_OPERATION:
        result = get_recall(message["data"], store)
    else:
        result = {"success": False, "error": "Unknown operation"}
    return reply_to, _response(correlation_id, operation, **result)


def run_worker() -> None:
    from confluent_kafka import Consumer, KafkaError

    from kafka_service.kafka_io import build_producer, ensure_topics, send_json

    ensure_topics()
    store: dict[str, dict] = {}
    producer = build_producer()
    consumer = Consumer(
        {
            "bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS,
            "group.id": WORKER_GROUP_ID,
            "auto.offset.reset": "earliest",
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
        log_flow("WORKER", "READY", f"assigned {assigned} in group {WORKER_GROUP_ID}")
        print("Consumer is ready and listening...", flush=True)

    consumer.subscribe([REQUEST_TOPIC], on_assign=on_assign)
    print(f"worker subscribed to {REQUEST_TOPIC} at {KAFKA_BOOTSTRAP_SERVERS}", flush=True)

    try:
        while running:
            msg = consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() != KafkaError._PARTITION_EOF:
                    print(f"consumer error: {msg.error()}", flush=True)
                continue

            location = f"{msg.topic()}[{msg.partition()}]@{msg.offset()}"
            try:
                message = json.loads(msg.value().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                log_flow("WORKER", "DROP", f"{location} is not valid JSON: {exc}")
                consumer.commit(message=msg, asynchronous=False)
                continue

            correlation_id = message.get("correlation_id") if isinstance(message, dict) else None
            operation = message.get("operation") if isinstance(message, dict) else None
            log_flow(
                "WORKER",
                "RECEIVE",
                f"corr={correlation_id} op={operation} <- {location}",
                message if isinstance(message, dict) else None,
            )

            reply_topic, response = handle_request(message, store)
            if reply_topic is None:
                log_flow("WORKER", "DROP", f"{location} has no correlation_id, cannot reply")
                consumer.commit(message=msg, asynchronous=False)
                continue

            log_flow(
                "WORKER",
                "PROCESS",
                f"corr={correlation_id} op={operation} success={response['success']} "
                f"store_size={len(store)}",
            )
            # Logged before producing: the client may log RESPONSE before the broker ack returns.
            log_flow(
                "WORKER",
                "REPLY",
                f"corr={correlation_id} op={operation} -> {reply_topic}",
                response,
            )
            send_json(producer, reply_topic, correlation_id, response)
            # Commit only after the reply is acknowledged, so a crash re-delivers the request.
            consumer.commit(message=msg, asynchronous=False)
    finally:
        consumer.close()
        producer.flush(5)
        print("worker stopped", flush=True)


if __name__ == "__main__":
    run_worker()
