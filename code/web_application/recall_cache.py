import logging
import os
import sys
from pathlib import Path

import redis
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

_CODE = Path(__file__).resolve().parents[1]
if str(_CODE) not in sys.path:
    sys.path.insert(0, str(_CODE))

from kafka_service.config import PREFIX  # noqa: E402
from models import Recall  # noqa: E402

log = logging.getLogger("recall_cache")


def view_key(recall_id: int) -> str:
    return f"{PREFIX}:views:recall:{recall_id}"


def redis_client() -> redis.Redis:
    client = redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
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


def ensure_view_count_column() -> None:
    """Add recalls.view_count when this database was created before HW9."""
    from database import engine

    columns = {column["name"] for column in inspect(engine).get_columns("recalls")}
    if "view_count" in columns:
        return
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE recalls ADD COLUMN view_count INT NOT NULL DEFAULT 0"))


class RecallCache:
    """Redis view counter for a recall row in s6491_rel."""

    def __init__(self, db: Session, redis_client: redis.Redis | None = None):
        self.db = db
        self.redis_client = redis_client if redis_client is not None else redis_client_from_env()

    def increment_recall_views(self, recall_id: int) -> int:
        key = view_key(recall_id)
        count = int(self.redis_client.incr(key))
        if count % 10 == 0:
            recall = self.db.get(Recall, recall_id)
            if recall is None:
                raise KeyError(f"no recall with id {recall_id}")
            recall.view_count = count
            self.db.commit()
            log.info("Synced views to database")
        return count


def redis_client_from_env() -> redis.Redis:
    return redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True,
    )
