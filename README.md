# data260-6491
Distributed System and Agentic AI

## Configuration (HW1)

| Value | Definition | This repo's value |
|---|---|---|
| SID4 | last 4 digits of SJSU ID | 6491 |
| PORT_BASE | 8000 + (SID4 mod 900) | 8191 |
| PREFIX | "s" + SID4 | s6491 |
| SEED | SID4 | 6491 |
| VERIFY_SEED | 260000 + SID4 | 266491 |
| DOMAIN_ID | SID4 mod 8 | 3 (Grocery supply and recall notices) |

## Repository layout

Shared application code lives at the repo root under `code/` and `src/` (per the
course's shared-code clarification) and gets extended across homeworks; each
homework's own report/results live under `reports/hw0N/`.
```
data260-6491/
├── code/web_application/   # index.html, script.js, Dockerfile, agents_demo.py, hw1_client.py
├── src/model_client.py     # exact path required by the assignment
├── reports/hw01/           # this homework's report, logs, raw data
├── scripts/                # helper scripts (Part 3 runner, self-check)
├── AGENT.md
├── DOMAIN_SCHEMA.md
└── README.md
```

## Part 1 - HTML/JS form, Docker, AWS ECS

Run locally with Docker:
```bash
cd code/web_application
docker build -t grocery-recall-app .
docker run -d -p 8191:80 --name grocery-recall-container grocery-recall-app
# open http://localhost:8191
```

Deployed to AWS ECS Fargate (single task) behind a public IP on port 8191; see
`reports/hw01/report.pdf` for the deployment screenshot and details.

## Part 2 - Agentic AI (Planner -> Reviewer -> Finalizer)

Requires Python 3.11/3.12 (a `conda create -n data260 python=3.11` environment works),
Ollama running locally with `qwen3:8b` pulled.

```bash
conda activate data260
cd code/web_application
python agents_demo.py --title "<entity title>" --content "<entity content>" \
  --email you@example.com --temperature 0.0
```

## Part 3 - Non-determinism experiment

Fixed input lives at `reports/hw01/cases/nondeterminism_input.json`. Runs the pipeline
20x at temperature 0.7 and 20x at temperature 0.0 against that exact input, saving raw
per-run tags/latency to `reports/hw01/raw/` and printing the computed metrics.

```bash
conda activate data260
python scripts/run_nondeterminism.py
```

## Part 4 - Model client & token accounting

```bash
conda activate data260
cd code/web_application
python hw1_client.py
```
Type messages at the `you>` prompt; `/stats` shows turn count, cumulative token counts,
and serialized conversation-history length without altering the history; `exit` prints
final cumulative totals. `AGENT.md` is loaded as the system prompt and asks for strict
bullet-only responses to any code-review request.

# How to run this project

## Part 1 — Web form (Docker)
cd code/web_application
docker build -t grocery-recall-app .
docker run -d -p 8191:80 --name grocery-recall-container grocery-recall-app
# open http://localhost:8191

## Part 2 — Agentic AI
# requires: Ollama running locally with qwen3:8b pulled
ollama pull qwen3:8b
cd code/web_application
python agents_demo.py --title "Trader Joe's Organic Frozen Blueberries, 16oz recall" \
  --content "Packaging seal failure noticed on the 16oz bag: a small tear near the top seal allowed frost buildup on the berries closest to the opening, discovered after purchase at the Stevens Creek location." \
  --email kshitija@example.com --temperature 0.0

## Part 3 — Non-determinism experiment (40 runs)
python scripts/run_nondeterminism.py

## Part 4 — Model client / token accounting CLI
python hw1_client.py
# type messages, use /stats to see running token counts, 'exit' to quit

## Verification
python verify_hw01.py
# writes reports/hw01/verification.json

### Conceptual answers (Part 4, Q7)

**Why is prior conversation context resent with every turn?** Because the model doesn't actually 
remember anything between calls every time I send a message, it's basically like talking to it 
for the first time again, except I attach the whole conversation so far along with it. All the 
"memory" is really just my code keeping a list and resending it each time, not the model remembering 
on its own.


**How is a system prompt different from a user message?** The system prompt is the standing 
instructions I set once at the start (like AGENT.md's bullet-only rule) it's not something 
the model treats as a question to answer, it's more like ground rules sitting in the
background. A user message is the actual thing being asked in that turn, which the
model responds to directly.


**Why do input tokens grow over a conversation?** Because every single turn,
I'm resending the entire conversation so far  system prompt plus everything
said before not just the newest message. So even if my new message is one word,
the input token count keeps climbing because of everything that came before it.


**What eventually limits that growth?** The model's context window a hard
cap on how many tokens it can take in at once. Once the conversation gets 
close to that limit, the request either gets cut off or rejected, or I'd have 
to start trimming/summarizing older turns myself to make room.

