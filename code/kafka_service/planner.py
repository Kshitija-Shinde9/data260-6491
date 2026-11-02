import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def make_plan(question: str) -> list[str]:
    """Turn a shopper's question into the steps the writer should follow."""
    text = question.lower()
    plan = ["Name the product the shopper is asking about."]
    if any(word in text for word in ("seal", "tear", "frost", "torn")):
        plan.append("Call this a packaging / seal failure.")
    elif any(word in text for word in ("peanut", "allergen", "soy", "egg")):
        plan.append("Call this an undeclared allergen.")
    elif any(word in text for word in ("warm", "spoil", "chicken", "smell")):
        plan.append("Call this a spoiled or quality issue.")
    else:
        plan.append("Pick the closest recall reason from the four types we use.")
    plan.append("Tell the shopper not to eat it and to take it back to the store.")
    return plan


def handle(message: dict) -> dict:
    question = str(message.get("question", "")).strip()
    return {
        "correlation_id": message["correlation_id"],
        "question": question,
        "plan": make_plan(question),
    }


def main() -> None:
    from kafka_service.config import INBOX_TOPIC, TASKS_TOPIC
    from kafka_service.pipeline import serve

    serve("PLANNER", INBOX_TOPIC, TASKS_TOPIC, "s6491_planner", handle)


if __name__ == "__main__":
    main()
