
from __future__ import annotations

import logging
import os
import random
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

try:
    from mcp.server.fastmcp import FastMCP as _Server
except ModuleNotFoundError:
    from mcp.server.mcpserver import MCPServer as _Server

from resilient_storage import VERIFY_SEED, call_with_retry

logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [s6491_rel] %(message)s",
)
log = logging.getLogger("s6491_rel")

_ENV_PATH = Path(__file__).resolve().parents[1] / "web_application" / ".env"
load_dotenv(_ENV_PATH)
load_dotenv()

mcp = _Server("s6491_rel")

_engine: Engine | None = None


def _get_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL missing. Set it in code/web_application/.env "
            "(same file used by the FastAPI app)."
        )
    _engine = create_engine(url, pool_pre_ping=True)
    return _engine


def envelope(*, ok: bool, data: Any = None, error: str | None = None) -> dict[str, Any]:
    return {"ok": ok, "data": data, "error": error}


def _row_to_recall(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "product_name": row.product_name,
        "recall_code": row.recall_code,
        "affected_units": row.affected_units,
        "supplier_id": row.supplier_id,
        "email": row.email,
        "description": row.description,
        "recall_type": row.recall_type,
    }


def _db_search(query: str, limit: int) -> dict[str, Any]:
    term = f"%{query.strip().lower()}%"
    with _get_engine().connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, product_name, recall_code, affected_units, supplier_id,
                       email, description, recall_type
                FROM recalls
                WHERE LOWER(product_name) LIKE :term
                   OR LOWER(recall_code) LIKE :term
                ORDER BY id
                LIMIT :limit
                """
            ),
            {"term": term, "limit": limit},
        ).fetchall()
    results = [_row_to_recall(r) for r in rows]
    return {"count": len(results), "items": results}


def _db_detail(recall_id: int) -> dict[str, Any]:
    with _get_engine().connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT r.id, r.product_name, r.recall_code, r.affected_units, r.supplier_id,
                       r.email, r.description, r.recall_type,
                       s.name AS supplier_name, s.supplier_code
                FROM recalls r
                LEFT JOIN suppliers s ON s.id = r.supplier_id
                WHERE r.id = :rid
                """
            ),
            {"rid": recall_id},
        ).fetchone()
    if row is None:
        raise LookupError(f"recall_id {recall_id} not found")
    data = _row_to_recall(row)
    data["supplier_name"] = row.supplier_name
    data["supplier_code"] = row.supplier_code
    return data


def _db_aggregate(min_units: int) -> dict[str, Any]:
    with _get_engine().connect() as conn:
        rows = conn.execute(
            text(
                """
                SELECT s.id AS supplier_id,
                       s.name AS supplier_name,
                       s.supplier_code,
                       COUNT(r.id) AS recall_count,
                       COALESCE(SUM(r.affected_units), 0) AS total_affected_units
                FROM suppliers s
                LEFT JOIN recalls r ON r.supplier_id = s.id
                GROUP BY s.id, s.name, s.supplier_code
                HAVING COALESCE(SUM(r.affected_units), 0) >= :min_units
                ORDER BY total_affected_units DESC, s.id
                """
            ),
            {"min_units": min_units},
        ).fetchall()
    items = [
        {
            "supplier_id": r.supplier_id,
            "supplier_name": r.supplier_name,
            "supplier_code": r.supplier_code,
            "recall_count": int(r.recall_count),
            "total_affected_units": int(r.total_affected_units),
        }
        for r in rows
    ]
    return {"count": len(items), "items": items}


def run_storage(
    operation,
    *,
    failure_rate: float = 0.0,
    rng: random.Random | None = None,
    force_mode: str | None = None,
):
    if rng is None:
        rng = random.Random(VERIFY_SEED)
    return call_with_retry(
        operation,
        rng=rng,
        failure_rate=failure_rate,
        force_mode=force_mode,
    )


@mcp.tool()
def search_recalls(query: str, limit: int = 10) -> dict[str, Any]:
    log.info("search_recalls query=%r limit=%s", query, limit)
    if not isinstance(query, str) or not query.strip():
        return envelope(ok=False, data=None, error="query must be a non-empty string")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1 or limit > 100:
        return envelope(ok=False, data=None, error="limit must be an integer between 1 and 100")

    result = run_storage(lambda: _db_search(query, limit))
    return envelope(ok=result.ok, data=result.data, error=result.error)


@mcp.tool()
def get_recall_detail(recall_id: int) -> dict[str, Any]:
    log.info("get_recall_detail recall_id=%r", recall_id)
    if not isinstance(recall_id, int) or isinstance(recall_id, bool) or recall_id < 1:
        return envelope(ok=False, data=None, error="recall_id must be a positive integer")

    result = run_storage(lambda: _db_detail(recall_id))
    return envelope(ok=result.ok, data=result.data, error=result.error)


@mcp.tool()
def aggregate_recalls_by_supplier(min_units: int = 0) -> dict[str, Any]:
    log.info("aggregate_recalls_by_supplier min_units=%r", min_units)
    if not isinstance(min_units, int) or isinstance(min_units, bool) or min_units < 0:
        return envelope(ok=False, data=None, error="min_units must be an integer >= 0")

    result = run_storage(lambda: _db_aggregate(min_units))
    return envelope(ok=result.ok, data=result.data, error=result.error)


if __name__ == "__main__":
    mcp.run()
