import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

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


def span_log_path() -> Path:
    configured = os.environ.get("SPAN_LOG_PATH", "")
    if configured:
        return Path(configured)
    root = Path(__file__).resolve().parents[2]
    return root / "reports" / "hw10" / "logs" / "part4_spans.jsonl"


def write_span(
    trace_id: str,
    stage: str,
    start: datetime,
    end: datetime,
    status: str,
    error: str = "",
    cache: str | None = None,
    detail: str = "",
) -> dict:
    """One JSON span. trace_id is the HW8 correlation_id, not a second id."""
    payload = {
        "trace_id": trace_id,
        "stage": stage,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "status": status,
        "error": error or "",
    }
    if cache in {"hit", "miss"}:
        payload["cache"] = cache
    if detail:
        payload["detail"] = detail
    path = span_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _file_lock, path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")
    return payload


def saved_flow_logs(repo_root: str | Path) -> list[Path]:
    """Logs already written by this service, plus any later span log under reports/hw10."""
    root = Path(repo_root)
    logs = sorted((root / "reports" / "hw08" / "logs").glob("*.log"))
    later = root / "reports" / "hw10" / "logs"
    if later.is_dir():
        logs.extend(sorted(later.glob("*.log")))
        logs.extend(sorted(later.glob("*.jsonl")))
    active = _flow_log_path()
    if active:
        current = Path(active)
        if current.is_file() and current not in logs:
            logs.append(current)
    return logs
