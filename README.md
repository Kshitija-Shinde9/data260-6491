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
type messages, use /stats to see running token counts, 'exit' to quit

## Verification
python verify_hw01.py
writes reports/hw01/verification.json

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

## Homework 2

HW2 extends the same codebase. The web application gains a FastAPI backend, and a
new agent graph replaces the sequential pipeline from HW1.

### Repository layout added in HW2

```
code/web_application/   main.py and static/ added alongside the HW1 files
code/agent_graph/       state.py, nodes.py, router.py, workflow.py, schema.py, helpers.py
scripts/run_experiment.py
scripts/verify_hw02.py
reports/hw02/           cases/, raw/, METRICS.md, RUN_LOG.txt, AI_USE.md, verification.json
```

### Requirements

Python 3.11 in a conda environment called `data260`, with fastapi, uvicorn, pydantic
and langgraph installed. Parts 3 and 4 also need Ollama running locally with the
`qwen3:8b` model pulled.

```bash
conda activate data260
ollama serve          # in a separate terminal, if it is not already running
ollama pull qwen3:8b  # only needed once
```

### Part 1 and Part 2 - the web application

```bash
cd code/web_application
python main.py
```

Then open http://localhost:8191

The server must be started from inside `code/web_application`, because `main.py`
refers to the `static` folder by a relative path. Records live in memory, so
restarting the server resets them to the three seeded notices.

Endpoints:

| Method | Path | Question |
|---|---|---|
| GET | `/api/recalls` | list, and Q4 search through `?search=` |
| POST | `/api/recalls` | Q1 add a record |
| PUT | `/api/recalls/{id}` | Q2 update a record |
| DELETE | `/api/recalls/highest` | Q3 delete the highest ID |
| GET | `/docs` | FastAPI interactive documentation |

### Part 3 - the agent graph

```bash
cd code/agent_graph
python workflow.py                                  # a normal run
python workflow.py --force_issues --max_turns 5     # the correction loop test
```

`--force_issues` makes the Reviewer reject every proposal, which is how the
assignment asks for the correction loop to be demonstrated. It is off by default.

Individual pieces can be checked on their own:

```bash
python try_nodes.py     # the Planner and Reviewer
python try_router.py    # every router decision
python try_schema.py    # the Pydantic rules
```

### Part 4 - the experiments

Run from the repository root. Each task writes its own CSV to `reports/hw02/raw/`
as it goes, so stopping one does not lose the runs already finished.

```bash
python scripts/run_experiment.py --task 3    # 30 runs on the frozen input
python scripts/run_experiment.py --task 4    # 20 runs at ceiling 2, then 20 at ceiling 10
python scripts/run_experiment.py --task 5    # 5 runs on the adversarial input
```

Add `--runs N` to do a shorter test run first.

All 75 runs together take roughly 45 minutes of model time on an Apple M4. Run one
task at a time, never two at once, or they compete for the model and the latency
numbers become meaningless.

### Self check

```bash
python scripts/verify_hw02.py
```

Writes `reports/hw02/verification.json`. Two of its checks need the web application
running on port 8191 and Ollama running on port 11434, so start those first if you
want a clean pass.

### Model configuration used for all reported results

qwen3:8b (8.2B parameters, Q4_K_M) served by Ollama 0.33.2 at temperature 0.0.
Every model call inside a node goes through `src/model_client.py`, the adapter
written in HW1, rather than calling Ollama or LangChain directly.

## Homework 3

HW3 extends the same codebase again. The web application gains a login system,
and a new retrieval-only RAG comparison is added over a local domain corpus.

### Repository layout added in HW3

```
code/web_application/routers/auth.py    the login/logout/dashboard routes
code/web_application/templates/         base.html, index.html, login.html, dashboard.html
scripts/prove_session_security.py       session-security evidence for Part 1
```

`code/web_application/main.py` was extended rather than replaced: it now adds
`SessionMiddleware` and includes the auth router. The `/` route, which used to
return the HW2 recall list directly, now shows the public welcome page; the
recall list moved behind the login onto `/dashboard`. The HW2 API endpoints
under `/api/recalls` are unchanged.

### Requirements

```bash
conda activate data260
pip install -r code/web_application/requirements.txt
```

### Part 1 - the authentication app

```bash
cd code/web_application
python -m uvicorn main:app --host 127.0.0.1 --port 8191
```

Then open http://localhost:8191 in **Chrome or Firefox**. The session cookie is
marked `Secure`; those two browsers treat `localhost` as a trustworthy origin
and still send it over HTTP, whereas Safari does not and the login will appear
to silently fail there.

Demo account: `kshitija` / `Recall@6491`

| Route | Purpose |
|---|---|
| `/` | public welcome page for the domain |
| `/login` | login form, with a Bootstrap alert on bad credentials |
| `/dashboard` | protected - the recall records, requires a live session |
| `/logout` | destroys the session and returns to `/` |
| `/api/recalls` | the HW2 API, unchanged |
| `/docs` | FastAPI interactive documentation |

Session cookie attributes, all three set in `main.py`:

| Attribute | Set by | Effect |
|---|---|---|
| `HttpOnly` | Starlette default | JavaScript cannot read the cookie |
| `Secure` | `https_only=True` | not sent over plain HTTP |
| `SameSite=lax` | `same_site="lax"` | not attached to cross-site POSTs |

Idle timeout defaults to 900 seconds and is set with the `SESSION_MAX_AGE`
environment variable. Starlette's session is stateless, so a cookie captured
before logout would otherwise still validate afterwards. `routers/auth.py`
therefore also keeps a server-side table of live session ids, and logging out
deletes the id - which is what makes a logged-out cookie genuinely unusable.

### Part 1 self-check

```bash
python scripts/prove_session_security.py
```

Starts its own copy of the app on port 8191 with a five-second idle timeout and
prints the `Set-Cookie` header plus proof that logged-out and idle-expired
sessions are both refused at `/dashboard`. Stop any server already running on
8191 first. It does not modify application code.
