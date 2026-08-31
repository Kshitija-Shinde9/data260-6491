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

### Conceptual answers (Part 4, Q7)

**Why is prior conversation context resent with every turn?** The model itself is
stateless between API calls -- it has no memory of earlier turns unless the full
conversation history is included again in the request. The "memory" of a conversation
lives entirely on the client side (here, the `history` list in `hw1_client.py`), not on
the model/server side.

**How is a system prompt different from a user message?** A system prompt sets
standing, persistent instructions/behavior for the whole conversation (here, `AGENT.md`'s
bullet-only code-review rule) and is written by the developer, not the end user; it isn't
something the model treats as a request to respond to. A user message is a single turn's
actual input, one of potentially many, that the model is expected to respond to directly.

**Why do input tokens grow over a conversation?** Because the entire history (system
prompt + every prior user and assistant message) is resent as the "input" on every turn,
input token count only ever grows (or stays flat), even if the newest message itself is
short -- it's cumulative, not per-message.

**What eventually limits that growth?** The model's context window (its maximum token
limit, e.g. `num_ctx` for a locally served model). Once resent history approaches that
limit, requests either get truncated, get rejected, or the application has to actively
manage the history (summarizing or dropping older turns) to stay within budget.
