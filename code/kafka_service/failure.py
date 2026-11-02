import random

from kafka_service.config import MAX_ATTEMPTS, VERIFY_SEED

ENTITIES = ("blueberries", "chicken", "trail mix", "spinach")


class PoisonMessage(RuntimeError):
    """The writer raises this for a message we agreed to treat as poison."""


def crash_plan(early_commit: bool, crash_before_commit: bool) -> list[str]:
    """The steps a writer takes when we are demonstrating a kill mid-message.

    EARLY_COMMIT is the broken version: the offset moves before the draft exists.
    CRASH with no EARLY_COMMIT is the fix: nothing is saved, so a restart reads it again.
    """
    steps = ["RECEIVE"]
    if early_commit:
        steps.append("EARLY_COMMIT")
    if crash_before_commit:
        steps.append("CRASH")
        return steps
    steps.extend(["WORK", "COMMIT"])
    return steps


def decide(
    message: dict,
    seen: dict,
    idempotent: bool,
    handle,
    max_attempts: int = MAX_ATTEMPTS,
    on_retry=None,
) -> dict:
    """Process one message, or refuse to do the work a second time.

    `seen` maps correlation_id to the outgoing message we already produced.
    """
    correlation_id = message["correlation_id"]
    if idempotent and correlation_id in seen:
        return {"action": "duplicate", "outgoing": seen[correlation_id]}

    errors: list[str] = []
    for attempt in range(1, max_attempts + 1):
        try:
            outgoing = dict(handle(message))
            outgoing["correlation_id"] = correlation_id
            seen[correlation_id] = outgoing
            return {
                "action": "processed",
                "outgoing": outgoing,
                "attempts": attempt,
                "errors": errors,
            }
        except Exception as exc:
            errors.append(str(exc))
            if on_retry is not None:
                on_retry(attempt, max_attempts, exc)
    return {"action": "dead", "attempts": max_attempts, "errors": errors}


def build_ordering_messages(seed: int = VERIFY_SEED, count: int = 20) -> list[dict]:
    """Twenty recall updates. Several share a product. The seed fixes their order."""
    if count % len(ENTITIES) != 0:
        raise ValueError("count must divide evenly across the four products")
    per_entity = count // len(ENTITIES)
    messages = []
    for entity in ENTITIES:
        for sequence in range(per_entity):
            messages.append(
                {
                    "correlation_id": f"ord-{entity.replace(' ', '-')}-{sequence}",
                    "entity": entity,
                    "entity_sequence": sequence,
                    "question": f"Recall update {sequence} for {entity}. The seal is torn.",
                    "plan": [
                        "Name the product the shopper is asking about.",
                        "Call this a packaging / seal failure.",
                        "Tell the shopper not to eat it and to take it back to the store.",
                    ],
                }
            )
    random.Random(seed).shuffle(messages)
    for index, message in enumerate(messages):
        message["produce_index"] = index
    return messages


def produced_sequences(messages: list[dict]) -> dict[str, list[int]]:
    """For each product, the order those updates were sent."""
    order: dict[str, list[int]] = {}
    for message in messages:
        order.setdefault(message["entity"], []).append(message["entity_sequence"])
    return order


def entity_views(records: list[dict]) -> dict[str, dict]:
    """Group what the writers actually saw.

    Offsets only compare inside one partition, so a product that landed on two
    partitions gets its updates lined up partition by partition. That is the
    order a restart would replay, and it is not the order they were sent.
    """
    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(record["entity"], []).append(record)
    views = {}
    for entity, rows in grouped.items():
        rows = sorted(rows, key=lambda row: (row["partition"], row["offset"]))
        views[entity] = {
            "partitions": sorted({row["partition"] for row in rows}),
            "sequences": [row["entity_sequence"] for row in rows],
        }
    return views


def order_preserved(views: dict, sent: dict[str, list[int]]) -> bool:
    for entity, wanted in sent.items():
        view = views.get(entity)
        if view is None:
            return False
        if view["sequences"] != wanted or len(view["partitions"]) != 1:
            return False
    return True


def any_entity_split(views: dict) -> bool:
    return any(len(view["partitions"]) > 1 for view in views.values())
