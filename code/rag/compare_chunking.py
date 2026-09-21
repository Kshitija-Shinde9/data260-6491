import csv
import os
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np
import yaml
from llama_index.core import Settings, SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.node_parser import (
    SemanticSplitterNodeParser,
    SentenceWindowNodeParser,
    TokenTextSplitter,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
CORPUS_DIR = os.path.join(ROOT, "data", "corpus")
REPORT_DIR = os.path.join(ROOT, "reports", "hw03")
RAW_DIR = os.path.join(REPORT_DIR, "raw")

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOP_K = 5


def cosine(a, b):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def build_chunkers(embed_model):
    return {
        "Token": TokenTextSplitter(chunk_size=256, chunk_overlap=40),
        "Semantic": SemanticSplitterNodeParser(
            buffer_size=1,
            breakpoint_percentile_threshold=95,
            embed_model=embed_model,
        ),
        "Sentence-window": SentenceWindowNodeParser.from_defaults(
            window_size=3,
            window_metadata_key="window",
            original_text_metadata_key="original_text",
        ),
    }


def retrieve(technique, index, embed_model, question, expected_source):
    qvec = embed_model.get_query_embedding(question["question"])

    print(f"\nTECHNIQUE: {technique}   QUESTION: {question['id']}")
    print(f"  {question['question']}")
    print(f"  query embedding dimension : {len(qvec)}")
    print(f"  first 8 values            : {[round(v, 4) for v in qvec[:8]]}")

    retriever = index.as_retriever(similarity_top_k=TOP_K)
    t0 = time.perf_counter()
    hits = retriever.retrieve(question["question"])
    latency_ms = (time.perf_counter() - t0) * 1000

    doc_vectors = [embed_model.get_text_embedding(h.node.get_content()) for h in hits]
    stacked = np.array(doc_vectors)

    print(f"  query vector shape        : {np.array(qvec).shape}")
    print(f"  stacked doc vector shape  : {stacked.shape}")
    print(f"  retrieval latency         : {latency_ms:.2f} ms")
    print()
    print(f"  {'rank':<6}{'store_score':<14}{'cosine_sim':<13}{'chunk_len':<11}preview")
    print("  " + "-" * 100)

    rows = []
    for rank, (hit, dvec) in enumerate(zip(hits, doc_vectors), 1):
        text = hit.node.get_content().replace("\n", " ")
        source = hit.node.metadata.get("file_name", "")
        sim = cosine(qvec, dvec)
        preview = text[:160]

        print(f"  {rank:<6}{hit.score:<14.4f}{sim:<13.4f}{len(text):<11}{preview[:70]}")

        rows.append({
            "question_id": question["id"],
            "technique": technique,
            "rank": rank,
            "store_score": round(hit.score, 6),
            "cosine_sim": round(sim, 6),
            "chunk_len": len(text),
            "source_file": source,
            "expected_source": expected_source,
            "is_expected": int(source == expected_source),
            "latency_ms": round(latency_ms, 3),
            "preview": preview,
        })

    return rows


def main():
    os.makedirs(RAW_DIR, exist_ok=True)

    embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL)
    Settings.embed_model = embed_model
    Settings.llm = None

    docs = SimpleDirectoryReader(input_dir=CORPUS_DIR).load_data()
    questions = yaml.safe_load(open(os.path.join(REPORT_DIR, "questions.yaml")))["questions"]

    print(f"documents : {len(docs)}")
    print(f"questions : {len(questions)}")
    print(f"embedding : {EMBED_MODEL}  top_k={TOP_K}")

    all_rows = []
    chunk_stats = []

    for technique, chunker in build_chunkers(embed_model).items():
        print("\n" + "=" * 106)
        print(f"BUILDING: {technique}")
        print("=" * 106)

        t0 = time.perf_counter()
        nodes = chunker.get_nodes_from_documents(docs)
        chunk_ms = (time.perf_counter() - t0) * 1000

        lengths = [len(n.get_content()) for n in nodes]
        print(f"  chunks           : {len(nodes)}")
        print(f"  avg chunk length : {sum(lengths) / len(lengths):.1f} characters")
        print(f"  chunking time    : {chunk_ms:.0f} ms")

        index = VectorStoreIndex(nodes, embed_model=embed_model, show_progress=False)

        chunk_stats.append({
            "technique": technique,
            "chunks": len(nodes),
            "avg_chunk_length": round(sum(lengths) / len(lengths), 2),
            "chunking_ms": round(chunk_ms, 2),
        })

        for q in questions:
            all_rows.append(retrieve(technique, index, embed_model, q, q["expected_source"]))

    all_rows = [r for group in all_rows for r in group]

    retrieval_csv = os.path.join(RAW_DIR, "retrieval_results.csv")
    with open(retrieval_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        writer.writeheader()
        writer.writerows(all_rows)

    chunk_csv = os.path.join(RAW_DIR, "chunk_stats.csv")
    with open(chunk_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(chunk_stats[0].keys()))
        writer.writeheader()
        writer.writerows(chunk_stats)

    print("\n" + "=" * 106)
    print(f"wrote {len(all_rows)} rows -> reports/hw03/raw/retrieval_results.csv")
    print(f"wrote {len(chunk_stats)} rows -> reports/hw03/raw/chunk_stats.csv")
    print("=" * 106)


if __name__ == "__main__":
    main()
