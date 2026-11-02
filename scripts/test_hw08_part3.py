import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))
sys.path.insert(0, str(REPO / "code" / "kafka_service"))

from kafka_service.config import DEAD_LETTER_TOPIC, VERIFY_SEED  # noqa: E402
from kafka_service.failure import (  # noqa: E402
    any_entity_split,
    build_ordering_messages,
    crash_plan,
    decide,
    entity_views,
    order_preserved,
    produced_sequences,
)
from writer import handle as write_handle  # noqa: E402


def _record(message, partition):
    return {
        "entity": message["entity"],
        "entity_sequence": message["entity_sequence"],
        "partition": partition,
        "offset": message["produce_index"],
    }


def test_dead_letter_topic_name():
    assert DEAD_LETTER_TOPIC == "s6491_dead_letter"
    assert VERIFY_SEED == 266491


def test_replay_without_idempotency_runs_the_handler_twice():
    calls = []

    def handle(message):
        calls.append(message["correlation_id"])
        return {"draft": "one"}

    message = {"correlation_id": "dup-266491"}
    seen = {}
    first = decide(message, seen, False, handle)
    second = decide(message, seen, False, handle)
    assert first["action"] == "processed"
    assert second["action"] == "processed"
    assert calls == ["dup-266491", "dup-266491"]


def test_replay_with_idempotency_runs_the_handler_once():
    calls = []

    def handle(message):
        calls.append(message["correlation_id"])
        return {"draft": "one"}

    message = {"correlation_id": "dup-266491"}
    seen = {}
    first = decide(message, seen, True, handle)
    second = decide(message, seen, True, handle)
    assert first["action"] == "processed"
    assert second["action"] == "duplicate"
    assert second["outgoing"]["draft"] == "one"
    assert calls == ["dup-266491"]


def test_poison_is_retried_three_times_and_the_next_message_still_runs():
    poison = decide({"correlation_id": "poison-266491", "poison": True}, {}, True, write_handle)
    assert poison["action"] == "dead"
    assert poison["attempts"] == 3
    assert poison["errors"] == ["poison message", "poison message", "poison message"]

    seen = {}
    good = decide(
        {
            "correlation_id": "good-266491",
            "question": "What about the blueberries?",
            "plan": ["Call this a packaging / seal failure."],
        },
        seen,
        True,
        write_handle,
    )
    assert good["action"] == "processed"
    assert "do not eat" in good["outgoing"]["draft"].lower()


def test_crash_before_commit_is_not_saved_and_an_early_commit_is():
    assert crash_plan(False, False) == ["RECEIVE", "WORK", "COMMIT"]
    assert crash_plan(False, True) == ["RECEIVE", "CRASH"]
    assert crash_plan(True, True) == ["RECEIVE", "EARLY_COMMIT", "CRASH"]


def test_seed_builds_20_related_messages():
    messages = build_ordering_messages(VERIFY_SEED, 20)
    assert len(messages) == 20
    counts = {}
    for message in messages:
        counts[message["entity"]] = counts.get(message["entity"], 0) + 1
    assert counts == {"blueberries": 5, "chicken": 5, "trail mix": 5, "spinach": 5}
    again = build_ordering_messages(VERIFY_SEED, 20)
    assert [item["correlation_id"] for item in messages] == [
        item["correlation_id"] for item in again
    ]


def test_round_robin_splits_a_product_and_a_key_keeps_order():
    messages = build_ordering_messages(VERIFY_SEED, 20)
    sent = produced_sequences(messages)
    spread = entity_views([_record(message, message["produce_index"] % 2) for message in messages])
    assert any_entity_split(spread)
    assert not order_preserved(spread, sent)

    keyed = entity_views([_record(message, 0) for message in messages])
    assert not any_entity_split(keyed)
    assert order_preserved(keyed, sent)


def main() -> int:
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
        except Exception as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {type(exc).__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
