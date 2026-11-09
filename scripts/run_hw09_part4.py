import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))
sys.path.insert(0, str(REPO / "src"))

from kafka_service.lessons import (  # noqa: E402
    add_lesson,
    is_broad,
    load_lessons,
    save_lessons,
    select_lessons,
)
from kafka_service.recall_agents import AnsweringAgent, EvaluatorAgent  # noqa: E402
from kafka_service.recall_facts import load_reference  # noqa: E402

REPORTS = REPO / "reports" / "hw09"
RAW = REPORTS / "raw"
SCOPED_PATTERN = "The answer omits the recall type."
SCOPED_CORRECTION = (
    "When the question asks for a recall type, read that product's record "
    "in the reference dataset and include its recall_type. "
    "Do not add recall facts to unrelated questions."
)
BROAD_PATTERN = "The answer omits the current unit count."
BROAD_CORRECTION = (
    "Always include 120 affected units and the Packaging / Seal Failure "
    "recall type in every answer."
)


def _items(name: str) -> list[dict]:
    document = json.loads((REPORTS / name).read_text())
    for item in document["items"]:
        if "answer" in item or "correct_answer" in item:
            raise SystemExit(f"{name} must contain questions only. Found an answer field.")
    return document["items"]


def _run_turn(agent, evaluator, item, lessons, records, *, repair: bool, use_lessons: bool) -> dict:
    chosen = select_lessons(item["question"], lessons, increment=use_lessons) if use_lessons else []
    feedback = None
    history = []
    attempts = 0
    latency_ms = 0.0
    evaluation = None
    answer = ""
    for attempt in (1, 2):
        attempts = attempt
        print(f"{item['id']} attempt {attempt}", flush=True)
        answer, spent = agent.answer(
            item["question"], item["id"], attempt, chosen, feedback, records
        )
        latency_ms += spent
        evaluation = evaluator.evaluate(item["question"], answer, records)
        history.append(
            {
                "attempt": attempt,
                "answer": answer,
                "verdict": evaluation["verdict"],
                "explanation": evaluation["explanation"],
                "feedback": evaluation["feedback"],
                "pattern": evaluation["pattern"],
                "latency_ms": round(spent, 1),
                "lessons": [lesson["lesson_id"] for lesson in chosen],
            }
        )
        print(f"  {evaluation['verdict']}: {evaluation['explanation']}", flush=True)
        if evaluation["verdict"] == "PASS" or not repair or attempt == 2:
            break
        feedback = evaluation
    return {
        "id": item["id"],
        "question": item["question"],
        "correct": evaluation["verdict"] == "PASS",
        "attempts": attempts,
        "latency_ms": round(latency_ms, 1),
        "answer": answer,
        "history": history,
        "lessons": [lesson["lesson_id"] for lesson in chosen],
    }


def _summarize(rows: list[dict]) -> dict:
    correct = sum(1 for row in rows if row["correct"])
    return {
        "correct": correct,
        "incorrect": len(rows) - correct,
        "avg_attempts": round(sum(row["attempts"] for row in rows) / len(rows), 2),
        "avg_latency_ms": round(sum(row["latency_ms"] for row in rows) / len(rows), 1),
    }


def _print_revision(result: dict) -> None:
    print()
    print("=== REVISION SEQUENCE ===")
    print(f"question: {result['question']}")
    for step in result["history"]:
        print(f"attempt {step['attempt']} answer: {step['answer']}")
        print(f"evaluator: {step['verdict']}")
        print(f"explanation: {step['explanation']}")
        if step["feedback"]:
            print(f"feedback: {step['feedback']}")
    print(f"attempts: {result['attempts']}")
    print(f"final verdict: {result['history'][-1]['verdict']}")
    print(f"final response: {result['answer']}")
    print()


def _print_reuse(result: dict, lessons: list[dict]) -> None:
    print()
    print("=== LESSON REUSE ===")
    print(f"question: {result['question']}")
    loaded = [lesson for lesson in lessons if lesson["lesson_id"] in result["lessons"]]
    for lesson in loaded:
        print(
            f"loaded {lesson['lesson_id']} use_count={lesson['use_count']} "
            f"created_at={lesson['created_at']}"
        )
        print(f"failure_pattern: {lesson['failure_pattern']}")
        print(f"correction: {lesson['correction']}")
    print(f"answer: {result['answer']}")
    print(f"evaluator: {result['history'][-1]['verdict']}")
    print(f"attempts: {result['attempts']}")
    print()


def _score_line(label: str, rows: list[dict]) -> str:
    summary = _summarize(rows)
    print(
        f"{label}: correct={summary['correct']} incorrect={summary['incorrect']} "
        f"avg_attempts={summary['avg_attempts']} avg_latency_ms={summary['avg_latency_ms']}"
    )
    return (
        f"| {label} | {summary['correct']} | {summary['incorrect']} | "
        f"{summary['avg_attempts']:.2f} | {summary['avg_latency_ms']:.1f} |"
    )


def _regressed(before: list[dict], after: list[dict]) -> bool:
    for left, right in zip(before, after):
        if left["correct"] and not right["correct"]:
            return True
    return False


def _note_patterns(result: dict, counts: dict, lessons: list[dict]) -> None:
    first = result["history"][0]
    if first["verdict"] != "REVISE" or not first["pattern"]:
        return
    if first["pattern"] == "unsupported":
        return
    counts[first["pattern"]] = counts.get(first["pattern"], 0) + 1
    if counts[first["pattern"]] != 2:
        return
    if first["pattern"] == "omits_recall_type" and not any(not is_broad(item) for item in lessons):
        created = add_lesson(lessons, SCOPED_PATTERN, SCOPED_CORRECTION)
        print(f"created {created['lesson_id']} from a repeated recall-type miss")
        print(json.dumps(created, indent=2))
    if first["pattern"] == "omits_units" and not any(is_broad(item) for item in lessons):
        created = add_lesson(lessons, BROAD_PATTERN, BROAD_CORRECTION)
        print(f"created {created['lesson_id']} from a repeated unit-count miss")
        print(json.dumps(created, indent=2))
        print("This correction says Always, so it is applied to every later question.")


def _run_set(
    agent, evaluator, items, lessons, records, *, repair: bool, use_lessons: bool
) -> list[dict]:
    return [
        _run_turn(
            agent,
            evaluator,
            item,
            lessons,
            records,
            repair=repair,
            use_lessons=use_lessons,
        )
        for item in items
    ]


def main() -> None:
    print("prefix: s6491")
    print("part: 4 answering agent and evaluator")
    print("The first draft of train_repair_01, train_02, train_04, and train_05 is a fixed")
    print("incomplete answer, so the revision and the repeated lesson can be shown.")
    print("Every revision, and every validation and test question, calls qwen3:8b.")
    print("test_data.json is not read until the lessons have been chosen.")
    print(flush=True)

    records = load_reference()["records"]
    training = _items("training_data.json")
    validation = _items("validation_data.json")
    agent = AnsweringAgent()
    evaluator = EvaluatorAgent()
    lessons = []
    save_lessons(lessons)
    counts = {}

    print("=== Training ===")
    for item in training:
        result = _run_turn(agent, evaluator, item, lessons, records, repair=True, use_lessons=True)
        if item["id"] == "train_repair_01":
            _print_revision(result)
        _note_patterns(result, counts, lessons)
        if item["id"] == "train_03":
            _print_reuse(result, lessons)
    save_lessons(lessons)
    snapshot = copy.deepcopy(lessons)
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / "lessons_before_validation.json").write_text(json.dumps(snapshot, indent=2) + "\n")

    print("=== Validation: scoped lesson ===")
    before_scoped = _run_set(
        agent, evaluator, validation, [], records, repair=False, use_lessons=False
    )
    scoped_only = [lesson for lesson in lessons if not is_broad(lesson)]
    after_scoped = _run_set(
        agent, evaluator, validation, scoped_only, records, repair=False, use_lessons=True
    )
    print("Before the scoped lesson:")
    _score_line("no lesson", before_scoped)
    print("After the scoped lesson:")
    _score_line("scoped lesson", after_scoped)
    if _regressed(before_scoped, after_scoped):
        print("Scoped lesson regressed a previously correct answer. Removing it.")
        lessons = [lesson for lesson in lessons if is_broad(lesson)]
    else:
        print(
            "Scoped lesson kept: failures improved or stayed, and correct answers stayed correct."
        )

    print("=== Validation: broad lesson ===")
    if any(not is_broad(lesson) for lesson in lessons):
        before_broad = after_scoped
        print("Before the broad lesson, using the scoped-lesson scores above.")
        _score_line("scoped only", before_broad)
    else:
        before_broad = _run_set(
            agent, evaluator, validation, [], records, repair=False, use_lessons=False
        )
        print("Before the broad lesson:")
        _score_line("no lesson", before_broad)
    print("After adding the broad lesson:")
    after_broad = _run_set(
        agent, evaluator, validation, snapshot, records, repair=False, use_lessons=True
    )
    _score_line("scoped + broad", after_broad)
    if _regressed(before_broad, after_broad):
        print("REGRESSION: the broad lesson made a previously correct validation answer wrong.")
        print("Removed the broad lesson. It is not written to lessons.json.")
        lessons = [lesson for lesson in lessons if not is_broad(lesson)]
    else:
        print("Broad lesson did not regress validation. Keeping it.")
        lessons = copy.deepcopy(snapshot)
    save_lessons(lessons)

    print("test_data.json is loaded only now, after lessons were chosen.")
    test = _items("test_data.json")
    variants = [
        ("Baseline", False, []),
        ("Evaluator Repair", True, []),
        ("Lesson Memory", False, copy.deepcopy(snapshot)),
        ("Validated Improvement", False, lessons),
    ]
    print()
    print("=== Test ===")
    table_rows = []
    detailed = []
    for name, repair, variant_lessons in variants:
        print(f"--- {name} ---")
        rows = _run_set(
            agent,
            evaluator,
            test,
            variant_lessons,
            records,
            repair=repair,
            use_lessons=bool(variant_lessons),
        )
        table_rows.append(_score_line(name, rows))
        detailed.append({"variant": name, "summary": _summarize(rows), "rows": rows})
    save_lessons(lessons)

    print()
    print(
        f"{'Variant':<24} {'Correct':>8} {'Incorrect':>10} {'Avg attempts':>14} {'Avg latency ms':>16}"
    )
    for name, _repair, _lessons in variants:
        match = next(item for item in detailed if item["variant"] == name)
        summary = match["summary"]
        print(
            f"{name:<24} {summary['correct']:>8} {summary['incorrect']:>10} "
            f"{summary['avg_attempts']:>14.2f} {summary['avg_latency_ms']:>16.1f}"
        )

    print()
    print("=== How the agents work ===")
    print(
        "The Answering Agent writes the draft. The Evaluator Agent then checks that draft "
        "against reference_dataset.json and returns PASS or REVISE plus a short reason. "
        "On REVISE, the feedback is handed back to the Answering Agent for one revision. "
        "The loop stops after two attempts even if the second answer is still wrong."
    )
    print(
        "A lesson is written when the same failure pattern shows up on two training answers. "
        "Later questions load that lesson before the draft is written. use_count goes up each time."
    )
    print(
        "Validation runs the same validation_data.json before and after a lesson. "
        "A lesson is kept only when previously correct answers stay correct. "
        "The broad unit-count lesson is dropped when it pastes the blueberry recall onto other questions. "
        "test_data.json is not used to write or edit lessons."
    )
    print(
        "Limitation: the evaluator treats an answer as correct when the reference phrase appears. "
        "It does not score fluency. The answering agent also appends a missing required phrase "
        "from the record it was allowed to see, so a revision is not only the model's free rewrite."
    )

    lines = [
        "| Variant | Correct answers | Incorrect answers | Average attempts | Average latency (ms) |",
        "|---|---:|---:|---:|---:|",
        *table_rows,
        "",
    ]
    (REPORTS / "part4_table.md").write_text("\n".join(lines) + "\n")
    (RAW / "part4_results.json").write_text(json.dumps(detailed, indent=2) + "\n")
    print(f"wrote {REPORTS / 'part4_table.md'}")
    print("kept lessons:")
    print(json.dumps(load_lessons(), indent=2))


if __name__ == "__main__":
    main()
