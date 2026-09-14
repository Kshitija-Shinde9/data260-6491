from typing import Literal

from state import AgentState



def router_logic(state: AgentState) -> Literal["planner", "reviewer", "END"]:
    turn = state.get("turn_count", 0)
    max_turns = state.get("max_turns", 5)
    proposal = state.get("planner_proposal") or {}
    feedback = state.get("reviewer_feedback") or {}


    if turn >= max_turns:
        print(f"   router: hit the turn ceiling of {max_turns}, stopping")
        return "END"

    # nobody has proposed anything yet so the Planner goes first
    if not proposal:
        print("   router: no proposal yet -> planner")
        return "planner"

    # the answer broke my Pydantic rules, so send it back to the Planner to fix
    if not state.get("schema_valid", True):
        print("   router: answer broke the schema rules -> back to planner")
        return "planner"

    # there is a proposal but nobody has checked it so the Reviewer goes
    if not feedback:
        print("   router: proposal not reviewed yet -> reviewer")
        return "reviewer"

    # Reviewer has been. if it found problems send it back to the Planner
    issues = feedback.get("data", {}).get("issues", [])
    if issues:
        print(f"   router: reviewer found {len(issues)} issue(s) -> back to planner")
        return "planner"

    # reviewer was happy so we are finished.
    print("   router: reviewer had no issues -> END")
    return "END"
