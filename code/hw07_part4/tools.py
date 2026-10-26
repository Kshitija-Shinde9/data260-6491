from __future__ import annotations

import ast
import csv
import difflib
import fnmatch
import hashlib
import io
import json
import operator
import re
import shlex
import sqlite3
import subprocess
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

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

ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_EVIDENCE = "reports/hw07/part4/policy"
FIXTURE_EVIDENCE = "reports/hw07/part5/policy"


def _ok(data: Any, source: str | None = None) -> dict[str, Any]:
    out = {"success": True, "data": data, "ts": datetime.now(timezone.utc).isoformat()}
    if source:
        out["source"] = source
    return out


def _err(message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "success": False,
        "error": message,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    if data is not None:
        out["data"] = data
    return out


def _table_status(db: sqlite3.Connection) -> dict[str, Any]:
    found = db.execute(
        "select name from sqlite_master where type = 'table' and name = 'trips'"
    ).fetchone()
    if not found:
        return {"table_exists": False, "trip_count": 0}
    count = db.execute("select count(*) from trips").fetchone()[0]
    return {"table_exists": True, "trip_count": int(count)}


def _load_trips(csv_text: str) -> tuple[sqlite3.Connection | None, dict[str, Any] | None]:
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    if not rows:
        return None, _err("uploaded.csv has no data rows")
    columns = list(rows[0])
    safe = {
        c: re.sub(r"\W+", "_", c).strip("_").lower() or f"col_{i}" for i, c in enumerate(columns)
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
        return None, _err(
            "CSV must include Start date/started_at and Duration/duration_minutes columns"
        )
    official_seconds = safe[duration_col] == "duration"
    db = sqlite3.connect(":memory:")
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
            [row.get(start_col, ""), duration, row.get(ride_col, str(i)) if ride_col else str(i)]
        )
    db.executemany("insert into trips values (?, ?, ?)", values)
    return db, None


def csv_sql(csv_text: str, sql: str, *, enforce_select: bool = True) -> dict[str, Any]:
    statement = " ".join(sql.strip().split())
    is_select = ";" not in statement and re.match(r"^select\b", statement, re.I) is not None
    db, failure = _load_trips(csv_text)
    if failure or db is None:
        return failure or _err("uploaded.csv has no data rows")
    try:
        if not is_select:
            status = _table_status(db)
            if enforce_select:
                return _err("csv_sql accepts one read-only SELECT statement", status)
            if re.fullmatch(r"drop\s+table\s+trips", statement, re.I):
                db.execute(statement)
                return _ok(
                    {
                        "statement": statement,
                        "executed": True,
                        "source": "uploaded.csv",
                        **_table_status(db),
                    },
                    "uploaded.csv",
                )
            return _err(
                "undefended demo only executes DROP TABLE trips on the in-memory trips table",
                status,
            )
        # Queries use the normalized names; dates and numeric fields are cast by the query.
        result = db.execute(statement).fetchall()
        names = [d[0] for d in db.execute(statement).description]
        return _ok(
            {
                "rows": [dict(zip(names, row)) for row in result],
                "row_count": len(result),
                "source": "uploaded.csv",
                **_table_status(db),
            },
            "uploaded.csv",
        )
    except Exception as exc:
        return _err(f"SQL error: {exc}")
    finally:
        db.close()


def _local_policy_path(url: str) -> Path | None:
    if url.startswith("file://"):
        path = Path(unquote(urlparse(url).path))
        return path if path.is_file() else None
    candidate = Path(url)
    if candidate.is_file():
        return candidate
    rooted = ROOT / url
    if rooted.is_file():
        return rooted
    return None


def policy_retriever(
    url: str, query: str, k: int = 4, evidence_dir: str | Path = OFFICIAL_EVIDENCE
) -> dict[str, Any]:
    try:
        local = _local_policy_path(url)
        if local is not None:
            raw = local.read_bytes()
            source_url = local.resolve().as_uri()
            if evidence_dir == OFFICIAL_EVIDENCE:
                evidence_dir = FIXTURE_EVIDENCE
        else:
            request = urllib.request.Request(url, headers={"User-Agent": "DATA260-HW7/1.0"})
            raw = urllib.request.urlopen(request, timeout=20).read()
            source_url = url
        text = re.sub(r"<[^>]+>", " ", raw.decode("utf-8", "ignore"))
        text = re.sub(r"\s+", " ", text).strip()
        terms = [t.lower() for t in re.findall(r"[A-Za-z0-9$%.-]+", query) if len(t) > 2]
        sentences = re.split(r"(?<=[.!?])\s+", text)
        scored = sorted(
            ((sum(t in s.lower() for t in terms), s[:400]) for s in sentences), reverse=True
        )
        passages = [
            {"text": s, "source": source_url, "score": score}
            for score, s in scored[: max(1, k)]
            if s
        ]
        evidence = Path(evidence_dir)
        evidence.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(raw).hexdigest()
        (evidence / "capital_bikeshare_pricing.html").write_bytes(raw)
        (evidence / "capital_bikeshare_pricing.txt").write_text(text, encoding="utf-8")
        (evidence / "metadata.json").write_text(
            json.dumps(
                {
                    "source_url": source_url,
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
                "text": text,
                "source_url": source_url,
                "accessed_at": datetime.now(timezone.utc).isoformat(),
                "sha256": digest,
            },
            source_url,
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


SAFE_PREFIXES = ("git status", "git diff", "python3", "python", "echo", "pwd", "ls")
_SANDBOX: Path | None = None
_DESTRUCTIVE_RULES = (
    (
        re.compile(r"\brm\b[^\n]*\s-(?:[a-zA-Z]*r[a-zA-Z]*|--recursive)\b", re.I),
        "recursive deletion",
    ),
    (re.compile(r"\b(?:sudo|pkexec|doas)\b|\bsu\s+-", re.I), "privilege escalation"),
    (re.compile(r"\b(?:chmod|chown|chgrp)\b", re.I), "permission or ownership change"),
    (re.compile(r"\bdd\b[^\n]*\bof=/dev/|\bof=/dev/", re.I), "raw-device write"),
    (re.compile(r"\b(?:mkfs|newfs)\b|\bdiskutil\s+erase\b", re.I), "filesystem creation"),
    (re.compile(r"(?:>>?)\s*/\S+"), "redirection to a root path"),
)


def set_sandbox(path: str | Path) -> Path:
    global _SANDBOX
    root = Path(path).resolve()
    root.mkdir(parents=True, exist_ok=True)
    _SANDBOX = root
    return root


def _sandbox_path(path: str) -> Path:
    if _SANDBOX is None:
        raise ValueError("course sandbox is not set")
    raw = Path(path)
    candidate = raw.resolve() if raw.is_absolute() else (_SANDBOX / raw).resolve()
    if candidate != _SANDBOX and _SANDBOX not in candidate.parents:
        raise ValueError("path is outside the course sandbox")
    return candidate


def _relative(path: Path) -> str:
    if _SANDBOX is None:
        return path.name
    try:
        return path.resolve().relative_to(_SANDBOX).as_posix()
    except ValueError:
        return path.name


def read_file(path: str, max_lines: int | None = None) -> dict[str, Any]:
    try:
        target = _sandbox_path(path)
        if not target.is_file():
            return _err(f"file not found: {_relative(target)}")
        lines = target.read_text(encoding="utf-8").splitlines()
        shown = lines if max_lines is None else lines[: max(0, max_lines)]
        return _ok(
            {
                "path": _relative(target),
                "content": "\n".join(shown),
                "line_count": len(lines),
                "truncated": max_lines is not None and len(lines) > max_lines,
            }
        )
    except Exception as exc:
        return _err(str(exc))


def write_file(path: str, content: str) -> dict[str, Any]:
    try:
        target = _sandbox_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return _ok({"path": _relative(target), "bytes": len(content.encode("utf-8"))})
    except Exception as exc:
        return _err(str(exc))


def edit_file(path: str, old: str, new: str) -> dict[str, Any]:
    try:
        target = _sandbox_path(path)
        if not target.is_file():
            return _err(f"file not found: {_relative(target)}")
        before = target.read_text(encoding="utf-8")
        if old not in before:
            return _err("old text was not found in the file")
        after = before.replace(old, new, 1)
        target.write_text(after, encoding="utf-8")
        diff = "".join(
            difflib.unified_diff(
                before.splitlines(keepends=True),
                after.splitlines(keepends=True),
                fromfile=_relative(target),
                tofile=_relative(target),
                n=1,
            )
        )
        short = "\n".join(diff.splitlines()[:12])
        return _ok({"path": _relative(target), "diff": short})
    except Exception as exc:
        return _err(str(exc))


def glob_files(pattern: str) -> dict[str, Any]:
    try:
        if _SANDBOX is None:
            return _err("course sandbox is not set")
        if ".." in Path(pattern).parts:
            return _err("pattern escapes the course sandbox")
        matches = sorted(
            path
            for path in _SANDBOX.glob(pattern)
            if path.is_file() and (_SANDBOX in path.resolve().parents or path.resolve() == _SANDBOX)
        )
        return _ok({"pattern": pattern, "files": [_relative(path) for path in matches]})
    except Exception as exc:
        return _err(str(exc))


def search_in_files(query: str, file_pattern: str = "*") -> dict[str, Any]:
    try:
        if _SANDBOX is None:
            return _err("course sandbox is not set")
        hits = []
        for path in sorted(_SANDBOX.rglob("*")):
            if not path.is_file():
                continue
            relative = _relative(path)
            if not fnmatch.fnmatch(relative, file_pattern):
                continue
            for number, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), 1
            ):
                if query in line:
                    hits.append({"path": relative, "line": number, "text": line.strip()})
        return _ok({"query": query, "file_pattern": file_pattern, "hits": hits})
    except Exception as exc:
        return _err(str(exc))


def _matches_safe_prefix(command: str) -> str | None:
    stripped = " ".join(command.strip().split())
    for prefix in SAFE_PREFIXES:
        if stripped == prefix or stripped.startswith(prefix + " "):
            return prefix
    return None


def is_destructive(command: str) -> bool:
    return any(rule.search(command) for rule, _reason in _DESTRUCTIVE_RULES)


def destructive_reason(command: str) -> str | None:
    for rule, reason in _DESTRUCTIVE_RULES:
        if rule.search(command):
            return reason
    return None


def confirm_bash(command: str, auto_approve: bool = False) -> dict[str, Any]:
    reason = destructive_reason(command)
    prefix = _matches_safe_prefix(command)
    if reason and not auto_approve:
        return {
            "decision": "block",
            "reason": f"destructive command requires confirmation: {reason}",
            "destructive": True,
            "prefix": prefix,
        }
    if reason and auto_approve:
        return {
            "decision": "allow",
            "reason": f"destructive command confirmed: {reason}",
            "destructive": True,
            "prefix": prefix,
        }
    if prefix is None:
        return {
            "decision": "block",
            "reason": "command is not on SAFE_PREFIXES",
            "destructive": False,
            "prefix": None,
        }
    return {
        "decision": "allow",
        "reason": f"command matches SAFE_PREFIXES ({prefix})",
        "destructive": False,
        "prefix": prefix,
    }


def bash(command: str, auto_approve: bool = False) -> dict[str, Any]:
    gate = confirm_bash(command, auto_approve=auto_approve)
    if gate["decision"] != "allow" or gate["destructive"]:
        return _err(gate["reason"], gate)
    if any(token in command for token in ("|", ";", "&&", "||", "`", "$(", ">", "<")):
        return _err("bash in this sandbox does not run shell operators", gate)
    if _SANDBOX is None:
        return _err("course sandbox is not set", gate)
    try:
        completed = subprocess.run(
            shlex.split(command),
            cwd=_SANDBOX,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:
        return _err(str(exc), gate)
    return _ok(
        {
            "returncode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
            **gate,
        }
    )
