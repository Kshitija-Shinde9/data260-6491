import os
import sys
import threading
import time
from pathlib import Path

_CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_CODE))
os.environ["SHORT_LOG"] = "1"
os.environ["ORDER_ONLY"] = "1"
os.environ["FLOW_LOG_PATH"] = str(_CODE.parent / "reports" / "hw08" / "logs" / "part3_ordering.log")


def print_table(title: str, messages: list[dict], records: list[dict]):
    from kafka_service.failure import entity_views, produced_sequences

    sent = produced_sequences(messages)
    views = entity_views(records)
    print(f"\n{title}", flush=True)
    print(f"{'product':<14} {'partitions':<14} {'sent':<16} processed", flush=True)
    for entity in sent:
        view = views.get(entity, {"partitions": [], "sequences": []})
        partitions = ",".join(str(part) for part in view["partitions"]) or "-"
        sent_text = " ".join(str(number) for number in sent[entity])
        got_text = " ".join(str(number) for number in view["sequences"]) or "-"
        print(f"{entity:<14} {partitions:<14} {sent_text:<16} {got_text}", flush=True)
    return views, sent


def run_writers(group_id: str, messages: list[dict], keyed: bool) -> list[dict]:
    from part3_common import publish
    from writer import handle

    from kafka_service.config import DRAFTS_TOPIC, TASKS_TOPIC
    from kafka_service.pipeline import serve

    records: list[dict] = []
    lock = threading.Lock()
    assignments: dict[str, set[int]] = {}
    ready = threading.Event()
    stop = threading.Event()
    finished = threading.Event()

    def on_ready(partitions, _name=None):
        name = threading.current_thread().name
        with lock:
            assignments[name] = {partition.partition for partition in partitions}
            covered = set()
            owners = 0
            for owned in assignments.values():
                if owned:
                    owners += 1
                    covered |= owned
            if owners >= 2 and covered == {0, 1}:
                ready.set()

    def on_finished(incoming, decision, partition, offset):
        if decision["action"] != "processed":
            return
        with lock:
            records.append(
                {
                    "entity": incoming["entity"],
                    "entity_sequence": incoming["entity_sequence"],
                    "partition": partition,
                    "offset": offset,
                }
            )
            if len(records) >= len(messages):
                finished.set()
                stop.set()

    threads = []
    for name in ("WRITER-A", "WRITER-B"):
        thread = threading.Thread(
            target=serve,
            name=name,
            kwargs={
                "component": name,
                "source": TASKS_TOPIC,
                "target": DRAFTS_TOPIC,
                "group_id": group_id,
                "handle": handle,
                "idempotent": True,
                "offset_reset": "latest",
                "on_ready": on_ready,
                "stop_event": stop,
                "on_finished": on_finished,
            },
            daemon=True,
        )
        thread.start()
        threads.append(thread)

    if not ready.wait(40):
        stop.set()
        raise SystemExit(
            "the two writers did not split s6491_tasks. Stop any other writer.py first."
        )
    time.sleep(3)
    for index, message in enumerate(messages):
        if keyed:
            publish(TASKS_TOPIC, message, key=message["entity"])
        else:
            publish(TASKS_TOPIC, message, key=None, partition=index % 2)
    if not finished.wait(40):
        stop.set()
        raise SystemExit(f"only {len(records)} of {len(messages)} messages were processed")
    for thread in threads:
        thread.join(10)
    return records


def main() -> int:
    from confluent_kafka.admin import AdminClient
    from part3_common import broker_is_up

    from kafka_service.config import KAFKA_BOOTSTRAP_SERVERS, TASKS_TOPIC, VERIFY_SEED
    from kafka_service.failure import any_entity_split, build_ordering_messages, order_preserved

    broker_is_up()
    admin = AdminClient({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})
    meta = admin.list_topics(timeout=10).topics.get(TASKS_TOPIC)
    if meta is None or len(meta.partitions) != 2:
        raise SystemExit(
            "s6491_tasks must already exist with 2 partitions. Create it the way Part 2 did."
        )

    messages = build_ordering_messages(VERIFY_SEED, 20)
    print(f"VERIFY_SEED = {VERIFY_SEED}", flush=True)
    print("20 messages, 4 products, 5 updates each, 2 writers, 2 partitions", flush=True)

    spread = run_writers("s6491_part3_order_spread", messages, keyed=False)
    views, _sent = print_table("RUN 1  no product key", messages, spread)
    split = any_entity_split(views)
    print(f"a product landed on both partitions: {'yes' if split else 'no'}", flush=True)
    if not split:
        return 1

    kept = run_writers("s6491_part3_order_keyed", messages, keyed=True)
    views, sent = print_table("RUN 2  key = product name", messages, kept)
    preserved = order_preserved(views, sent)
    print(
        f"every product stayed on one partition, in the order it was sent: {'yes' if preserved else 'no'}",
        flush=True,
    )
    return 0 if preserved else 1


if __name__ == "__main__":
    sys.exit(main())
