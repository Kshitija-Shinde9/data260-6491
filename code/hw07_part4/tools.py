from __future__ import annotations

import ast
import csv
import hashlib
import io
import json
import operator
import re
import sqlite3
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CSV_SQL_SCHEMA = {
    "name": "csv_sql",
    "input": {"type": "object", "properties": {"sql": {"type": "string"}}, "required": ["sql"]},
}
POLICY_SCHEMA = {
    "name": "policy_retriever",
    "input": {
        "type": "object",
        "properties": {
            "url": {"type": "string"},
            "query": {"type": "string"},
            "k": {"type": "number"},
        },
        "required": ["url", "query"],
    },
}
CALCULATOR_SCHEMA = {
    "name": "calculator",
    "input": {
        "type": "object",
        "properties": {"expression": {"type": "string"}, "units": {"type": "string"}},
        "required": ["expression"],
    },
}


def _ok(data: Any, source: str | None = None) -> dict[str, Any]:
    out = {"success": True, "data": data, "ts": datetime.now(timezone.utc).isoformat()}
    if source:
        out["source"] = source
    return out


def _err(message: str) -> dict[str, Any]:
    return {"success": False, "error": message, "ts": datetime.now(timezone.utc).isoformat()}


def csv_sql(csv_text: str, sql: str) -> dict[str, Any]:
    if not re.match(r"^\s*select\b", sql, re.I) or ";" in sql:
        return _err("csv_sql accepts one read-only SELECT statement")
    try:
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        if not rows:
            return _err("uploaded.csv has no data rows")
        db = sqlite3.connect(":memory:")
        columns = list(rows[0])
        safe = {
            c: re.sub(r"\W+", "_", c).strip("_").lower() or f"col_{i}"
            for i, c in enumerate(columns)
        }
        by_name = {safe[c]: c for c in columns}
        start_col = next(
            (by_name[n] for n in ("started_at", "start_date", "startdate") if n in by_name), None
        )
        duration_col = next(
            (by_name[n] for n in ("duration_minutes", "duration") if n in by_name), None
        )
        ride_col = next(
            (by_name[n] for n in ("ride_id", "bike_number", "bike_number_") if n in by_name), None
        )
        if not start_col or not duration_col:
            return _err(
                "CSV must include Start date/started_at and Duration/duration_minutes columns"
            )
        official_seconds = safe[duration_col] == "duration"
        db.execute("create table trips (started_at text, duration_minutes real, ride_id text)")
        values = []
        for i, row in enumerate(rows, 1):
            try:
                duration = float(row.get(duration_col, 0) or 0)
                if official_seconds:
                    duration /= 60.0
            except ValueError:
                duration = 0.0
            values.append(
                [
                    row.get(start_col, ""),
                    duration,
                    row.get(ride_col, str(i)) if ride_col else str(i),
                ]
            )
        db.executemany("insert into trips values (?, ?, ?)", values)
        # Queries use the normalized names; dates and numeric fields are cast by the query.
        result = db.execute(sql).fetchall()
        names = [d[0] for d in db.execute(sql).description]
        return _ok(
            {
                "rows": [dict(zip(names, r)) for r in result],
                "row_count": len(result),
                "source": "uploaded.csv",
            },
            "uploaded.csv",
        )
    except Exception as exc:
        return _err(f"SQL error: {exc}")


def policy_retriever(
    url: str, query: str, k: int = 4, evidence_dir: str | Path = "reports/hw07/part4/policy"
) -> dict[str, Any]:
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "DATA260-HW7/1.0"})
        raw = urllib.request.urlopen(request, timeout=20).read()
        text = re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "ignore"))
        text = re.sub(r"\s+", " ", text).strip()
        terms = [t.lower() for t in re.findall(r"[A-Za-z0-9$%.-]+", query) if len(t) > 2]
        sentences = re.split(r"(?<=[.!?])\s+", text)
        scored = sorted(
            ((sum(t in s.lower() for t in terms), s[:400]) for s in sentences), reverse=True
        )
        passages = [
            {"text": s, "source": url, "score": score} for score, s in scored[: max(1, k)] if s
        ]
        evidence = Path(evidence_dir)
        evidence.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(raw).hexdigest()
        (evidence / "capital_bikeshare_pricing.html").write_bytes(raw)
        (evidence / "capital_bikeshare_pricing.txt").write_text(text, encoding="utf-8")
        (evidence / "metadata.json").write_text(
            json.dumps(
                {
                    "source_url": url,
                    "accessed_at": datetime.now(timezone.utc).isoformat(),
                    "sha256": digest,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return _ok(
            {
                "passages": passages,
                "source_url": url,
                "accessed_at": datetime.now(timezone.utc).isoformat(),
                "sha256": digest,
            },
            url,
        )
    except Exception as exc:
        return _err(f"policy fetch error: {exc}")


_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.USub: operator.neg,
}


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    raise ValueError("only numeric arithmetic is allowed")


def calculator(expression: str, units: str | None = None) -> dict[str, Any]:
    if not re.fullmatch(r"[0-9+\-*/().\s]+", expression):
        return _err("expression contains unsupported characters")
    try:
        return _ok(
            {
                "value": round(_eval(ast.parse(expression, mode="eval").body), 2),
                "units": units or "",
            }
        )
    except Exception as exc:
        return _err(f"calculation error: {exc}")
