# AI_USE.md - DATA-260 HW2

> Read this through and change anything that does not match how you remember it.
> These answers should be yours.

## 1. What I used an AI assistant for, and what I did myself

I used an AI assistant a lot in this homework, more as something to explain things to me
than as something to write code for me. The parts I leaned on it for were understanding
what langgraph actually is, working out what the supervisor pattern means in practice,
and getting the structure of the four agent graph files right. I also used it to help me
word the longer explanations in this report.

What I did myself was run every experiment, take every screenshot, check that each piece
worked before moving on to the next one, and decide what my adversarial input should be.
I also chose the turn ceiling for deployment based on my own numbers rather than being
told which one to pick.

The pieces I reused from HW1 are my own earlier work: `src/model_client.py` and the four
cleanup functions in `helpers.py` that strip the model's rambling and force its answer
into a usable shape.

## 2. One AI-produced output that was wrong or unsuitable

The first version of my `classify()` function counted every Planner attempt as a schema
retry. That was wrong, because the Planner is sent back for two different reasons: when
my Pydantic schema rejects the answer, and separately when the Reviewer objects to it.
Counting them together would have put runs into the wrong buckets in my Task 3 table.

There was a second, worse problem. My Part 4 validation was checking the answer after my
HW1 `coerce_reply()` had already repaired it. That function pads a short tag list up to
three tags and trims a long summary down to 25 words, so by the time Pydantic saw the
answer it was always valid. My retry path could never fire, and all 30 runs would have
come back as "valid first attempt" for a reason that had nothing to do with the model.

## 3. How I detected the problem and verified the result

I found the classification problem by reading the actual console output from a test run
of my adversarial input. The run reported 8 attempts and looked like it had failed
validation repeatedly, but every line said `schema check: PASSED`. Those two things could
not both be true, which is what made me look closer.

I found the coercion problem the same way. I ran my adversarial input expecting it to
break the schema, and it passed first time. That did not make sense for an input designed
to be difficult, so I printed the raw model reply next to the repaired one and could see
my own HW1 code fixing the answer before the check happened.

I verified the fixes by rerunning. The adversarial input then went from 1 attempt to 8,
and hit the turn ceiling in 5 out of 5 runs.

## 4. What I changed, and why it works now

For the coercion problem I added `parse_raw()` to `helpers.py`. It pulls the JSON out of
the model's reply without repairing anything, and `planner_node` now validates that raw
version. `coerce_reply()` still runs, so the rest of the graph always has something
usable, but it no longer hides schema failures from the check.

For the classification problem I added a separate `schema_failures` counter to my state.
My CSVs now record `attempts` and `schema_failures` as two different columns, and
`classify()` sorts runs by schema failures rather than total attempts. I also made a run
count as abandoned if it used up its turn ceiling, even if the last answer happened to be
valid, because an answer the Reviewer never approved is not a finished run.

This works because the check now happens on what the model actually produced, and the two
loops in my graph are counted separately instead of being confused with each other. Across
all 75 runs I can now say honestly that the schema rejected nothing, and that both failure
modes I saw came from somewhere else: a turn ceiling set too low for the graph, and a
Reviewer asking for output my schema does not allow.
