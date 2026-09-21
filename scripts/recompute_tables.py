import collections
import csv
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
RAW = os.path.join(ROOT, "reports", "hw03", "raw")

TECHNIQUES = ["Token", "Semantic", "Sentence-window"]


def load():
    rows = list(csv.DictReader(open(os.path.join(RAW, "retrieval_results.csv"))))
    chunks = {r["technique"]: r for r in csv.DictReader(open(os.path.join(RAW, "chunk_stats.csv")))}
    return rows, chunks


def by_question(rows, technique):
    grouped = collections.defaultdict(list)
    for r in rows:
        if r["technique"] == technique:
            grouped[r["question_id"]].append(r)
    return grouped


def summarise(rows, chunks):
    table = []
    for t in TECHNIQUES:
        grouped = by_question(rows, t)
        top1 = statistics.mean(max(float(x["cosine_sim"]) for x in v) for v in grouped.values())
        meank = statistics.mean(float(r["cosine_sim"]) for r in rows if r["technique"] == t)
        recall = sum(1 for v in grouped.values() if any(x["is_expected"] == "1" for x in v)) / len(grouped)
        latency = statistics.mean(float(v[0]["latency_ms"]) for v in grouped.values())
        table.append({
            "technique": t,
            "chunks": int(chunks[t]["chunks"]),
            "avg_chunk_length": float(chunks[t]["avg_chunk_length"]),
            "top1_cosine": top1,
            "meank_cosine": meank,
            "recall_at_k": recall,
            "latency_ms": latency,
            "chunking_ms": float(chunks[t]["chunking_ms"]),
        })
    return table


def per_question(rows):
    out = []
    for q in sorted({r["question_id"] for r in rows}):
        row = {"question_id": q}
        for t in TECHNIQUES:
            hits = [r for r in rows if r["question_id"] == q and r["technique"] == t]
            row[t] = {
                "top1": max(float(h["cosine_sim"]) for h in hits),
                "found": any(h["is_expected"] == "1" for h in hits),
                "best_rank": min((int(h["rank"]) for h in hits if h["is_expected"] == "1"), default=None),
            }
        out.append(row)
    return out


def banner(n, title):
    print()
    print("=" * 96)
    print(f"METRIC {n}: {title}")
    print("=" * 96)


def main():
    rows, chunks = load()
    k = max(int(r["rank"]) for r in rows)
    qids = sorted({r["question_id"] for r in rows})
    table = summarise(rows, chunks)
    perq = per_question(rows)

    print(f"Recomputed from reports/hw03/raw/retrieval_results.csv ({len(rows)} rows)")
    print(f"{len(qids)} questions x {len(TECHNIQUES)} techniques x top-{k}")

    banner(1, "top-1 cosine (highest similarity among the top-k for that technique)")
    print(f"  {'Technique':<20}{'Top-1 cosine':<16}per-question best cosine")
    print("  " + "-" * 92)
    for t in TECHNIQUES:
        grouped = by_question(rows, t)
        bests = [max(float(x["cosine_sim"]) for x in grouped[q]) for q in qids]
        detail = "  ".join(f"{q}={b:.4f}" for q, b in zip(qids, bests))
        print(f"  {t:<20}{statistics.mean(bests):<16.4f}{detail}")
    print()
    print("  Reported as the mean across the 5 questions of the highest cosine inside that")
    print("  question's top-5, so it reflects consistency rather than one best case.")

    banner(2, "mean@k cosine (average of top-k cosines)")
    print(f"  {'Technique':<20}{'Mean@k cosine':<17}{'k':<5}{'values averaged':<18}min      max")
    print("  " + "-" * 92)
    for t in TECHNIQUES:
        vals = [float(r["cosine_sim"]) for r in rows if r["technique"] == t]
        print(f"  {t:<20}{statistics.mean(vals):<17.4f}{k:<5}{len(vals):<18}{min(vals):.4f}   {max(vals):.4f}")
    print()
    print(f"  Every cosine in every top-{k} list is averaged: {len(qids)} questions x {k} ranks = {len(qids)*k} values per technique.")

    banner(3, "#chunks produced by the chunker and the avg chunk length (characters or tokens)")
    print(f"  {'Technique':<20}{'Chunks':<12}{'Avg chunk length':<22}{'Chunking time (ms)':<22}")
    print("  " + "-" * 92)
    for r in table:
        print(f"  {r['technique']:<20}{r['chunks']:<12}{r['avg_chunk_length']:<22.1f}{r['chunking_ms']:<22.0f}")
    print()
    print("  Avg chunk length is measured in CHARACTERS.")
    print("  Chunking time is the cost of building the chunks, separate from search latency.")

    banner(4, "retrieval latency in milliseconds (time the similarity search took)")
    print(f"  {'Technique':<20}{'Mean latency (ms)':<21}{'Chunks searched':<19}per-question latency (ms)")
    print("  " + "-" * 92)
    for t in TECHNIQUES:
        grouped = by_question(rows, t)
        lats = [float(grouped[q][0]["latency_ms"]) for q in qids]
        n = int(chunks[t]["chunks"])
        detail = "  ".join(f"{v:.2f}" for v in lats)
        print(f"  {t:<20}{statistics.mean(lats):<21.2f}{n:<19}{detail}")
    print()
    print("  Timed with time.perf_counter() around retriever.retrieve() only, so it measures")
    print("  the similarity search and excludes chunking and index construction.")

    banner("R", "Recall@k  (not defined in the assignment - defined here)")
    print(f"  {'Technique':<20}{'Recall@k':<12}{'questions found':<18}k")
    print("  " + "-" * 92)
    for t in TECHNIQUES:
        grouped = by_question(rows, t)
        found = sum(1 for q in qids if any(x["is_expected"] == "1" for x in grouped[q]))
        print(f"  {t:<20}{found/len(qids):<12.0%}{f'{found} of {len(qids)}':<18}{k}")
    print()
    print("  Recall@k = fraction of questions whose expected_source from questions.yaml")
    print(f"  appeared anywhere in the top-{k} results.")

    print()
    print("=" * 96)
    print("COMBINED TABLE (the assignment's format)")
    print("=" * 96)
    print()
    print("| Technique | Chunks | Avg chunk length | Top-1 cosine | Mean@k cosine | Recall@k | Mean retrieval latency (ms) |")
    print("|---|---|---|---|---|---|---|")
    for r in table:
        print(f"| {r['technique']} | {r['chunks']} | {r['avg_chunk_length']:.1f} | "
              f"{r['top1_cosine']:.4f} | {r['meank_cosine']:.4f} | "
              f"{r['recall_at_k']:.0%} | {r['latency_ms']:.2f} |")

    print()
    print("=" * 96)
    print(f"PER QUESTION: was the expected source found in the top-{k}?")
    print("=" * 96)
    print()
    print(f"  {'Question':<12}" + "".join(f"{t:<30}" for t in TECHNIQUES))
    print("  " + "-" * 92)
    for r in perq:
        cells = ""
        for t in TECHNIQUES:
            d = r[t]
            where = "rank " + str(d["best_rank"]) if d["found"] else "NOT FOUND"
            cells += f"{where}, top1 {d['top1']:.3f}".ljust(30)
        print(f"  {r['question_id']:<12}{cells}")


if __name__ == "__main__":
    main()
