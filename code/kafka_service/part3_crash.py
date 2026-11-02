import os
import subprocess
import sys
import threading
import time
from pathlib import Path

_SERVICE = Path(__file__).resolve().parent
_CODE = _SERVICE.parent
sys.path.insert(0, str(_CODE))
os.environ["SHORT_LOG"] = "1"
os.environ["FLOW_LOG_PATH"] = str(_CODE.parent / "reports" / "hw08" / "logs" / "part3_crash.log")


def _reader(proc, bucket: list[str]) -> None:
    if proc.stdout is None:
        return
    for line in proc.stdout:
        print(line, end="", flush=True)
        bucket.append(line)


def start_writer(extra: dict) -> tuple[subprocess.Popen, list[str]]:
    env = os.environ.copy()
    env.update(extra)
    env["PYTHONUNBUFFERED"] = "1"
    env["SHORT_LOG"] = "1"
    env["FLOW_LOG_PATH"] = os.environ["FLOW_LOG_PATH"]
    proc = subprocess.Popen(
        [sys.executable, "writer.py"],
        cwd=_SERVICE,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    lines: list[str] = []
    threading.Thread(target=_reader, args=(proc, lines), daemon=True).start()
    return proc, lines


def wait_for(lines: list[str], needle: str, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if any(needle in line for line in lines):
            return True
        time.sleep(0.2)
    return False


def stop_quietly(proc: subprocess.Popen) -> None:
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def run_phase(
    title: str, correlation_id: str, group_id: str, crash_env: dict, expect_redelivery: bool
) -> None:
    from part3_common import publish, recreate_topic

    from kafka_service.config import CRASH_TOPIC, DRAFTS_TOPIC

    print(f"\n{title}", flush=True)
    print(f"correlation_id = {correlation_id}", flush=True)
    recreate_topic(CRASH_TOPIC, partitions=1)
    message = {
        "correlation_id": correlation_id,
        "question": "A bag of blueberries has a torn seal. What should the shopper do?",
        "plan": [
            "Name the product the shopper is asking about.",
            "Call this a packaging / seal failure.",
            "Tell the shopper not to eat it and to take it back to the store.",
        ],
    }
    base = {
        "WRITER_SOURCE": CRASH_TOPIC,
        "WRITER_TARGET": DRAFTS_TOPIC,
        "WRITER_GROUP": group_id,
        "OFFSET_RESET": "earliest",
        "CRASH_BEFORE_COMMIT": "1",
    }
    base.update(crash_env)
    print("--- writer starts, then dies mid-message ---", flush=True)
    first, first_lines = start_writer(base)
    if not wait_for(first_lines, "ready and listening", 40):
        stop_quietly(first)
        raise SystemExit("writer did not start")
    time.sleep(2)
    publish(CRASH_TOPIC, message, key=correlation_id, partition=0)
    try:
        code = first.wait(timeout=30)
    except subprocess.TimeoutExpired:
        stop_quietly(first)
        raise SystemExit("writer did not die. The crash flag did not fire.") from None
    if code != 86:
        raise SystemExit(f"writer exited {code}, expected 86")

    print("--- same writer, started again ---", flush=True)
    restarted = {key: value for key, value in base.items() if key != "CRASH_BEFORE_COMMIT"}
    restarted["COMMIT_BEFORE_WORK"] = "0"
    second, second_lines = start_writer(restarted)
    try:
        if expect_redelivery:
            if not wait_for(second_lines, "committed after success", 40):
                raise SystemExit("restart did not finish the message")
            if not any(correlation_id in line and "RECEIVE" in line for line in second_lines):
                raise SystemExit("restart did not receive the same id")
            print(
                "redelivered = yes. The offset was saved only after the draft was sent.", flush=True
            )
        else:
            time.sleep(12)
            if any(correlation_id in line and "RECEIVE" in line for line in second_lines):
                raise SystemExit("the message came back even though the offset was already saved")
            print(
                "redelivered = no. The offset had been saved before the work finished.", flush=True
            )
    finally:
        stop_quietly(second)


def main() -> int:
    from part3_common import broker_is_up

    broker_is_up()
    run_phase(
        "BEFORE FIX  save the offset, then die",
        "crash-before-266491",
        "s6491_part3_crash_before",
        {"COMMIT_BEFORE_WORK": "1"},
        expect_redelivery=False,
    )
    run_phase(
        "AFTER FIX  die before saving the offset",
        "crash-after-266491",
        "s6491_part3_crash_after",
        {"COMMIT_BEFORE_WORK": "0"},
        expect_redelivery=True,
    )
    print("\nBefore: COMMIT, then CRASH, and the restart is quiet.", flush=True)
    print("After: CRASH with no COMMIT, then the restart RECEIVE, SEND, COMMIT.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
