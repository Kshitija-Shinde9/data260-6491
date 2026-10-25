import csv
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

try:
    import yaml
except ImportError:
    sys.exit("Install PyYAML in the same environment: pip install pyyaml")

PORT = 8191
BASE = f"http://127.0.0.1:{PORT}"
CONVERSATION = [
    "My name is Kshitija and I shop at Trader Joe's on Stevens Creek.",
    "I bought Organic Frozen Blueberries in a 16oz bag.",
    "The blueberry lot code was TJ-16OZ-221.",
    "Please remember that I am allergic to peanuts.",
    "I bought Kirkland Signature Trail Mix, 4lb, from Costco.",
    "The trail mix label does not list peanuts even though peanuts are in the bag.",
    "The Safeway rotisserie chicken from the hot case was lukewarm.",
    "That chicken pack date was two days old.",
    "I keep a fridge thermometer on the middle shelf.",
    "The fridge was at 38 degrees this morning.",
    "I also bought plain rice from the same trip.",
    "The rice bag was sealed and looked normal.",
    "I store raw chicken on the bottom shelf.",
    "I use separate cutting boards for meat and vegetables.",
    "I washed the blueberries before I noticed the torn seal.",
    "The tear was at the top of the bag.",
    "Frost was only on the berries near that opening.",
    "I did not eat any of the berries.",
    "I kept the trail mix bag closed after I saw the peanuts.",
    "The Costco receipt is dated March 14.",
    "The Safeway receipt is dated March 10.",
    "I can return both products with those receipts.",
    "Please remember the chicken was sold from the hot case.",
    "The hot case chicken should have been steaming, not lukewarm.",
    "I did not feed that chicken to anyone.",
    "The blueberries are still in my freezer.",
    "The trail mix is still in the pantry.",
    "The supplier phone number for follow-up is 408-555-0142.",
    "Please save 408-555-0142 with the rest of my recall notes.",
    "I will check the blueberries again tomorrow.",
]
SETTINGS = [
    {
        "name": "SHORT_TERM_N=4",
        "n": "4",
        "policy": "full",
        "user": "part3-n4",
        "session": "part3-n4",
    },
    {
        "name": "SHORT_TERM_N=12",
        "n": "12",
        "policy": "full",
        "user": "part3-n12",
        "session": "part3-n12",
    },
    {
        "name": "SHORT_TERM_N=30",
        "n": "30",
        "policy": "full",
        "user": "part3-n30",
        "session": "part3-n30",
    },
    {
        "name": "Eviction/compression policy",
        "n": "30",
        "policy": "compress",
        "user": "part3-compress",
        "session": "part3-compress",
    },
]


def repo_root() -> str:
    root = os.getcwd()
    if not os.path.exists(os.path.join(root, "code", "web_application", "main.py")):
        sys.exit("Run this from the data260-6491 folder.")
    return root


def port_open() -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", PORT)) == 0


def wait_until_up(proc: subprocess.Popen, timeout: int = 40) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            sys.exit("The API process exited before it was ready.")
        if port_open():
            return
        time.sleep(0.5)
    proc.terminate()
    sys.exit("The API did not start on port 8191.")


def wait_until_down(timeout: int = 15) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not port_open():
            return
        time.sleep(0.3)


def start_api(root: str, setting: dict) -> subprocess.Popen:
    env = os.environ.copy()
    env["SHORT_TERM_N"] = setting["n"]
    env["MEMORY_POLICY"] = setting["policy"]
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(PORT)],
        cwd=os.path.join(root, "code", "web_application"),
        env=env,
    )


def post_chat(user_id: str, session_id: str, message: str) -> dict:
    body = json.dumps({"user_id": user_id, "session_id": session_id, "message": message}).encode()
    request = urllib.request.Request(
        BASE + "/api/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.loads(response.read().decode())


def load_probes(root: str) -> list:
    path = os.path.join(root, "memory_probes.yaml")
    with open(path) as handle:
        return yaml.safe_load(handle)["probes"]


def score_reply(reply: str, expected: list) -> int:
    found = sum(1 for term in expected if term.lower() in (reply or "").lower())
    total = len(expected)
    if found == total:
        return 5
    if total > 1 and found == total - 1:
        return 4
    if found >= max(1, total / 2) and found < total:
        return 3 if found > 1 else 2
    if found == 1:
        return 2
    return 1


def rows_for(root: str, session_id: str) -> list:
    path = os.path.join(root, "reports", "hw06", "raw", "chat_turns.csv")
    with open(path) as handle:
        return [row for row in csv.DictReader(handle) if row["session_id"] == session_id]


def mean(rows: list, key: str) -> float:
    values = [float(row[key]) for row in rows]
    return sum(values) / len(values) if values else 0.0


def cost_for_10000(prompt_mean: float, completion_mean: float) -> float:
    turns = 30 * 10000
    return (prompt_mean * turns) / 1_000_000 * 1 + (completion_mean * turns) / 1_000_000 * 5


def write_report(root: str, results: list) -> None:
    ranked = sorted(results, key=lambda item: (-item["probe_quality"], item["prompt_tokens"]))
    best = ranked[0]
    worst = max(results, key=lambda item: item["prompt_tokens"])
    lines = [
        "# Part 3 memory cost",
        "",
        "| Setting | Mean prompt tokens/turn | Mean latency (ms) | Probe quality (1-5) |",
        "|---|---:|---:|---:|",
    ]
    for item in results:
        lines.append(
            f"| {item['name']} | {item['prompt_tokens']:.1f} | {item['latency_ms']:.0f} | {item['probe_quality']:.2f} |"
        )
    lines.extend(
        [
            "",
            f"Best setting: {best['name']}.",
            f"Worst setting: {worst['name']}.",
            "",
            "The best setting is the one with the highest probe score. If two scores are close, the lower prompt-token setting is preferred. The worst setting is the one with the highest mean prompt tokens.",
            "",
            "Cost of 10,000 conversations of 30 turns, at $1 per million input tokens and $5 per million output tokens:",
            "",
            f"- Best ({best['name']}): ${cost_for_10000(best['prompt_tokens'], best['completion_tokens']):.2f}",
            f"- Worst ({worst['name']}): ${cost_for_10000(worst['prompt_tokens'], worst['completion_tokens']):.2f}",
            "",
            "Prompt and completion token means come from Ollama. Primer, summary, short-term, and episodic token columns in chat_turns.csv are estimates of 4 characters per token, because Ollama returns only the total prompt size.",
            "",
            "The compression policy keeps the last 4 short-term messages in full, replaces older messages with one truncated line, and sends only the single closest episodic fact.",
        ]
    )
    out = os.path.join(root, "reports", "hw06", "METRICS.md")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as handle:
        handle.write("\n".join(lines) + "\n")
    with open(os.path.join(root, "reports", "hw06", "raw", "part3_summary.json"), "w") as handle:
        json.dump(
            {"results": results, "best": best["name"], "worst": worst["name"]}, handle, indent=2
        )


def run_setting(root: str, setting: dict, probes: list) -> dict:
    print(f"\n===== {setting['name']} =====", flush=True)
    proc = start_api(root, setting)
    answers = []
    try:
        wait_until_up(proc)
        messages = CONVERSATION + [probe["question"] for probe in probes]
        for index, message in enumerate(messages, start=1):
            print(f"  turn {index}/{len(messages)}", flush=True)
            payload = post_chat(setting["user"], setting["session"], message)
            if index > len(CONVERSATION):
                probe = probes[index - len(CONVERSATION) - 1]
                answers.append(
                    {
                        "id": probe["id"],
                        "question": probe["question"],
                        "reply": payload.get("reply", ""),
                        "score": score_reply(payload.get("reply", ""), probe["expected"]),
                    }
                )
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        wait_until_down()
    rows = rows_for(root, setting["session"])
    conversation_rows = rows[: len(CONVERSATION)]
    quality = sum(item["score"] for item in answers) / len(answers)
    result = {
        "name": setting["name"],
        "prompt_tokens": mean(conversation_rows, "prompt_tokens"),
        "completion_tokens": mean(conversation_rows, "completion_tokens"),
        "latency_ms": mean(conversation_rows, "latency_ms"),
        "probe_quality": quality,
        "answers": answers,
    }
    print(
        f"  prompt {result['prompt_tokens']:.1f}  latency {result['latency_ms']:.0f} ms  quality {quality:.2f}",
        flush=True,
    )
    return result


def main() -> None:
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    root = repo_root()
    if not os.path.exists(os.path.join(root, "memory_probes.yaml")):
        sys.exit("Copy memory_probes.yaml into the data260-6491 folder first.")
    if port_open():
        sys.exit("Port 8191 is already in use. Stop the running API, then run this again.")
    probes = load_probes(root)
    chosen = [
        item
        for item in SETTINGS
        if not only or only in item["name"] or only == item["policy"] or only == item["n"]
    ]
    results = [run_setting(root, setting, probes) for setting in chosen]
    raw = os.path.join(root, "reports", "hw06", "raw")
    os.makedirs(raw, exist_ok=True)
    with open(os.path.join(raw, "probe_answers.json"), "w") as handle:
        json.dump(results, handle, indent=2)
    if len(results) == len(SETTINGS):
        write_report(root, results)
        print("\nWrote reports/hw06/METRICS.md")
    else:
        print("\nPartial run. Run all four settings to write METRICS.md.")


if __name__ == "__main__":
    main()
