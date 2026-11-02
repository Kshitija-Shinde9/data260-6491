import json
import time

from confluent_kafka import KafkaError, KafkaException, Producer
from confluent_kafka.admin import AdminClient, NewTopic

from kafka_service.config import KAFKA_BOOTSTRAP_SERVERS, REQUEST_TOPIC, RESPONSE_TOPIC


def wait_for_broker(bootstrap: str = KAFKA_BOOTSTRAP_SERVERS, attempts: int = 30) -> AdminClient:
    admin = AdminClient({"bootstrap.servers": bootstrap})
    for attempt in range(1, attempts + 1):
        try:
            admin.list_topics(timeout=5)
            return admin
        except KafkaException as exc:
            print(
                f"waiting for Kafka at {bootstrap} (attempt {attempt}/{attempts}): {exc}",
                flush=True,
            )
            time.sleep(2)
    raise RuntimeError(f"Kafka is not reachable at {bootstrap}")


def ensure_topics(bootstrap: str = KAFKA_BOOTSTRAP_SERVERS) -> None:
    admin = wait_for_broker(bootstrap)
    existing = set(admin.list_topics(timeout=10).topics)
    wanted = [
        NewTopic(topic, num_partitions=1, replication_factor=1)
        for topic in (REQUEST_TOPIC, RESPONSE_TOPIC)
        if topic not in existing
    ]
    if not wanted:
        return
    for topic, future in admin.create_topics(wanted).items():
        try:
            future.result()
            print(f"created topic {topic}", flush=True)
        except KafkaException as exc:
            if exc.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:
                raise


def build_producer(bootstrap: str = KAFKA_BOOTSTRAP_SERVERS) -> Producer:
    return Producer(
        {
            "bootstrap.servers": bootstrap,
            "acks": "all",
            "enable.idempotence": True,
        }
    )


def send_json(
    producer: Producer,
    topic: str,
    key: str | None,
    payload: dict,
    partition: int | None = None,
) -> dict:
    """Produce one JSON message, wait for the broker ack, and return its partition/offset."""
    delivery: dict = {}

    def on_delivery(error, message):
        if error is not None:
            delivery["error"] = str(error)
        else:
            delivery["partition"] = message.partition()
            delivery["offset"] = message.offset()

    produce_args = {
        "topic": topic,
        "value": json.dumps(payload).encode("utf-8"),
        "on_delivery": on_delivery,
    }
    if key:
        produce_args["key"] = key.encode()
    if partition is not None:
        produce_args["partition"] = int(partition)
    producer.produce(**produce_args)
    producer.flush(10)
    if "error" in delivery:
        raise RuntimeError(f"delivery to {topic} failed: {delivery['error']}")
    return delivery
