#!/usr/bin/env python3


from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import warnings

warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "code", "web_application")
MCP_DIR = os.path.join(ROOT, "code", "mcp")

SID4 = 6491
PORT_BASE = 8000 + (SID4 % 900)
PREFIX = f"s{SID4}"
SEED = SID4
VERIFY_SEED = 260000 + SID4
DOMAIN_ID = SID4 % 8
BASE = f"http://127.0.0.1:{PORT_BASE}"
DEMO_EMAIL = "admin@s6491.com"
DEMO_PASSWORD = "Recall@6491"
COOKIE_NAME = "s6491_sid"

checks = []


def check(name, passed, detail=""):
    checks.append({"name": name, "passed": bool(passed), "detail": str(detail)})
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def path(*parts):
    return os.path.join(ROOT, *parts)


def git(*args):
    try:
        out = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, timeout=10)
        return out.stdout.strip()
    except Exception:
        return ""


def port_open(port):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = urllib.request.build_opener(NoRedirect)


def fetch(fetch_path, method="GET", body=None, cookie=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + fetch_path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        r = OPENER.open(req, timeout=15)
        raw = r.read().decode(errors="replace")
        return r.status, r.headers, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = None
        return e.code, e.headers, parsed


def check_deliverables():
    for rel in [
        "code/web_application/models.py",
        "code/web_application/schemas.py",
        "code/web_application/routers/suppliers.py",
        "code/web_application/routers/recalls.py",
        "code/web_application/frontend/src/store/recallsSlice.js",
        "code/mcp/meals_server.py",
        "code/mcp/domain_server.py",
        "code/mcp/execute_tool.py",
        "code/mcp/agent_loop.py",
        "scripts/test_hw05_part4.py",
        "scripts/run_hw05_part3_faults.py",
        "scripts/verify_hw05.py",
        "reports/hw05/AI_USE.md",
        "reports/hw05/METRICS.md",
        "reports/hw05/RUN_LOG.txt",
        "reports/hw05/REFLECTION.md",
    ]:
        check(f"deliverable present: {rel}", os.path.isfile(path(rel)))


def check_mysql_schema():
    env_path = path("code", "web_application", ".env")
    if not os.path.isfile(env_path):
        for t in ("suppliers", "recalls", "users", "sessions"):
            check(f"table exists: {t}", False, "code/web_application/.env missing (gitignored)")
        return
    try:
        sys.path.insert(0, APP_DIR)
        from dotenv import load_dotenv
        from urllib.parse import urlparse, unquote
        import pymysql

        load_dotenv(env_path)
        url = urlparse(os.environ["DATABASE_URL"].replace("mysql+pymysql", "mysql"))
        conn = pymysql.connect(
            host=url.hostname,
            port=url.port or 3306,
            user=url.username,
            password=unquote(url.password or ""),
            database=url.path.lstrip("/"),
        )
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES")
            tables = {row[0] for row in cur.fetchall()}
        conn.close()
        for t in ("suppliers", "recalls", "users", "sessions"):
            check(f"table exists: {t}", t in tables)
    except Exception as error:
        for t in ("suppliers", "recalls", "users", "sessions"):
            check(f"table exists: {t}", False, error)


def check_api_smoke():
    status, _, _ = fetch("/api/recalls")
    check("unauthenticated GET /api/recalls is rejected", status in (401, 403), f"HTTP {status}")

    status, headers, _ = fetch(
        "/api/auth/login",
        "POST",
        {"email": DEMO_EMAIL, "password": DEMO_PASSWORD},
    )
    check("login succeeds on PORT_BASE", status == 200, f"HTTP {status}")
    raw_cookie = headers.get("set-cookie", "") if status == 200 else ""
    token = ""
    if "=" in raw_cookie:
        token = raw_cookie.split(";")[0].split("=", 1)[1]
    cookie = f"{COOKIE_NAME}={token}"

    status, _, suppliers = fetch("/api/suppliers?skip=0&limit=2", cookie=cookie)
    check(
        "GET /api/suppliers paginated returns a list",
        status == 200 and isinstance(suppliers, list),
        f"HTTP {status}, n={len(suppliers) if isinstance(suppliers, list) else 'n/a'}",
    )

    status, _, recalls = fetch("/api/recalls", cookie=cookie)
    check(
        "authenticated GET /api/recalls returns a list",
        status == 200 and isinstance(recalls, list),
        f"HTTP {status}",
    )


def _envelope_ok(payload):
    return (
        isinstance(payload, dict)
        and "ok" in payload
        and "data" in payload
        and "error" in payload
    )


def check_mcp_tool_smoke():
    sys.path.insert(0, MCP_DIR)

    try:
        import httpx
        import meals_server

        _orig_client = httpx.Client

        class _SmokeClient(_orig_client):
            def __init__(self, *args, **kwargs):
                kwargs.setdefault("verify", False)
                super().__init__(*args, **kwargs)

        httpx.Client = _SmokeClient
        try:
            raised = False
            try:
                meals_server.search_meals_by_name("Arrabiata", limit=0)
            except ValueError:
                raised = True
            check("meals MCP rejects invalid limit", raised)

            result = meals_server.search_meals_by_name("Arrabiata", limit=3)
            ok = (
                isinstance(result, list)
                and len(result) >= 1
                and isinstance(result[0], dict)
                and "id" in result[0]
                and "name" in result[0]
            )
            check("meals MCP tool responds to search_meals_by_name", ok, f"n={len(result) if isinstance(result, list) else 'n/a'}")
        finally:
            httpx.Client = _orig_client
    except Exception as error:
        check("meals MCP rejects invalid limit", False, error)
        check("meals MCP tool responds to search_meals_by_name", False, error)

    try:
        import domain_server

        ok_env = callable(getattr(domain_server, "envelope", None))
        sample = domain_server.envelope(ok=True, data={"count": 0, "items": []}, error=None)
        check(
            "domain MCP envelope helper returns {ok,data,error}",
            ok_env and _envelope_ok(sample) and sample["ok"] is True,
            "envelope shape",
        )

        env_path = path("code", "web_application", ".env")
        if os.path.isfile(env_path):
            tool_result = domain_server.search_recalls("a", limit=3)
            check(
                "domain MCP tool search_recalls returns envelope",
                _envelope_ok(tool_result) and isinstance(tool_result.get("ok"), bool),
                f"ok={tool_result.get('ok')}",
            )
        else:
            check(
                "domain MCP tool search_recalls returns envelope",
                False,
                "skipped: code/web_application/.env missing",
            )
    except Exception as error:
        check("domain MCP envelope helper returns {ok,data,error}", False, error)
        check("domain MCP tool search_recalls returns envelope", False, error)

    try:
        from execute_tool import SAFETY_ERROR, execute_tool

        allowed = json.loads(
            execute_tool(
                "search_recalls",
                {"query": "Blueberries", "limit": 5},
                backends={
                    "search_recalls": lambda query, limit: {
                        "ok": True,
                        "data": {"count": 1, "items": [{"id": 1, "product_name": query}]},
                        "error": None,
                    },
                    "get_recall_detail": lambda recall_id: {"ok": True, "data": {"id": recall_id}, "error": None},
                    "aggregate_recalls_by_supplier": lambda min_units: {
                        "ok": True,
                        "data": {"count": 0, "items": []},
                        "error": None,
                    },
                },
            )
        )
        blocked = json.loads(
            execute_tool(
                "search_recalls",
                {"query": "rohan1@gmail.com"},
                backends={
                    "search_recalls": lambda query, limit: {
                        "ok": True,
                        "data": {"count": 0, "items": []},
                        "error": None,
                    },
                    "get_recall_detail": lambda recall_id: {"ok": False, "data": None, "error": "x"},
                    "aggregate_recalls_by_supplier": lambda min_units: {
                        "ok": True,
                        "data": {"count": 0, "items": []},
                        "error": None,
                    },
                },
            )
        )
        check(
            "execute_tool returns JSON envelope on allowed call",
            _envelope_ok(allowed) and allowed.get("ok") is True,
        )
        check(
            "execute_tool safety rule blocks email lookup",
            _envelope_ok(blocked) and blocked.get("ok") is False and blocked.get("error") == SAFETY_ERROR,
            blocked.get("error"),
        )
    except Exception as error:
        check("execute_tool returns JSON envelope on allowed call", False, error)
        check("execute_tool safety rule blocks email lookup", False, error)


def check_offline_tests():
    python = sys.executable
    try:
        out = subprocess.run(
            [python, path("scripts", "test_hw05_part4.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        text = (out.stdout or "") + (out.stderr or "")
        check(
            "offline Part4/Part5 test runner finishes with all tests passed",
            out.returncode == 0 and "tests passed" in text,
            text.strip().splitlines()[-1] if text.strip() else f"exit {out.returncode}",
        )
    except Exception as error:
        check("offline Part4/Part5 test runner finishes with all tests passed", False, error)


def main():
    print(f"HW5 self-check - SID4 {SID4}, PORT_BASE {PORT_BASE}, VERIFY_SEED {VERIFY_SEED}\n")
    check_deliverables()
    print()
    check_mysql_schema()
    print()
    check_mcp_tool_smoke()
    print()
    check_offline_tests()
    print()

    started_here = False
    server = None
    python = sys.executable
    if not port_open(PORT_BASE):
        server = subprocess.Popen(
            [python, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(PORT_BASE)],
            cwd=APP_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        started_here = True
        for _ in range(40):
            if port_open(PORT_BASE):
                break
            time.sleep(0.5)
        check("FastAPI backend responds on PORT_BASE", port_open(PORT_BASE), BASE)
    else:
        check("FastAPI backend responds on PORT_BASE", True, f"already running at {BASE}")

    try:
        if port_open(PORT_BASE):
            check_api_smoke()
        else:
            check("login succeeds on PORT_BASE", False, "server not up")
            check("GET /api/suppliers paginated returns a list", False, "server not up")
            check("authenticated GET /api/recalls returns a list", False, "server not up")
            check("unauthenticated GET /api/recalls is rejected", False, "server not up")
    finally:
        if started_here and server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
            print("\ntest server stopped.")

    commit = git("rev-parse", "HEAD") or "not a git repository"
    tag = (
        git("describe", "--tags", "--exact-match", "HEAD")
        or git("tag", "--points-at", "HEAD")
        or "no tag (create tag hw5 after commit)"
    )
    if "\n" in tag:
        tag = tag.splitlines()[0]

    passed = sum(1 for c in checks if c["passed"])
    doc = {
        "homework": "HW5",
        "homework_number": 5,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sid4": SID4,
        "port_base": PORT_BASE,
        "prefix": PREFIX,
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "domain_id": DOMAIN_ID,
        "domain": "Grocery supply and recall notices",
        "commit_hash": commit,
        "tag": tag,
        "model_configuration": {
            "local_model": "qwen3:8b via Ollama",
            "agent": "code/mcp/agent_loop.py run_agent + execute_tool",
            "database": f"MySQL {PREFIX}_rel",
        },
        "total_checks": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
        "checks": checks,
    }

    out = path("reports", "hw05", "verification.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(doc, f, indent=2)

    print(f"\n{passed}/{len(checks)} checks passed.")
    print("Written to reports/hw05/verification.json")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
