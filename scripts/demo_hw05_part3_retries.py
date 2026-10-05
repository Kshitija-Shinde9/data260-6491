#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "code", "mcp"))

from resilient_storage import call_with_retry  # noqa: E402


def fake_storage():
    return {"demo": "ok", "source": "fake_storage"}


def show(label: str, force_mode: str):
    print("\n===", label, "===")
    result = call_with_retry(fake_storage, failure_rate=0.0, force_mode=force_mode)
    payload = {
        "ok": result.ok,
        "data": result.data,
        "error": result.error,
        "attempts": result.attempts,
        "latency_ms": round(result.latency_ms, 2),
        "trace": [
            {
                "attempt": t.attempt,
                "injected_failure": t.injected_failure,
                "error": t.error,
            }
            for t in result.trace
        ],
    }
    print(json.dumps(payload, indent=2))


def main():
    show("Success on first attempt", "success_first")
    show("Fail on first attempt, success after retry", "fail_then_success")
    show("Fail after all retries — clean error", "fail_all")


if __name__ == "__main__":
    main()
