
from __future__ import annotations

import json
import re
import sys
from typing import Any, Callable

from pathlib import Path

SAFETY_ERROR = "safety rule: looking up grocery recalls by submitter email is not allowed"
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

sys.path.insert(0, str(Path(__file__).resolve().parent))


def envelope(*, ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload)


def safety_violation(inputs: dict[str, Any]) -> str | None:
    blob = json.dumps(inputs)
    if _EMAIL_RE.search(blob):
        return SAFETY_ERROR
    return None


def _as_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    return value


def _dispatch_search(inputs: dict[str, Any], search_fn: Callable) -> dict[str, Any]:
    query = inputs.get("query", "")
    limit = inputs.get("limit", 10)
    if not isinstance(query, str) or not query.strip():
        return envelope(ok=False, data=None, error="query must be a non-empty string")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 100:
        return envelope(ok=False, data=None, error="limit must be an integer between 1 and 100")
    return search_fn(query=query, limit=limit)


def _dispatch_detail(inputs: dict[str, Any], detail_fn: Callable) -> dict[str, Any]:
    if "recall_id" not in inputs:
        return envelope(ok=False, data=None, error="recall_id is required")
    try:
        recall_id = _as_int(inputs["recall_id"], "recall_id")
    except ValueError as exc:
        return envelope(ok=False, data=None, error=str(exc))
    if recall_id < 1:
        return envelope(ok=False, data=None, error="recall_id must be a positive integer")
    return detail_fn(recall_id=recall_id)


def _dispatch_aggregate(inputs: dict[str, Any], aggregate_fn: Callable) -> dict[str, Any]:
    min_units = inputs.get("min_units", 0)
    try:
        min_units = _as_int(min_units, "min_units")
    except ValueError as exc:
        return envelope(ok=False, data=None, error=str(exc))
    if min_units < 0:
        return envelope(ok=False, data=None, error="min_units must be an integer >= 0")
    return aggregate_fn(min_units=min_units)


def _live_backends() -> dict[str, Callable]:
    import domain_server as domain

    def search_fn(query: str, limit: int) -> dict[str, Any]:
        return domain.search_recalls(query, limit)

    def detail_fn(recall_id: int) -> dict[str, Any]:
        return domain.get_recall_detail(recall_id)

    def aggregate_fn(min_units: int) -> dict[str, Any]:
        return domain.aggregate_recalls_by_supplier(min_units)

    return {
        "search_recalls": search_fn,
        "get_recall_detail": detail_fn,
        "aggregate_recalls_by_supplier": aggregate_fn,
    }


def execute_tool(name: str, inputs: dict[str, Any] | None = None, backends: dict | None = None) -> str:
    try:
        if not isinstance(name, str) or not name.strip():
            return _to_json(envelope(ok=False, data=None, error="tool name must be a non-empty string"))
        if inputs is None:
            inputs = {}
        if not isinstance(inputs, dict):
            return _to_json(envelope(ok=False, data=None, error="inputs must be a JSON object"))

        blocked = safety_violation(inputs)
        if blocked:
            return _to_json(envelope(ok=False, data=None, error=blocked))

        handlers = backends if backends is not None else _live_backends()
        if name == "search_recalls":
            return _to_json(_dispatch_search(inputs, handlers["search_recalls"]))
        if name == "get_recall_detail":
            return _to_json(_dispatch_detail(inputs, handlers["get_recall_detail"]))
        if name == "aggregate_recalls_by_supplier":
            return _to_json(_dispatch_aggregate(inputs, handlers["aggregate_recalls_by_supplier"]))
        return _to_json(envelope(ok=False, data=None, error=f"unknown tool: {name}"))
    except Exception as exc:
        return _to_json(envelope(ok=False, data=None, error=str(exc)))