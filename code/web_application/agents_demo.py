"""
agents_demo.py

DATA-260 HW1 Part 2 - Agentic AI

example run:
    python agents_demo.py --title "Trader Joe's Organic Frozen Blueberries recall" \
        --content "Packaging seal failure noticed on the 16oz bag, frost buildup near torn seam." \
        --email kshitija@example.com
"""

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import List, Dict, Any, Iterable, Tuple

from langchain_ollama import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser


# just common english filler words, not domain-specific, used as a fallback when
# building tags straight from whatever title/content gets passed in
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

    # some models wrap reasoning in <think> tags instead, so catch that style too
    s = re.sub(r"<think>.*?</think>", "", s, flags=re.DOTALL | re.IGNORECASE)

    # strip any ```json fences and stray backticks the model tosses in
    s = re.sub(r"```(?:json)?", "", s)
    s = s.replace("`", "")

    return " ".join(s.split())


def extract_json_block(text: str) -> str:
    # pull out the first { ... } chunk we can find in the cleaned text.
    # if nothing looks like json, just wrap whatever text we got into a message field
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

    # brace never closed properly, bail out safely
    return json.dumps({"message": cleaned})


def tokens(txt: str) -> List[str]:
    # lowercase words only, keeping hyphens since some tags are hyphenated
    return re.findall(r"[a-z][a-z\-]+", str(txt).lower())


def ngrams(words: List[str], n: int) -> Iterable[Tuple[str, ...]]:
    for i in range(max(0, len(words) - n + 1)):
        yield tuple(words[i:i + n])


def phrase_candidates(title: str, content: str, maxn: int = 12) -> List[str]:
    # this is just a backup in case the model doesn't hand us 3 real tags.
    # everything here comes straight from the actual title/content, nothing hardcoded
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

    # some models occasionally emit flat "data.tags"/"data.summary"/"data.issues" keys
    # instead of a nested "data" object, despite the prompt asking for nesting. recover
    # those here rather than silently falling through to the generic fallback below.
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

    # need exactly 3 tags, so pad from the real text if the model gave us fewer
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



# agent wrapper


@dataclass
class SimpleAgent:
    name: str
    system: str
    model: Any  # langchain chat model

    def respond(
        self,
        conversation: List[Dict[str, str]],
        task: str,
        title: str,
        content: str,
        strict: bool,
    ) -> Dict[str, Any]:
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.system),
            ("human",
             "Task:\n{task}\n\n"
             "Prior agent proposals in this pipeline so far (each line is the previous "
             "agent's actual proposed tags/summary/issues as JSON, not just a message). "
             "Build on the most recent one instead of generating independently from "
             "scratch:\n{history}\n\n"
             "Return ONLY one JSON object, with this exact nested shape (no code fences, "
             "no markdown, no explanations, no dotted key names like \"data.tags\"):\n"
             "{{\n"
             '  "thought": "<string>",\n'
             '  "message": "<non-empty, <=60 words, no code>",\n'
             '  "data": {{\n'
             '    "tags": ["<exactly 3 topical tags derived only from the task\'s title/content, '
             'never fixed domain keywords>"],\n'
             '    "summary": "<<=25 words, ends with a period, no ellipses>",\n'
             '    "issues": []\n'
             "  }}\n"
             "}}\n"
             "The \"data\" key's value MUST be a nested JSON object as shown above, never "
             "flat keys such as \"data.tags\". Do not add extra text outside this JSON object."
            ),
        ])

        history_text = "\n".join(
            [f'{m["role"]}: {m["content"]}' for m in conversation]
        ) or "(none yet, this is the first proposal)"
        chain = prompt | self.model | StrOutputParser()

        raw = chain.invoke({"task": task, "history": history_text})
        return parse_and_coerce(raw, title, content, strict)



# pipeline 


def build_llm(model: str, base_url: str, temperature: float) -> ChatOllama:
    return ChatOllama(
        model=model,
        temperature=temperature,
        base_url=base_url,
        num_ctx=2048,
        format="json",
        # qwen3 still tries to "think" before answering even with format=json, and that
        # was making every call way slower than it needs to be (236s vs 17.5s in my
        # testing) plus sometimes leaving data.summary blank. turning it off fixes both.
        reasoning=False,
        keep_alive="30m",  # keep the model loaded between calls instead of reloading it every time
    )


def build_agents(llm: ChatOllama) -> Tuple[SimpleAgent, SimpleAgent, SimpleAgent]:
    planner = SimpleAgent(
        name="Planner",
        system="Propose exactly 3 distinct, topical tags (prefer multi-word phrases) and a one-line summary for the given domain entity.",
        model=llm,
    )
    reviewer = SimpleAgent(
        name="Reviewer",
        system=(
            "You are given the Planner's proposed data.tags/data.summary in the conversation "
            "history. Critique that specific proposal, do not invent a new one from scratch: "
            "check the tags are topical (not generic filler) and distinct from each other, and "
            "that the summary is <=25 words with no code or markdown. "
            "If you find a problem, output corrected data.tags/data.summary that fix it and "
            "describe what you changed in data.issues. If the proposal is already fine, "
            "echo the Planner's exact tags/summary back and set data.issues to []."
        ),
        model=llm,
    )
    finalizer = SimpleAgent(
        name="Finalizer",
        system=(
            "You are given the Reviewer's proposed data.tags/data.summary/data.issues in the "
            "conversation history. Adopt the Reviewer's tags/summary as-is if data.issues was "
            "empty; if data.issues listed problems, apply those fixes yourself. Output exactly "
            "3 tags in data.tags and the final summary in data.summary. Set data.issues to []."
        ),
        model=llm,
    )
    return planner, reviewer, finalizer


def run_pipeline(
    llm: ChatOllama,
    title: str,
    content: str,
    email: str,
    strict: bool = False,
) -> Dict[str, Any]:
    # one full pass through planner -> reviewer -> finalizer. pulled this out of
    # main() so the part 3 runner script can call the exact same logic instead of
    # copy-pasting it and risking the two drifting apart.
    planner, reviewer, finalizer = build_agents(llm)

    task = (
        f'Given entity title "{title}" and content "{content}", produce exactly 3 topical tags '
        f'and a one-sentence summary in your own words. Submitter email is {email}.'
    )

    transcript: List[Dict[str, str]] = []

    t0 = time.time()
    a = planner.respond(transcript, task, title, content, strict)
    planner_ms = int((time.time() - t0) * 1000)
    transcript.append({"role": "Planner", "content": json.dumps(a.get("data", {}))})

    t0 = time.time()
    b = reviewer.respond(transcript, task, title, content, strict)
    reviewer_ms = int((time.time() - t0) * 1000)
    transcript.append({"role": "Reviewer", "content": json.dumps(b.get("data", {}))})

    t0 = time.time()
    final = finalizer.respond(transcript, task, title, content, strict)
    finalizer_ms = int((time.time() - t0) * 1000)

    package = {
        "title": title,
        "email": email,
        "content": content,
        "agents": {"transcript": transcript, "final": final.get("data", {})},
        "submissionDate": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    return {
        "planner": a,
        "reviewer": b,
        "finalizer": final,
        "package": package,
        "latency_ms": {
            "planner": planner_ms,
            "reviewer": reviewer_ms,
            "finalizer": finalizer_ms,
            "total": planner_ms + reviewer_ms + finalizer_ms,
        },
    }



# cli entrypoint


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--title", required=True, help="domain entity title, e.g. the recalled product name")
    ap.add_argument("--content", required=True, help="domain entity content/description")
    ap.add_argument("--email", default="student@example.com")
    ap.add_argument("--model", default=os.environ.get("SMOL_MODEL", "qwen3:8b"))
    ap.add_argument("--base_url", default=os.environ.get("OLLAMA_URL", "http://localhost:11434"))
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--turns", type=int, default=1)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    try:
        llm = build_llm(args.model, args.base_url, args.temperature)
    except Exception:
        print(
            "couldn't start ChatOllama, is ollama actually running?\n"
            "try `ollama serve` and `ollama pull <model tag>` first.",
            file=sys.stderr,
        )
        raise

    result = run_pipeline(llm, args.title, args.content, args.email, args.strict)

    print(f"\n--- Planner ({result['latency_ms']['planner']} ms) ---\n{json.dumps(result['planner'], indent=2)}")
    print(f"\n--- Reviewer ({result['latency_ms']['reviewer']} ms) ---\n{json.dumps(result['reviewer'], indent=2)}")
    print(f"\n--- Finalizer ({result['latency_ms']['finalizer']} ms) ---\n{json.dumps(result['finalizer'], indent=2)}")
    print(f"\n--- Publish Package ---\n{json.dumps(result['package'], indent=2)}")


if __name__ == "__main__":
    main()
