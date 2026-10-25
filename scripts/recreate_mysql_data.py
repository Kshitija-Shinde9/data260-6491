"""Create the s6491_rel schema and restore the repository's demo data.

This script is intentionally non-destructive: it never drops tables or rows.
Create the database first, set DATABASE_URL, then run this file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import bcrypt

ROOT = Path(__file__).resolve().parents[1]
WEB_APP = ROOT / "code" / "web_application"
sys.path.insert(0, str(WEB_APP))

from database import Base, SessionLocal, engine  # noqa: E402
from models import Recall, Supplier, User  # noqa: E402


def seed_database() -> None:
    if not os.getenv("DATABASE_URL"):
        raise SystemExit("Set DATABASE_URL before running this script.")

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        suppliers = [
            ("Trader Joe's", "Monrovia, CA", "SUP-0001"),
            ("Safeway Deli", "Pleasanton, CA", "SUP-0002"),
            ("Costco Wholesale", "Issaquah, WA", "SUP-0003"),
        ]
        for name, headquarters, supplier_code in suppliers:
            if not db.query(Supplier).filter_by(supplier_code=supplier_code).first():
                db.add(
                    Supplier(
                        name=name,
                        headquarters=headquarters,
                        supplier_code=supplier_code,
                    )
                )
        db.commit()

        supplier_by_code = {
            row.supplier_code: row
            for row in db.query(Supplier).filter(
                Supplier.supplier_code.in_([item[2] for item in suppliers])
            )
        }
        recalls = [
            (
                "Trader Joe's Organic Frozen Blueberries, 16oz",
                "REC-0001",
                120,
                "SUP-0001",
                "rohan1@gmail.com",
                "Small tear near the top seal, frost buildup on the berries.",
                "Packaging / Seal Failure",
            ),
            (
                "Safeway Signature Rotisserie Chicken",
                "REC-0002",
                40,
                "SUP-0002",
                "rohan1@gmail.com",
                "Served lukewarm from the hot case, pack date two days old.",
                "Spoiled or Quality Issue",
            ),
            (
                "Kirkland Signature Trail Mix, 4lb",
                "REC-0003",
                75,
                "SUP-0003",
                "rohan1@gmail.com",
                "Ingredient panel does not list peanuts but peanuts are in the bag.",
                "Undeclared Allergen",
            ),
        ]
        for (
            product_name,
            recall_code,
            units,
            supplier_code,
            email,
            description,
            recall_type,
        ) in recalls:
            if not db.query(Recall).filter_by(recall_code=recall_code).first():
                db.add(
                    Recall(
                        product_name=product_name,
                        recall_code=recall_code,
                        affected_units=units,
                        supplier_id=supplier_by_code[supplier_code].id,
                        email=email,
                        description=description,
                        recall_type=recall_type,
                    )
                )

        users = [
            ("admin", "Admin User", "admin@s6491.com", "Recall@6491", "moderator"),
            ("reader", "Reader User", "reader@s6491.com", "Reader@6491", "reader"),
            ("writer", "Writer User", "writer@s6491.com", "Writer@6491", "writer"),
        ]
        for username, name, email, password, role in users:
            user = db.query(User).filter_by(username=username).first()
            if user is None:
                db.add(
                    User(
                        username=username,
                        name=name,
                        email=email,
                        password_hash=bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
                        role=role,
                    )
                )
            else:
                user.role = role
        db.commit()

        print("Database schema is ready.")
        print("Demo suppliers, recalls, and users are present.")
        print("No existing tables or rows were deleted.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
