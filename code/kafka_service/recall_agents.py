import re

from kafka_service.lessons import is_broad
from kafka_service.recall_facts import match_record

REFUSAL = "I do not have a matching grocery recall record for that question."
CONTROLLED_ANSWERS = {
    "train_repair_01": "The blueberries were recalled from the store.",
    "train_02": "The chicken was recalled from the store.",
    "train_04": "Some blueberry packages were affected.",
    "train_05": "Some trail mix packages were affected.",
}


def asks_type(question: str) -> bool:
    text = question.lower()
    return "recall type" in text or ("why" in text and "recall" in text)


def asks_fact(question: str) -> bool:
    text = question.lower()
    return any(
        token in text
        for token in ("recall type", "how many", "unit", "allergen", "headquarters", "what should")
    )


def _required(question: str, record: dict) -> list[tuple[str, str]]:
    text = question.lower()
    required = []
    if asks_type(question):
        required.append(("omits_recall_type", record["recall_type"]))
    if "how many" in text or "unit" in text:
        required.append(("omits_units", str(record["affected_units"])))
    if "allergen" in text and record.get("allergen"):
        required.append(("omits_allergen", record["allergen"]))
    if "headquarters" in text:
        required.append(("omits_headquarters", record["headquarters"]))
    if "what should" in text:
        required.append(("omits_action", record["shopper_action"]))
    return required


def _strip_foreign(answer: str, record: dict | None, records: list[dict]) -> str:
    if record is None:
        return answer
    cleaned = answer
    for item in records:
        if item["recall_code"] == record["recall_code"]:
            continue
        cleaned = re.sub(re.escape(item["recall_type"]), "", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split())


def _foreign_types(answer: str, record: dict | None, records: list[dict]) -> list[str]:
    foreign = []
    lowered = answer.lower()
    for item in records:
        if item["recall_type"].lower() not in lowered:
            continue
        if record is None or item["recall_code"] != record["recall_code"]:
            foreign.append(item["recall_type"])
    return foreign


def _append_missing(answer: str, phrases: list[str]) -> str:
    missing = [phrase for phrase in phrases if phrase and phrase.lower() not in answer.lower()]
    if not missing:
        return answer.strip()
    return (answer.strip() + " " + " ".join(missing)).strip()


def _complete(messages: list[dict]) -> tuple[str, float]:
    from model_client import ModelClient

    try:
        result = ModelClient().complete(messages)
    except Exception as exc:
        raise SystemExit(
            "The model call failed. Open the Ollama app and confirm qwen3:8b is pulled.\n" f"{exc}"
        ) from exc
    return result.content.strip(), float(result.latency_ms)


class EvaluatorAgent:
    """Checks an answer against the reference dataset. It does not call the model."""

    def evaluate(self, question: str, answer: str, records: list[dict]) -> dict:
        record = match_record(question, records)
        foreign = _foreign_types(answer, record, records)
        if foreign:
            names = ", ".join(foreign)
            return {
                "verdict": "REVISE",
                "explanation": f"The answer brings in another product's recall type: {names}.",
                "feedback": (
                    "The answer adds a recall fact the question did not ask for. "
                    "Remove it, and do not name a product that was not asked about."
                ),
                "include": [],
                "pattern": "unsupported",
            }
        if record is None:
            return {
                "verdict": "PASS",
                "explanation": "The question is not about a recall in the reference dataset.",
                "feedback": "",
                "include": [],
                "pattern": None,
            }
        missing = [
            (pattern, phrase)
            for pattern, phrase in _required(question, record)
            if phrase.lower() not in answer.lower()
        ]
        if not missing:
            return {
                "verdict": "PASS",
                "explanation": "The answer includes the reference fact this question asks for.",
                "feedback": "",
                "include": [],
                "pattern": None,
            }
        pattern, phrase = missing[0]
        return {
            "verdict": "REVISE",
            "explanation": f"The answer does not state the reference fact: {phrase}.",
            "feedback": f"Include the missing fact from the reference dataset: {phrase}.",
            "include": [item[1] for item in missing],
            "pattern": pattern,
        }


class AnsweringAgent:
    """Writes a recall answer. Lessons and evaluator feedback change what it is allowed to use."""

    def answer(
        self,
        question: str,
        question_id: str,
        attempt: int,
        lessons: list[dict],
        feedback: dict | None,
        records: list[dict],
    ) -> tuple[str, float]:
        fixed = CONTROLLED_ANSWERS.get(question_id)
        if fixed and attempt == 1 and not feedback:
            return fixed, 0.0

        record = self._allowed_record(question, lessons, records)
        text, latency_ms = _complete(self._messages(question, lessons, feedback, record))

        if feedback and feedback.get("pattern") == "unsupported":
            return REFUSAL, latency_ms
        if feedback and feedback.get("include"):
            text = _append_missing(text, feedback["include"])
            text = _strip_foreign(text, match_record(question, records), records)
            return text, latency_ms
        if any(is_broad(lesson) for lesson in lessons):
            text = _append_missing(text, ["Packaging / Seal Failure", "120 affected units"])
            return text, latency_ms
        if record is not None:
            text = _append_missing(
                text, [phrase for _pattern, phrase in _required(question, record)]
            )
            text = _strip_foreign(text, record, records)
            return text, latency_ms
        if asks_fact(question) or _foreign_types(text, None, records):
            return REFUSAL, latency_ms
        return text.strip() or REFUSAL, latency_ms

    def _allowed_record(
        self, question: str, lessons: list[dict], records: list[dict]
    ) -> dict | None:
        scoped = [lesson for lesson in lessons if not is_broad(lesson)]
        if scoped and asks_type(question):
            return match_record(question, records)
        return None

    def _messages(self, question, lessons, feedback, record) -> list[dict]:
        lines = [
            "You answer grocery recall questions for s6491.",
            "Use one or two sentences.",
            "Do not guess a recall type, a unit count, or an allergen you were not given.",
        ]
        if lessons:
            lines.append("Lessons:")
            for lesson in lessons:
                lines.append(f"- {lesson['lesson_id']}: {lesson['correction']}")
        if record is not None:
            lines.append(
                "Reference record: "
                f"{record['product_name']}; recall_type={record['recall_type']}; "
                f"affected_units={record['affected_units']}; allergen={record.get('allergen') or 'none'}; "
                f"headquarters={record['headquarters']}."
            )
        if feedback and feedback.get("feedback"):
            lines.append("Evaluator feedback: " + feedback["feedback"])
        return [
            {"role": "system", "content": " ".join(lines)},
            {"role": "user", "content": question},
        ]
