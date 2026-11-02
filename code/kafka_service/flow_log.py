import json
import os
import threading
from datetime import datetime, timezone

_file_lock = threading.Lock()


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _flow_log_path() -> str:
    return os.environ.get("FLOW_LOG_PATH", "")


def log_flow(component: str, stage: str, detail: str, payload: dict | None = None) -> str:
    line = f"{_timestamp()} | {component:<6} | {stage:<8} | {detail}"
    if payload is not None:
        line += " | " + json.dumps(payload, sort_keys=False)
    print(line, flush=True)
    path = _flow_log_path()
    if path:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with _file_lock, open(path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    return line


def read_flow_lines(correlation_id: str) -> list[str]:
    path = _flow_log_path()
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return [line.rstrip("\n") for line in handle if correlation_id in line]
