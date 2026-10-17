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

MESSAGE_SCHEMA = {
    "bsonType": "object",
    "required": ["user_id", "session_id", "role", "content", "created_at"],
    "properties": {
        "user_id": {"bsonType": "string", "minLength": 1},
        "session_id": {"bsonType": "string", "minLength": 1},
        "role": {"enum": ["user", "assistant"]},
        "content": {"bsonType": "string", "minLength": 1},
        "created_at": {"bsonType": "date"},
    },
}

SUMMARY_SCHEMA = {
    "bsonType": "object",
    "required": ["user_id", "session_id", "scope", "text", "created_at"],
    "properties": {
        "user_id": {"bsonType": "string", "minLength": 1},
        "session_id": {"bsonType": ["string", "null"]},
        "scope": {"enum": ["session", "user"]},
        "text": {"bsonType": "string", "minLength": 1},
        "created_at": {"bsonType": "date"},
    },
}

EPISODE_SCHEMA = {
    "bsonType": "object",
    "required": ["user_id", "session_id", "fact", "importance", "embedding", "created_at"],
    "properties": {
        "user_id": {"bsonType": "string", "minLength": 1},
        "session_id": {"bsonType": "string", "minLength": 1},
        "fact": {"bsonType": "string", "minLength": 1, "maxLength": 200},
        "importance": {"bsonType": "double", "minimum": 0, "maximum": 1},
        "embedding": {"bsonType": "array", "items": {"bsonType": "double"}},
        "created_at": {"bsonType": "date"},
    },
}

_client = MongoClient(MONGO_URL)


def get_database() -> Database:
    return _client[DB_NAME]


def get_notices() -> Collection:
    return get_database()[COLLECTION_NAME]


def get_messages() -> Collection:
    return get_database()["messages"]


def get_summaries() -> Collection:
    return get_database()["summaries"]


def get_episodes() -> Collection:
    return get_database()["episodes"]


def _ensure_collection(name: str, schema: dict) -> None:
    database = get_database()
    validator = {"$jsonSchema": schema}
    if name not in database.list_collection_names():
        database.create_collection(
            name,
            validator=validator,
            validationLevel="strict",
            validationAction="error",
        )
    else:
        database.command(
            "collMod",
            name,
            validator=validator,
            validationLevel="strict",
            validationAction="error",
        )


def ensure_notices_collection() -> None:
    _ensure_collection(COLLECTION_NAME, NOTICE_SCHEMA)


def ensure_memory_collections() -> None:
    _ensure_collection("messages", MESSAGE_SCHEMA)
    _ensure_collection("summaries", SUMMARY_SCHEMA)
    _ensure_collection("episodes", EPISODE_SCHEMA)
    get_messages().create_index([("session_id", 1), ("created_at", 1)])
    get_messages().create_index([("user_id", 1), ("created_at", 1)])
    get_summaries().create_index([("user_id", 1), ("created_at", -1)])
    get_episodes().create_index([("user_id", 1), ("created_at", -1)])


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
