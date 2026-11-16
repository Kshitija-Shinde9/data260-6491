"""Turn the lines written by kafka_service.flow_log into dashboard requests.

trace_id is the correlation_id those lines already carry. A correlation_id reused
for a later operation stays that same id and is shown as separate segments.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from kafka_service.flow_log import saved_flow_logs

STAGE_ORDER = (
    "cache_lookup",
    "inbox",
    "client",
    "planner",
    "writer",
    "reviewer",
    "worker",
    "queue_wait",
    "response",
    "final",
    "evaluation",
)
TERMINAL_STAGES = {"RESPONSE", "HTTP-OUT", "FINAL", "DEAD", "CRASH"}
START_STAGES = {"SEND", "HTTP-IN"}
FAILURE_STAGES = {"CRASH", "DEAD", "DROP"}

_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T[\d:.]+Z)"
    r"\s+\|\s+(?P<component>\S+)"
    r"\s+\|\s+(?P<stage>\S+)"
    r"\s+\|\s+(?P<rest>.*)$"
)
_CORR_RE = re.compile(r"corr=(\S+)")
_OP_RE = re.compile(r"op=(\S+)")
_HTTP_RE = re.compile(r"status=(\d{3})")
_PART2_RE = re.compile(
    r"(\d+) queries, (\d+) hits, (\d+) misses, hit rate ([0-9.]+)%\s+"
    r"average cached latency ([0-9.]+) ms\s+"
    r"average non-cached latency ([0-9.]+) ms"
)

EVAL_FILENAME = "part2_evaluation.json"
JUDGE_FILENAME = "part3_judge_validation.json"


def repo_root_from_here() -> Path:
    return Path(__file__).resolve().parents[2]


def parse_timestamp(value: str) -> datetime:
    text = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


@dataclass
class FlowEvent:
    ts: datetime
    component: str
    raw_stage: str
    detail: str
    payload: dict | None
    correlation_id: str
    source: str
    end_ts: datetime | None = None
    cache: str | None = None
    span_status: str | None = None
    span_error: str | None = None
    explicit_stage: str | None = None

    @property
    def pipeline_stage(self) -> str:
        if self.explicit_stage:
            return self.explicit_stage
        detail = self.detail.lower()
        component = self.component.upper()
        if self.cache or "cache hit" in detail or "cache miss" in detail or component == "CACHE":
            return "cache_lookup"
        if component == "PLANNER":
            return "planner"
        if component == "WRITER":
            return "writer"
        if component == "REVIEWER":
            return "reviewer"
        if component == "WORKER":
            return "worker"
        if self.raw_stage == "FINAL":
            return "final"
        if self.raw_stage in {"RESPONSE", "HTTP-OUT"}:
            return "response"
        if component in {"YOU", "CLIENT", "API"} and self.raw_stage in START_STAGES:
            return "inbox"
        if component in {"CLIENT", "API", "YOU"}:
            return "client"
        return component.lower() or "unknown"


@dataclass
class StageSpan:
    stage: str
    start: datetime
    end: datetime
    status: str
    error: str
    event_count: int

    @property
    def duration_ms(self) -> float:
        return round((self.end - self.start).total_seconds() * 1000, 1)

    def as_dict(self) -> dict:
        return {
            "stage": self.stage,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
        }


@dataclass
class RequestRecord:
    trace_id: str
    segment: int
    events: list[FlowEvent] = field(default_factory=list)

    @property
    def started(self) -> datetime:
        return self.events[0].ts

    @property
    def ended(self) -> datetime:
        return max(event.end_ts or event.ts for event in self.events)

    @property
    def duration_ms(self) -> float:
        return round((self.ended - self.started).total_seconds() * 1000, 1)

    @property
    def source(self) -> str:
        return self.events[0].source

    @property
    def operation(self) -> str:
        for event in self.events:
            match = _OP_RE.search(event.detail)
            if match:
                return match.group(1)
            if event.payload and event.payload.get("operation"):
                return str(event.payload["operation"])
        for event in self.events:
            if event.payload and event.payload.get("question"):
                return "QUESTION"
        return ""

    @property
    def question(self) -> str:
        for event in self.events:
            if event.payload and event.payload.get("question"):
                return str(event.payload["question"])
        return ""

    @property
    def cache_path(self) -> str:
        declared = [event.cache for event in self.events if event.cache in {"hit", "miss"}]
        if "hit" in declared:
            return "hit"
        if "miss" in declared:
            return "miss"
        text = " ".join(event.detail.lower() for event in self.events)
        if "cache hit" in text or "is_cached=true" in text or "cache=hit" in text:
            return "hit"
        if "cache miss" in text or "is_cached=false" in text or "cache=miss" in text:
            return "miss"
        return "not_recorded"

    @property
    def stages(self) -> list[StageSpan]:
        grouped: dict[str, list[FlowEvent]] = {}
        for event in self.events:
            grouped.setdefault(event.pipeline_stage, []).append(event)
        spans = [_span_for(name, grouped[name]) for name in grouped]
        spans.sort(key=lambda span: (_order_index(span.stage), span.start))
        return spans

    @property
    def error(self) -> str:
        messages: list[str] = []
        for event in self.events:
            if event.raw_stage == "RETRY" and "poison" in event.detail.lower():
                _append_unique(messages, "poison message")
            if event.span_error:
                _append_unique(messages, event.span_error)
            payload_error = _payload_error(event)
            if payload_error:
                _append_unique(messages, payload_error)
            other = _event_error(event)
            if other:
                _append_unique(messages, other)
        specific = [message for message in messages if message != "success=false"]
        if specific:
            return specific[0]
        return messages[0] if messages else ""

    @property
    def status(self) -> str:
        if self.error or any(span.status == "error" for span in self.stages):
            return "error"
        return "ok"

    def as_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "segment": self.segment,
            "started": self.started.isoformat(),
            "ended": self.ended.isoformat(),
            "duration_ms": self.duration_ms,
            "operation": self.operation,
            "status": self.status,
            "error": self.error,
            "cache_path": self.cache_path,
            "source": self.source,
            "question": self.question,
        }


def _order_index(stage: str) -> int:
    try:
        return STAGE_ORDER.index(stage)
    except ValueError:
        return len(STAGE_ORDER)


def _append_unique(messages: list[str], text: str) -> None:
    cleaned = text.strip()
    if cleaned and cleaned not in messages:
        messages.append(cleaned)


def _payload_error(event: FlowEvent) -> str:
    if not event.payload:
        return ""
    error = event.payload.get("error")
    if isinstance(error, str) and error.strip():
        return error.strip()
    return ""


def _event_error(event: FlowEvent) -> str:
    if event.span_status == "error" and event.span_error:
        return event.span_error
    if event.raw_stage in FAILURE_STAGES:
        return event.detail
    if event.payload and event.payload.get("success") is False:
        return "success=false"
    if "success=False" in event.detail or "success=false" in event.detail:
        return "success=false"
    match = _HTTP_RE.search(event.detail)
    if match and int(match.group(1)) >= 400:
        return f"HTTP {match.group(1)}"
    return ""


def _span_for(name: str, events: list[FlowEvent]) -> StageSpan:
    start = min(event.ts for event in events)
    end = max(event.end_ts or event.ts for event in events)
    error = ""
    for event in events:
        if _payload_error(event):
            error = _payload_error(event)
            break
    if not error:
        for event in events:
            if event.span_error:
                error = event.span_error
                break
    if not error:
        for event in events:
            other = _event_error(event)
            if other and other != "success=false":
                error = other
                break
    if not error:
        for event in events:
            other = _event_error(event)
            if other:
                error = other
                break
    status = "error" if error or any(event.span_status == "error" for event in events) else "ok"
    return StageSpan(name, start, end, status, error, len(events))


def _split_payload(rest: str) -> tuple[str, dict | None]:
    marker = " | {"
    if marker not in rest:
        return rest, None
    detail, raw = rest.split(marker, 1)
    try:
        payload = json.loads("{" + raw)
    except json.JSONDecodeError:
        return rest, None
    return detail, payload if isinstance(payload, dict) else None


def parse_flow_line(line: str, source: str) -> FlowEvent | None:
    match = _LINE_RE.match(line.rstrip("\n"))
    if not match:
        return None
    detail, payload = _split_payload(match.group("rest").strip())
    correlation = ""
    found = _CORR_RE.search(detail)
    if found:
        correlation = found.group(1)
    elif payload and payload.get("correlation_id"):
        correlation = str(payload["correlation_id"])
    if not correlation:
        return None
    return FlowEvent(
        ts=parse_timestamp(match.group("ts")),
        component=match.group("component").strip(),
        raw_stage=match.group("stage").strip(),
        detail=detail,
        payload=payload,
        correlation_id=correlation,
        source=source,
    )


def parse_span_object(payload: dict, source: str) -> FlowEvent | None:
    trace_id = payload.get("trace_id") or payload.get("correlation_id")
    if not trace_id or not payload.get("start"):
        return None
    start = parse_timestamp(str(payload["start"]))
    end = parse_timestamp(str(payload["end"])) if payload.get("end") else start
    cache = payload.get("cache")
    if cache not in {"hit", "miss", None}:
        cache = None
    error = payload.get("error")
    return FlowEvent(
        ts=start,
        end_ts=end,
        component=str(payload.get("stage") or "SPAN"),
        raw_stage=str(payload.get("stage") or "SPAN"),
        detail=str(payload.get("detail") or ""),
        payload=payload,
        correlation_id=str(trace_id),
        source=source,
        cache=cache,
        span_status=str(payload["status"]) if payload.get("status") else None,
        span_error=str(error) if error else None,
        explicit_stage=str(payload.get("stage") or ""),
    )


def list_log_files(root: Path) -> list[Path]:
    return saved_flow_logs(root)


def source_signature(root: Path) -> str:
    parts = []
    for path in list_log_files(root):
        stat = path.stat()
        parts.append(f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}")
    for relative in (
        "reports/hw09/RUN_LOG.txt",
        "reports/hw09/part3_results.json",
        f"reports/hw10/{EVAL_FILENAME}",
        f"reports/hw10/{JUDGE_FILENAME}",
        "reports/hw10/part4_latency.json",
    ):
        path = root / relative
        if path.is_file():
            stat = path.stat()
            parts.append(f"{relative}:{stat.st_mtime_ns}:{stat.st_size}")
    return "|".join(parts)


def load_events(root: Path) -> list[FlowEvent]:
    events: list[FlowEvent] = []
    for path in list_log_files(root):
        source = path.name
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix == ".jsonl":
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    continue
                if isinstance(payload, dict):
                    event = parse_span_object(payload, source)
                    if event is not None:
                        events.append(event)
            continue
        for line in text.splitlines():
            event = parse_flow_line(line, source)
            if event is not None:
                events.append(event)
    events.sort(key=lambda event: (event.correlation_id, event.ts))
    return events


def split_correlation(events: list[FlowEvent]) -> list[list[FlowEvent]]:
    """Split a reused correlation_id when a new send starts after a finished operation."""
    segments: list[list[FlowEvent]] = []
    current: list[FlowEvent] = []
    closed = False
    for event in events:
        if (
            closed
            and event.raw_stage in START_STAGES
            and event.pipeline_stage in {"inbox", "client"}
        ):
            segments.append(current)
            current = []
            closed = False
        current.append(event)
        if event.raw_stage in TERMINAL_STAGES:
            closed = True
    if current:
        segments.append(current)
    return segments


def build_requests(events: list[FlowEvent], source: str | None = None) -> list[RequestRecord]:
    chosen = (
        events
        if not source or source == "All captured logs"
        else [event for event in events if event.source == source]
    )
    by_id: dict[str, list[FlowEvent]] = {}
    for event in chosen:
        by_id.setdefault(event.correlation_id, []).append(event)
    records: list[RequestRecord] = []
    for trace_id, grouped in by_id.items():
        grouped.sort(key=lambda event: event.ts)
        for index, segment in enumerate(split_correlation(grouped), start=1):
            records.append(RequestRecord(trace_id, index, segment))
    records.sort(key=lambda record: record.started, reverse=True)
    return records


def summarize_requests(records: list[RequestRecord]) -> dict:
    if not records:
        return {
            "request_count": 0,
            "error_count": 0,
            "error_rate": 0.0,
            "mean_e2e_ms": None,
            "latency_sample_count": 0,
            "window_start": None,
            "window_end": None,
            "sources": [],
        }
    errors = [record for record in records if record.status == "error"]
    timed = [record.duration_ms for record in records if record.duration_ms > 0]
    started = min(record.started for record in records)
    ended = max(record.ended for record in records)
    mean = round(sum(timed) / len(timed), 1) if timed else None
    return {
        "request_count": len(records),
        "error_count": len(errors),
        "error_rate": round(len(errors) / len(records), 4),
        "mean_e2e_ms": mean,
        "latency_sample_count": len(timed),
        "window_start": started.isoformat(),
        "window_end": ended.isoformat(),
        "sources": sorted({record.source for record in records}),
    }


def parse_cache_part2(run_log: Path) -> dict | None:
    if not run_log.is_file():
        return None
    text = run_log.read_text(encoding="utf-8", errors="replace")
    match = _PART2_RE.search(text)
    if not match:
        return None
    queries, hits, misses, hit_rate, hit_ms, miss_ms = match.groups()
    note = ""
    if "Strawberry question: hit on the blueberry answer" in text:
        note = (
            "The hit count includes the strawberry question, which returned the cached "
            "blueberry answer. RUN_LOG.txt records that false hit at similarity 0.9292."
        )
    return {
        "queries": int(queries),
        "hits": int(hits),
        "misses": int(misses),
        "hit_rate": float(hit_rate),
        "mean_hit_ms": float(hit_ms),
        "mean_miss_ms": float(miss_ms),
        "source": "reports/hw09/RUN_LOG.txt",
        "window": "HW9 Part 2 run on 2026-11-09 (12 questions, threshold 0.85)",
        "note": note,
    }


def parse_cache_part3(path: Path) -> dict | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    shipped = float(data.get("ship_threshold", 0))
    chosen = None
    for row in data.get("thresholds", []):
        if float(row.get("threshold", -1)) == shipped:
            chosen = row
            break
    if chosen is None:
        return None
    return {
        "threshold": shipped,
        "hit_rate": chosen.get("hit_rate"),
        "false_hit_rate": chosen.get("false_hit_rate"),
        "correct_hits": chosen.get("correct_hits"),
        "false_hits": chosen.get("false_hits"),
        "misses": chosen.get("misses"),
        "mean_latency_ms": chosen.get("mean_latency_ms"),
        "source": "reports/hw09/part3_results.json",
        "window": "HW9 Part 3 threshold sweep on 2026-11-09 (40 labeled cases)",
    }


def load_optional_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def load_part4(path: Path) -> dict | None:
    document = load_optional_json(path)
    if not document or not document.get("stages"):
        return None
    return document


def _case_number(case: dict, *names: str) -> float | None:
    for name in names:
        if name in case and case[name] is not None and case[name] != "":
            try:
                return float(case[name])
            except (TypeError, ValueError):
                return None
    return None


def evaluation_cases(document: dict | None) -> list[dict]:
    if not document:
        return []
    raw_cases = document.get("cases") or document.get("results") or []
    rows = []
    for case in raw_cases:
        if not isinstance(case, dict):
            continue
        draft = _case_number(case, "draft_score", "writer_helpfulness")
        final = _case_number(case, "final_score", "final_answer_helpfulness")
        difference = _case_number(case, "improvement", "final_minus_draft")
        if difference is None and draft is not None and final is not None:
            difference = round(final - draft, 2)
        rows.append(
            {
                "case_id": case.get("case_id") or case.get("id") or "",
                "trace_id": case.get("trace_id") or case.get("correlation_id") or "",
                "plan_quality": _case_number(case, "plan_quality"),
                "plan_reason": case.get("plan_reason") or case.get("plan_quality_reason") or "",
                "writer_helpfulness": _case_number(case, "writer_helpfulness", "draft_score"),
                "final_answer_helpfulness": _case_number(
                    case, "final_answer_helpfulness", "final_score"
                ),
                "improvement": difference,
                "final_answer": case.get("final_answer") or "",
            }
        )
    return rows


def stage_means(cases: list[dict]) -> dict:
    def mean(name: str) -> float | None:
        values = [case[name] for case in cases if isinstance(case.get(name), (int, float))]
        if not values:
            return None
        return round(sum(values) / len(values), 2)

    return {
        "plan_quality": mean("plan_quality"),
        "writer_helpfulness": mean("writer_helpfulness"),
        "final_answer_helpfulness": mean("final_answer_helpfulness"),
        "final_minus_draft": mean("improvement"),
    }


def interpret_coordination(means: dict) -> str:
    plan = means.get("plan_quality")
    writer = means.get("writer_helpfulness")
    final = means.get("final_answer_helpfulness")
    improvement = means.get("final_minus_draft")
    if plan is None or writer is None or final is None:
        return ""
    sentences = [
        (
            f"Mean plan quality is {plan:.2f}, mean writer helpfulness is {writer:.2f}, "
            f"and mean final-answer helpfulness is {final:.2f} on a 1-5 scale."
        )
    ]
    if improvement is None or improvement <= 0:
        sentences.append(
            "The final answer did not score above the writer draft. "
            "On this set the reviewer pass left the shopper-facing answer no better than the draft."
        )
    else:
        sentences.append(
            f"The final answer scores {improvement:.2f} above the draft. "
            "That gap is the reviewer changing the writer output before it is returned."
        )
    if plan > writer + 0.5:
        sentences.append(
            "The plan scores above the draft, so the writer is dropping steps the planner asked for."
        )
    elif writer > plan + 0.5:
        sentences.append(
            "The draft scores above the plan, so the writer is adding content the plan score does not cover."
        )
    else:
        sentences.append(
            "Plan and writer scores sit close together, so the writer is following the plan."
        )
    return " ".join(sentences)


def interpret_judge(document: dict | None) -> str:
    if not document:
        return ""
    spearman = document.get("spearman")
    difference = document.get("mean_absolute_difference")
    if spearman is None or difference is None:
        return ""
    repeat = document.get("repeatability") or {}
    sentences = [
        (
            f"Spearman correlation with the human labels is {float(spearman):.3f}. "
            f"Mean absolute difference is {float(difference):.3f} points on the 1-5 scale."
        )
    ]
    changed = repeat.get("scores_changed")
    runs = repeat.get("runs")
    mean_change = repeat.get("mean_absolute_change")
    if changed is not None and runs is not None and mean_change is not None:
        sentences.append(
            f"Across {runs} repeated runs, {changed} case scores changed. "
            f"Mean absolute change was {float(mean_change):.3f}."
        )
    weak_rank = float(spearman) < 0.5
    wide_gap = float(difference) >= 1.0
    unstable = mean_change is not None and float(mean_change) >= 0.5
    if weak_rank or wide_gap or unstable:
        sentences.append(
            "These figures do not support trusting this judge as a deployment gate yet. "
            "The additional evidence to collect first is a higher rank agreement with the "
            "frozen human labels and a smaller change across repeated runs."
        )
    else:
        sentences.append(
            "On this frozen set the judge follows the human ranking and the repeated runs "
            "stay close. That evidence covers these drafts only."
        )
    return " ".join(sentences)


class OpsIndex:
    """In-memory index of the flow logs. Built once and reused across dashboard reruns."""

    def __init__(self, root: Path):
        self.root = root
        self.events = load_events(root)
        self.cache_part2 = parse_cache_part2(root / "reports" / "hw09" / "RUN_LOG.txt")
        self.cache_part3 = parse_cache_part3(root / "reports" / "hw09" / "part3_results.json")
        hw10 = root / "reports" / "hw10"
        self.evaluation = load_optional_json(hw10 / EVAL_FILENAME)
        self.judge = load_optional_json(hw10 / JUDGE_FILENAME)

    def sources(self) -> list[str]:
        names = sorted({event.source for event in self.events})
        return ["All captured logs", *names]

    def requests(self, source: str | None = None) -> list[RequestRecord]:
        return build_requests(self.events, source)

    def request_for(self, trace_id: str, source: str | None = None) -> list[RequestRecord]:
        wanted = trace_id.strip()
        return [record for record in self.requests(source) if record.trace_id == wanted]

    def summary(self, source: str | None = None) -> dict:
        summary = summarize_requests(self.requests(source))
        summary["cache_part2"] = self.cache_part2
        summary["cache_part3"] = self.cache_part3
        return summary
