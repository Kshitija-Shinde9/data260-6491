#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "code", "mcp"))

from execute_tool import SAFETY_ERROR, envelope, execute_tool  # noqa: E402


FIXTURE_RECALLS = [
    {
        "id": 1,
        "product_name": "Trader Joe's Organic Frozen Blueberries, 16oz",
        "recall_code": "REC-0001",
        "affected_units": 120,
        "supplier_id": 1,
        "supplier_name": "Trader Joe's",
        "supplier_code": "SUP-0001",
    },
    {
        "id": 2,
        "product_name": "Safeway Signature Rotisserie Chicken",
        "recall_code": "REC-0002",
        "affected_units": 40,
        "supplier_id": 2,
        "supplier_name": "Safeway Deli",
        "supplier_code": "SUP-0002",
    },
]


def fake_search(query: str, limit: int) -> dict:
    term = query.strip().lower()
    items = [
        r
        for r in FIXTURE_RECALLS
        if term in r["product_name"].lower() or term in r["recall_code"].lower()
    ][:limit]
    return envelope(ok=True, data={"count": len(items), "items": items}, error=None)


def fake_detail(recall_id: int) -> dict:
    for row in FIXTURE_RECALLS:
        if row["id"] == recall_id:
            return envelope(ok=True, data=row, error=None)
    return envelope(ok=False, data=None, error=f"recall_id {recall_id} not found")


def fake_aggregate(min_units: int) -> dict:
    totals = {}
    for row in FIXTURE_RECALLS:
        bucket = totals.setdefault(
            row["supplier_id"],
            {
                "supplier_id": row["supplier_id"],
                "supplier_name": row["supplier_name"],
                "supplier_code": row["supplier_code"],
                "recall_count": 0,
                "total_affected_units": 0,
            },
        )
        bucket["recall_count"] += 1
        bucket["total_affected_units"] += row["affected_units"]
    items = [b for b in totals.values() if b["total_affected_units"] >= min_units]
    return envelope(ok=True, data={"count": len(items), "items": items}, error=None)


BACKENDS = {
    "search_recalls": fake_search,
    "get_recall_detail": fake_detail,
    "aggregate_recalls_by_supplier": fake_aggregate,
}


def call(name, inputs):
    raw = execute_tool(name, inputs, backends=BACKENDS)
    parsed = json.loads(raw)
    assert isinstance(raw, str)
    assert "ok" in parsed and "data" in parsed and "error" in parsed
    return parsed


def run_test(name, fn):
    try:
        fn()
        print(f"PASS  {name}")
        return True
    except AssertionError as exc:
        print(f"FAIL  {name}  ({exc})")
        return False
    except Exception as exc:
        print(f"FAIL  {name}  (crashed: {exc})")
        return False


def test_search_valid():
    out = call("search_recalls", {"query": "Blueberries", "limit": 10})
    assert out["ok"] is True
    assert out["error"] is None
    assert out["data"]["count"] >= 1


def test_search_invalid_empty_query():
    out = call("search_recalls", {"query": "", "limit": 10})
    assert out["ok"] is False
    assert out["data"] is None
    assert "non-empty" in out["error"]


def test_detail_valid():
    out = call("get_recall_detail", {"recall_id": 1})
    assert out["ok"] is True
    assert out["error"] is None
    assert out["data"]["id"] == 1


def test_detail_invalid_missing_id():
    out = call("get_recall_detail", {"recall_id": 99999})
    assert out["ok"] is False
    assert out["data"] is None
    assert "not found" in out["error"]


def test_aggregate_valid():
    out = call("aggregate_recalls_by_supplier", {"min_units": 0})
    assert out["ok"] is True
    assert out["error"] is None
    assert out["data"]["count"] >= 1


def test_aggregate_invalid_negative():
    out = call("aggregate_recalls_by_supplier", {"min_units": -1})
    assert out["ok"] is False
    assert out["data"] is None
    assert ">= 0" in out["error"]


def test_safety_rule_blocks_email_lookup():
    out = call("search_recalls", {"query": "rohan1@gmail.com", "limit": 10})
    assert out["ok"] is False
    assert out["data"] is None
    assert out["error"] == SAFETY_ERROR


def test_agent_stops_at_max_steps():
    from agent_loop import MockModel, run_agent

    summary = run_agent(
        "keep searching",
        model=MockModel(),
        max_steps=2,
        backends=BACKENDS,
        log_path=None,
    )
    assert summary["stop_reason"] == "max_steps"
    assert summary["step_count"] == 2
    assert summary["tool_call_count"] == 2


def main():
    tests = [
        ("search_recalls valid", test_search_valid),
        ("search_recalls invalid empty query", test_search_invalid_empty_query),
        ("get_recall_detail valid", test_detail_valid),
        ("get_recall_detail invalid 99999", test_detail_invalid_missing_id),
        ("aggregate_recalls_by_supplier valid", test_aggregate_valid),
        ("aggregate_recalls_by_supplier invalid min_units=-1", test_aggregate_invalid_negative),
        ("execute_tool blocks email search (safety rule)", test_safety_rule_blocks_email_lookup),
        ("run_agent MockModel stops at max_steps", test_agent_stops_at_max_steps),
    ]
    passed = 0
    for name, fn in tests:
        if run_test(name, fn):
            passed += 1
    total = len(tests)
    print(f"\n{passed}/{total} tests passed")
    if passed != total:
        sys.exit(1)


if __name__ == "__main__":
    main()
