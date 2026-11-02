# HW8 Part 1 - TODO (run on any laptop)

Backend service request/response over Kafka, built on top of the HW1-HW7 recall app.

| Value | This repo |
|---|---|
| SID4 / PREFIX / PORT_BASE | 6491 / `s6491` / `8191` |
| Primary entity | Recall notice -> `CREATE_RECALL`, `GET_RECALL`, `recall_id` |
| Request topic | `s6491_recall_requests` |
| Response topic | `s6491_recall_responses` |
| Worker consumer group | `s6491_recall_worker` |
| Kafka | `apache/kafka:3.9.0`, single node KRaft (no ZooKeeper) |
| Containers | `s6491_kafka`, `s6491_worker`, `s6491_api` |

> Topic naming: the handout says to replace ENTITY/entity with your entity name
> (`entity_id` -> `course_id`), so `<PREFIX>_entity_requests` became `s6491_recall_requests`.
> If your instructor wants the literal names, set them for every container in
> `docker-compose.yml`: `REQUEST_TOPIC=s6491_entity_requests` and
> `RESPONSE_TOPIC=s6491_entity_responses`. No code changes are needed.

---

## 0. Files that are new or changed for HW8

New:
```
code/kafka_service/__init__.py
code/kafka_service/config.py
code/kafka_service/flow_log.py
code/kafka_service/recall_entity.py
code/kafka_service/kafka_io.py
code/kafka_service/kafka_client.py
code/kafka_service/worker.py
code/kafka_service/homework_demo.py
code/kafka_service/requirements-kafka.txt
code/kafka_service/Dockerfile
code/kafka_service/docker-compose.yml
code/web_application/kafka_api.py
code/web_application/routers/kafka_recalls.py
scripts/test_hw08_part1.py
scripts/verify_hw08.py
reports/hw08/logs/.gitkeep
reports/hw08/HW8_PART1_TODO.md   (this file)
```
Changed (extended, nothing removed):
```
code/web_application/main.py           + include kafka_recalls router
code/web_application/requirements.txt  + confluent-kafka==2.12.1
README.md                              + Homework 8 section
```

The Docker build only needs `code/kafka_service/` plus the two `code/web_application`
files above. The zip `data260-6491-hw08.zip` holds exactly those files, plus the HW8
edits to `main.py`, `requirements.txt`, and `README.md`. Unzipping it **into** the
existing repo adds the new files and overwrites only those three. Nothing else in the
repo is deleted.

---

## 1. One-time setup on the other laptop

- [ ] The full HW1-HW7 repo is already on this laptop.
- [ ] Put `data260-6491-hw08.zip` **inside the repo root** (the folder that contains
      `README.md` and `code/`).
- [ ] Apply the zip with one command. Run it from the repo root.

macOS / Linux:

```bash
cd /path/to/data260-6491
rm -rf /tmp/hw08-unpack
unzip -q -o data260-6491-hw08.zip -d /tmp/hw08-unpack
rsync -a --exclude '.DS_Store' --exclude '__MACOSX' /tmp/hw08-unpack/data260-6491-hw08/ ./
rm -rf /tmp/hw08-unpack
find code/kafka_service scripts/test_hw08_part1.py scripts/verify_hw08.py reports/hw08 -type f
```

Windows PowerShell (run from the repo root):

```powershell
cd C:\path\to\data260-6491
$tmp = Join-Path $env:TEMP "hw08-unpack"
if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
Expand-Archive -LiteralPath .\data260-6491-hw08.zip -DestinationPath $tmp -Force
robocopy (Join-Path $tmp "data260-6491-hw08") . /E /XF .DS_Store /NFL /NDL /NJH /NJS
Remove-Item $tmp -Recurse -Force
Get-ChildItem -Recurse code\kafka_service, scripts\test_hw08_part1.py, scripts\verify_hw08.py, reports\hw08
```

`robocopy` prints a summary and exits with a code from 0 to 7 when the copy worked.
A code of 8 or higher means it failed.

Check that these showed up:

```text
code/kafka_service/docker-compose.yml
code/kafka_service/homework_demo.py
code/web_application/kafka_api.py
code/web_application/routers/kafka_recalls.py
scripts/test_hw08_part1.py
scripts/verify_hw08.py
reports/hw08/HW8_PART1_TODO.md
```

- [ ] Install **Docker Desktop** and start it. Wait until it says "Engine running".
- [ ] Check it works:
  ```bash
  docker --version
  docker compose version
  ```
- [ ] Stay in the repo root. Every command below is run from there.
- [ ] Python 3.10+ is needed only for `scripts/verify_hw08.py` and the offline tests.
      They use only the standard library, so no `pip install` is needed.
- [ ] Make sure nothing else is using ports **8191** or **9094**. Stop the HW1-HW7
      uvicorn server if it is running.
  ```bash
  # macOS / Linux
  lsof -i :8191 -i :9094
  # Windows PowerShell
  netstat -ano | findstr ":8191 :9094"
  ```

---

## 2. Offline sanity check (no Docker needed, about 1 second)

```bash
python3 scripts/test_hw08_part1.py        # Windows: python scripts\test_hw08_part1.py
```
Expected: `8/8 tests passed`. Without FastAPI installed, the API-wrapper test prints
`(skipped: fastapi/httpx not installed)` and still counts as a pass.
If anything says FAIL, stop and fix that first.

---

## 3. Start Kafka, the worker, and the FastAPI wrapper

```bash
docker compose -f code/kafka_service/docker-compose.yml up -d --build
```
The first run downloads `apache/kafka:3.9.0` and `python:3.11-slim`, which takes a few
minutes. Then wait about 20 seconds and check:

```bash
docker compose -f code/kafka_service/docker-compose.yml ps
```
All three should be `running`, and kafka should be `(healthy)`. If the worker or api shows
`restarting`, run `docker logs s6491_worker` (see Troubleshooting at the bottom).

Start with an empty message-flow log so the evidence only has this run:
```bash
# macOS / Linux
: > reports/hw08/logs/message_flow.log
# Windows PowerShell
Set-Content reports/hw08/logs/message_flow.log ""
```

---

## 4. SCREENSHOT 1 - Docker containers running + startup logs

Run these three commands in one terminal, one after the other:
```bash
docker ps
docker logs s6491_worker
docker logs s6491_api
```

**📸 TAKE SCREENSHOT 1 now.** It must show:
- [ ] `docker ps` with **3 rows**: `s6491_kafka` (image `apache/kafka:3.9.0`, port
      `0.0.0.0:9094->9094/tcp`), `s6491_worker`, and `s6491_api` (port
      `127.0.0.1:8191->8191/tcp`), all with STATUS `Up ...`.
- [ ] Worker log line: **`Consumer is ready and listening...`**
      (just above it: `... | WORKER | READY | assigned s6491_recall_requests[0] in group s6491_recall_worker`).
- [ ] API log line: **`FastAPI server started at http://127.0.0.1:8191`**
      (plus `Kafka topics: requests=s6491_recall_requests responses=s6491_recall_responses`
      and uvicorn's `Application startup complete.`).

If the window is too small, take one screenshot of `docker ps` and one of the two logs (1a, 1b).

---

## 5. SCREENSHOT 2 - CREATE_RECALL and GET_RECALL execution (homework_demo.py)

```bash
docker compose -f code/kafka_service/docker-compose.yml run --rm demo
```
This runs `code/kafka_service/homework_demo.py` inside the Kafka network. It prints
STEP 1 through STEP 10 in the order the handout asks for.

**📸 TAKE SCREENSHOT 2a** (scroll to the top of the output). It must show:
- [ ] `Request topic : s6491_recall_requests` / `Response topic: s6491_recall_responses`
- [ ] STEP 1 with `correlation_id = <uuid>`
- [ ] STEP 2 with the recall `data` (product_name, supplier, recall_code, recall_type,
      description, affected_units)
- [ ] The `CREATE_RECALL response` JSON with `"success": true`,
      `"recall_id": "<uuid>"`, `"message": "Recall created"`, and the **same**
      `"correlation_id"` as STEP 1
- [ ] STEP 7 `recall_id = <uuid>`

**📸 TAKE SCREENSHOT 2b** (bottom of the output). It must show:
- [ ] STEP 8 / STEP 9 and the `GET_RECALL response` with `"success": true` and the
      `"recall": {...}` object
- [ ] STEP 10 with `preserved=True` for both CREATE_RECALL and GET_RECALL, and
      `retrieved recall_id matches   : True`

Optional extra evidence for the "General Requirements" (validation and errors):
```bash
docker compose -f code/kafka_service/docker-compose.yml run --rm demo \
  python code/kafka_service/homework_demo.py --with-errors
```
**📸 OPTIONAL SCREENSHOT 2c**: the `EXTRA` section showing `Unknown operation`,
`Missing required field(s): ...`, `recall_type must be one of ...`, and `Recall not found`,
each with `correlation_id preserved: True`.

---

## 6. SCREENSHOT 3 - Kafka message flow through the FastAPI wrapper

This shows FastAPI receiving the call, sending to Kafka, the worker processing it, and
FastAPI returning the response to the caller.

Pick one correlation_id:
```bash
# macOS / Linux
CORR=$(uuidgen | tr 'A-Z' 'a-z'); echo $CORR
# Windows PowerShell
$CORR = [guid]::NewGuid().ToString(); $CORR
```

CREATE_RECALL through the API (`-i` shows the `X-Correlation-ID` response header):
```bash
# macOS / Linux
curl -s -i -X POST http://127.0.0.1:8191/api/kafka/recalls \
  -H "Content-Type: application/json" -H "X-Correlation-ID: $CORR" \
  -d '{"product_name":"Kirkland Signature Trail Mix, 4lb","supplier":"Costco Wholesale","recall_code":"REC-0303","recall_type":"Undeclared Allergen","description":"Ingredient panel does not list peanuts but peanuts are in the bag.","affected_units":75}'
```
```powershell
# Windows PowerShell
$body = '{"product_name":"Kirkland Signature Trail Mix, 4lb","supplier":"Costco Wholesale","recall_code":"REC-0303","recall_type":"Undeclared Allergen","description":"Ingredient panel does not list peanuts but peanuts are in the bag.","affected_units":75}'
Invoke-WebRequest -Method POST -Uri http://127.0.0.1:8191/api/kafka/recalls -ContentType "application/json" -Headers @{"X-Correlation-ID"=$CORR} -Body $body | Select-Object StatusCode, Headers, Content | Format-List
```
Copy the `recall_id` from the response, then GET it:
```bash
# macOS / Linux
RECALL_ID=<paste recall_id here>
curl -s -i http://127.0.0.1:8191/api/kafka/recalls/$RECALL_ID -H "X-Correlation-ID: $CORR"
# Windows PowerShell
$RECALL_ID = "<paste recall_id here>"
Invoke-WebRequest -Uri http://127.0.0.1:8191/api/kafka/recalls/$RECALL_ID -Headers @{"X-Correlation-ID"=$CORR} | Select-Object StatusCode, Content | Format-List
```
(If you run this twice, change `REC-0303`. The worker rejects a duplicate recall_code.
`docker restart s6491_worker` also clears the in-memory dict.)

Now show every log line for that correlation_id:
```bash
# macOS / Linux
grep "$CORR" reports/hw08/logs/message_flow.log
# Windows PowerShell
Select-String -Path reports/hw08/logs/message_flow.log -Pattern $CORR | ForEach-Object Line
```

**📸 TAKE SCREENSHOT 3a**: the curl output, showing `HTTP/1.1 201 Created`,
`x-correlation-id: <CORR>`, and the JSON with `"success":true` and `"recall_id"`, plus the
GET output with `HTTP/1.1 200 OK` and the `"recall"` object.

**📸 TAKE SCREENSHOT 3b**: the grep output. For CREATE_RECALL it must show these lines in
order, all with the same `corr=`:
```
| API    | HTTP-IN  | corr=... op=CREATE_RECALL POST /api/kafka/recalls      <- caller -> FastAPI
| API    | SEND     | corr=... op=CREATE_RECALL -> s6491_recall_requests     <- message sent to request topic
| WORKER | RECEIVE  | corr=... op=CREATE_RECALL <- s6491_recall_requests[0]@N <- worker received
| WORKER | PROCESS  | corr=... op=CREATE_RECALL success=True store_size=...  <- worker processed
| WORKER | REPLY    | corr=... op=CREATE_RECALL -> s6491_recall_responses    <- response sent to response topic
| API    | RESPONSE | corr=... op=CREATE_RECALL <- s6491_recall_responses[0]@M correlation_preserved=True
| API    | HTTP-OUT | corr=... op=CREATE_RECALL status=201                   <- returned to the caller
```
...and then the same 7 lines for GET_RECALL.

You can also show the per-container view (optional screenshot 3c):
```bash
docker logs s6491_api    2>&1 | grep "$CORR"
docker logs s6491_worker 2>&1 | grep "$CORR"
```

---

## 7. SCREENSHOT 4 - Full sequence log excerpt (CREATE_RECALL -> GET_RECALL)

A compact version of the same lines (timestamp, component, stage, detail), easy to paste
into the report as text:
```bash
# macOS / Linux
grep "$CORR" reports/hw08/logs/message_flow.log | cut -d'|' -f1-4
# Windows PowerShell
Select-String -Path reports/hw08/logs/message_flow.log -Pattern $CORR | ForEach-Object { ($_.Line -split '\|')[0..3] -join '|' }
```
**📸 TAKE SCREENSHOT 4** of that output, **and also paste the text into the report** as
the "log excerpt". It must read top to bottom:
CREATE_RECALL HTTP-IN -> SEND -> RECEIVE -> PROCESS -> REPLY -> RESPONSE -> HTTP-OUT,
then GET_RECALL with the same 7 stages, and the same `corr=` on every line.

To capture the demo's direct-Kafka run instead (CLIENT instead of API), use the
correlation_id printed in STEP 1 of the demo in place of `$CORR`.

Save the whole flow log with the report:
```bash
cp reports/hw08/logs/message_flow.log reports/hw08/RUN_LOG.txt
```

---

## 8. Self-check -> verification.json

```bash
python3 scripts/verify_hw08.py          # Windows: python scripts\verify_hw08.py
```
Expected: all checks PASS. It checks the files, the offline tests, the 3 containers, the
two required log lines, CREATE/GET through the API, the error responses, and the 7-stage
order in the flow log. It writes `reports/hw08/verification.json`.
**📸 OPTIONAL SCREENSHOT 5**: the PASS list and the `N/N checks passed` line.

---

## 9. Code screenshots for the report

The handout asks for screenshots of the **Kafka client, homework_demo.py, the worker, and
the API wrapper**. Open each file in VS Code/Cursor and screenshot these parts. Each
screenshot should show the file name tab and line numbers.

| # | File | What to capture |
|---|---|---|
| C1 | `code/kafka_service/config.py` | the whole file (topic names, PREFIX, PORT_BASE) |
| C2 | `code/kafka_service/kafka_client.py` | `build_request()` and `RecallKafkaClient.request()` |
| C3 | `code/kafka_service/kafka_client.py` | `start()` and `_read_responses()` (matching by correlation_id) |
| C4 | `code/kafka_service/worker.py` | `create_recall()`, `get_recall()`, `handle_request()` |
| C5 | `code/kafka_service/worker.py` | `run_worker()` loop (subscribe, "Consumer is ready and listening...", RECEIVE/PROCESS/REPLY, commit) |
| C6 | `code/kafka_service/recall_entity.py` | `validate_recall_fields()` |
| C7 | `code/kafka_service/homework_demo.py` | `main()` (STEP 1-10) |
| C8 | `code/web_application/routers/kafka_recalls.py` | `forward_to_worker()` and the 3 routes |
| C9 | `code/kafka_service/docker-compose.yml` | the `kafka`, `worker`, `api` services |

Code snippets to paste into the report next to the screenshots:

**Request message built by the client** (`kafka_client.py`)
```python
def build_request(operation: str, data: dict, correlation_id: str) -> dict:
    return {
        "correlation_id": correlation_id,
        "reply_to": RESPONSE_TOPIC,
        "operation": operation,
        "data": data,
    }
```

**Worker routing and correlation_id echo** (`worker.py`)
```python
def handle_request(message, store):
    if not isinstance(message, dict):
        return None, None
    correlation_id = message.get("correlation_id")
    if not isinstance(correlation_id, str) or not correlation_id.strip():
        return None, None

    operation = message.get("operation")
    reply_to = message.get("reply_to")
    if reply_to not in ALLOWED_REPLY_TOPICS:
        return RESPONSE_TOPIC, _response(correlation_id, operation, success=False,
                                         error=f"reply_to must be {RESPONSE_TOPIC}")
    if "data" not in message:
        return reply_to, _response(correlation_id, operation, success=False,
                                   error="data is required")

    if operation == CREATE_OPERATION:
        result = create_recall(message["data"], store)
    elif operation == GET_OPERATION:
        result = get_recall(message["data"], store)
    else:
        result = {"success": False, "error": "Unknown operation"}
    return reply_to, _response(correlation_id, operation, **result)
```

**UUID generation and the plain dict store** (`worker.py`)
```python
def create_recall(data, store):
    fields, error = validate_recall_fields(data)
    if error:
        return {"success": False, "error": error}
    if any(record["recall_code"] == fields["recall_code"] for record in store.values()):
        return {"success": False, "error": f"recall_code {fields['recall_code']} already exists"}
    recall_id = str(uuid.uuid4())
    store[recall_id] = {"recall_id": recall_id, **fields,
                        "created_at": datetime.now(timezone.utc).isoformat()}
    return {"success": True, "recall_id": recall_id, "message": "Recall created"}
```

**Client waits for the reply with the same correlation_id** (`kafka_client.py`)
```python
waiter = {"event": threading.Event(), "response": None, "location": None}
with self._lock:
    self._pending[correlation_id] = waiter
log_flow(self.component, "SEND", f"corr={correlation_id} op={operation} -> {REQUEST_TOPIC}", message)
send_json(self._producer, REQUEST_TOPIC, correlation_id, message)
if not waiter["event"].wait(self.timeout_sec):
    return {"correlation_id": correlation_id, "operation": operation,
            "success": False, "error": "Timed out ..."}
return waiter["response"]
```

**FastAPI wrapper keeps the caller's correlation_id** (`routers/kafka_recalls.py`)
```python
def forward_to_worker(operation, data, correlation_id, http_route, success_status=200):
    correlation_id = (correlation_id or "").strip() or new_correlation_id()
    log_flow("API", "HTTP-IN", f"corr={correlation_id} op={operation} {http_route}", {"data": data})
    response = get_kafka_client().request(operation, data, correlation_id=correlation_id)
    status_code = _status_for(response, success_status)
    log_flow("API", "HTTP-OUT", f"corr={correlation_id} op={operation} status={status_code}")
    return JSONResponse(status_code=status_code, content=response,
                        headers={"X-Correlation-ID": correlation_id})
```

---

## 10. Report content (copy into the HW8 report)

### 10.1 Topic names

| Topic | Producer | Consumer |
|---|---|---|
| `s6491_recall_requests` | client (`homework_demo.py`) / FastAPI wrapper | worker, group `s6491_recall_worker` |
| `s6491_recall_responses` | worker (topic named in `reply_to`) | the client or FastAPI wrapper that sent the request |

Both topics: 1 partition, replication factor 1, created at startup by `kafka_io.ensure_topics()`
(broker auto-create is turned off so a typo cannot create a stray topic).

### 10.2 Request message schema

```json
{
  "correlation_id": "string, UUID created once by the client",
  "reply_to": "s6491_recall_responses",
  "operation": "CREATE_RECALL | GET_RECALL",
  "data": { }
}
```
`CREATE_RECALL` data (all required; no user-specific fields such as submitter email):

| Field | Rule |
|---|---|
| `product_name` | non-empty string, max 255 (primary field) |
| `supplier` | non-empty string, max 255 (secondary field) |
| `recall_code` | `REC-####`, unique in the worker's store |
| `recall_type` | one of `Packaging / Seal Failure`, `Contamination`, `Undeclared Allergen`, `Spoiled or Quality Issue` |
| `description` | string longer than 25 characters (the HW1 form rule), max 2000 |
| `affected_units` | integer >= 0 |

`GET_RECALL` data: `{"recall_id": "<uuid>"}`

### 10.3 Response message schemas

```json
{"correlation_id": "<same>", "operation": "CREATE_RECALL", "success": true,
 "recall_id": "<uuid4 generated by the worker>", "message": "Recall created"}

{"correlation_id": "<same>", "operation": "GET_RECALL", "success": true,
 "recall": {"recall_id": "...", "product_name": "...", "supplier": "...",
            "recall_code": "...", "recall_type": "...", "description": "...",
            "affected_units": 120, "created_at": "ISO-8601"}}

{"correlation_id": "<same>", "operation": "<as sent>", "success": false,
 "error": "Recall not found | Unknown operation | Missing required field(s): ... | ..."}
```

### 10.4 correlation_id flow

```
caller ──HTTP (X-Correlation-ID: C)──▶ FastAPI wrapper  (or homework_demo.py creates C itself)
   FastAPI ──{correlation_id: C, reply_to, operation, data}──▶ s6491_recall_requests
      worker consumes ─ validates ─ processes (dict store, uuid4) 
      worker ──{correlation_id: C, success, ...}──▶ topic named by reply_to = s6491_recall_responses
   FastAPI consumer reads s6491_recall_responses, keeps only the reply whose correlation_id == C
caller ◀──HTTP 201/200/400/404 + body {correlation_id: C} + header X-Correlation-ID: C
```
C is created once, either by the caller or by the client when none is given. No component
ever changes it. Every response, including errors, echoes it.

### 10.5 Design notes (the problems a single process hides)

- **Out-of-order or interleaved replies:** the client never assumes "the next message is
  my answer". It keeps a `pending[correlation_id]` table and only wakes the request whose id
  matches, so many API requests can share one response topic.
- **Lost replies:** each request waits at most `REQUEST_TIMEOUT_SEC` (15 s) and then returns
  `success: false, error: "Timed out ..."` with the same correlation_id, instead of hanging.
- **Missed fast replies:** the client pins the response partition at its current end offset
  (`assign` at the high watermark) **before** it sends, so a reply that arrives quickly is
  never skipped. A consumer-group rebalance would not guarantee that.
- **Duplicates:** the producer uses `acks=all` + `enable.idempotence=True`, so a retried
  send is not written twice. The worker commits its offset only **after** the reply is
  acknowledged (at-least-once). A crash in between redelivers the request, and the
  unique `recall_code` check stops that replay from creating a second recall.
- **Unsafe reply_to:** the worker only replies to `s6491_recall_responses`. Any other
  `reply_to` gets an error on the service's own response topic, so a request cannot make
  the worker write into arbitrary topics.

---

## 11. Stop / clean up

```bash
docker compose -f code/kafka_service/docker-compose.yml down        # stop, keep images
docker compose -f code/kafka_service/docker-compose.yml down -v     # also drop volumes
```
The worker stores recalls in a Python dict, so every restart starts with an empty store.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `port is already allocated` for 8191 | stop the HW1-HW7 uvicorn server or any container using 8191 |
| worker/api keep restarting, log says `waiting for Kafka` | Kafka is still starting. Wait 30 s, or run `docker compose ... up -d` again |
| demo says `Timed out ... waiting for s6491_recall_responses` | worker not running: `docker logs s6491_worker`, then `docker restart s6491_worker` |
| `recall_code REC-0303 already exists` | use another code, or `docker restart s6491_worker` |
| `grep` finds nothing in message_flow.log | check the log folder mount: `ls reports/hw08/logs`. Run the commands from the repo root |
| Apple Silicon / Windows ARM image issues | both images are multi-arch. Run `docker compose ... build --no-cache` once |
| Running homework_demo.py on the host instead of Docker | `pip install -r code/kafka_service/requirements-kafka.txt`, then `PYTHONPATH=code FLOW_LOG_PATH=reports/hw08/logs/message_flow.log python3 code/kafka_service/homework_demo.py` (it uses `localhost:9094` by default) |

## Final checklist

- [ ] Screenshot 1: docker ps + "Consumer is ready and listening..." + "FastAPI server started at http://127.0.0.1:8191"
- [ ] Screenshot 2a/2b: homework_demo.py CREATE_RECALL + GET_RECALL (operation, data, recall_id, success, correlation_id)
- [ ] Screenshot 3a/3b: API call + flow lines (request topic -> worker -> response topic -> FastAPI -> caller)
- [ ] Screenshot 4 + pasted text: full CREATE -> GET sequence in order
- [ ] Code screenshots C1-C9 (client, demo, worker, API wrapper, compose)
- [ ] Report sections 10.1-10.5 (topics, request/response schemas, correlation_id flow)
- [ ] `reports/hw08/verification.json` and `reports/hw08/RUN_LOG.txt` saved
