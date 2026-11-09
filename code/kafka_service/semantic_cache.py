import hashlib
import os

import redis

from kafka_service.config import EMBED_DIM, EMBED_MODEL, QA_INDEX, QA_KEY_PREFIX

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

_embedder = None


def embed_text(text: str):
    global _embedder
    if _embedder is None:
        from sentence_transformers import SentenceTransformer

        print(f"loading embedding model {EMBED_MODEL}", flush=True)
        _embedder = SentenceTransformer(EMBED_MODEL)
    import numpy as np

    vector = _embedder.encode([text], normalize_embeddings=True)[0]
    return np.asarray(vector, dtype=np.float32)


def redis_client() -> redis.Redis:
    client = redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=False,
    )
    try:
        client.ping()
    except redis.RedisError as exc:
        raise SystemExit(
            "Redis is not running. Start it with:\n"
            "  docker compose -f code/web_application/docker-compose.redis.yml up -d\n"
            f"{exc}"
        ) from exc
    return client


def require_search(client: redis.Redis) -> None:
    try:
        modules = client.module_list()
    except redis.ResponseError:
        modules = []
    names = []
    for module in modules:
        name = module.get("name", module.get(b"name", ""))
        if isinstance(name, bytes):
            name = name.decode()
        names.append(name)
    if not any("search" in name for name in names):
        raise SystemExit(
            "This Redis has no vector index. Part 1 started plain Redis, and that image\n"
            "cannot store embeddings. Recreate the same container as Redis Stack:\n"
            "  bash scripts/setup_hw09_part2.sh"
        )


def _text(value) -> str:
    if isinstance(value, bytes):
        return value.decode()
    return "" if value is None else str(value)


class SemanticCache:
    """Cosine cache of question embeddings, stored under the s6491 prefix."""

    def __init__(self, client: redis.Redis | None = None):
        self.redis = client or redis_client()
        require_search(self.redis)
        self._ensure_index()

    def _ensure_index(self) -> None:
        from redis.commands.search.field import TextField, VectorField

        try:
            from redis.commands.search.index_definition import IndexDefinition, IndexType
        except ImportError:
            from redis.commands.search.indexDefinition import IndexDefinition, IndexType

        try:
            self.redis.ft(QA_INDEX).info()
            return
        except redis.ResponseError:
            pass
        schema = (
            TextField("query"),
            TextField("answer"),
            TextField("data_version"),
            TextField("recall_code"),
            VectorField(
                "embedding",
                "FLAT",
                {"TYPE": "FLOAT32", "DIM": EMBED_DIM, "DISTANCE_METRIC": "COSINE"},
            ),
        )
        definition = IndexDefinition(prefix=[QA_KEY_PREFIX], index_type=IndexType.HASH)
        self.redis.ft(QA_INDEX).create_index(schema, definition=definition)

    def reset(self) -> None:
        try:
            self.redis.ft(QA_INDEX).dropindex(delete_documents=True)
        except redis.ResponseError:
            pass
        self._ensure_index()

    def key_for(self, query: str) -> str:
        digest = hashlib.sha256(query.encode()).hexdigest()[:16]
        return f"{QA_KEY_PREFIX}{digest}"

    def store(self, query: str, answer: str, data_version: str, recall_code: str) -> str:
        key = self.key_for(query)
        self.redis.hset(
            key,
            mapping={
                "query": query,
                "answer": answer.replace("\n", " "),
                "data_version": str(data_version),
                "recall_code": recall_code or "",
                "embedding": embed_text(query).tobytes(),
            },
        )
        return key

    def search(self, query: str) -> dict | None:
        from redis.commands.search.query import Query

        statement = (
            Query("(*)=>[KNN 1 @embedding $vec AS vector_score]")
            .return_fields("query", "answer", "data_version", "recall_code", "vector_score")
            .sort_by("vector_score")
            .dialect(2)
        )
        try:
            found = self.redis.ft(QA_INDEX).search(
                statement,
                query_params={"vec": embed_text(query).tobytes()},
            )
        except redis.ResponseError:
            return None
        if not found.docs:
            return None
        doc = found.docs[0]
        distance = float(_text(doc.vector_score) or "1")
        similarity = max(0.0, min(1.0, 1.0 - distance))
        return {
            "key": _text(doc.id),
            "query": _text(doc.query),
            "answer": _text(doc.answer),
            "data_version": _text(doc.data_version),
            "recall_code": _text(doc.recall_code),
            "similarity": similarity,
        }

    def delete(self, key: str) -> None:
        if key:
            self.redis.delete(key)

    def entry(self, query: str) -> dict:
        raw = self.redis.hgetall(self.key_for(query))
        visible = {}
        for key, value in raw.items():
            name = _text(key)
            if name == "embedding":
                continue
            visible[name] = _text(value)
        return visible
