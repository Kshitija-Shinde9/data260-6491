import os
import sys

REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))



from src.model_client import ModelClient
from nodes import planner_node, reviewer_node

state = {
    "title": "Trader Joe's Organic Frozen Blueberries, 16oz",
    "content": "The bag seal was torn near the top and there was frost buildup on the berries.",
    "email": "kshitija@example.com",
    "task": "Give exactly 3 topical tags and a one-line summary for this grocery recall notice.",
    "strict": False,
    "llm": ModelClient(),
    "planner_proposal": {},
    "reviewer_feedback": {},
    "turn_count": 0,
    "max_turns": 5,
}

print("Recall:", state["title"])
print()

state.update(planner_node(state))
state.update(reviewer_node(state))

print()
print("Planner wrote :", state["planner_proposal"]["data"]["tags"])
print("Reviewer said :", state["reviewer_feedback"]["data"]["issues"] or "no problems")
