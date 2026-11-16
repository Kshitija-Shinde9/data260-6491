"""Score the frozen writer drafts three times and compare them with the human labels.

Reads reports/hw10/eval_cases.json and reports/hw10/human_labels.csv.
Does not rewrite either file.
"""

import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))

from kafka_service.evaluator import (  # noqa: E402
    JUDGE_TIMEOUT_SEC,
    EvaluationError,
    judge_model_name,
    mean_absolute_difference,
    ollama_url,
    score_writer_draft,
    spearman,
)

CASES_PATH = REPO / "reports" / "hw10" / "eval_cases.json"
LABELS_PATH = REPO / "reports" / "hw10" / "human_labels.csv"
OUT_PATH = REPO / "reports" / "hw10" / "part3_judge_validation.json"
RUNS = 3


def load_frozen() -> list[dict]:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))["cases"]
    with LABELS_PATH.open(encoding="utf-8") as handle:
        labels = {row["case_id"]: int(row["helpfulness"]) for row in csv.DictReader(handle)}
    if len(cases) != 20 or len(labels) != 20:
        raise EvaluationError("Part 3 expects 20 frozen drafts and 20 human labels.")
    rows = []
    for case in cases:
        if case["case_id"] not in labels:
            raise EvaluationError(f"{case['case_id']} has no human label.")
        label = labels[case["case_id"]]
        if label < 1 or label > 5:
            raise EvaluationError(f"{case['case_id']} label {label} is outside 1-5.")
        rows.append({**case, "human_label": label})
    return rows


def main() -> int:
    model = judge_model_name()
    print(f"judge = {model} (local Ollama, GEval writer helpfulness, temperature 0)", flush=True)
    print(
        f"runs = {RUNS}, timeout = {JUDGE_TIMEOUT_SEC}s, labels read from {LABELS_PATH.name}",
        flush=True,
    )
    try:
        rows = load_frozen()
        runs: list[list[int]] = []
        for run in range(1, RUNS + 1):
            scores = []
            for row in rows:
                verdict = score_writer_draft(row["question"], row["plan"], row["draft"], model)
                scores.append(verdict["score"])
                print(f"run {run} {row['case_id']} {verdict['score']}", flush=True)
            runs.append(scores)
    except EvaluationError as exc:
        print(f"judge validation stopped: {exc}", flush=True)
        return 1

    human = [row["human_label"] for row in rows]
    compared = runs[0]
    per_case = []
    changes = []
    for index, row in enumerate(rows):
        trio = [runs[run][index] for run in range(RUNS)]
        change = max(trio) - min(trio)
        changes.append(change)
        per_case.append(
            {
                "case_id": row["case_id"],
                "human_label": row["human_label"],
                "judge_run_1": trio[0],
                "judge_run_2": trio[1],
                "judge_run_3": trio[2],
                "absolute_difference": abs(row["human_label"] - trio[0]),
                "max_abs_change": change,
            }
        )
    rank = spearman(human, compared)
    difference = mean_absolute_difference(human, compared)
    if rank is None:
        print("judge validation stopped: the scores have no rank variation.", flush=True)
        return 1
    document = {
        "judge": {
            "method": "GEval",
            "criterion": "Writer helpfulness",
            "model": model,
            "provider": f"local Ollama at {ollama_url()}",
            "temperature": 0,
            "scale": "1 very poor, 5 excellent",
            "timeout_sec": JUDGE_TIMEOUT_SEC,
            "comparison_run": 1,
            "cases_file": "reports/hw10/eval_cases.json",
            "labels_file": "reports/hw10/human_labels.csv",
        },
        "spearman": round(rank, 3),
        "mean_absolute_difference": round(difference, 3),
        "repeatability": {
            "runs": RUNS,
            "scores_changed": sum(1 for change in changes if change),
            "mean_absolute_change": round(sum(changes) / len(changes), 3),
            "maximum_absolute_change": max(changes),
        },
        "per_case": per_case,
    }
    OUT_PATH.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    print(f"Spearman {document['spearman']}", flush=True)
    print(f"mean absolute difference {document['mean_absolute_difference']}", flush=True)
    print(document["repeatability"], flush=True)
    print(f"wrote {OUT_PATH.relative_to(REPO)}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
