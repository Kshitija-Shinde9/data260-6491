# small script to show my router making every decision it can make
# and prints which node it picks each time.

from nodes import supervisor_node
from router import router_logic


def make_state(**changes):
    state = {
        "planner_proposal": {},
        "reviewer_feedback": {},
        "turn_count": 0,
        "max_turns": 5,
    }
    state.update(changes)
    return state


print("Testing every decision my router can make")
print("=" * 55)

situations = [
    ("nothing written yet",
     make_state()),

    ("planner wrote, nobody checked it",
     make_state(planner_proposal={"data": {"tags": ["a", "b", "c"]}})),

    ("reviewer found a problem",
     make_state(planner_proposal={"data": {}},
                reviewer_feedback={"data": {"issues": ["tag is too vague"]}})),

    ("reviewer was happy",
     make_state(planner_proposal={"data": {}},
                reviewer_feedback={"data": {"issues": []}})),

    ("too many turns already",
     make_state(turn_count=5,
                planner_proposal={"data": {}},
                reviewer_feedback={"data": {"issues": ["still bad"]}})),
]

for name, state in situations:
    print(f"\nSituation: {name}")
    decision = router_logic(state)
    print(f"   router picked: {decision}")

print()
print("=" * 55)
print("Testing the supervisor counter")
state = make_state(turn_count=0)
result = supervisor_node(state)
print(f"   it returned: {result}")
print("   it only returns the one key it changed, not the whole state")
