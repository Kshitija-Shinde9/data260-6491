import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))

from kafka_service.flow_log import log_flow, saved_flow_logs  # noqa: E402
from kafka_service.ops_metrics import (  # noqa: E402
    OpsIndex,
    build_requests,
    evaluation_cases,
    interpret_coordination,
    interpret_judge,
    list_log_files,
    load_events,
    load_optional_json,
    parse_cache_part2,
    parse_flow_line,
    stage_means,
)

OUT = REPO / "reports" / "hw10" / "part1_verification.json"
PLANNER_TRACE = "2b83f4a7-e6f0-46cc-b334-409b5205daa4"
checks = []


def record(name, passed, detail=""):
    checks.append({"name": name, "passed": bool(passed), "detail": str(detail)})
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def main() -> int:
    index = OpsIndex(REPO)
    record("flow events loaded", len(index.events) > 0, f"{len(index.events)} events")

    all_requests = index.requests()
    summary = index.summary()
    record("request count is positive", summary["request_count"] > 0, str(summary["request_count"]))
    record(
        "error rate is a share of those requests",
        0 < summary["error_rate"] < 1,
        f"{summary['error_count']} errors, rate {summary['error_rate']}",
    )
    record(
        "mean end-to-end latency is present",
        summary["mean_e2e_ms"] is not None and summary["mean_e2e_ms"] > 0,
        str(summary["mean_e2e_ms"]),
    )
    record(
        "request window has a start and an end",
        bool(summary["window_start"]) and summary["window_start"] < summary["window_end"],
        f"{summary['window_start']} -> {summary['window_end']}",
    )

    reused = [item for item in all_requests if item.trace_id.startswith("daaf6214")]
    record(
        "reused correlation_id stays one trace_id across two operations",
        len(reused) == 2 and {item.trace_id for item in reused} == {reused[0].trace_id},
        f"{len(reused)} segments",
    )

    planner = index.request_for(PLANNER_TRACE)
    stage_names = [span.stage for span in planner[0].stages] if planner else []
    record(
        "planner trace stages follow inbox, planner, writer, reviewer, final",
        stage_names == ["inbox", "planner", "writer", "reviewer", "final"],
        " -> ".join(stage_names),
    )
    record(
        "planner trace cache path is not recorded",
        bool(planner) and planner[0].cache_path == "not_recorded",
        planner[0].cache_path if planner else "missing",
    )

    poison = index.request_for("poison-266491")
    record(
        "poison trace is an error",
        bool(poison) and poison[0].status == "error" and "poison" in poison[0].error.lower(),
        poison[0].error if poison else "missing",
    )
    crash = index.request_for("crash-before-266491")
    record(
        "crash-before trace names the failing stage",
        bool(crash) and crash[0].status == "error" and "killed" in crash[0].error.lower(),
        crash[0].error if crash else "missing",
    )

    part2 = index.cache_part2
    record(
        "Part 2 cache hits and misses are separated",
        part2 is not None
        and part2["hits"] == 7
        and part2["misses"] == 5
        and part2["hit_rate"] == 58.3,
        str(part2),
    )
    part3 = index.cache_part3
    record(
        "Part 3 shipped threshold reports hits, false hits, and misses",
        part3 is not None
        and part3["threshold"] == 0.95
        and part3["false_hits"] == 0
        and part3["misses"] == 21
        and part3["correct_hits"] == 19,
        str(part3),
    )
    cases = evaluation_cases(index.evaluation)
    record(
        "evaluation file is absent until Part 2 writes it, or those scores load",
        index.evaluation is None or bool(cases),
        "absent" if index.evaluation is None else f"{len(cases)} cases",
    )
    judge_ready = index.judge is None or index.judge.get("spearman") is not None
    record(
        "judge-validation file is absent until Part 3 writes it, or those scores load",
        judge_ready,
        "absent" if index.judge is None else f"spearman {index.judge.get('spearman')}",
    )

    hit = parse_flow_line(
        "2026-11-14T00:00:00.000000Z | CACHE | LOOKUP | corr=hit-demo cache hit similarity=1.0",
        "memory",
    )
    miss = parse_flow_line(
        "2026-11-14T00:00:01.000000Z | CACHE | LOOKUP | corr=miss-demo cache miss similarity=0.1",
        "memory",
    )
    hit_path = build_requests([hit])[0].cache_path if hit else ""
    miss_path = build_requests([miss])[0].cache_path if miss else ""
    record(
        "cache hit and cache miss paths are different labels",
        hit_path == "hit" and miss_path == "miss",
        f"hit={hit_path} miss={miss_path}",
    )
    written = log_flow("CACHE", "LOOKUP", "corr=extend-check cache hit similarity=1.0000")
    parsed = parse_flow_line(written, "flow_log")
    record(
        "a line from flow_log.log_flow is the line the dashboard parses",
        parsed is not None
        and parsed.correlation_id == "extend-check"
        and parsed.pipeline_stage == "cache_lookup",
        written,
    )
    record(
        "dashboard log list is the list the Kafka service already saves",
        list_log_files(REPO) == saved_flow_logs(REPO),
        str(len(list_log_files(REPO))),
    )

    weaker = interpret_coordination(
        {
            "plan_quality": 4.0,
            "writer_helpfulness": 3.0,
            "final_answer_helpfulness": 2.5,
            "final_minus_draft": -0.5,
        }
    )
    stronger = interpret_coordination(
        {
            "plan_quality": 3.0,
            "writer_helpfulness": 3.2,
            "final_answer_helpfulness": 4.0,
            "final_minus_draft": 0.8,
        }
    )
    record(
        "a lower final score is described as no improvement",
        "did not score above" in weaker,
        weaker,
    )
    record(
        "a higher final score reports the gap",
        "0.80 above the draft" in stronger,
        stronger,
    )
    judge_text = interpret_judge(
        {
            "spearman": 0.2,
            "mean_absolute_difference": 1.4,
            "repeatability": {"runs": 3, "scores_changed": 8, "mean_absolute_change": 0.7},
        }
    )
    record(
        "a weak judge is not described as ready to gate a deployment",
        "do not support trusting" in judge_text,
        judge_text,
    )

    with tempfile.TemporaryDirectory() as tmp:
        fixture = Path(tmp) / "part2_evaluation.json"
        fixture.write_text(
            json.dumps(
                {
                    "cases": [
                        {
                            "case_id": "case-1",
                            "trace_id": "abc",
                            "plan_quality": 4,
                            "writer_helpfulness": 3,
                            "final_answer_helpfulness": 5,
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        loaded = evaluation_cases(load_optional_json(fixture))
        means = stage_means(loaded)
        record(
            "evaluation loader reads scores by case",
            len(loaded) == 1 and means["final_minus_draft"] == 2.0,
            str(means),
        )

    record(
        "dashboard app and requirements exist",
        (REPO / "code" / "ops_dashboard" / "app.py").is_file()
        and (REPO / "code" / "ops_dashboard" / "requirements-dashboard.txt").is_file(),
    )
    record(
        "cache parser agrees with the index",
        parse_cache_part2(REPO / "reports" / "hw09" / "RUN_LOG.txt") == index.cache_part2,
    )
    record(
        "events used by the index come from load_events",
        len(load_events(REPO)) == len(index.events),
    )

    passed = sum(1 for check in checks if check["passed"])
    document = {
        "homework": "HW10",
        "part": 1,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sid4": 6491,
        "prefix": "s6491",
        "total_checks": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
        "summary": summary,
        "checks": checks,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"\n{passed}/{len(checks)} passed. Wrote {OUT.relative_to(REPO)}")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
