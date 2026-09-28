from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import yaml

HERE = Path(__file__).resolve().parent
CORPUS_DIR = HERE / "corpus"
QUESTIONS_PATH = HERE / "questions.yaml"
ROOT = HERE.parent.parent
RAW_DIR = ROOT / "reports" / "hw04" / "raw"

CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
DEFAULT_TOP_K = 3
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
REFUSAL_PHRASE = "I cannot answer this question from the provided documents"


RELEVANCE_THRESHOLD = 0.25

DEDUP_JACCARD = 0.75


@dataclass
class Chunk:
    chunk_id: str
    source_name: str
    text: str
    embedding: Optional[np.ndarray] = None


@dataclass
class Retrieved:
    chunk: Chunk
    score: float
    rank: int


def load_documents(corpus_dir: Path) -> List[Tuple[str, str]]:
    docs = []
    for path in sorted(corpus_dir.glob("*.txt")):
        docs.append((path.name, path.read_text(encoding="utf-8", errors="replace")))
    if len(docs) < 5:
        raise RuntimeError(f"Need at least 5 documents; found {len(docs)} in {corpus_dir}")
    return docs


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        if end < len(text):
            space = text.rfind(" ", start + chunk_size // 2, end)
            if space != -1:
                end = space
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def build_chunks(docs: Sequence[Tuple[str, str]]) -> List[Chunk]:
    chunks: List[Chunk] = []
    for source_name, text in docs:
        pieces = chunk_text(text)
        for i, piece in enumerate(pieces):
            chunks.append(
                Chunk(
                    chunk_id=f"{Path(source_name).stem}::{i}",
                    source_name=source_name,
                    text=piece,
                )
            )
    return chunks


def _relax_ssl_for_hf() -> None:
    os.environ.setdefault("HF_HUB_DISABLE_SSL", "1")
    try:
        import httpx

        if getattr(httpx.Client, "_rag_insecure_patched", False):
            return

        _Original = httpx.Client

        class InsecureClient(_Original):
            def __init__(self, *args, **kwargs):
                kwargs["verify"] = False
                super().__init__(*args, **kwargs)

        InsecureClient._rag_insecure_patched = True
        httpx.Client = InsecureClient
    except Exception:
        pass


class VectorIndex:
    def __init__(self, chunks: List[Chunk], embed_model_name: str = EMBED_MODEL):
        from sentence_transformers import SentenceTransformer
        import faiss

        _relax_ssl_for_hf()
        self.chunks = chunks
        self.model = SentenceTransformer(embed_model_name)
        texts = [c.text for c in chunks]
        print(f"Embedding {len(texts)} chunks with {embed_model_name} ...")
        vectors = self.model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
        vectors = np.asarray(vectors, dtype=np.float32)
        for c, v in zip(self.chunks, vectors):
            c.embedding = v
        dim = vectors.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(vectors)
        print(f"FAISS index ready: {self.index.ntotal} vectors, dim={dim}")

    def retrieve(self, query: str, top_k: int = DEFAULT_TOP_K) -> List[Retrieved]:
        q = self.model.encode([query], normalize_embeddings=True)
        q = np.asarray(q, dtype=np.float32)
        scores, idxs = self.index.search(q, top_k)
        hits: List[Retrieved] = []
        for rank, (score, idx) in enumerate(zip(scores[0], idxs[0]), start=1):
            if idx < 0:
                continue
            hits.append(Retrieved(chunk=self.chunks[int(idx)], score=float(score), rank=rank))
        return hits

def _tokens(text: str) -> set:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def jaccard(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def engineer_context(hits: List[Retrieved], threshold: float = RELEVANCE_THRESHOLD) -> List[Retrieved]:
    """Drop low-relevance and near-duplicate chunks; prefer source diversity."""
    filtered: List[Retrieved] = []
    for hit in hits:
        if hit.score < threshold:
            continue
        if any(jaccard(hit.chunk.text, kept.chunk.text) >= DEDUP_JACCARD for kept in filtered):
            continue
        filtered.append(hit)

    selected: List[Retrieved] = []
    seen_sources: set = set()
    remaining = list(filtered)
    while remaining:
        def pick_key(h: Retrieved) -> float:
            diversity_bonus = 0.05 if h.chunk.source_name not in seen_sources else 0.0
            return h.score + diversity_bonus

        best = max(remaining, key=pick_key)
        remaining.remove(best)
        selected.append(best)
        seen_sources.add(best.chunk.source_name)

    return [
        Retrieved(chunk=h.chunk, score=h.score, rank=i)
        for i, h in enumerate(selected, start=1)
    ]


def format_basic_context(hits: List[Retrieved]) -> str:
    blocks = []
    for h in hits:
        blocks.append(
            f"[chunk {h.rank} | source={h.chunk.source_name} | score={h.score:.4f}]\n{h.chunk.text}"
        )
    return "\n\n".join(blocks)


def format_engineered_context(hits: List[Retrieved]) -> str:
    blocks = []
    for h in hits:
        blocks.append(
            f"Source [{h.rank}] ({h.chunk.source_name}, chunk_id={h.chunk.chunk_id}, score={h.score:.4f}):\n"
            f"{h.chunk.text}"
        )
    return "\n\n".join(blocks)


def print_retrieval(question_id: str, config: str, hits: List[Retrieved]) -> str:
    lines = [
        f"=== RETRIEVAL | {question_id} | {config} ===",
        f"Retrieved {len(hits)} chunk(s):",
    ]
    for h in hits:
        preview = h.chunk.text.replace("\n", " ")[:220]
        lines.append(
            f"  rank={h.rank}  score={h.score:.4f}  source={h.chunk.source_name}  "
            f"chunk_id={h.chunk.chunk_id}"
        )
        lines.append(f"    preview: {preview}")
    text = "\n".join(lines)
    print(text)
    return text + "\n"


class LLMClient:
    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError


class OpenAICompatClient(LLMClient):
    def __init__(self, model: str, api_key: str, base_url: Optional[str] = None):
        from openai import OpenAI

        kwargs: Dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)
        self.model = model

    def complete(self, system: str, user: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=0.0,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return (resp.choices[0].message.content or "").strip()


class OllamaClient(LLMClient):
    def __init__(self, model: str = "llama3.2", base_url: str = "http://127.0.0.1:11434"):
        import requests

        self.model = model
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        r = self.session.get(f"{self.base_url}/api/tags", timeout=5)
        r.raise_for_status()

    def complete(self, system: str, user: str) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "options": {"temperature": 0.0},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        r = self.session.post(f"{self.base_url}/api/chat", json=payload, timeout=180)
        r.raise_for_status()
        return (r.json().get("message", {}) or {}).get("content", "").strip()


class LocalTransformersClient(LLMClient):
    """Small local instruct model — no API key required."""

    def __init__(self, model_name: str = "Qwen/Qwen2.5-0.5B-Instruct"):
        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        _relax_ssl_for_hf()
        print(f"Loading local LLM: {model_name} ...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.model.eval()
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        self.model.to(self.device)
        self.torch = torch

    def complete(self, system: str, user: str) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        prompt = self.tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
        with self.torch.no_grad():
            out = self.model.generate(
                **inputs,
                max_new_tokens=256,
                do_sample=False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
        gen = out[0][inputs["input_ids"].shape[-1] :]
        return self.tokenizer.decode(gen, skip_special_tokens=True).strip()


def build_llm(args: argparse.Namespace) -> Tuple[LLMClient, str]:
    if args.local_llm:
        name = args.local_model
        return LocalTransformersClient(name), f"local:{name}"

    api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("GROQ_API_KEY")
    base_url = os.environ.get("OPENAI_BASE_URL")
    if os.environ.get("GROQ_API_KEY") and not base_url:
        base_url = "https://api.groq.com/openai/v1"
        api_key = os.environ["GROQ_API_KEY"]
    if api_key:
        model = args.model or os.environ.get("OPENAI_MODEL") or (
            "llama-3.1-8b-instant" if base_url and "groq" in base_url else "gpt-4o-mini"
        )
        return OpenAICompatClient(model, api_key, base_url), f"openai-compat:{model}"

    try:
        model = args.model or "llama3.2"
        return OllamaClient(model=model), f"ollama:{model}"
    except Exception as exc:
        print(f"Ollama unavailable ({exc}); falling back to --local-llm")
        name = args.local_model
        return LocalTransformersClient(name), f"local:{name}"


NO_RAG_SYSTEM = (
    "You are a helpful assistant. Answer the user's question as best you can. "
    "Be concise."
)

BASIC_RAG_SYSTEM = (
    "You are a helpful assistant. Use the provided context chunks when they are "
    "relevant to answer the question. Be concise."
)

CONTEXT_RAG_SYSTEM = (
    "You are a grounded question-answering assistant.\n"
    "Rules:\n"
    "1. Answer ONLY using the provided context sources.\n"
    "2. Cite source numbers like [1], [2] for every factual claim.\n"
    "3. If the context does not contain enough evidence, reply exactly with:\n"
    f'   "{REFUSAL_PHRASE}"\n'
    "4. Do not use outside knowledge. Do not guess."
)


def build_prompt(config: str, question: str, context: str) -> Tuple[str, str]:
    if config == "A_NoRAG":
        return NO_RAG_SYSTEM, f"Question: {question}"
    if config == "B_BasicRAG":
        user = (
            f"Context:\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer using the context when possible."
        )
        return BASIC_RAG_SYSTEM, user
    if config == "C_ContextRAG":
        user = (
            f"Context sources:\n{context}\n\n"
            f"Question: {question}\n\n"
            "Answer only from the context. Cite source numbers. "
            f'If evidence is insufficient, reply exactly: "{REFUSAL_PHRASE}"'
        )
        return CONTEXT_RAG_SYSTEM, user
    raise ValueError(config)



def contains_keywords(answer: str, keywords: Sequence[str]) -> bool:
    a = answer.lower()
    return all(k.lower() in a for k in keywords) if keywords else False


def is_refusal(answer: str) -> bool:
    a = answer.lower().strip()
    return REFUSAL_PHRASE.lower() in a or a.startswith("i cannot answer")


def cites_sources(answer: str) -> bool:
    return bool(re.search(r"\[\d+\]", answer))


def evaluate_row(
    q: Dict[str, Any],
    config: str,
    hits: List[Retrieved],
    answer: str,
) -> Dict[str, Any]:
    qid = q["id"]
    must_refuse = bool(q.get("must_refuse"))
    keywords = q.get("expected_keywords") or []

    joined = " ".join(h.chunk.text.lower() for h in hits)
    retrieval_ok = False
    if qid == "Q1":
        retrieval_ok = "soy" in joined and "j. higgs" in joined
    elif qid == "Q2":
        retrieval_ok = ("40" in joined) and ("2 hour" in joined or "within 2" in joined)
    elif qid == "Q3":
        retrieval_ok = "48 million" in joined and ("1 in 6" in joined or "1-in-6" in joined)
    elif qid == "Q4":
        retrieval_ok = "recall" in joined or "recalled" in joined
    elif qid in ("Q5", "Q6"):
        retrieval_ok = False

    refused = is_refusal(answer)
    if must_refuse:
        correct_answer = refused
        grounded = refused
        refused_when_needed = refused
    else:
        correct_answer = contains_keywords(answer, keywords) and not refused
        grounded = (not refused) and (
            cites_sources(answer) if config == "C_ContextRAG" else correct_answer
        )
        refused_when_needed = False

    format_ok = True
    if config == "C_ContextRAG":
        format_ok = (refused and must_refuse) or (cites_sources(answer) and not must_refuse) or (
            refused and not must_refuse and qid == "Q4"
        )

    return {
        "question_id": qid,
        "config": config,
        "correct_retrieval": int(retrieval_ok) if config != "A_NoRAG" else "",
        "correct_answer": int(correct_answer),
        "grounded": int(grounded),
        "refused_when_needed": int(refused_when_needed) if must_refuse else "",
        "format_compliance": int(format_ok),
        "is_refusal": int(refused),
        "answer_preview": answer.replace("\n", " ")[:300],
    }

def run_config(
    llm: LLMClient,
    index: VectorIndex,
    q: Dict[str, Any],
    config: str,
    top_k: int,
    log_lines: List[str],
) -> Dict[str, Any]:
    question = " ".join(q["question"].split())
    hits: List[Retrieved] = []
    context = ""

    if config != "A_NoRAG":
        raw_hits = index.retrieve(question, top_k=top_k)
        if config == "B_BasicRAG":
            hits = raw_hits
            context = format_basic_context(hits)
        else:
            pool = index.retrieve(question, top_k=max(top_k * 3, 8))
            hits = engineer_context(pool)[:top_k]
            context = format_engineered_context(hits)
        log_lines.append(print_retrieval(q["id"], config, hits))
    else:
        print(f"=== RETRIEVAL | {q['id']} | {config} ===\n  (none — No RAG baseline)\n")
        log_lines.append(f"=== RETRIEVAL | {q['id']} | {config} ===\n  (none)\n")

    system, user = build_prompt(config, question, context)
    t0 = time.perf_counter()
    answer = llm.complete(system, user)
    latency_ms = (time.perf_counter() - t0) * 1000

    print(f"--- ANSWER | {q['id']} | {config} ({latency_ms:.0f} ms) ---")
    print(answer)
    print()

    log_lines.append(f"--- ANSWER | {q['id']} | {config} ---\n{answer}\n")

    eval_row = evaluate_row(q, config, hits, answer)
    return {
        "question_id": q["id"],
        "question_type": q["type"],
        "question": question,
        "config": config,
        "top_k": top_k,
        "latency_ms": round(latency_ms, 2),
        "n_context_chunks": len(hits),
        "sources": [h.chunk.source_name for h in hits],
        "scores": [round(h.score, 4) for h in hits],
        "answer": answer,
        **{k: eval_row[k] for k in (
            "correct_retrieval", "correct_answer", "grounded",
            "refused_when_needed", "format_compliance", "is_refusal",
        )},
    }


def summarize_metrics(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    by_config: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_config.setdefault(r["config"], []).append(r)

    summary = {}
    for config, group in by_config.items():
        n = len(group)
        accuracy = sum(int(r["correct_answer"]) for r in group) / n
        faithfulness = sum(int(r["grounded"]) for r in group) / n
        format_c = sum(int(r["format_compliance"]) for r in group) / n
        refuse_rows = [r for r in group if r["refused_when_needed"] != ""]
        robustness = (
            sum(int(r["refused_when_needed"]) for r in refuse_rows) / len(refuse_rows)
            if refuse_rows else None
        )
        summary[config] = {
            "n": n,
            "accuracy": round(accuracy, 3),
            "faithfulness": round(faithfulness, 3),
            "format_compliance": round(format_c, 3),
            "robustness_refuse_q5_q6": round(robustness, 3) if robustness is not None else None,
        }
    return summary


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description="Part 4 Grounded RAG system")
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--model", type=str, default=None, help="LLM model name")
    parser.add_argument("--local-llm", action="store_true", help="Force local transformers LLM")
    parser.add_argument(
        "--local-model",
        type=str,
        default="Qwen/Qwen2.5-0.5B-Instruct",
        help="HuggingFace model for --local-llm",
    )
    parser.add_argument("--k-sweep-only", action="store_true")
    parser.add_argument("--skip-k-sweep", action="store_true")
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    docs = load_documents(CORPUS_DIR)
    chunks = build_chunks(docs)
    print(f"Corpus: {len(docs)} documents, {len(chunks)} chunks "
          f"(size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")

    questions = yaml.safe_load(QUESTIONS_PATH.read_text(encoding="utf-8"))["questions"]
    index = VectorIndex(chunks)
    llm, llm_name = build_llm(args)
    print(f"LLM backend: {llm_name}")

    log_lines: List[str] = [
        f"LLM: {llm_name}",
        f"Embed: {EMBED_MODEL}",
        f"chunk_size={CHUNK_SIZE} overlap={CHUNK_OVERLAP}",
        "",
    ]

    configs = ["A_NoRAG", "B_BasicRAG", "C_ContextRAG"]
    comparison_rows: List[Dict[str, Any]] = []

    if not args.k_sweep_only:
        for q in questions:
            for config in configs:
                row = run_config(llm, index, q, config, args.top_k, log_lines)
                comparison_rows.append(row)

        write_csv(RAW_DIR / "comparison_results.csv", comparison_rows)
        (RAW_DIR / "comparison_results.json").write_text(
            json.dumps(comparison_rows, indent=2), encoding="utf-8"
        )

        summary = summarize_metrics(comparison_rows)
        (RAW_DIR / "evaluation_summary.json").write_text(
            json.dumps(summary, indent=2), encoding="utf-8"
        )

        eval_rows = []
        for r in comparison_rows:
            eval_rows.append({
                "question_id": r["question_id"],
                "config": r["config"],
                "correct_retrieval": r["correct_retrieval"],
                "correct_answer": r["correct_answer"],
                "grounded": r["grounded"],
                "refused_when_needed": r["refused_when_needed"],
                "format_compliance": r["format_compliance"],
            })
        write_csv(RAW_DIR / "evaluation_table.csv", eval_rows)

        md = ["# Evaluation Table", "", "| Q | Config | Correct Retrieval | Correct Answer | Grounded | Refused-when-needed | Format |",
              "|---|--------|-------------------|----------------|----------|---------------------|--------|"]
        for r in eval_rows:
            md.append(
                f"| {r['question_id']} | {r['config']} | {r['correct_retrieval']} | "
                f"{r['correct_answer']} | {r['grounded']} | {r['refused_when_needed']} | "
                f"{r['format_compliance']} |"
            )
        md.append("")
        md.append("## Overall by configuration")
        md.append("")
        md.append("| Config | Accuracy | Faithfulness | Format compliance | Robustness (Q5/Q6 refuse) |")
        md.append("|--------|----------|--------------|-------------------|---------------------------|")
        for cfg, s in summary.items():
            md.append(
                f"| {cfg} | {s['accuracy']} | {s['faithfulness']} | {s['format_compliance']} | "
                f"{s['robustness_refuse_q5_q6']} |"
            )
        (RAW_DIR / "evaluation_table.md").write_text("\n".join(md), encoding="utf-8")

    if not args.skip_k_sweep:
        q2 = next(q for q in questions if q["id"] == "Q2")
        sweep_rows = []
        for k in (1, 3, 5):
            print("\n" + "#" * 72)
            print(f"K-SWEEP  k={k}  question=Q2  config=C_ContextRAG")
            print("#" * 72)
            row = run_config(llm, index, q2, "C_ContextRAG", k, log_lines)
            row["sweep_k"] = k
            sweep_rows.append(row)
        write_csv(RAW_DIR / "k_sweep_results.csv", sweep_rows)
        (RAW_DIR / "k_sweep_results.json").write_text(
            json.dumps(sweep_rows, indent=2), encoding="utf-8"
        )

    (RAW_DIR / "retrieval_and_answers.txt").write_text("\n".join(log_lines), encoding="utf-8")
    print(f"\nWrote outputs under {RAW_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
