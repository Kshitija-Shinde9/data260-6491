import re
import sys
import time
from datetime import datetime
from pathlib import Path

_CODE = Path(__file__).resolve().parents[1]
_REPO = _CODE.parent
for _entry in (_CODE, _CODE / "web_application", _REPO / "src"):
    if str(_entry) not in sys.path:
        sys.path.insert(0, str(_entry))

from dotenv import load_dotenv

load_dotenv(_CODE / "web_application" / ".env")

from database import SessionLocal  # noqa: E402
from models import Recall  # noqa: E402

from kafka_service.config import QA_THRESHOLD  # noqa: E402
from kafka_service.planner import make_plan  # noqa: E402
from kafka_service.reviewer import review_draft  # noqa: E402
from kafka_service.semantic_cache import SemanticCache  # noqa: E402
from model_client import ModelClient  # noqa: E402

_STOP = {
    "organic",
    "frozen",
    "signature",
    "trader",
    "joes",
    "joe's",
    "safeway",
    "costco",
    "wholesale",
    "should",
    "shopper",
    "recall",
}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9']+", text.lower())
    return {word for word in words if len(word) >= 5 and word not in _STOP}


def load_records() -> list[dict]:
    db = SessionLocal()
    try:
        rows = db.query(Recall).order_by(Recall.id).all()
        if not rows:
            raise SystemExit(
                "No recalls in s6491_rel. Run bash scripts/setup_hw09_part1.sh once so the three notices exist."
            )
        records = []
        for row in rows:
            supplier = row.supplier
            stamp = row.updated_at.isoformat(timespec="seconds") if row.updated_at else "none"
            records.append(
                {
                    "recall_code": row.recall_code,
                    "product_name": row.product_name,
                    "recall_type": row.recall_type or "",
                    "affected_units": row.affected_units,
                    "description": row.description or "",
                    "supplier": supplier.name if supplier else "",
                    "headquarters": supplier.headquarters if supplier else "",
                    "data_version": f"{row.affected_units}@{stamp}",
                }
            )
        return records
    finally:
        db.close()


def match_recall(question: str, records: list[dict]) -> dict | None:
    """Bind a question to one notice only when it uses a word unique to that notice."""
    bags = [_tokens(f"{row['product_name']} {row['description']}") for row in records]
    asked = _tokens(question)
    best = None
    best_score = 0
    for index, row in enumerate(records):
        others = set().union(*(bags[:index] + bags[index + 1 :]))
        score = len((bags[index] - others) & asked)
        if score > best_score:
            best = row
            best_score = score
    return best


def _fact_sheet(records: list[dict]) -> str:
    lines = []
    for row in records:
        lines.append(
            f"{row['recall_code']} | {row['product_name']} | type={row['recall_type']} | "
            f"units={row['affected_units']} | supplier={row['supplier']} | "
            f"headquarters={row['headquarters']} | {row['description']}"
        )
    return "\n".join(lines)


def run_hw8_path(question: str, records: list[dict]) -> dict:
    """HW8 planner, then the local model through src/model_client.py, then the HW8 reviewer."""
    plan = make_plan(question)
    matched = match_recall(question, records)
    messages = [
        {
            "role": "system",
            "content": (
                "You answer questions about grocery recall notices for s6491. "
                "Use only the records below. If the product is not in the records, "
                "say there is no recall on file for it. Use one or two sentences.\n"
                "Plan:\n- " + "\n- ".join(plan) + "\n\nRecords:\n" + _fact_sheet(records)
            ),
        },
        {"role": "user", "content": question},
    ]
    client = ModelClient()
    try:
        draft = client.complete(messages).content.strip()
    except Exception as exc:
        raise SystemExit(
            "The model call failed. In another terminal run:\n"
            "  ollama serve\n"
            "  ollama pull qwen3:8b\n"
            f"{exc}"
        ) from exc
    if matched and ("how many" in question.lower() or "unit" in question.lower()):
        sentence = f"The current affected_units value is {matched['affected_units']}."
        if sentence not in draft:
            draft = draft.rstrip() + " " + sentence
    if matched and "do not eat" not in draft.lower():
        draft = draft.rstrip() + " Do not eat it."
    status, answer = review_draft(draft)
    return {
        "answer": answer,
        "plan": plan,
        "review": status,
        "model": client.model,
        "recall_code": matched["recall_code"] if matched else "",
        "data_version": matched["data_version"] if matched else "0",
    }


def _version_for(records: list[dict], recall_code: str) -> str | None:
    for row in records:
        if row["recall_code"] == recall_code:
            return row["data_version"]
    return None


def set_affected_units(recall_code: str, units: int) -> dict:
    """Change one s6491_rel row. The data_version includes the unit count and the timestamp."""
    db = SessionLocal()
    try:
        row = db.query(Recall).filter(Recall.recall_code == recall_code).one()
        row.affected_units = units
        row.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(row)
        stamp = row.updated_at.isoformat(timespec="seconds") if row.updated_at else "none"
        return {
            "recall_code": row.recall_code,
            "affected_units": row.affected_units,
            "data_version": f"{row.affected_units}@{stamp}",
        }
    finally:
        db.close()


def answer_question(
    question: str,
    cache: SemanticCache,
    records: list[dict] | None = None,
    threshold: float = QA_THRESHOLD,
    *,
    validate_version: bool = True,
    store_miss: bool = True,
) -> dict:
    """Ingress in front of the HW8 path.

    A hit returns the stored answer and does not call the planner or the model.
    A data_version mismatch deletes that hit and runs the HW8 path again.
    A miss runs the HW8 path and stores the query, embedding, answer, and data_version.
    """
    records = load_records() if records is None else records
    started = time.perf_counter()
    found = cache.search(question)
    best = 0.0 if found is None else found["similarity"]

    if found is not None and found["similarity"] >= threshold:
        cached_version = found["data_version"]
        current_version = (
            _version_for(records, found["recall_code"]) if found["recall_code"] else None
        )
        stale = bool(found["recall_code"]) and cached_version != current_version
        if validate_version and stale:
            cache.delete(found["key"])
            print(
                f"invalidated {found['recall_code']} "
                f"cached data_version={cached_version} current data_version={current_version}",
                flush=True,
            )
            found = None
        else:
            latency_ms = (time.perf_counter() - started) * 1000
            print(
                f"cache hit similarity={found['similarity']:.4f} "
                f"is_cached=true latency_ms={latency_ms:.1f}",
                flush=True,
            )
            return {
                "answer": found["answer"],
                "is_cached": True,
                "similarity": found["similarity"],
                "latency_ms": latency_ms,
                "data_version": found["data_version"],
                "recall_code": found["recall_code"],
                "stale": stale,
                "plan": [],
                "review": "",
                "model": "",
            }

    generated = run_hw8_path(question, records)
    if store_miss:
        cache.store(
            question,
            generated["answer"],
            generated["data_version"],
            generated["recall_code"],
        )
    latency_ms = (time.perf_counter() - started) * 1000
    print(
        f"HW8 path: planner -> {generated['model']} via src/model_client.py -> reviewer",
        flush=True,
    )
    print("plan: " + " | ".join(generated["plan"]), flush=True)
    print(f"review: {generated['review']}", flush=True)
    if store_miss:
        print(
            f"stored data_version={generated['data_version']} "
            f"recall_code={generated['recall_code'] or '-'}",
            flush=True,
        )
    print(
        f"cache miss similarity={best:.4f} is_cached=false latency_ms={latency_ms:.1f}",
        flush=True,
    )
    return {
        "answer": generated["answer"],
        "is_cached": False,
        "similarity": best,
        "latency_ms": latency_ms,
        "data_version": generated["data_version"],
        "recall_code": generated["recall_code"],
        "plan": generated["plan"],
        "review": generated["review"],
        "model": generated["model"],
    }
