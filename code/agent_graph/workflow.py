import argparse
import os
import sys

# src/model_client.py lives at the repo root, two levels up from this file.
# Same pattern I used in HW1 hw1_client.py.
REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph.graph import END, StateGraph

from nodes import planner_node, reviewer_node, supervisor_node
from router import router_logic
from src.model_client import ModelClient
from state import AgentState


# wires my 3 nodes together into one graph
def build_workflow():
    workflow = StateGraph(AgentState)

    # My workers. Each one is a plain function that takes the state.
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("reviewer", reviewer_node)

    #  supervisor always goes first
    workflow.set_entry_point("supervisor")

    # After the supervisor, the router picks which door to take.
    workflow.add_conditional_edges(
        "supervisor",
        router_logic,
        {
            "planner": "planner",
            "reviewer": "reviewer",
            "END": END,
        },
    )

    #  two lines are what make it a loop. After the planner or the reviewer
    # has worked the state always goes back to the supervisor who decides again.
    workflow.add_edge("planner", "supervisor")
    workflow.add_edge("reviewer", "supervisor")

    return workflow.compile()


# builds the first version of the shared state before anything has run.
def build_initial_state(title, content, email, max_turns, strict=False, force_issues=False):
    task = (
        f'Give exactly 3 topical tags and a one-line summary for this grocery recall notice. '
        f'Title: "{title}". Content: "{content}".'
    )
    return {
        "title": title,
        "content": content,
        "email": email,
        "task": task,
        "strict": strict,
        "llm": ModelClient(),
        "planner_proposal": {},
        "reviewer_feedback": {},
        "turn_count": 0,
        "max_turns": max_turns,
        "force_issues": force_issues,
        "schema_valid": True,
        "schema_error": "",
        "planner_attempts": 0,
        "schema_failures": 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="Trader Joe's Organic Frozen Blueberries, 16oz")
    parser.add_argument("--content", default="The bag seal was torn near the top and there was frost buildup on the berries.")
    parser.add_argument("--email", default="kshitija@example.com")
    parser.add_argument("--max_turns", type=int, default=5)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--force_issues", action="store_true",
                        help="make the Reviewer always complain, to test the correction loop")
    args = parser.parse_args()

    graph = build_workflow()
    state = build_initial_state(args.title, args.content, args.email, args.max_turns, args.strict, args.force_issues)

    print("=" * 60)
    print("RECALL:", args.title)
    print("TURN CEILING:", args.max_turns)
    if args.force_issues:
        print("MODE: force_issues is ON - the Reviewer will always reject, to test the loop")
    print("=" * 60)

    # .stream() gives me each step as it happens instead of only the final answer,
    # so I can watch the graph move between nodes.
    final = {}
    for step in graph.stream(state):
        for node_name, update in step.items():
            final.update(update)

    print()
    print("=" * 60)
    print("FINISHED after", final.get("turn_count", 0), "turns")
    tags = final.get("planner_proposal", {}).get("data", {}).get("tags", [])
    summary = final.get("planner_proposal", {}).get("data", {}).get("summary", "")
    issues = final.get("reviewer_feedback", {}).get("data", {}).get("issues", [])
    print("FINAL TAGS   :", tags)
    print("FINAL SUMMARY:", summary)
    print("LAST REVIEW  :", issues if issues else "no issues")
    print("=" * 60)


if __name__ == "__main__":
    main()
