import json

from helpers import parse_and_coerce, parse_raw
from schema import validate_planner_output
from state import AgentState


JSON_SHAPE = (
    'Reply with ONE JSON object and nothing else:\n'
    '{"thought": "<string>", "message": "<under 60 words>", '
    '"data": {"tags": ["<exactly 3 tags>"], "summary": "<under 25 words>", "issues": []}}'
)


PLANNER_SYSTEM = (
    "You propose exactly 3 distinct, topical tags, preferring multi-word phrases, "
    "and a one-line summary for the given domain entity. "
    "Base the tags only on the title and content you are given."
)


REVIEWER_SYSTEM = (
    "You are given the Planner's proposed tags and summary. Critique that specific "
    "proposal, do not invent a new one. Check the tags are topical and not generic "
    "filler, that they are distinct from each other, and that the summary is under "
    "25 words with no code or markdown. "
    "If you find a problem, put a short description of it in data.issues and give "
    "corrected tags and summary. If the proposal is fine, echo the same tags and "
    "summary back and set data.issues to an empty list."
)


# ask the AI  question and cleans up whatever comes back
def ask_model(state: AgentState, system_prompt: str, user_prompt: str) -> dict:
    # every call goes through my HW1 model_client never Langchain or Ollama directly
    client = state["llm"]
    result = client.complete([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ])
    # I keep both: the raw answer for my Pydantic check, and the repaired one
    # so the rest of the graph always has something usable.
    raw = parse_raw(result.content)
    cleaned = parse_and_coerce(result.content, state["title"], state["content"], state["strict"])
    return cleaned, raw


# Planner, it comes up with 3 tags and a summary and writes them on its own line
def planner_node(state: AgentState) -> dict:
    print("---NODE: Planner---")

    attempt = state.get("planner_attempts", 0) + 1
    prompt = f"{state['task']}\n\n{JSON_SHAPE}"

    # if my rulebook rejected the last answer i paste the error straight back in
    # so the Planner knows exactly what to fix
    schema_error = state.get("schema_error", "")
    if schema_error:
        last = state.get("planner_proposal", {}).get("data", {})
        prompt = (
            f"{state['task']}\n\n"
            f"Your last answer was: {json.dumps(last)}\n"
            f"It broke the rules: {schema_error}\n"
            f"The rules are: exactly 3 tags, each 3 to 30 characters, "
            f"and a summary of at most 25 words.\n"
            f"Fix it and try again.\n\n{JSON_SHAPE}"
        )
        print(f"   retrying because the rules were broken: {schema_error}")

    # if the Reviewer complained last time i show the Planner what was wrong so it can fix it
    feedback = state.get("reviewer_feedback") or {}
    issues = feedback.get("data", {}).get("issues", [])
    if issues and not schema_error:
        prompt = (
            f"{state['task']}\n\n"
            f"Your last attempt was: {json.dumps(feedback.get('data', {}))}\n"
            f"The reviewer found these problems: {issues}\n"
            f"Fix them and try again.\n\n{JSON_SHAPE}"
        )
        print(f"   fixing {len(issues)} problem(s) the Reviewer found")

    proposal, raw = ask_model(state, PLANNER_SYSTEM, prompt)
    print(f"   model actually said: {raw.get('tags', [])}")

    # I check the RAW answer, not the repaired one. My HW1 coerce_reply pads
    # missing tags and trims long summaries, so validating after that would
    # always pass and I would never see a retry.
    is_valid, error = validate_planner_output(raw)
    schema_failures = state.get("schema_failures", 0) + (0 if is_valid else 1)
    if is_valid:
        print(f"   schema check: PASSED (attempt {attempt})")
    else:
        print(f"   schema check: FAILED (attempt {attempt}) - {error}")

    return {
        "planner_proposal": proposal,
        "schema_valid": is_valid,
        "schema_error": "" if is_valid else error,
        "planner_attempts": attempt,
        "schema_failures": schema_failures,
    }


# Reviewer, it looks at the Planners tags and says if there is a problem
def reviewer_node(state: AgentState) -> dict:
    print("---NODE: Reviewer---")

    proposal = state.get("planner_proposal") or {}
    prompt = (
        f"{state['task']}\n\n"
        f"The Planner proposed: {json.dumps(proposal.get('data', {}))}\n"
        f"Judge this proposal.\n\n{JSON_SHAPE}"
    )

    feedback, _ = ask_model(state, REVIEWER_SYSTEM, prompt)


    if state.get("force_issues"):
        feedback["data"]["issues"] = ["FORCED TEST ISSUE: always reject, to test the correction loop"]
        print("   (force_issues is ON, so I am rejecting this on purpose)")

    issues = feedback["data"]["issues"]
    print(f"   issues found: {issues if issues else 'none'}")

    return {"reviewer_feedback": feedback}


# supervisor: its only job is to tick the turn counter, it does not decide anything
def supervisor_node(state: AgentState) -> dict:
    turn = state.get("turn_count", 0) + 1
    print(f"---NODE: Supervisor--- (turn {turn} of {state.get('max_turns', 5)})")
    return {"turn_count": turn}
