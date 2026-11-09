import logging
import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WEB = REPO / "code" / "web_application"
sys.path.insert(0, str(REPO / "code"))
sys.path.insert(0, str(WEB))

from dotenv import load_dotenv

load_dotenv(WEB / ".env")

from database import SessionLocal  # noqa: E402
from models import Recall  # noqa: E402
from recall_cache import (  # noqa: E402
    RecallCache,
    ensure_view_count_column,
    redis_client,
    view_key,
)

RECALL_ID = 1
ACCESSES = 25


class _Grab(logging.Handler):
    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


def main() -> None:
    name = os.getenv("STUDENT_NAME", "").strip()
    if not name:
        raise SystemExit('Set your name first: export STUDENT_NAME="Your Full Name"')
    if not os.getenv("DATABASE_URL"):
        raise SystemExit(
            "DATABASE_URL is missing. Put it in code/web_application/.env\n"
            "  DATABASE_URL=mysql+pymysql://USER:PASSWORD@127.0.0.1:3306/s6491_rel"
        )

    print(f"student: {name}")
    print("prefix: s6491")
    print("part: 1 view counter")
    print(flush=True)

    ensure_view_count_column()
    client = redis_client()
    db = SessionLocal()
    try:
        recall = db.get(Recall, RECALL_ID)
        if recall is None:
            raise SystemExit(
                "No recall with id 1 in s6491_rel. Start the web app once so it seeds the three notices."
            )
        recall.view_count = 0
        db.commit()
        client.delete(view_key(RECALL_ID))

        logger = logging.getLogger("recall_cache")
        logger.setLevel(logging.INFO)
        logger.propagate = False
        grab = _Grab()
        logger.handlers = [grab]
        cache = RecallCache(db, client)

        print(f"student: {name}")
        print("=== Testing Counter ===")
        print()
        for number in range(1, ACCESSES + 1):
            grab.messages.clear()
            count = cache.increment_recall_views(RECALL_ID)
            print(f"Access #{number}: Total = {count}")
            if any("Synced views to database" in message for message in grab.messages):
                print("✓ Synced views to database")

        db.refresh(recall)
        print()
        print(f"student: {name}")
        print(f"Redis key {view_key(RECALL_ID)} = {client.get(view_key(RECALL_ID))}")
        print(f"Database s6491_rel recalls.id={RECALL_ID} view_count = {recall.view_count}")
        print("The last sync was at 20. Accesses 21-25 are only in Redis until the next 10th view.")
        print()
        print("Optional second check:")
        print(f"  docker exec s6491_redis redis-cli GET {view_key(RECALL_ID)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
