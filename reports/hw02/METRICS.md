# METRICS.md - DATA-260 HW2

All numbers below come from the CSV files in `reports/hw02/raw/`. 
Every run used the frozen input in `reports/hw02/cases/schema_input.json`


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


**Chosen for deployment: turn ceiling 10.**

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

**Why it causes trouble.** 
my adversarial input is a recall notice with instructions inside it that fight my own schema. it asks for five or six tags when my rule is exactly three. it asks for a summary of at least sixty words when my rule caps it at twenty five. a real user could type something like this into my form so it felt like a fair test.
it hit the turn ceiling in all five runs. every run used the full ten turns and eight planner attempts. the average was about 107000 ms which is five times slower than my normal input at about 21000 ms.
the surprising part is that my pydantic schema never failed once. the looping was not caused by the schema. it was caused by the reviewer.
from attempt three onwards the planner gives identical tags every time and the reviewer gives identical complaints every time. they are deadlocked. the reviewer asks for things my schema forbids. it wants the tags to cover six products when only three tags are allowed. it wants a longer summary when twenty five words is the limit. the planner cannot satisfy the reviewer without breaking the schema so nothing changes and the turns run out.


**Proposed fix.**
my fix is to tell the reviewer what the schema rules are.
my reviewer prompt currently says nothing about the three tag limit or the twenty five word limit so it asks for impossible things. i would add the rules to its prompt. the planner must give exactly three tags of three to thirty characters and a summary of at most twenty five words. do not ask for more tags or a longer summary because that breaks the schema. if everything cannot be covered within those limits then accept the best three tags.
this fixes the cause rather than the symptom. once the reviewer stops asking for the impossible the planner can satisfy it and the run finishes.


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

