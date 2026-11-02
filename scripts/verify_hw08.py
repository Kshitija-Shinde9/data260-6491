import json
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))

from kafka_service.config import (  # noqa: E402
    PORT_BASE,
    PREFIX,
    REQUEST_TOPIC,
    RESPONSE_TOPIC,
    SID4,
)

API = f"http://127.0.0.1:{PORT_BASE}"
FLOW_LOG = REPO / "reports" / "hw08" / "logs" / "message_flow.log"
DELIVERABLES = [
    "code/kafka_service/config.py",
    "code/kafka_service/recall_entity.py",
    "code/kafka_service/kafka_io.py",
    "code/kafka_service/kafka_client.py",
    "code/kafka_service/worker.py",
    "code/kafka_service/homework_demo.py",
    "code/kafka_service/Dockerfile",
    "code/kafka_service/docker-compose.yml",
    "code/web_application/kafka_api.py",
    "code/web_application/routers/kafka_recalls.py",
    "scripts/test_hw08_part1.py",
]
FLOW_STAGES = ["HTTP-IN", "SEND", "RECEIVE", "PROCESS", "REPLY", "RESPONSE", "HTTP-OUT"]

checks = []


def record(name, passed, detail=""):
    checks.append({"name": name, "passed": bool(passed), "detail": str(detail)})
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def http_json(method, path, body=None, correlation_id=None):
    headers = {"Content-Type": "application/json"}
    if correlation_id:
        headers["X-Correlation-ID"] = correlation_id
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(API + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def commit_hash():
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return "not a git checkout"


def check_deliverables():
    for relative in DELIVERABLES:
        record(f"deliverable present: {relative}", (REPO / relative).is_file())


def check_offline_tests():
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "test_hw08_part1.py")],
        capture_output=True,
        text=True,
    )
    summary = [line for line in result.stdout.splitlines() if "tests passed" in line]
    record("offline worker/API tests pass", result.returncode == 0, summary[-1] if summary else "")


def check_containers():
    try:
        output = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, check=True
        ).stdout.split()
    except Exception as exc:
        record("docker ps lists kafka, worker, api", False, exc)
        return
    for name in ("s6491_kafka", "s6491_worker", "s6491_api"):
        record(f"container running: {name}", name in output)
    logs = subprocess.run(["docker", "logs", "s6491_worker"], capture_output=True, text=True)
    record(
        'worker log says "Consumer is ready and listening..."',
        "Consumer is ready and listening..." in logs.stdout + logs.stderr,
    )
    logs = subprocess.run(["docker", "logs", "s6491_api"], capture_output=True, text=True)
    record(
        f"API log says server started at http://127.0.0.1:{PORT_BASE}",
        f"FastAPI server started at http://127.0.0.1:{PORT_BASE}" in logs.stdout + logs.stderr,
    )


def check_live_flow():
    try:
        status, health = http_json("GET", "/api/kafka/health")
        record("API wrapper responds on PORT_BASE", status == 200, f"{API} -> {health}")
    except Exception as exc:
        record("API wrapper responds on PORT_BASE", False, exc)
        return

    correlation_id = str(uuid.uuid4())
    recall = {
        "product_name": "Safeway Signature Rotisserie Chicken",
        "supplier": "Safeway Deli",
        "recall_code": f"REC-{int(time.time()) % 10000:04d}",
        "recall_type": "Spoiled or Quality Issue",
        "description": "Served lukewarm from the hot case and the pack date was two days old.",
        "affected_units": 40,
    }
    status, created = http_json("POST", "/api/kafka/recalls", recall, correlation_id)
    record("CREATE_RECALL succeeds", status == 201 and created.get("success"), created)
    record("CREATE_RECALL echoes correlation_id", created.get("correlation_id") == correlation_id)
    recall_id = created.get("recall_id", "")
    try:
        uuid.UUID(recall_id)
        record("worker generated a UUID recall_id", True, recall_id)
    except ValueError:
        record("worker generated a UUID recall_id", False, recall_id)

    status, fetched = http_json("GET", f"/api/kafka/recalls/{recall_id}", None, correlation_id)
    record(
        "GET_RECALL returns the created recall",
        status == 200 and (fetched.get("recall") or {}).get("recall_id") == recall_id,
    )
    record("GET_RECALL echoes correlation_id", fetched.get("correlation_id") == correlation_id)

    error_corr = str(uuid.uuid4())
    status, missing = http_json("GET", "/api/kafka/recalls/no-such-id", None, error_corr)
    record(
        "GET_RECALL unknown id -> Recall not found",
        status == 404 and missing.get("error") == "Recall not found",
    )
    record("error response keeps correlation_id", missing.get("correlation_id") == error_corr)
    status, unknown = http_json("POST", "/api/kafka/requests", {"operation": "X", "data": {}})
    record("unknown operation -> Unknown operation", unknown.get("error") == "Unknown operation")
    status, invalid = http_json("POST", "/api/kafka/recalls", {"product_name": ""})
    record("invalid CREATE_RECALL data is rejected", status == 400 and not invalid.get("success"))

    time.sleep(0.5)
    lines = (
        [line for line in FLOW_LOG.read_text().splitlines() if correlation_id in line]
        if FLOW_LOG.exists()
        else []
    )
    for operation in ("CREATE_RECALL", "GET_RECALL"):
        stages = [line.split(" | ")[2].strip() for line in lines if f"op={operation}" in line]
        record(
            f"flow log has {operation} {' -> '.join(FLOW_STAGES)} in order",
            stages == FLOW_STAGES,
            " -> ".join(stages),
        )


def main() -> int:
    print(f"HW8 Part 1 self-check - SID4 {SID4}, PREFIX {PREFIX}, PORT_BASE {PORT_BASE}\n")
    check_deliverables()
    check_offline_tests()
    check_containers()
    check_live_flow()
    passed = sum(check["passed"] for check in checks)
    output = {
        "homework": "HW8",
        "homework_number": 8,
        "part": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sid4": SID4,
        "port_base": PORT_BASE,
        "prefix": PREFIX,
        "request_topic": REQUEST_TOPIC,
        "response_topic": RESPONSE_TOPIC,
        "hardware": platform.platform(),
        "commit_hash": commit_hash(),
        "total_checks": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
        "checks": checks,
    }
    target = REPO / "reports" / "hw08" / "verification.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(output, indent=2) + "\n")
    print(f"\n{passed}/{len(checks)} checks passed. Written to {target.relative_to(REPO)}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
