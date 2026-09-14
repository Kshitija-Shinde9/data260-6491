# Smoke test for HW2.
#
# This starts my system up and checks that the basic things actually work. It tests
# behaviour rather than looking for particular words in my source files, because the
# model does not say the same thing twice. So instead of asking "does the code contain
# this string", it asks "did the request succeed" and "did it return exactly 3 tags".
#
# It writes the result to reports/hw02/verification.json.
#
# run it with:  python scripts/verify_hw02.py

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SID4 = 6491
PORT_BASE = 8000 + (SID4 % 900)
SEED = SID4
VERIFY_SEED = 260000 + SID4
API = f"http://localhost:{PORT_BASE}/api/recalls"

checks = []


def check(name, passed, detail=""):
    checks.append({"name": name, "passed": bool(passed), "detail": str(detail)})
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def request(url, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as response:
        raw = response.read()
        if not raw:
            return response.status, None
        try:
            return response.status, json.loads(raw)
        except ValueError:
            # the home page returns html, not json, which is fine
            return response.status, raw.decode(errors="replace")


def port_is_open(port):
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex(("127.0.0.1", port)) == 0


def commit_hash():
    try:
        out = subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "not committed yet"
    except Exception:
        return "not a git repository"


def current_tag():
    try:
        out = subprocess.run(["git", "-C", ROOT, "describe", "--tags", "--abbrev=0"],
                             capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or "no tag"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------- required files

def check_files():
    for rel in ["reports/hw02/RUN_LOG.txt", "reports/hw02/METRICS.md",
                "reports/hw02/AI_USE.md", "reports/hw02/cases/schema_input.json",
                "reports/hw02/raw/task3_schema_runs.csv",
                "reports/hw02/raw/task4_ceiling_2.csv",
                "reports/hw02/raw/task4_ceiling_10.csv",
                "reports/hw02/raw/task5_adversarial.csv"]:
        check(f"deliverable present: {rel}", os.path.isfile(os.path.join(ROOT, rel)))


# ---------------------------------------------------------- parts 1 and 2, the API

def check_web_app():
    server = None
    started_here = False

    if not port_is_open(PORT_BASE):
        # start the app myself so the smoke test does not depend on me
        # remembering to launch it first
        server = subprocess.Popen(
            [sys.executable, "main.py"],
            cwd=os.path.join(ROOT, "code", "web_application"),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        started_here = True
        for _ in range(30):
            if port_is_open(PORT_BASE):
                break
            time.sleep(1)

    try:
        # does the backend answer at all on my PORT_BASE
        try:
            status, _ = request(f"http://localhost:{PORT_BASE}/")
            check(f"backend responds on PORT_BASE {PORT_BASE}", status == 200, f"http {status}")
        except Exception as error:
            check(f"backend responds on PORT_BASE {PORT_BASE}", False, error)
            return

        status, before = request(API)
        check("list endpoint returns a list of records", status == 200 and isinstance(before, list),
              f"{len(before) if isinstance(before, list) else '?'} records")

        # Q1 - adding a record should succeed and make the list one longer
        status, created = request(API, "POST", {
            "product_name": "Smoke Test Product 500g",
            "supplier": "Smoke Test Supplier",
            "email": "smoke@test.com",
            "description": "temporary record created by the smoke test, deleted again at the end",
            "recall_type": "Contamination",
        })
        check("Q1 add: request succeeded", status == 201, f"http {status}")
        check("Q1 add: server assigned an id", bool(created and created.get("id")), created.get("id") if created else None)
        _, after_add = request(API)
        check("Q1 add: the list grew by one", len(after_add) == len(before) + 1,
              f"{len(before)} -> {len(after_add)}")

        new_id = created["id"]

        # Q2 - updating should change the stored values
        status, updated = request(f"{API}/{new_id}", "PUT",
                                  {"product_name": "Smoke Test Renamed", "supplier": "Renamed Supplier"})
        check("Q2 update: request succeeded", status == 200, f"http {status}")
        check("Q2 update: the record actually changed",
              updated["product_name"] == "Smoke Test Renamed" and updated["supplier"] == "Renamed Supplier")

        # Q4 - searching should narrow the list, on both fields
        _, by_primary = request(f"{API}?search=Smoke%20Test%20Renamed")
        check("Q4 search: matches on the primary field",
              len(by_primary) >= 1 and all("smoke" in r["product_name"].lower() for r in by_primary),
              f"{len(by_primary)} result(s)")
        _, by_secondary = request(f"{API}?search=Renamed%20Supplier")
        check("Q4 search: matches on the secondary field",
              len(by_secondary) >= 1 and all("renamed" in r["supplier"].lower() for r in by_secondary),
              f"{len(by_secondary)} result(s)")
        _, no_match = request(f"{API}?search=zzzzzzzz")
        check("Q4 search: a term that matches nothing returns nothing", no_match == [],
              f"{len(no_match)} result(s)")

        # Q3 - deleting the highest id should remove the largest one
        _, full = request(API)
        highest = max(r["id"] for r in full)
        status, _ = request(f"{API}/highest", "DELETE")
        check("Q3 delete highest: request succeeded", status == 204, f"http {status}")
        _, after_delete = request(API)
        check("Q3 delete highest: the largest id is gone",
              highest not in [r["id"] for r in after_delete], f"removed id {highest}")
        check("Q3 delete highest: the list shrank by one",
              len(after_delete) == len(full) - 1, f"{len(full)} -> {len(after_delete)}")

        # a request for something that does not exist should fail cleanly
        try:
            request(f"{API}/99999")
            check("missing record returns an error rather than crashing", False, "no error raised")
        except urllib.error.HTTPError as error:
            check("missing record returns an error rather than crashing", error.code == 404, f"http {error.code}")

    finally:
        if started_here and server:
            server.terminate()
            server.wait(timeout=10)


# ------------------------------------------------------ parts 3 and 4, the graph

def check_agent_graph():
    sys.path.insert(0, os.path.join(ROOT, "code", "agent_graph"))
    sys.path.insert(0, ROOT)

    # the schema should accept a good answer and reject bad ones, whatever the wording
    try:
        from schema import validate_planner_output
        ok, _ = validate_planner_output(
            {"tags": ["torn packaging seal", "frozen berry recall", "frost damage"],
             "summary": "Blueberries recalled because the bag seal was torn."})
        check("schema accepts a valid answer", ok)

        bad_two, _ = validate_planner_output({"tags": ["one tag", "two tag"], "summary": "short summary."})
        check("schema rejects fewer than 3 tags", not bad_two)

        bad_four, _ = validate_planner_output({"tags": ["a tag", "b tag", "c tag", "d tag"], "summary": "short."})
        check("schema rejects more than 3 tags", not bad_four)

        bad_short, _ = validate_planner_output({"tags": ["ok", "b tag", "c tag"], "summary": "short."})
        check("schema rejects a tag under 3 characters", not bad_short)

        bad_long, _ = validate_planner_output(
            {"tags": ["x" * 31, "b tag", "c tag"], "summary": "short."})
        check("schema rejects a tag over 30 characters", not bad_long)

        bad_summary, _ = validate_planner_output(
            {"tags": ["a tag", "b tag", "c tag"], "summary": " ".join(["word"] * 40)})
        check("schema rejects a summary over 25 words", not bad_summary)
    except Exception as error:
        check("schema module loads and validates", False, error)
        return

    # the router should send work back to the planner when the reviewer objects
    try:
        from router import router_logic
        first = router_logic({"planner_proposal": {}, "reviewer_feedback": {},
                              "turn_count": 0, "max_turns": 10, "schema_valid": True})
        check("router sends the first turn to the planner", first == "planner", first)

        looped = router_logic({"planner_proposal": {"data": {}},
                               "reviewer_feedback": {"data": {"issues": ["not good enough"]}},
                               "turn_count": 1, "max_turns": 10, "schema_valid": True})
        check("router routes back to the planner when the reviewer objects",
              looped == "planner", looped)

        stopped = router_logic({"planner_proposal": {"data": {}},
                                "reviewer_feedback": {"data": {"issues": ["still bad"]}},
                                "turn_count": 10, "max_turns": 10, "schema_valid": True})
        check("router stops the graph at the turn ceiling", stopped == "END", stopped)
    except Exception as error:
        check("router module loads and routes", False, error)
        return

    # the graph itself should finish rather than hang, and give back 3 usable tags
    try:
        if not port_is_open(11434):
            check("graph finishes and returns exactly 3 tags", False,
                  "ollama is not running on port 11434, cannot smoke test the graph")
            return

        from workflow import build_initial_state, build_workflow
        case = json.load(open(os.path.join(ROOT, "reports", "hw02", "cases", "schema_input.json")))
        graph = build_workflow()
        state = build_initial_state(case["title"], case["content"], case["email"], 10)

        started = time.time()
        final = {}
        for step in graph.stream(state, {"recursion_limit": 60}):
            for _, update in step.items():
                final.update(update)
        elapsed = int((time.time() - started) * 1000)

        check("graph finishes instead of hanging", bool(final), f"{elapsed} ms")
        tags = final.get("planner_proposal", {}).get("data", {}).get("tags", [])
        check("graph returned exactly 3 tags", len(tags) == 3, f"{len(tags)} tags")
        check("every tag is a non-empty string",
              all(isinstance(t, str) and t.strip() for t in tags))
        summary = final.get("planner_proposal", {}).get("data", {}).get("summary", "")
        check("graph returned a summary", bool(summary.strip()))
        check("graph respected the turn ceiling",
              0 < final.get("turn_count", 0) <= 10, f"{final.get('turn_count')} turns")
    except Exception as error:
        check("graph finishes and returns exactly 3 tags", False, error)


def main():
    print(f"HW2 smoke test - SID4 {SID4}, PORT_BASE {PORT_BASE}\n")
    check_files()
    print()
    check_web_app()
    print()
    check_agent_graph()

    passed = sum(1 for c in checks if c["passed"])
    doc = {
        "homework": "HW2",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sid4": SID4,
        "port_base": PORT_BASE,
        "prefix": f"s{SID4}",
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "domain_id": SID4 % 8,
        "commit_hash": commit_hash(),
        "tag": current_tag(),
        "model_configuration": {
            "model": "qwen3:8b",
            "server": "Ollama 0.33.2 at http://localhost:11434",
            "temperature": 0.0,
            "adapter": "src/model_client.py from HW1",
        },
        "total_checks": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
        "checks": checks,
    }

    out = os.path.join(ROOT, "reports", "hw02", "verification.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(doc, f, indent=2)

    print(f"\n{passed}/{len(checks)} checks passed.")
    print("Written to reports/hw02/verification.json")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
