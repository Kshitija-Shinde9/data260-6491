import json
from datetime import date
from pathlib import Path

LESSONS_PATH = Path(__file__).resolve().parents[2] / "reports" / "hw09" / "lessons.json"


def load_lessons() -> list[dict]:
    if not LESSONS_PATH.exists():
        return []
    data = json.loads(LESSONS_PATH.read_text())
    return data if isinstance(data, list) else []


def save_lessons(lessons: list[dict]) -> None:
    LESSONS_PATH.write_text(json.dumps(lessons, indent=2) + "\n")


def is_broad(lesson: dict) -> bool:
    return lesson["correction"].lower().startswith("always")


def add_lesson(lessons: list[dict], failure_pattern: str, correction: str) -> dict:
    lesson = {
        "lesson_id": f"lesson_{len(lessons) + 1:03d}",
        "failure_pattern": failure_pattern,
        "correction": correction,
        "created_at": date.today().isoformat(),
        "use_count": 0,
    }
    lessons.append(lesson)
    save_lessons(lessons)
    return lesson


def select_lessons(question: str, lessons: list[dict], *, increment: bool) -> list[dict]:
    text = question.lower()
    asks_type = "recall type" in text or ("why" in text and "recall" in text)
    chosen = []
    for lesson in lessons:
        if is_broad(lesson) or (asks_type and not is_broad(lesson)):
            chosen.append(lesson)
    if increment and chosen:
        for lesson in chosen:
            lesson["use_count"] = int(lesson.get("use_count", 0)) + 1
    return chosen
