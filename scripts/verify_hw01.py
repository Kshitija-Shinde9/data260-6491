# self-check script for hw1. runs through a bunch of quick checks on the repo
# and the live deployment, prints them, and dumps reports/hw01/verification.json.
# run with: python scripts/verify_hw01.py
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.join(os.path.dirname(__file__), "..")
HW01_DIR = os.path.join(ROOT, "reports", "hw01")

PORT_BASE = 8191
PUBLIC_IP = "3.19.65.182"  # AWS ECS deployment verified for this submission

checks = []


def check(name, passed, detail=""):
    checks.append({"name": name, "passed": bool(passed), "detail": detail})


def file_exists(rel_path):
    return os.path.isfile(os.path.join(ROOT, rel_path))


def main():
    required_files = [
        "code/web_application/index.html", "code/web_application/script.js",
        "code/web_application/Dockerfile", "DOMAIN_SCHEMA.md",
        "code/web_application/agents_demo.py", "AGENT.md",
        "code/web_application/hw1_client.py", "src/model_client.py",
        "README.md",
        "reports/hw01/cases/nondeterminism_input.json",
        "reports/hw01/AI_USE.md",
    ]
    for rel in required_files:
        check(f"file exists: {rel}", file_exists(rel))

    index_path = os.path.join(ROOT, "code", "web_application", "index.html")
    if os.path.isfile(index_path):
        with open(index_path) as f:
            html = f.read()
        check("index.html <title> starts with HW1-", bool(re.search(r"<title>\s*HW1-", html)))
        check("index.html has an <h1> heading", "<h1" in html)
        check("index.html has autofocus on an input", "autofocus" in html)
        check(
            "index.html has the exact terms checkbox label",
            "I agree to the terms and conditions." in html,
        )
    else:
        check("index.html readable", False)

    docker_path = os.path.join(ROOT, "code", "web_application", "Dockerfile")
    if os.path.isfile(docker_path):
        with open(docker_path) as f:
            df = f.read()
        check(f"Dockerfile exposes PORT_BASE {PORT_BASE}", str(PORT_BASE) in df)
    else:
        check("Dockerfile readable", False)

    try:
        sys.path.insert(0, os.path.join(ROOT, "code", "web_application"))
        import agents_demo  # noqa: E402

        check("agents_demo.py imports cleanly", True)
        check("agents_demo.py exposes run_pipeline()", hasattr(agents_demo, "run_pipeline"))
        check("agents_demo.py exposes build_llm()", hasattr(agents_demo, "build_llm"))
    except Exception as e:
        check("agents_demo.py imports cleanly", False, str(e))

    check("Part 3 raw CSV present", file_exists("reports/hw01/raw/nondeterminism_runs.csv"))
    check("Part 3 metrics JSON present", file_exists("reports/hw01/raw/nondeterminism_metrics.json"))
    check("Part 4 per-turn token counts CSV present", file_exists("reports/hw01/raw/hw1_client_turns.csv"))

    try:
        result = subprocess.run(
            [
                "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "10",
                f"http://{PUBLIC_IP}:{PORT_BASE}/",
            ],
            capture_output=True, text=True, timeout=15,
        )
        status = result.stdout.strip()
        check(
            f"AWS ECS public IP reachable (http://{PUBLIC_IP}:{PORT_BASE}/)",
            status == "200",
            f"http_status={status}",
        )
    except Exception as e:
        check("AWS ECS public IP reachable", False, str(e))

    try:
        result = subprocess.run(
            [
                "curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", "5",
                f"http://localhost:{PORT_BASE}/",
            ],
            capture_output=True, text=True, timeout=10,
        )
        status = result.stdout.strip()
        check(
            f"local Docker container reachable (http://localhost:{PORT_BASE}/)",
            status == "200",
            f"http_status={status}",
        )
    except Exception as e:
        check("local Docker container reachable", False, str(e))

    passed_count = sum(1 for c in checks if c["passed"])
    result_doc = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_checks": len(checks),
        "passed": passed_count,
        "failed": len(checks) - passed_count,
        "checks": checks,
    }

    os.makedirs(HW01_DIR, exist_ok=True)
    out_path = os.path.join(HW01_DIR, "verification.json")
    with open(out_path, "w") as f:
        json.dump(result_doc, f, indent=2)

    print(json.dumps(result_doc, indent=2))
    print(f"\n{passed_count}/{len(checks)} checks passed. Written to {out_path}")


if __name__ == "__main__":
    main()
