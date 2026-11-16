import sys
from pathlib import Path

_CODE = Path(__file__).resolve().parents[1]
if str(_CODE) not in sys.path:
    sys.path.insert(0, str(_CODE))

import streamlit as st  # noqa: E402
from kafka_service.ops_metrics import (  # noqa: E402
    EVAL_FILENAME,
    JUDGE_FILENAME,
    OpsIndex,
    evaluation_cases,
    interpret_coordination,
    interpret_judge,
    load_part4,
    parse_cache_part2,
    parse_cache_part3,
    repo_root_from_here,
    source_signature,
    stage_means,
)

ROOT = repo_root_from_here()

PATH_COPY = {
    "hit": (
        "Cache hit",
        "The semantic cache returned the stored answer. Planner, Writer, and Reviewer did not run.",
    ),
    "miss": (
        "Cache miss",
        "The cache lookup missed, so the request continued through the agent stages.",
    ),
    "not_recorded": (
        "Cache not recorded",
        "This journey has no cache_lookup event. The HW8 flow logs were written before the semantic cache.",
    ),
}


@st.cache_resource
def get_index(root_str: str, signature: str) -> OpsIndex:
    del signature
    return OpsIndex(Path(root_str))


@st.cache_data
def load_cache_metrics(run_log_path: str, part3_path: str, run_mtime: float, part3_mtime: float):
    """Reload the HW9 measurement files only when those files change."""
    del run_mtime, part3_mtime
    return parse_cache_part2(Path(run_log_path)), parse_cache_part3(Path(part3_path))


def _mtime(path: Path) -> float:
    return path.stat().st_mtime if path.is_file() else 0.0


def _show_path(cache_path: str) -> None:
    title, body = PATH_COPY.get(cache_path, PATH_COPY["not_recorded"])
    if cache_path == "hit":
        st.success(f"**{title}.** {body}")
    elif cache_path == "miss":
        st.warning(f"**{title}.** {body}")
    else:
        st.info(f"**{title}.** {body}")


def _metric_sources(summary: dict, source_label: str) -> None:
    window = "no requests in this selection"
    if summary["window_start"] and summary["window_end"]:
        window = f"{summary['window_start']} to {summary['window_end']}"
    files = ", ".join(summary["sources"]) if summary["sources"] else source_label
    latency = "n/a" if summary["mean_e2e_ms"] is None else f"{summary['mean_e2e_ms']:.1f} ms"
    rows = [
        {
            "metric": "Recent request count",
            "value": str(summary["request_count"]),
            "time_window": window,
            "data_source": files,
        },
        {
            "metric": "Error rate",
            "value": f"{summary['error_count']} / {summary['request_count']} ({summary['error_rate']:.1%})",
            "time_window": window,
            "data_source": f"{files}; a request is an error when any stage records a failure",
        },
        {
            "metric": "End-to-end latency (mean)",
            "value": latency,
            "time_window": window,
            "data_source": (
                f"{files}; last event minus first event, "
                f"{summary['latency_sample_count']} requests with a later end event"
            ),
        },
    ]
    st.dataframe(rows, width="stretch", hide_index=True)


def render_summary(index: OpsIndex, source: str) -> None:
    st.header("Summary")
    st.caption(
        "Request, error, and latency figures come from the lines kafka_service.flow_log already writes. "
        "Cache figures come from the HW9 measurement files. The two windows are stated separately."
    )
    summary = index.summary(source)
    left, middle, right = st.columns(3)
    left.metric("Recent requests", summary["request_count"])
    middle.metric("Error rate", f"{summary['error_rate']:.1%}", f"{summary['error_count']} errors")
    latency = "n/a" if summary["mean_e2e_ms"] is None else f"{summary['mean_e2e_ms']:.0f} ms"
    right.metric("Mean end-to-end latency", latency)
    _metric_sources(summary, source)

    st.subheader("Semantic cache")
    part2, part3 = load_cache_metrics(
        str(ROOT / "reports" / "hw09" / "RUN_LOG.txt"),
        str(ROOT / "reports" / "hw09" / "part3_results.json"),
        _mtime(ROOT / "reports" / "hw09" / "RUN_LOG.txt"),
        _mtime(ROOT / "reports" / "hw09" / "part3_results.json"),
    )
    if part2 is None:
        st.info("reports/hw09/RUN_LOG.txt has no Part 2 hit/miss summary.")
    else:
        st.markdown(
            f"**Part 2 measurement.** Source: `{part2['source']}`. Time window: {part2['window']}."
        )
        hits, misses, rate = st.columns(3)
        hits.metric("Cache hits", part2["hits"])
        misses.metric("Cache misses", part2["misses"])
        rate.metric("Hit rate", f"{part2['hit_rate']:.1f}%")
        st.bar_chart({"cache hits": [part2["hits"]], "cache misses": [part2["misses"]]})
        slow, fast = st.columns(2)
        fast.metric("Mean latency, cache hits", f"{part2['mean_hit_ms']:.1f} ms")
        slow.metric("Mean latency, cache misses", f"{part2['mean_miss_ms']:.1f} ms")
        if part2["note"]:
            st.caption(part2["note"])

    if part3 is None:
        st.info("reports/hw09/part3_results.json has no shipped-threshold row.")
    else:
        st.markdown(
            f"**Part 3 shipped threshold {part3['threshold']}.** "
            f"Source: `{part3['source']}`. Time window: {part3['window']}. "
            "This sweep is a different measurement from the Part 2 hit rate above."
        )
        correct, false_hits, missed = st.columns(3)
        correct.metric("Correct hits", part3["correct_hits"])
        false_hits.metric("False hits", part3["false_hits"])
        missed.metric("Cache misses", part3["misses"])
        st.caption(
            f"Hit rate {part3['hit_rate']}%. False-hit rate {part3['false_hit_rate']}%. "
            f"Mean latency {part3['mean_latency_ms']} ms."
        )

    part4 = load_part4(ROOT / "reports" / "hw10" / "part4_latency.json")
    if part4 is not None:
        st.subheader("Stage latency, cache misses")
        st.caption(
            f"{part4['miss_count']} confirmed cache misses. {part4['window']}. "
            "Cache-hit latency is separate from this table."
        )
        hit = part4.get("cache_hit_latency_ms") or {}
        st.metric("Cache-hit latency (p50)", f"{hit.get('p50', 0):.1f} ms")
        st.dataframe(part4["stages"], width="stretch", hide_index=True)
        st.caption(part4.get("optimize_first", ""))

    st.subheader("Recent requests")
    records = index.requests(source)
    st.dataframe(
        [record.as_dict() for record in records[:25]],
        width="stretch",
        hide_index=True,
    )
    if len(records) > 25:
        st.caption(f"Showing the 25 latest of {len(records)} requests in this window.")


def render_evaluation(index: OpsIndex) -> None:
    st.header("Evaluation")
    st.caption(
        "Scores use the 1-5 scale from Homework 10: 1 is very poor and 5 is excellent. "
        "The interpretation is computed from the saved scores."
    )
    cases = evaluation_cases(index.evaluation)
    if not cases:
        st.info(
            "Part 2 has not written evaluation scores yet. "
            f"When `reports/hw10/{EVAL_FILENAME}` exists, this page lists plan quality, "
            "writer helpfulness, final-answer helpfulness, and the draft-to-final difference "
            "for each case."
        )
    else:
        means = stage_means(cases)
        plan, writer, final, gap = st.columns(4)
        plan.metric("Mean plan quality", _fmt(means["plan_quality"]))
        writer.metric("Mean writer helpfulness", _fmt(means["writer_helpfulness"]))
        final.metric("Mean final helpfulness", _fmt(means["final_answer_helpfulness"]))
        gap.metric("Mean final minus draft", _fmt(means["final_minus_draft"]))
        st.subheader("Scores by case")
        st.dataframe(cases, width="stretch", hide_index=True)
        saved = (index.evaluation or {}).get("interpretation")
        interpretation = saved or interpret_coordination(means)
        if interpretation:
            st.subheader("What the scores suggest")
            st.write(interpretation)

    judge = index.judge
    st.subheader("Judge validation")
    if not judge:
        st.info(
            "Part 3 has not written judge-validation results yet. "
            f"`reports/hw10/{JUDGE_FILENAME}` should carry the Spearman correlation, "
            "the mean absolute difference from the human labels, and the repeatability of three runs."
        )
        return
    spearman, difference, changed = st.columns(3)
    spearman.metric("Spearman correlation", _fmt(judge.get("spearman"), digits=3))
    difference.metric(
        "Mean absolute difference",
        _fmt(judge.get("mean_absolute_difference"), digits=3),
    )
    repeat = judge.get("repeatability") or {}
    changed.metric("Scores changed across runs", _fmt(repeat.get("scores_changed"), digits=0))
    if repeat:
        st.dataframe([repeat], width="stretch", hide_index=True)
    per_case = judge.get("per_case") or judge.get("cases") or []
    if per_case:
        st.subheader("Per-case judge comparison")
        st.dataframe(per_case, width="stretch", hide_index=True)
    judge_text = interpret_judge(judge)
    if judge_text:
        st.subheader("Whether the judge is trustworthy on this set")
        st.write(judge_text)


def render_trace(index: OpsIndex, source: str) -> None:
    st.header("Trace lookup")
    st.caption(
        "trace_id is the HW8 correlation_id. Cache-hit journeys are marked in green and stop "
        "before the agent stages. Cache-miss journeys are marked in amber and include those stages."
    )
    known = []
    seen = set()
    for record in index.requests(source):
        if record.trace_id not in seen:
            seen.add(record.trace_id)
            known.append(record.trace_id)

    def use_selected_trace() -> None:
        choice = st.session_state["trace_choice"]
        if choice != "(type one below)":
            st.session_state["trace_id"] = choice

    st.selectbox(
        "Recent trace_id",
        ["(type one below)", *known],
        key="trace_choice",
        on_change=use_selected_trace,
    )
    st.text_input("trace_id", key="trace_id")
    trace_id = st.session_state.get("trace_id", "").strip()
    if not trace_id:
        st.info(
            "Enter a trace_id. Example from the planner log: `2b83f4a7-e6f0-46cc-b334-409b5205daa4`."
        )
        return
    matches = index.request_for(trace_id, source)
    if not matches:
        st.error(f"No journey for `{trace_id}` in {source}.")
        return
    if len(matches) > 1:
        st.caption(
            f"`{trace_id}` was reused for {len(matches)} operations. "
            "Each block below is one operation, in time order, under the same trace_id."
        )
    for record in sorted(matches, key=lambda item: item.segment):
        title = record.operation or "operation"
        st.subheader(f"Segment {record.segment}: {title}")
        _show_path(record.cache_path)
        if record.question:
            st.markdown(f"**Question.** {record.question}")
        meta = st.columns(3)
        meta[0].metric("Status", record.status)
        meta[1].metric("End-to-end", f"{record.duration_ms:.1f} ms")
        meta[2].metric("Log", record.source)
        if record.error:
            st.error(record.error)
        st.dataframe(
            [span.as_dict() for span in record.stages],
            width="stretch",
            hide_index=True,
        )
        with st.expander("Raw events"):
            for event in record.events:
                stamp = event.ts.isoformat()
                st.text(f"{stamp}  {event.component}  {event.raw_stage}  {event.detail}")


def _fmt(value, digits: int = 2) -> str:
    if value is None or value == "":
        return "n/a"
    if isinstance(value, (int, float)):
        if digits == 0:
            return str(int(value))
        return f"{float(value):.{digits}f}"
    return str(value)


def main() -> None:
    st.set_page_config(page_title="s6491 operations", layout="wide")
    st.title("s6491 operations dashboard")
    st.caption(
        "Grocery recall pipeline for prefix s6491. This view reads the Kafka service flow log "
        "and the semantic-cache measurements already produced for this repo."
    )
    signature = source_signature(ROOT)
    index = get_index(str(ROOT), signature)
    source = st.sidebar.selectbox("Log source", index.sources())
    page = st.sidebar.radio("Page", ["Summary", "Evaluation", "Trace lookup"])
    if st.sidebar.button("Reload logs"):
        st.cache_resource.clear()
        st.cache_data.clear()
        st.rerun()
    st.sidebar.caption(f"Repo: {ROOT}")
    if page == "Summary":
        render_summary(index, source)
    elif page == "Evaluation":
        render_evaluation(index)
    else:
        render_trace(index, source)


main()
