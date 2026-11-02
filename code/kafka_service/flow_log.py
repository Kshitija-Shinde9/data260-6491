import json
import os
import threading
from datetime import datetime, timezone

from kafka_service.config import FLOW_LOG_PATH

_file_lock = threading.Lock()


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def log_flow(component: str, stage: str, detail: str, payload: dict | None = None) -> str:
    line = f"{_timestamp()} | {component:<6} | {stage:<8} | {detail}"
    if payload is not None:
        line += " | " + json.dumps(payload, sort_keys=False)
    print(line, flush=True)
    if FLOW_LOG_PATH:
        os.makedirs(os.path.dirname(FLOW_LOG_PATH) or ".", exist_ok=True)
        with _file_lock, open(FLOW_LOG_PATH, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return line


def read_flow_lines(correlation_id: str) -> list[str]:
    if not FLOW_LOG_PATH or not os.path.exists(FLOW_LOG_PATH):
        return []
    with open(FLOW_LOG_PATH, encoding="utf-8") as handle:
        return [line.rstrip("\n") for line in handle if correlation_id in line]
