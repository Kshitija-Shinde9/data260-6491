import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def review_draft(draft: str) -> tuple[str, str]:
    """Approve a draft that tells the shopper not to eat the product."""
    text = (draft or "").strip()
    if text and "do not eat" in text.lower():
        return "approved", text
    if not text:
        return "rejected", "No answer was written."
    return "rejected", text


def handle(message: dict) -> dict:
    status, answer = review_draft(str(message.get("draft", "")))
    return {
        "correlation_id": message["correlation_id"],
        "status": status,
        "answer": answer,
    }


def main() -> None:
    from kafka_service.config import DRAFTS_TOPIC, FINAL_TOPIC
    from kafka_service.pipeline import serve

    serve("REVIEWER", DRAFTS_TOPIC, FINAL_TOPIC, "s6491_reviewer", handle)


if __name__ == "__main__":
    main()
