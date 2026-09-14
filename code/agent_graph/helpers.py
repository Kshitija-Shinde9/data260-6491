

import json
import re
from typing import Any, Dict, Iterable, List, Tuple



STOP = {
    "the", "and", "for", "that", "with", "this", "from", "into", "than", "your", "you",
    "are", "was", "were", "have", "has", "had", "use", "used", "using", "about", "how",
    "can", "will", "more", "less", "very", "over", "under", "their", "there", "then",
    "our", "out", "on", "in", "of", "to", "by", "a", "an", "is", "it", "as",
}


# text cleanup + extraction


def strip_code_and_md(s: str) -> str:
    # qwen3 likes to think out loud before answering, so we cut that part out first.
    # it usually looks like "Thinking... blah blah ...done thinking." right before the real reply
    s = str(s)
    s = re.sub(r"Thinking\.\.\..*?done thinking\.", "", s, flags=re.DOTALL | re.IGNORECASE)

    
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL | re.IGNORECASE)

    
    s = re.sub(r"```(?:json)?", "", s)
    s = s.replace("`", "")

    return " ".join(s.split())


def extract_json_block(text: str) -> str:
    
    
    cleaned = strip_code_and_md(text)

    start = cleaned.find("{")
    if start == -1:
        return json.dumps({"message": cleaned})

    depth = 0
    for i in range(start, len(cleaned)):
        if cleaned[i] == "{":
            depth += 1
        elif cleaned[i] == "}":
            depth -= 1
            if depth == 0:
                return cleaned[start:i + 1]

   
    return json.dumps({"message": cleaned})


def tokens(txt: str) -> List[str]:
 
    return re.findall(r"[a-z][a-z\-]+", str(txt).lower())


def ngrams(words: List[str], n: int) -> Iterable[Tuple[str, ...]]:
    for i in range(max(0, len(words) - n + 1)):
        yield tuple(words[i:i + n])


def phrase_candidates(title: str, content: str, maxn: int = 12) -> List[str]:

   
    words = [w for w in tokens(f"{title} {content}") if w not in STOP and len(w) > 2]

    freq: Dict[str, int] = {}
    for n in (3, 2):
        for gram in ngrams(words, n):
            phrase = " ".join(gram)
            freq[phrase] = freq.get(phrase, 0) + 1

    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], -len(kv[0])))
    candidates = [p for p, _ in ranked]

    # if we're still short, just fall back to single words
    if len(candidates) < maxn:
        seen = set(candidates)
        for w in words:
            if w not in seen:
                candidates.append(w)
                seen.add(w)
            if len(candidates) >= maxn:
                break

    return candidates[:maxn]



# output schema coercion


def _word_count(s: str) -> int:
    return len(str(s).split())


def coerce_reply(raw_obj: Any, title: str, content: str, strict: bool) -> Dict[str, Any]:
    # no matter what the model actually returned, this makes sure we always end up with:
    # thought (string), message (<=60 words), data.tags (exactly 3), data.summary (<=25 words), data.issues
    if not isinstance(raw_obj, dict):
        raw_obj = {}

    thought = str(raw_obj.get("thought", "")).strip()

    message = str(raw_obj.get("message", "")).strip()
    if not message:
        message = "ok, proposal reviewed, tags and summary are ready."
    if _word_count(message) > 60:
        message = " ".join(message.split()[:60])

    data = raw_obj.get("data", {})
    if not isinstance(data, dict):
        data = {}



   
    if not data:
        data = {
            k.split("data.", 1)[1]: v
            for k, v in raw_obj.items()
            if k.startswith("data.")
        }

    tags = data.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    tags = [str(t).strip() for t in tags if str(t).strip()]


    if len(tags) < 3:
        for cand in phrase_candidates(title, content):
            if cand not in tags:
                tags.append(cand)
            if len(tags) >= 3:
                break
    tags = tags[:3]
    while len(tags) < 3:
        tags.append("untitled topic")

    summary = str(data.get("summary", "")).strip()
    if not summary:
        summary = " ".join(tokens(content))[:120] or "no summary available."
    if _word_count(summary) > 25:
        summary = " ".join(summary.split()[:25])
    if not summary.endswith("."):
        summary = summary.rstrip(".") + "."

    issues = data.get("issues", [])
    if not isinstance(issues, list):
        issues = []
    issues = [str(i).strip() for i in issues if str(i).strip()]

    if strict:
        multiword = [t for t in tags if len(t.split()) > 1]
        if len(multiword) < 2:
            issues.append("fewer than two multi-word tags")

    return {
        "thought": thought,
        "message": message,
        "data": {"tags": tags, "summary": summary, "issues": issues},
    }


def parse_and_coerce(text: str, title: str, content: str, strict: bool) -> Dict[str, Any]:
    block = extract_json_block(text)
    try:
        obj = json.loads(block)
    except Exception:
        # model didn't give us clean json, just fall back to whatever text it said
        obj = {"message": strip_code_and_md(text)}
    return coerce_reply(obj, title, content, strict)


# Part 4 needs to see what the model ACTUALLY said, before my repair code fixes
# it up. coerce_reply pads missing tags and trims long summaries, so if I
# validate after that it can never fail. This gives me the raw answer instead.
def parse_raw(text: str) -> Dict[str, Any]:
    block = extract_json_block(text)
    try:
        obj = json.loads(block)
    except Exception:
        return {}
    data = obj.get("data", obj)
    if not isinstance(data, dict):
        return {}
    return data
