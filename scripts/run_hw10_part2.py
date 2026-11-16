"""Score the captured Planner -> Writer -> Reviewer journey and save it for the dashboard."""

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))

from kafka_service.evaluator import (  # noqa: E402
    DEFAULT_TRACE,
    EvaluationError,
    evaluate_joined,
    judge_model_name,
    load_joined,
    result_document,
    write_result,
)


def main() -> int:
    correlation_id = sys.argv[1].strip() if len(sys.argv) > 1 else DEFAULT_TRACE
    model = judge_model_name()
    print(f"trace_id = {correlation_id}", flush=True)
    print(f"judge = {model} (local Ollama, GEval, 1-5, timeout 30s)", flush=True)
    try:
        joined = load_joined(REPO, correlation_id)
        case = evaluate_joined(joined, model)
    except EvaluationError as exc:
        print(f"evaluation stopped: {exc}", flush=True)
        return 1
    path = write_result(REPO, result_document(case, model))
    print(
        "plan {plan_quality} ({plan_reason})".format(**case),
        flush=True,
    )
    print(
        f"writer {case['writer_helpfulness']}  final {case['final_answer_helpfulness']}  "
        f"difference {case['improvement']}",
        flush=True,
    )
    print(case["improvement_interpretation"], flush=True)
    print(f"wrote {path.relative_to(REPO)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
