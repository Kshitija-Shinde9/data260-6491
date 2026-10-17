import os
from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = "s6491_doc"
COLLECTION_NAME = "notices"

NOTICE_SCHEMA = {
    "bsonType": "object",
    "required": [
        "product_name",
        "status",
        "recall_type",
        "noticed_at",
        "created_at",
        "updated_at",
    ],
    "properties": {
        "product_name": {"bsonType": "string", "minLength": 1, "maxLength": 100},
        "description": {"bsonType": ["string", "null"], "maxLength": 2000},
        "status": {"enum": ["reported", "investigating", "resolved"]},
        "recall_type": {
            "enum": [
                "Packaging / Seal Failure",
                "Contamination",
                "Undeclared Allergen",
                "Spoiled or Quality Issue",
            ]
        },
        "noticed_at": {"bsonType": "date"},
        "created_at": {"bsonType": "date"},
        "updated_at": {"bsonType": "date"},
    },
}

_client = MongoClient(MONGO_URL)


def get_database() -> Database:
    return _client[DB_NAME]


def get_notices() -> Collection:
    return get_database()[COLLECTION_NAME]


def ensure_notices_collection() -> None:
    database = get_database()
    validator = {"$jsonSchema": NOTICE_SCHEMA}
    if COLLECTION_NAME not in database.list_collection_names():
        database.create_collection(
            COLLECTION_NAME,
            validator=validator,
            validationLevel="strict",
            validationAction="error",
        )
    else:
        database.command(
            "collMod",
            COLLECTION_NAME,
            validator=validator,
            validationLevel="strict",
            validationAction="error",
        )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
