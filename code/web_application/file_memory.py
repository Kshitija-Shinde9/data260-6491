import os
import re
from datetime import datetime, timedelta

from mongo_db import get_messages, utcnow

STALE_AFTER = timedelta(hours=24)
LINE_LIMIT = 40


def repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def agent_path() -> str:
    return os.path.join(repo_root(), "AGENT.md")


def memory_path() -> str:
    return os.path.join(repo_root(), "MEMORY.md")


def original_memory_path() -> str:
    return os.path.join(repo_root(), "MEMORY.original.md")


def read_text(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path) as handle:
        return handle.read()


def content_lines(text: str) -> list:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("<!--"):
            continue
        lines.append(stripped)
    return lines


def last_consolidated_at(text: str):
    match = re.search(r"consolidated:\s*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)", text)
    if not match:
        return None
    return datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))


def consolidation_required(text: str) -> tuple:
    count = len(content_lines(text))
    recorded = last_consolidated_at(text)
    too_long = count > LINE_LIMIT
    too_old = recorded is None or utcnow() - recorded > STALE_AFTER
    reasons = []
    if too_long:
        reasons.append(f"{count} content lines is more than {LINE_LIMIT}")
    if too_old:
        reasons.append("the last consolidation is missing or more than 24 hours old")
    return (too_long or too_old), reasons, count


def file_memory_block() -> str:
    agent = read_text(agent_path()).strip()
    memory = read_text(memory_path()).strip()
    return f"File memory instructions:\n{agent}\n\nDurable facts:\n{memory}"


def _split_fact(line: str) -> tuple:
    body = line[2:].strip() if line.startswith("- ") else line
    if ": " not in body:
        return body, body
    key, value = body.split(": ", 1)
    return key.strip(), value.strip()


def consolidate_text(text: str) -> str:
    groups = {}
    order = []
    for line in content_lines(text):
        key, value = _split_fact(line)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(value)
    written = [f"<!-- consolidated: {utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')} -->"]
    for key in order:
        values = groups[key]
        unique = []
        for value in values:
            if value not in unique:
                unique.append(value)
        if len(unique) == 1:
            suffix = f" (recorded {len(values)} times)" if len(values) > 1 else ""
            written.append(f"- {key}: {unique[0]}{suffix}")
        else:
            rest = "; ".join(unique[1:])
            written.append(
                f'- {key}: Conflict. Kept "{unique[0]}" because it appeared first. Also recorded: {rest}.'
            )
    return "\n".join(written) + "\n"


def compact_memory() -> str:
    path = memory_path()
    current = read_text(path)
    before = len(content_lines(current))
    required, reasons, _ = consolidation_required(current)
    original = original_memory_path()
    if not os.path.exists(original):
        with open(original, "w") as handle:
            handle.write(current)
    updated = consolidate_text(current)
    with open(path, "w") as handle:
        handle.write(updated)
    after = len(content_lines(updated))
    reason = "; ".join(reasons) if required else "requested with /compact"
    return f"/compact before={before} after={after}\nConsolidation reason: {reason}"


def remember_recent_facts(user_id: str, session_id: str) -> str:
    query = {"user_id": user_id, "role": "user"}
    if session_id:
        query["session_id"] = session_id
    rows = list(get_messages().find(query).sort("created_at", -1).limit(8))
    rows.reverse()
    if not rows:
        return "/dream found no recent user messages."
    current = read_text(memory_path())
    added = []
    for row in rows:
        fact = " ".join(row["content"].split())[:160]
        line = f"- dream: {fact}"
        if fact and line not in current and fact not in current:
            added.append(line)
        if len(added) == 3:
            break
    if not added:
        return "/dream found no new facts to add."
    with open(memory_path(), "a") as handle:
        handle.write("\n" + "\n".join(added) + "\n")
    return "/dream added " + str(len(added)) + " fact(s):\n" + "\n".join(added)


def run_memory_command(command: str, user_id: str, session_id: str) -> dict:
    name = command.strip().split()[0]
    if name == "/help":
        reply = (
            "/memory shows AGENT.md and MEMORY.md.\n"
            "/compact consolidates MEMORY.md and reports the before and after line counts.\n"
            "/dream adds up to 3 new facts from the recent conversation.\n"
            "/help lists these commands."
        )
    elif name == "/memory":
        text = read_text(memory_path())
        required, reasons, count = consolidation_required(text)
        recorded = last_consolidated_at(text)
        reply = (
            read_text(agent_path()).strip()
            + "\n\n"
            + text.strip()
            + f"\n\ncontent_lines={count}"
            + f"\nlast_consolidated={recorded.isoformat() if recorded else 'none'}"
            + f"\nconsolidation_required={'yes' if required else 'no'}"
            + ("\nreason: " + "; ".join(reasons) if reasons else "")
        )
    elif name == "/compact":
        reply = compact_memory()
    elif name == "/dream":
        reply = remember_recent_facts(user_id, session_id)
    else:
        reply = "Unknown command. Use /help."
    return {
        "session_id": session_id or "file-memory",
        "reply": reply,
        "used": {
            "short_term_count": 0,
            "short_term": [],
            "long_term_summary": None,
            "episodic_facts": [],
        },
    }
