from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from tools import calculator, csv_sql, policy_retriever

PRICING_URL = "https://help.capitalbikeshare.com/hc/en-us/articles/360039401111-30-Day-Membership"


def run_agent(csv_text: str, pricing_url: str = PRICING_URL) -> dict[str, Any]:
    started = time.perf_counter()
    timeline: list[dict[str, Any]] = []

    def call(name: str, inputs: dict[str, Any], fn) -> dict[str, Any]:
        t0 = time.perf_counter()
        result = fn()
        elapsed = round((time.perf_counter() - t0) * 1000, 1)
        timeline.append(
            {"tool": name, "inputs": inputs, "observation": result, "elapsed_ms": elapsed}
        )
        return result

    # MRKL routing: SQL for uploaded facts, policy retriever for official rules, calculator for arithmetic.
    summary = call(
        "csv_sql",
        {"sql": "weekly summary"},
        lambda: csv_sql(
            csv_text,
            "SELECT substr(started_at,1,7) AS week, COUNT(*) AS ride_count, ROUND(AVG(CAST(duration_minutes AS REAL)),2) AS avg_minutes, ROUND(SUM(CAST(duration_minutes AS REAL)),2) AS total_minutes FROM trips GROUP BY week ORDER BY week",
        ),
    )
    total = call(
        "csv_sql",
        {"sql": "overall summary"},
        lambda: csv_sql(
            csv_text,
            "SELECT COUNT(*) AS ride_count, ROUND(AVG(CAST(duration_minutes AS REAL)),2) AS avg_minutes, ROUND(SUM(CAST(duration_minutes AS REAL)),2) AS total_minutes FROM trips",
        ),
    )
    policy = call(
        "policy_retriever",
        {
            "url": pricing_url,
            "query": "monthly membership price included minutes per minute surcharge unlock fee",
        },
        lambda: policy_retriever(
            pricing_url, "monthly membership price included minutes per minute surcharge unlock fee"
        ),
    )

    row = (total.get("data") or {}).get("rows", [{}])[0] if total.get("success") else {}
    rides = int(row.get("ride_count") or 0)
    minutes = float(row.get("total_minutes") or 0)
    # Capital Bikeshare membership price and usage assumptions are explicitly exposed in the result.
    membership = 25.0
    included = 45.0
    overage = max(0.0, minutes - rides * included)
    month_count_result = call(
        "csv_sql",
        {"sql": "active month count"},
        lambda: csv_sql(
            csv_text, "SELECT COUNT(DISTINCT substr(started_at,1,7)) AS month_count FROM trips"
        ),
    )
    month_count = int(
        ((month_count_result.get("data") or {}).get("rows") or [{"month_count": 1}])[0].get(
            "month_count"
        )
        or 1
    )
    monthly = call(
        "calculator",
        {"expression": f"{rides} * 1 + {minutes} * 0.15", "units": "USD"},
        lambda: calculator(f"{rides} * 1 + {minutes} * 0.15", "USD"),
    )
    member_calc = call(
        "calculator",
        {"expression": f"{membership} * {month_count} + {overage} * 0.05", "units": "USD"},
        lambda: calculator(f"{membership} * {month_count} + {overage} * 0.05", "USD"),
    )
    pay_cost = (monthly.get("data") or {}).get("value")
    member_cost = (member_calc.get("data") or {}).get("value")
    decision = (
        "Buy Monthly Membership"
        if member_cost is not None and pay_cost is not None and member_cost < pay_cost
        else "Pay Per Ride/Minute"
    )
    result = {
        "decision": decision,
        "justification": f"The uploaded file contains {rides} rides across {month_count} active month(s), totaling {minutes:.1f} minutes. Under the official-rate assumptions, pay-per-use is ${pay_cost:.2f} and membership is ${member_cost:.2f}; the lower cost is recommended. Policy evidence is saved with the source URL, access time, and SHA-256 hash.",
        "costs": {
            "pay_per_use": pay_cost,
            "membership": member_cost,
            "rides": rides,
            "active_months": month_count,
            "total_minutes": minutes,
            "overage_minutes": round(overage, 2),
        },
        "weekly": (summary.get("data") or {}).get("rows", []),
        "citations": (policy.get("data") or {}).get("passages", []),
        "policy_metadata": {
            k: (policy.get("data") or {}).get(k) for k in ("source_url", "accessed_at", "sha256")
        },
        "assumptions": [
            "duration_minutes is treated as classic-bike ride time",
            "official policy rates used: $25 per 30-day membership, $1 unlock plus $0.15/minute for single rides, 45 minutes included per classic ride, then $0.05/minute; taxes and ebike charges are excluded",
        ],
        "timeline": timeline,
        "metrics": {
            "step_count": len(timeline),
            "total_time_ms": round((time.perf_counter() - started) * 1000, 1),
            "stop_reason": "success",
        },
    }
    Path("reports/hw07/part4").mkdir(parents=True, exist_ok=True)
    Path("reports/hw07/part4/latest_result.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    return result
