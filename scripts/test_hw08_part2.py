import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))
sys.path.insert(0, str(REPO / "code" / "kafka_service"))

from kafka_service.config import (  # noqa: E402
    DRAFTS_TOPIC,
    FINAL_TOPIC,
    INBOX_TOPIC,
    PART2_TOPICS,
    TASKS_TOPIC,
)
from planner import handle as plan_handle  # noqa: E402
from planner import make_plan  # noqa: E402
from reviewer import handle as review_handle  # noqa: E402
from reviewer import review_draft  # noqa: E402
from writer import handle as write_handle  # noqa: E402
from writer import write_draft  # noqa: E402

QUESTION = (
    "A 16oz bag of Trader Joe's organic frozen blueberries has a tear at the top seal "
    "and frost near the opening. What should the shopper do?"
)
CORR = "11111111-1111-1111-1111-111111111111"


def test_topic_names_and_partition_counts():
    assert INBOX_TOPIC == "s6491_inbox"
    assert TASKS_TOPIC == "s6491_tasks"
    assert DRAFTS_TOPIC == "s6491_drafts"
    assert FINAL_TOPIC == "s6491_final"
    counts = dict(PART2_TOPICS)
    assert counts == {
        "s6491_inbox": 1,
        "s6491_tasks": 2,
        "s6491_drafts": 1,
        "s6491_final": 1,
    }


def test_plan_names_a_seal_failure():
    plan = make_plan(QUESTION)
    text = " ".join(plan).lower()
    assert "packaging / seal failure" in text
    assert "not to eat" in text


def test_pipeline_keeps_the_same_id_through_every_stage():
    planned = plan_handle({"correlation_id": CORR, "question": QUESTION})
    drafted = write_handle(planned)
    final = review_handle(drafted)
    assert planned["correlation_id"] == CORR
    assert drafted["correlation_id"] == CORR
    assert final["correlation_id"] == CORR
    assert final["status"] == "approved"
    assert "do not eat" in final["answer"].lower()
    assert "blueberries" in final["answer"].lower()


def test_reviewer_rejects_an_empty_draft():
    status, answer = review_draft("   ")
    assert status == "rejected"
    assert answer == "No answer was written."
    final = review_handle({"correlation_id": CORR, "draft": ""})
    assert final["status"] == "rejected"
    assert final["correlation_id"] == CORR


def test_writer_uses_the_plan():
    draft = write_draft("What about the chicken?", ["Call this a spoiled or quality issue."])
    assert "chicken" in draft.lower()
    assert "spoiled or quality issue" in draft.lower()


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
    print(f"\n{len(tests) - failures}/{len(tests)} tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
