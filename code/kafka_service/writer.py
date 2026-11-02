import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def write_draft(question: str, plan: list) -> str:
    """Write the shopper-facing answer from the planner's steps."""
    steps = " ".join(str(step).rstrip(".") + "." for step in plan if str(step).strip())
    product = "this product"
    lowered = question.lower()
    if "blueberr" in lowered:
        product = "these blueberries"
    elif "chicken" in lowered:
        product = "this chicken"
    elif "trail mix" in lowered or "peanut" in lowered:
        product = "this trail mix"
    return (
        f"Do not eat {product}. {steps} "
        "Take it back to the store and ask them to write up the recall."
    )


def handle(message: dict) -> dict:
    question = str(message.get("question", "")).strip()
    plan = message.get("plan") or []
    if not isinstance(plan, list):
        plan = [str(plan)]
    return {
        "correlation_id": message["correlation_id"],
        "question": question,
        "plan": plan,
        "draft": write_draft(question, plan),
    }


def main() -> None:
    from kafka_service.config import DRAFTS_TOPIC, TASKS_TOPIC
    from kafka_service.pipeline import serve

    serve("WRITER", TASKS_TOPIC, DRAFTS_TOPIC, "s6491_writer", handle)


if __name__ == "__main__":
    main()
