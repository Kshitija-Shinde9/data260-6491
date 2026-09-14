# METRICS.md - DATA-260 HW2

All numbers below come from the CSV files in `reports/hw02/raw/`. Nothing here is
typed by hand. Every run used the frozen input in `reports/hw02/cases/schema_input.json`
except Task 5, which used `reports/hw02/cases/adversarial_input.json`.

| | |
|---|---|
| SID4 | 6491 |
| PORT_BASE | 8191 |
| SEED / VERIFY_SEED | 6491 / 266491 |
| DOMAIN_ID | 3 (grocery supply and recall notices) |
| Model | qwen3:8b served locally by Ollama 0.33.2 |
| Temperature | 0.0 |
| Hardware | MacBook Air, Apple M4, 16 GB RAM |
| Python | 3.11.16 (conda env `data260`) |

---

## Task 3 - outcome over 30 runs

Fixed input, turn ceiling 10, 30 runs.
Raw data: `raw/task3_schema_runs.csv`

| Outcome over 30 runs | Count | Mean latency (ms) |
|---|---|---|
| Valid first attempt | 30 | 21,440 |
| Valid after 1 retry | 0 | - |
| Valid after 2+ retries | 0 | - |
| Hit turn ceiling | 0 | - |
| **Total** | **30** | |

Extra detail:

| | |
|---|---|
| Schema failures across all 30 runs | 0 |
| Turns used | 3 in every run |
| Latency min / median / max | 19,820 / 20,373 / 25,360 ms |
| Distinct tag sets produced | **1** |

**What this shows.** Every run passed the Pydantic schema on the first attempt, so the
retry path never fired for this input. All 30 runs produced the same three tags, not
just similar ones. That is because the frozen input uses temperature 0.0, where the
model is deterministic. This matches HW1, where temperature 0.0 gave 1 distinct tag set
across 20 runs and temperature 0.7 gave 19. The latency spread of 5.5 seconds is just
normal variation in how quickly the laptop served the model, since every run did the
same amount of work.

---

## Task 4 - turn ceiling 2 compared with turn ceiling 10

Same frozen input and same model settings for both. 20 runs each.
Raw data: `raw/task4_ceiling_2.csv` and `raw/task4_ceiling_10.csv`

| Turn ceiling | Runs | Completed | Completion rate | Mean latency (ms) | Turns used |
|---|---|---|---|---|---|
| 2 | 20 | 0 | **0%** | 12,213 | 2 in every run |
| 10 | 20 | 20 | **100%** | 22,425 | 3 in every run |

A run counts as completed only if it did not run out of turns. A valid answer that was
cut off before the Reviewer approved it still counts as abandoned.

**Chosen for deployment: turn ceiling 10.**

The ceiling of 2 failed every run, and the reason is structural rather than bad luck.
The graph needs three supervisor turns in its shortest path: one to reach the Planner,
one to reach the Reviewer, and one to end. A ceiling of 2 makes that third turn
impossible. In all 20 runs the Planner produced a valid answer that was then discarded
without ever being reviewed.

The ceiling of 2 was about 45% faster, but only because it gave up before doing the
work. A ceiling of 10 finished every run in 3 turns and left 7 turns of headroom, which
matters because the Task 5 input needed 8 Planner attempts. Paying roughly 10 extra
seconds per run to move from a 0% to a 100% completion rate is the correct trade.

---

## Task 5 - adversarial input

Adversarial input, turn ceiling 10, 5 runs.
Raw data: `raw/task5_adversarial.csv`

| Outcome over 5 adversarial runs | Count | Mean latency (ms) |
|---|---|---|
| Valid first attempt | 0 | - |
| Valid after 1 retry | 0 | - |
| Valid after 2+ retries | 0 | - |
| Hit turn ceiling | **5** | **106,896** |
| **Total** | **5** | |

| | |
|---|---|
| Reached the ceiling | **5 of 5 runs (100%)** |
| Planner attempts | 8 in every run |
| Turns used | 10 in every run |
| Schema failures | **0** |
| Latency min / max | 102,033 / 119,421 ms |
| Slowdown against Task 3 | **5.0x** |

**Why it causes trouble.** The adversarial input is a recall notice containing
instructions that contradict the schema. It asks for five or six tags when the rule is
exactly three, and a summary of at least sixty words when the rule caps it at twenty
five. A real user could type text like this into the form.

The Pydantic schema never failed once across the 5 runs. The looping was caused
entirely by the Reviewer. From attempt 3 onwards the Planner returns identical tags
every time and the Reviewer returns identical complaints every time, so the two agents
are deadlocked. The Reviewer asks for the tags to cover six products when only three
tags are allowed, and for a longer summary when 25 words is the limit. The Planner
cannot satisfy the Reviewer without breaking the schema, so nothing changes until the
turn ceiling stops the run.

**Proposed fix.** Give the Reviewer the schema rules in its system prompt. It currently
knows nothing about the three tag limit or the 25 word limit, so it asks for things that
are impossible. Telling it not to request more tags or a longer summary, and to accept
the best three tags when everything cannot be covered, removes the cause rather than the
symptom. A cheaper fallback would be to stop early when the Planner returns identical
output twice in a row, which would have cut each run from 8 attempts to 3, but that only
hides the symptom.

---

## Comparison across all three experiments

| | Task 3 (normal) | Task 4 ceiling 2 | Task 4 ceiling 10 | Task 5 (adversarial) |
|---|---|---|---|---|
| Runs | 30 | 20 | 20 | 5 |
| Completion rate | 100% | 0% | 100% | 0% |
| Planner attempts | 1 | 1 | 1 | 8 |
| Turns used | 3 | 2 | 3 | 10 |
| Mean latency (ms) | 21,440 | 12,213 | 22,425 | 106,896 |
| Schema failures | 0 | 0 | 0 | 0 |

Across all 75 runs the Pydantic schema never rejected a single answer. Both failure
modes seen in this homework came from elsewhere: a turn ceiling set too low for the
graph, and a Reviewer asking for output the schema forbids.
