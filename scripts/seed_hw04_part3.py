import os
import random
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_DIR = os.path.join(ROOT, "code", "web_application")
sys.path.insert(0, APP_DIR)

from database import Base, SessionLocal, engine
from models import Recall, RecallNote

SEED = 6491
RECALL_COUNT = 5000
NOTE_COUNT = 200


def main():
    random.seed(SEED)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing_notes = db.query(RecallNote).count()
        if existing_notes >= NOTE_COUNT:
            print(f"recall_notes already has {existing_notes} rows, skipping seed.")
            return

        recall_types = [
            "Packaging / Seal Failure",
            "Contamination",
            "Undeclared Allergen",
            "Spoiled or Quality Issue",
        ]

        new_recalls = []
        for i in range(1, RECALL_COUNT + 1):
            new_recalls.append(Recall(
                product_name=f"Bench Product {i}",
                supplier=f"Bench Supplier {i % 50}",
                email="bench@example.com",
                description=f"Synthetic benchmark record #{i} for HW4 Part 3 N+1 testing.",
                recall_type=recall_types[i % len(recall_types)],
            ))

        db.add_all(new_recalls)
        db.commit()

        for recall in new_recalls:
            db.refresh(recall)
        recall_ids = sorted(r.id for r in new_recalls)

        target_ids = recall_ids[:NOTE_COUNT]
        new_notes = [
            RecallNote(
                recall_id=recall_id,
                note=f"Bench note for recall {recall_id}",
                created_at=datetime.now(timezone.utc).replace(tzinfo=None),
            )
            for recall_id in target_ids
        ]
        db.add_all(new_notes)
        db.commit()

        print(f"Inserted {len(new_recalls)} recalls (ids {recall_ids[0]}-{recall_ids[-1]}).")
        print(f"Inserted {len(new_notes)} recall_notes for recall ids {target_ids[0]}-{target_ids[-1]}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
