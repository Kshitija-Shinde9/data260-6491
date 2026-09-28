import csv
import json
import os
import time
import urllib.error
import urllib.request

SID4 = 6491
PORT_BASE = 8000 + (SID4 % 900)
BASE = f"http://127.0.0.1:{PORT_BASE}"

DEMO_EMAIL = "admin@s6491.com"
DEMO_PASSWORD = "Recall@6491"

PAGE_SIZES = [10, 50, 200]
REQUESTS_PER_CELL = 30
ENDPOINTS = {
    "naive": "/api/bench/naive",
    "fixed": "/api/bench/fixed",
}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "reports", "hw04", "raw")


def fetch(path, method="GET", cookie=None):
    req = urllib.request.Request(BASE + path, method=method)
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return r.status, r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.headers


def login():
    req = urllib.request.Request(
        BASE + "/api/auth/login",
        data=json.dumps({"email": DEMO_EMAIL, "password": DEMO_PASSWORD}).encode(),
        method="POST",
    )
    req.add_header("Content-Type", "application/json")
    r = urllib.request.urlopen(req, timeout=15)
    raw_cookie = r.headers.get("set-cookie", "")
    token = raw_cookie.split(";")[0]
    return token


def endpoint_available(path, cookie):
    status, _ = fetch(f"{path}?page_size=1", cookie=cookie)
    return status == 200


def percentile(data, p):
    data = sorted(data)
    if len(data) == 1:
        return data[0]
    k = (len(data) - 1) * (p / 100)
    f = int(k)
    c = min(f + 1, len(data) - 1)
    if f == c:
        return data[f]
    return data[f] + (data[c] - data[f]) * (k - f)


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    cookie = login()
    print(f"Logged in as {DEMO_EMAIL}.")

    rows = []
    for version, path in ENDPOINTS.items():
        if not endpoint_available(path, cookie):
            print(f"[skip] {version} ({path}) not available yet.")
            continue

        for page_size in PAGE_SIZES:
            for i in range(REQUESTS_PER_CELL):
                start = time.perf_counter()
                status, headers = fetch(f"{path}?page_size={page_size}", cookie=cookie)
                latency_ms = (time.perf_counter() - start) * 1000
                query_count = int(headers.get("x-query-count", -1))

                if status != 200:
                    print(f"  [warn] {version} page_size={page_size} req#{i}: HTTP {status}")

                rows.append({
                    "version": version,
                    "page_size": page_size,
                    "request_index": i,
                    "status": status,
                    "query_count": query_count,
                    "latency_ms": round(latency_ms, 3),
                })

            print(f"{version:>6} page_size={page_size:<4} done ({REQUESTS_PER_CELL} requests).")

    raw_path = os.path.join(RAW_DIR, "n_plus_1_raw.csv")
    with open(raw_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["version", "page_size", "request_index", "status", "query_count", "latency_ms"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nWrote {len(rows)} raw request records to {raw_path}")

    print(f"\n{'page_size':<10}{'version':<10}{'SQL stmts/req':<16}{'p50 (ms)':<12}{'p95 (ms)':<12}{'p99 (ms)':<12}")
    summary = []
    for version in ENDPOINTS:
        for page_size in PAGE_SIZES:
            cell = [r for r in rows if r["version"] == version and r["page_size"] == page_size]
            if not cell:
                continue
            latencies = [r["latency_ms"] for r in cell]
            query_counts = {r["query_count"] for r in cell}
            qc = query_counts.pop() if len(query_counts) == 1 else f"varies:{query_counts}"
            p50, p95, p99 = percentile(latencies, 50), percentile(latencies, 95), percentile(latencies, 99)
            print(f"{page_size:<10}{version:<10}{str(qc):<16}{p50:<12.2f}{p95:<12.2f}{p99:<12.2f}")
            summary.append({
                "page_size": page_size, "version": version, "sql_stmts_per_req": qc,
                "p50_ms": round(p50, 2), "p95_ms": round(p95, 2), "p99_ms": round(p99, 2),
            })

    summary_path = os.path.join(RAW_DIR, "n_plus_1_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote summary to {summary_path}")


if __name__ == "__main__":
    main()
