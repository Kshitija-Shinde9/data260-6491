
from __future__ import annotations

import logging
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

log = logging.getLogger("s6491_rel.resilient")
if not log.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [resilient] %(message)s"))
    log.addHandler(_handler)
    log.setLevel(logging.INFO)
    log.propagate = False

T = TypeVar("T")

MAX_ATTEMPTS = 3
TIMEOUT_SEC = 2.0
BASE_BACKOFF_SEC = 0.05
BACKOFF_CAP_SEC = 0.8
VERIFY_SEED = 266491


class SimulatedFailure(RuntimeError):
    pass


class StorageTimeout(RuntimeError):
    pass


@dataclass
class AttemptTrace:
    attempt: int
    injected_failure: bool
    error: str | None
    latency_ms: float


@dataclass
class CallResult:
    ok: bool
    data: Any
    error: str | None
    attempts: int
    latency_ms: float
    trace: list[AttemptTrace]


def _backoff_seconds(attempt_index: int) -> float:
    delay = BASE_BACKOFF_SEC * (2**attempt_index)
    return min(delay, BACKOFF_CAP_SEC)


def run_with_timeout(fn: Callable[[], T], timeout_sec: float = TIMEOUT_SEC) -> T:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(fn)
        try:
            return future.result(timeout=timeout_sec)
        except FuturesTimeout as exc:
            raise StorageTimeout(f"operation timed out after {timeout_sec:.2f}s") from exc


def call_with_retry(
    operation: Callable[[], T],
    *,
    rng: random.Random | None = None,
    failure_rate: float = 0.0,
    max_attempts: int = MAX_ATTEMPTS,
    timeout_sec: float = TIMEOUT_SEC,
    force_mode: str | None = None,
) -> CallResult:
    if rng is None:
        rng = random.Random(VERIFY_SEED)

    started = time.perf_counter()
    traces: list[AttemptTrace] = []
    last_error: str | None = None

    for attempt in range(1, max_attempts + 1):
        attempt_started = time.perf_counter()
        injected = False

        if force_mode == "success_first":
            injected = False
        elif force_mode == "fail_then_success":
            injected = attempt == 1
        elif force_mode == "fail_all":
            injected = True
        elif failure_rate > 0:
            injected = rng.random() < failure_rate

        if injected:
            last_error = f"simulated storage failure on attempt {attempt}"
            traces.append(
                AttemptTrace(
                    attempt=attempt,
                    injected_failure=True,
                    error=last_error,
                    latency_ms=(time.perf_counter() - attempt_started) * 1000,
                )
            )
            log.warning("%s", last_error)
            if attempt < max_attempts:
                time.sleep(_backoff_seconds(attempt - 1))
            continue

        try:
            data = run_with_timeout(operation, timeout_sec=timeout_sec)
            traces.append(
                AttemptTrace(
                    attempt=attempt,
                    injected_failure=False,
                    error=None,
                    latency_ms=(time.perf_counter() - attempt_started) * 1000,
                )
            )
            return CallResult(
                ok=True,
                data=data,
                error=None,
                attempts=attempt,
                latency_ms=(time.perf_counter() - started) * 1000,
                trace=traces,
            )
        except Exception as exc:
            last_error = str(exc)
            traces.append(
                AttemptTrace(
                    attempt=attempt,
                    injected_failure=False,
                    error=last_error,
                    latency_ms=(time.perf_counter() - attempt_started) * 1000,
                )
            )
            log.error("attempt %s failed: %s", attempt, last_error)
            if attempt < max_attempts:
                time.sleep(_backoff_seconds(attempt - 1))

    return CallResult(
        ok=False,
        data=None,
        error=last_error or "unknown storage failure",
        attempts=max_attempts,
        latency_ms=(time.perf_counter() - started) * 1000,
        trace=traces,
    )


def make_experiment_rng(failure_rate: float, call_index: int) -> random.Random:
    rate_key = int(round(failure_rate * 1000))
    seed = VERIFY_SEED + rate_key * 10_000 + call_index
    return random.Random(seed)
