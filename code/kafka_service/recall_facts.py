import json
from pathlib import Path

REFERENCE_PATH = Path(__file__).resolve().parents[2] / "reports" / "hw09" / "reference_dataset.json"


def load_reference() -> dict:
    return json.loads(REFERENCE_PATH.read_text())


def match_record(question: str, records: list[dict]) -> dict | None:
    """Pick the recall whose match_terms appear in the question. None if it is off-domain."""
    text = question.lower()
    best = None
    best_score = 0
    for record in records:
        score = 0
        for term in record.get("match_terms", []):
            if term.lower() in text:
                score += len(term)
        if score > best_score:
            best = record
            best_score = score
    return best
