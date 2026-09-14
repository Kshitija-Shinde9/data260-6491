from typing import Any, Dict, TypedDict


# this is the one common state that all my agents read from and write to
class AgentState(TypedDict):
    # What the recall notice is about, so both agents know the job.
    title: str
    content: str
    email: str

    # instructions i am giving the agents written out as a sentence
    task: str

    # turns on the stricter tag checks I wrote in HW1
    strict: bool

    # my HW1 model_client so the agents can talk to the AI through it
    llm: Any

    # the tags and summary the Planner came up with
    planner_proposal: Dict[str, Any]

    # what the reviewer said about them including any problems it found
    reviewer_feedback: Dict[str, Any]

    # how many turns have happene and the most i allow before stopping
    turn_count: int
    max_turns: int

    # Test switch. When True the Reviewer always complains, so I can watch the loop.
    force_issues: bool

    # Did the Planner's last answer pass my Pydantic rules, and if not what was wrong.
    schema_valid: bool
    schema_error: str

    # How many times the Planner has tried, so I can classify runs in Part 4.
    planner_attempts: int

    # How many times the answer broke my rules, counted apart from reviewer retries.
    schema_failures: int
