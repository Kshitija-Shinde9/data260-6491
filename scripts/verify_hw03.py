"""
scripts/verify_hw03.py - self-check for HW3.

Runs objective checks on the tagged commit and writes reports/hw03/verification.json.
Checks behaviour and committed artefacts, not exact wording, so nothing here depends
on the model saying the same thing twice.

    python scripts/verify_hw03.py
"""

import hashlib
import json
import os
import subprocess
import sys
import time
import warnings

warnings.filterwarnings("ignore")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SID4 = 6491
PORT_BASE = 8000 + (SID4 % 900)
SEED = SID4
VERIFY_SEED = 260000 + SID4
DOMAIN_ID = SID4 % 8
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
MIN_CORPUS_BYTES = 200 * 1024

checks = []


def check(name, passed, detail=""):
    checks.append({"name": name, "passed": bool(passed), "detail": str(detail)})
    print(f"[{'PASS' if passed else 'FAIL'}] {name}" + (f"  ({detail})" if detail else ""))


def path(*parts):
    return os.path.join(ROOT, *parts)


def git(*args):
    try:
        out = subprocess.run(["git", "-C", ROOT, *args], capture_output=True, text=True, timeout=10)
        return out.stdout.strip()
    except Exception:
        return ""


def check_deliverables():
    for rel in ["reports/hw03/questions.yaml", "reports/hw03/SOURCES.md",
                "reports/hw03/CORPUS_MANIFEST.json", "reports/hw03/METRICS.md",
                "reports/hw03/AI_USE.md", "reports/hw03/RUN_LOG.txt",
                "reports/hw03/raw/retrieval_results.csv", "reports/hw03/raw/chunk_stats.csv",
                "code/rag/compare_chunking.py", "code/rag/requirements.txt",
                "scripts/recompute_tables.py"]:
        check(f"deliverable present: {rel}", os.path.isfile(path(rel)))


def check_corpus():
    d = path("data", "corpus")
    if not os.path.isdir(d):
        check("corpus directory exists", False)
        return
    files = sorted(f for f in os.listdir(d) if f.endswith(".txt"))
    total = sum(os.path.getsize(os.path.join(d, f)) for f in files)
    check("corpus meets the 200 KB minimum", total >= MIN_CORPUS_BYTES,
          f"{total:,} bytes = {total/1024:.1f} KB")
    check("corpus has more than one document", len(files) > 1, f"{len(files)} documents")

    mpath = path("reports", "hw03", "CORPUS_MANIFEST.json")
    if not os.path.isfile(mpath):
        check("manifest matches the corpus on disk", False, "no manifest")
        return
    man = json.load(open(mpath))
    docs = man.get("documents", [])
    check("manifest lists every corpus file", len(docs) == len(files),
          f"manifest {len(docs)}, on disk {len(files)}")

    bad = 0
    for d_ in docs:
        p = os.path.join(d, d_["file"])
        if not os.path.isfile(p):
            bad += 1
            continue
        b = open(p, "rb").read()
        if len(b) != d_["bytes"] or hashlib.sha256(b).hexdigest() != d_["sha256"]:
            bad += 1
    check("every manifest byte size and SHA-256 matches", bad == 0,
          f"{len(docs) - bad}/{len(docs)} verified")


def check_questions():
    try:
        import yaml
    except ImportError:
        check("questions.yaml parses", False, "PyYAML not installed")
        return
    p = path("reports", "hw03", "questions.yaml")
    if not os.path.isfile(p):
        check("questions.yaml parses", False, "file missing")
        return
    qs = yaml.safe_load(open(p))["questions"]
    check("questions.yaml parses", True, f"{len(qs)} questions")
    check("questions.yaml has five questions", len(qs) == 5, len(qs))

    single = sum(1 for q in qs if q.get("single_source"))
    check("at least two questions are single-source", single >= 2, f"{single} of {len(qs)}")

    have_answer = sum(1 for q in qs if str(q.get("expected_answer", "")).strip())
    check("every question records an expected answer", have_answer == len(qs),
          f"{have_answer}/{len(qs)}")

    missing = [q["id"] for q in qs
               if not os.path.isfile(path("data", "corpus", q.get("expected_source", "")))]
    check("every expected_source exists in the corpus", not missing,
          "missing: " + ", ".join(missing) if missing else "all present")


def check_results():
    import csv
    p = path("reports", "hw03", "raw", "retrieval_results.csv")
    if not os.path.isfile(p):
        check("retrieval results present", False)
        return
    rows = list(csv.DictReader(open(p)))
    check("retrieval results present", bool(rows), f"{len(rows)} rows")

    techs = sorted({r["technique"] for r in rows})
    check("all three chunking techniques produced results", len(techs) == 3, ", ".join(techs))

    qids = sorted({r["question_id"] for r in rows})
    k = max(int(r["rank"]) for r in rows)
    check("rows equal questions x techniques x k",
          len(rows) == len(qids) * len(techs) * k,
          f"{len(qids)} x {len(techs)} x {k} = {len(qids)*len(techs)*k}")

    check("both a store score and a computed cosine are recorded",
          all(r.get("store_score") and r.get("cosine_sim") for r in rows))

    sims = [float(r["cosine_sim"]) for r in rows]
    check("every cosine similarity is within [-1, 1]", all(-1 <= s <= 1 for s in sims),
          f"min {min(sims):.4f}, max {max(sims):.4f}")

    check("retrieval latency was recorded for every row",
          all(float(r["latency_ms"]) > 0 for r in rows))

    for t in techs:
        hits = {q for r in rows if r["technique"] == t and r["is_expected"] == "1"
                for q in [r["question_id"]]}
        check(f"{t}: expected source found for at least one question", bool(hits),
              f"{len(hits)}/{len(qids)} questions")


def check_embedding():
    try:
        from llama_index.embeddings.huggingface import HuggingFaceEmbedding
        t0 = time.time()
        e = HuggingFaceEmbedding(model_name=EMBED_MODEL)
        v = e.get_text_embedding("undeclared allergen in a recalled grocery product")
        check("embedding model loads and returns a vector", len(v) > 0,
              f"{EMBED_MODEL}, {time.time()-t0:.1f}s")
        check("embedding dimension is 384", len(v) == 384, len(v))
    except Exception as error:
        check("embedding model loads and returns a vector", False, error)


def main():
    print(f"HW3 self-check - SID4 {SID4}, DOMAIN_ID {DOMAIN_ID}\n")
    check_deliverables(); print()
    check_corpus(); print()
    check_questions(); print()
    check_results(); print()
    check_embedding()

    passed = sum(1 for c in checks if c["passed"])
    doc = {
        "homework": "HW3",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sid4": SID4,
        "port_base": PORT_BASE,
        "prefix": f"s{SID4}",
        "seed": SEED,
        "verify_seed": VERIFY_SEED,
        "domain_id": DOMAIN_ID,
        "domain": "Grocery supply and recall notices",
        "commit_hash": git("rev-parse", "HEAD") or "not committed",
        "tag": git("describe", "--tags", "--abbrev=0") or "no tag",
        "configuration": {
            "part1_model": "none - Part 1 is a FastAPI auth app, no model",
            "part2_embedding_model": EMBED_MODEL,
            "part2_embedding_dimension": 384,
            "part2_generative_model": "none - retrieval-only, Settings.llm = None",
            "top_k": 5,
            "chunkers": {
                "Token": "TokenTextSplitter(chunk_size=256, chunk_overlap=40)",
                "Semantic": "SemanticSplitterNodeParser(buffer_size=1, breakpoint_percentile_threshold=95)",
                "Sentence-window": "SentenceWindowNodeParser(window_size=3)",
            },
        },
        "total_checks": len(checks),
        "passed": passed,
        "failed": len(checks) - passed,
        "checks": checks,
    }

    out = path("reports", "hw03", "verification.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as f:
        json.dump(doc, f, indent=2)

    print(f"\n{passed}/{len(checks)} checks passed.")
    print("Written to reports/hw03/verification.json")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    sys.exit(main())
