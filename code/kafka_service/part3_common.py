import time

from confluent_kafka import KafkaError, KafkaException
from confluent_kafka.admin import NewTopic

from kafka_service.config import KAFKA_BOOTSTRAP_SERVERS
from kafka_service.kafka_io import build_producer, send_json, wait_for_broker


def ensure_topic(name: str, partitions: int = 1) -> None:
    admin = wait_for_broker()
    existing = set(admin.list_topics(timeout=10).topics)
    if name in existing:
        return
    future = admin.create_topics([NewTopic(name, num_partitions=partitions, replication_factor=1)])[
        name
    ]
    try:
        future.result()
        print(f"created {name}", flush=True)
    except KafkaException as exc:
        if exc.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:
            raise


def recreate_topic(name: str, partitions: int = 1) -> None:
    """Start the crash demo from an empty channel so a restart cannot see old messages."""
    admin = wait_for_broker()
    existing = set(admin.list_topics(timeout=10).topics)
    if name in existing:
        future = admin.delete_topics([name], operation_timeout=20)[name]
        try:
            future.result()
        except KafkaException as exc:
            if exc.args[0].code() != KafkaError.UNKNOWN_TOPIC_OR_PART:
                raise
        deadline = time.time() + 20
        while time.time() < deadline:
            if name not in admin.list_topics(timeout=10).topics:
                break
            time.sleep(0.5)
        else:
            raise RuntimeError(f"{name} was not deleted in time")
    future = admin.create_topics([NewTopic(name, num_partitions=partitions, replication_factor=1)])[
        name
    ]
    try:
        future.result()
    except KafkaException as exc:
        if exc.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:
            raise
    deadline = time.time() + 20
    while time.time() < deadline:
        meta = admin.list_topics(timeout=10).topics.get(name)
        if meta is not None and len(meta.partitions) == partitions:
            print(f"channel {name} is empty and ready", flush=True)
            return
        time.sleep(0.5)
    raise RuntimeError(f"{name} was not created in time")


def publish(
    topic: str, payload: dict, key: str | None = None, partition: int | None = None
) -> dict:
    producer = build_producer()
    try:
        return send_json(producer, topic, key, payload, partition=partition)
    finally:
        producer.flush(5)


def broker_is_up() -> None:
    wait_for_broker(attempts=5)
    print(f"broker {KAFKA_BOOTSTRAP_SERVERS}", flush=True)
