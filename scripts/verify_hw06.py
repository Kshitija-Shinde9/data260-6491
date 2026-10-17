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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SID4 = 6491
PORT_BASE = 8000 + (SID4 % 900)
PREFIX = f"s{SID4}"
SEED = SID4
VERIFY_SEED = 260000 + SID4
DOMAIN_ID = SID4 % 8
BASE = f"http://127.0.0.1:{PORT_BASE}"

checks = []


def check(name, passed, detail=""):
    checks.append({"name": name, "passed": bool(passed), "detail": str(detail)})
    mark = "PASS" if passed else "FAIL"
    suffix = f"  ({detail})" if detail else ""
    print(f"[{mark}] {name}{suffix}")


def git(*args):
    try:
        out = subprocess.run(
            ["git", "-C", ROOT, *args],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def port_open(port):
    with socket.socket() as sock:
        sock.settimeout(1)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def fetch(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(BASE + path, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode(errors="replace")
            parsed = json.loads(raw) if raw else None
            return response.status, parsed
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode(errors="replace")
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = None
        return exc.code, parsed
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return 0, str(exc)


def main():
    listening = port_open(PORT_BASE)
    check("FastAPI responds on PORT_BASE", listening, BASE)
    if not listening:
        check("GET /api/notices returns a list", False, "server is not running")
        check("POST /api/chat /help returns a reply", False, "server is not running")
        check("GET /api/memory/{user_id} returns JSON", False, "server is not running")
        check("invalid notice body is rejected", False, "server is not running")
    else:
        status, body = fetch("/api/notices")
        check(
            "GET /api/notices returns a list",
            status == 200 and isinstance(body, list),
            f"HTTP {status}",
        )

        status, body = fetch(
            "/api/chat",
            "POST",
            {"user_id": "kshitija", "session_id": "sess-6491-verify", "message": "/help"},
        )
        reply = body.get("reply") if isinstance(body, dict) else None
        check(
            "POST /api/chat /help returns a reply",
            status == 200 and isinstance(reply, str) and reply.strip() != "",
            f"HTTP {status}",
        )

        status, body = fetch("/api/memory/kshitija")
        check(
            "GET /api/memory/{user_id} returns JSON",
            status == 200 and isinstance(body, dict),
            f"HTTP {status}",
        )

        status, body = fetch("/api/notices", "POST", {})
        check(
            "invalid notice body is rejected",
            status == 422,
            f"HTTP {status}",
        )

    commit = git("rev-parse", "HEAD") or "not a git repository"
    tag = git("describe", "--tags", "--exact-match", "HEAD") or git("tag", "--points-at", "HEAD")
    if not tag:
        tag = "no tag yet"
    if "\n" in tag:
        tag = tag.splitlines()[0]

    passed = sum(1 for item in checks if item["passed"])
    document = {
        "homework": "HW6",
        "homework_number": 6,
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
            "database": f"MongoDB {PREFIX}_doc",
        },
        "total_checks": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
        "checks": checks,
    }

    out = os.path.join(ROOT, "reports", "hw06", "verification.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as handle:
        json.dump(document, handle, indent=2)
        handle.write("\n")

    print(f"\n{passed}/{len(checks)} checks passed.")
    print("Written to reports/hw06/verification.json")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
