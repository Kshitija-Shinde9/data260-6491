import csv
import hashlib
import json
import math
import os
import re
import sys
import time

from mongo_db import get_episodes, get_messages, get_summaries, utcnow

SUMMARIZE_EVERY_USER_MSGS = int(os.getenv("SUMMARIZE_EVERY_USER_MSGS", "4"))
EPISODE_TOP_K = int(os.getenv("EPISODE_TOP_K", "3"))
LOG_FIELDS = [
    "created_at",
    "user_id",
    "session_id",
    "short_term_n",
    "policy",
    "prompt_tokens",
    "completion_tokens",
    "primer_tokens",
    "long_term_tokens",
    "short_term_tokens",
    "episodic_tokens",
    "latency_ms",
]
SYSTEM_PRIMER = (
    "You are a grocery recall assistant for project s6491. "
    "Answer from the long-term summaries, the short-term window, and the episodic facts. "
    "If the context does not contain the answer, say you do not have that information. "
    "Reply in plain text."
)
EXTRACT_INSTRUCTIONS = (
    "Extract at most 3 durable facts from the user message. "
    'Return only JSON: {"facts": [{"fact": "short text", "importance": 0.5}]}. '
    "importance is a number from 0 to 1. "
    'If there is no durable fact, return {"facts": []}.'
)

_embed_mode = "ollama"


class ModelUnavailable(Exception):
    pass


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def short_term_n() -> int:
    return int(os.getenv("SHORT_TERM_N", "8"))


def memory_policy() -> str:
    return os.getenv("MEMORY_POLICY", "full")


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def apply_memory_policy(prior: list, episodes: list) -> tuple:
    if memory_policy() != "compress":
        return prior, episodes
    if len(prior) > 4:
        older = " | ".join(item["content"].replace("\n", " ")[:40] for item in prior[:-4])
        prior = [{"role": "user", "content": "Compressed earlier turns: " + older}] + prior[-4:]
    return prior, episodes[:1]


def log_chat_turn(row: dict) -> None:
    raw_dir = os.path.join(_repo_root(), "reports", "hw06", "raw")
    os.makedirs(raw_dir, exist_ok=True)
    csv_path = os.getenv("CHAT_LOG_PATH", os.path.join(raw_dir, "chat_turns.csv"))
    jsonl_path = os.path.splitext(csv_path)[0] + ".jsonl"
    new_file = not os.path.exists(csv_path)
    with open(csv_path, "a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS)
        if new_file:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in LOG_FIELDS})
    with open(jsonl_path, "a") as handle:
        handle.write(json.dumps(row) + "\n")


def get_model():
    root = _repo_root()
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from src.model_client import ModelClient
    except ModuleNotFoundError as exc:
        raise ModelUnavailable("Install ollama in the virtualenv: pip install ollama") from exc
    return ModelClient()


def save_message(user_id: str, session_id: str, role: str, content: str) -> None:
    get_messages().insert_one({
        "user_id": user_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": utcnow(),
    })


def load_short_term(session_id: str, limit: int) -> list:
    rows = list(
        get_messages()
        .find({"session_id": session_id})
        .sort("created_at", -1)
        .limit(limit)
    )
    rows.reverse()
    return rows


def latest_summary(user_id: str, scope: str, session_id):
    query = {"user_id": user_id, "scope": scope}
    if scope == "session":
        query["session_id"] = session_id
    else:
        query["session_id"] = None
    return get_summaries().find_one(query, sort=[("created_at", -1)])


def parse_json_object(text: str) -> dict:
    cleaned = re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object")
    payload = json.loads(cleaned[start:end + 1])
    if not isinstance(payload, dict):
        raise ValueError("JSON value was not an object")
    return payload


def hash_embed(text: str, dims: int = 64) -> list:
    vector = [0.0] * dims
    for token in re.findall(r"[a-z0-9]+", text.lower()):
        digest = hashlib.sha256(token.encode()).digest()
        vector[int.from_bytes(digest[:4], "little") % dims] += 1.0
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def embed_text(client, text: str) -> list:
    global _embed_mode
    if _embed_mode == "ollama":
        try:
            vector = client.embed(text)
            if vector:
                return [float(value) for value in vector]
        except Exception:
            _embed_mode = "hash"
    return hash_embed(text)


def cosine(left: list, right: list) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def extract_facts(client, message: str) -> list:
    raw = client.complete([
        {"role": "system", "content": EXTRACT_INSTRUCTIONS},
        {"role": "user", "content": message},
    ]).content
    try:
        facts = parse_json_object(raw).get("facts", [])[:3]
    except (ValueError, json.JSONDecodeError, TypeError):
        snippet = message.strip()[:160]
        return [{"fact": snippet, "importance": 0.4}] if snippet else []

    cleaned = []
    for item in facts:
        if not isinstance(item, dict):
            continue
        fact = str(item.get("fact", "")).strip()[:200]
        if not fact:
            continue
        try:
            importance = float(item.get("importance", 0.5))
        except (TypeError, ValueError):
            importance = 0.5
        cleaned.append({"fact": fact, "importance": max(0.0, min(1.0, importance))})
    return cleaned


def store_episodes(user_id: str, session_id: str, message: str, client) -> None:
    for item in extract_facts(client, message):
        get_episodes().insert_one({
            "user_id": user_id,
            "session_id": session_id,
            "fact": item["fact"],
            "importance": float(item["importance"]),
            "embedding": embed_text(client, item["fact"]),
            "created_at": utcnow(),
        })


def retrieve_episodes(user_id: str, message: str, client, top_k: int) -> list:
    query_vector = embed_text(client, message)
    ranked = []
    for episode in get_episodes().find({"user_id": user_id}):
        ranked.append((cosine(query_vector, episode.get("embedding") or []), episode))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [
        {"fact": episode["fact"], "importance": episode["importance"]}
        for score, episode in ranked[:top_k]
        if score > 0
    ]


def assemble_prompt(session_summary, lifetime_summary, prior_messages, episodes, message) -> list:
    long_term_lines = []
    if session_summary and session_summary.get("text"):
        long_term_lines.append("Session summary:\n" + session_summary["text"])
    if lifetime_summary and lifetime_summary.get("text"):
        long_term_lines.append("Lifetime summary:\n" + lifetime_summary["text"])
    fact_lines = [
        f"- {item['fact']} (importance {item['importance']:.2f})"
        for item in episodes
    ]
    from file_memory import file_memory_block

    system = SYSTEM_PRIMER + "\n\n" + file_memory_block()
    if long_term_lines:
        system += "\n\nLong-term memory:\n" + "\n\n".join(long_term_lines)
    if fact_lines:
        system += "\n\nEpisodic facts:\n" + "\n".join(fact_lines)

    messages = [{"role": "system", "content": system}]
    for item in prior_messages:
        messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": message})
    return messages


def long_term_text(session_summary, lifetime_summary):
    parts = []
    if session_summary and session_summary.get("text"):
        parts.append(session_summary["text"])
    if lifetime_summary and lifetime_summary.get("text"):
        parts.append(lifetime_summary["text"])
    return "\n".join(parts) or None


def _bullet_summary(client, instruction: str, source: str) -> str:
    raw = client.complete([
        {"role": "system", "content": instruction},
        {"role": "user", "content": source},
    ]).content
    text = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.DOTALL).strip()
    return text[:2000] or "- No summary produced."


def maybe_summarize(user_id: str, session_id: str, client) -> None:
    user_turns = get_messages().count_documents({"session_id": session_id, "role": "user"})
    if user_turns == 0 or user_turns % SUMMARIZE_EVERY_USER_MSGS != 0:
        return

    recent = load_short_term(session_id, short_term_n())
    transcript = "\n".join(f"{item['role']}: {item['content']}" for item in recent)
    session_text = _bullet_summary(
        client,
        "Summarize this grocery-recall conversation in at most 5 bullet lines starting with '- '. No other text.",
        transcript,
    )
    get_summaries().insert_one({
        "user_id": user_id,
        "session_id": session_id,
        "scope": "session",
        "text": session_text,
        "created_at": utcnow(),
    })

    session_count = get_summaries().count_documents({"user_id": user_id, "scope": "session"})
    if session_count % 2 != 0:
        return

    session_rows = list(
        get_summaries()
        .find({"user_id": user_id, "scope": "session"})
        .sort("created_at", 1)
    )
    combined = "\n\n".join(row["text"] for row in session_rows)
    lifetime_text = _bullet_summary(
        client,
        "Condense these session summaries into at most 6 bullet lines starting with '- '. Keep every distinct fact. No other text.",
        combined,
    )
    get_summaries().insert_one({
        "user_id": user_id,
        "session_id": None,
        "scope": "user",
        "text": lifetime_text,
        "created_at": utcnow(),
    })


def run_chat_turn(user_id: str, session_id: str, message: str) -> dict:
    started = time.perf_counter()
    client = get_model()
    save_message(user_id, session_id, "user", message)
    window_n = short_term_n()
    short_term = load_short_term(session_id, window_n)
    prior = short_term[:-1]
    session_summary = latest_summary(user_id, "session", session_id)
    lifetime_summary = latest_summary(user_id, "user", None)

    try:
        episodes = retrieve_episodes(user_id, message, client, EPISODE_TOP_K)
        prompt_prior, prompt_episodes = apply_memory_policy(prior, episodes)
        prompt = assemble_prompt(session_summary, lifetime_summary, prompt_prior, prompt_episodes, message)
        result = client.complete(prompt)
    except ModelUnavailable:
        raise
    except Exception as exc:
        raise ModelUnavailable("Local model is unavailable. Start Ollama and make sure qwen3:8b is pulled.") from exc

    reply = re.sub(r"<think>.*?</think>", "", result.content or "", flags=re.DOTALL).strip()
    if not reply:
        reply = "I could not produce a reply."
    save_message(user_id, session_id, "assistant", reply)
    try:
        store_episodes(user_id, session_id, message, client)
        maybe_summarize(user_id, session_id, client)
    except Exception:
        # The reply is already saved. A later fact or summary failure should not hide it.
        pass

    long_term = long_term_text(session_summary, lifetime_summary) or ""
    short_term_text = "\n".join(item["content"] for item in prompt_prior)
    episodic_text = "\n".join(item["fact"] for item in prompt_episodes)
    log_chat_turn({
        "created_at": utcnow().isoformat(),
        "user_id": user_id,
        "session_id": session_id,
        "short_term_n": window_n,
        "policy": memory_policy(),
        "prompt_tokens": result.usage.input_tokens,
        "completion_tokens": result.usage.output_tokens,
        "primer_tokens": estimate_tokens(SYSTEM_PRIMER),
        "long_term_tokens": estimate_tokens(long_term),
        "short_term_tokens": estimate_tokens(short_term_text),
        "episodic_tokens": estimate_tokens(episodic_text),
        "latency_ms": int((time.perf_counter() - started) * 1000),
    })

    return {
        "session_id": session_id,
        "reply": reply,
        "used": {
            "short_term_count": len(short_term),
            "short_term": [
                {"role": item["role"], "content": item["content"]}
                for item in short_term
            ],
            "long_term_summary": long_term_text(session_summary, lifetime_summary),
            "episodic_facts": episodes,
        },
    }


def memory_view(user_id: str) -> dict:
    messages = list(
        get_messages()
        .find({"user_id": user_id})
        .sort("created_at", -1)
        .limit(16)
    )
    messages.reverse()
    episodes = list(
        get_episodes()
        .find({"user_id": user_id}, {"embedding": 0})
        .sort("created_at", -1)
        .limit(20)
    )
    episodes.reverse()
    return {
        "messages": messages,
        "session_summary": get_summaries().find_one(
            {"user_id": user_id, "scope": "session"},
            sort=[("created_at", -1)],
        ),
        "lifetime_summary": latest_summary(user_id, "user", None),
        "episodes": episodes,
    }


def aggregate_view(user_id: str) -> dict:
    counts = list(get_messages().aggregate([
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]))
    summaries = list(
        get_summaries()
        .find({"user_id": user_id})
        .sort("created_at", -1)
        .limit(5)
    )
    return {
        "daily_counts": [{"date": row["_id"], "count": row["count"]} for row in counts],
        "recent_summaries": summaries,
    }
