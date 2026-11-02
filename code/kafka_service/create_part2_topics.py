import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from confluent_kafka import KafkaError, KafkaException
from confluent_kafka.admin import NewTopic

from kafka_service.config import KAFKA_BOOTSTRAP_SERVERS, PART2_TOPICS
from kafka_service.kafka_io import wait_for_broker


def create_part2_topics() -> None:
    admin = wait_for_broker()
    existing = set(admin.list_topics(timeout=10).topics)
    wanted = [
        NewTopic(name, num_partitions=partitions, replication_factor=1)
        for name, partitions in PART2_TOPICS
        if name not in existing
    ]
    if wanted:
        for topic, future in admin.create_topics(wanted).items():
            try:
                future.result()
                print(f"created {topic}", flush=True)
            except KafkaException as exc:
                if exc.args[0].code() != KafkaError.TOPIC_ALREADY_EXISTS:
                    raise
    else:
        print("topics already exist", flush=True)

    fresh = admin.list_topics(timeout=10).topics
    print(f"broker {KAFKA_BOOTSTRAP_SERVERS}", flush=True)
    for name, wanted_partitions in PART2_TOPICS:
        got = len(fresh[name].partitions) if name in fresh else 0
        print(f"  {name}  partitions={got}", flush=True)
        if got != wanted_partitions:
            print(f"  warning: {name} should have {wanted_partitions} partitions", flush=True)


if __name__ == "__main__":
    create_part2_topics()
