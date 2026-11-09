import os

SID4 = 6491
PREFIX = f"s{SID4}"
PORT_BASE = 8000 + (SID4 % 900)

ENTITY = "recall"
CREATE_OPERATION = "CREATE_RECALL"
GET_OPERATION = "GET_RECALL"
SUPPORTED_OPERATIONS = (CREATE_OPERATION, GET_OPERATION)

REQUEST_TOPIC = os.getenv("REQUEST_TOPIC", f"{PREFIX}_{ENTITY}_requests")
RESPONSE_TOPIC = os.getenv("RESPONSE_TOPIC", f"{PREFIX}_{ENTITY}_responses")
INBOX_TOPIC = f"{PREFIX}_inbox"
TASKS_TOPIC = f"{PREFIX}_tasks"
DRAFTS_TOPIC = f"{PREFIX}_drafts"
FINAL_TOPIC = f"{PREFIX}_final"
PART2_TOPICS = (
    (INBOX_TOPIC, 1),
    (TASKS_TOPIC, 2),
    (DRAFTS_TOPIC, 1),
    (FINAL_TOPIC, 1),
)
DEAD_LETTER_TOPIC = f"{PREFIX}_dead_letter"
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))
VERIFY_SEED = 266491
CRASH_TOPIC = f"{PREFIX}_part3_crash"

KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9094")

# HW9 Part 2. The semantic cache sits in front of the HW8 planner, model, and reviewer.
QA_THRESHOLD = float(os.getenv("QA_THRESHOLD", "0.85"))
QA_INDEX = f"{PREFIX}_qa_idx"
QA_KEY_PREFIX = f"{PREFIX}:qa:"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384
WORKER_GROUP_ID = os.getenv("WORKER_GROUP_ID", f"{PREFIX}_{ENTITY}_worker")
CLIENT_GROUP_PREFIX = f"{PREFIX}_{ENTITY}_client"

REQUEST_TIMEOUT_SEC = float(os.getenv("REQUEST_TIMEOUT_SEC", "15"))
FLOW_LOG_PATH = os.getenv("FLOW_LOG_PATH", "")
