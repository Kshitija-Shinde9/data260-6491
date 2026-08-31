# hw1_client.py - part 4 CLI demo, sits on top of src/model_client.py.
# keeps a running conversation (AGENT.md gets loaded in as the system prompt),
# prints token usage after every reply, and has a /stats command for checking
# the running totals without touching the actual history.
#
# run it with: python hw1_client.py
# type at the "you>" prompt, /stats for the running totals, exit/quit to leave.
import argparse
import json
import os
import sys

# repo layout: code/web_application/hw1_client.py, with src/model_client.py and
# AGENT.md two levels up at the repo root.
REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, REPO_ROOT)

from src.model_client import ModelClient


def load_agent_system_prompt() -> str:
    path = os.path.join(REPO_ROOT, "AGENT.md")
    with open(path) as f:
        return f.read()


def print_turn_stats(turn_count: int, usage) -> None:
    print(
        f"[turn {turn_count}] input_tokens={usage.input_tokens} "
        f"output_tokens={usage.output_tokens} total_tokens={usage.total_tokens}"
    )


def print_stats_command(history, turn_count: int, cum_input: int, cum_output: int) -> None:
    # reads existing state only; must not call the model or mutate history
    serialized_len = len(json.dumps(history))
    print(
        f"[/stats] turn_count={turn_count} "
        f"cumulative_input_tokens={cum_input} "
        f"cumulative_output_tokens={cum_output} "
        f"cumulative_total_tokens={cum_input + cum_output} "
        f"serialized_history_chars={serialized_len}"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=os.environ.get("SMOL_MODEL", "qwen3:8b"))
    ap.add_argument("--base_url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    ap.add_argument("--temperature", type=float, default=0.0)
    args = ap.parse_args()

    client = ModelClient(model=args.model, base_url=args.base_url, temperature=args.temperature)
    history = [{"role": "system", "content": load_agent_system_prompt()}]
    turn_count = 0
    cum_input = 0
    cum_output = 0

    print("HW1 model-client demo. Type a message, '/stats' for stats, or 'exit' to quit.\n")

    while True:
        try:
            user_input = input("you> ").strip()
        except EOFError:
            break
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit"):
            break
        if user_input == "/stats":
            print_stats_command(history, turn_count, cum_input, cum_output)
            continue

        history.append({"role": "user", "content": user_input})
        result = client.complete(history)
        history.append({"role": "assistant", "content": result.content})

        turn_count += 1
        cum_input += result.usage.input_tokens
        cum_output += result.usage.output_tokens

        print(f"assistant> {result.content}")
        print_turn_stats(turn_count, result.usage)
        print()

    print(
        f"[exit] turn_count={turn_count} "
        f"cumulative_input_tokens={cum_input} "
        f"cumulative_output_tokens={cum_output} "
        f"cumulative_total_tokens={cum_input + cum_output}"
    )


if __name__ == "__main__":
    main()
