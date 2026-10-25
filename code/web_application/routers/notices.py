from typing import List

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, HTTPException
from mongo_db import get_notices, utcnow
from mongo_schemas import NoticeCreate, NoticeOut, NoticeUpdate
from pymongo import ReturnDocument

router = APIRouter(prefix="/api/notices", tags=["notices"])


def _to_out(doc: dict) -> NoticeOut:
    return NoticeOut(
        id=str(doc["_id"]),
        product_name=doc["product_name"],
        description=doc.get("description"),
        status=doc["status"],
        recall_type=doc["recall_type"],
        noticed_at=doc["noticed_at"],
        created_at=doc["created_at"],
        updated_at=doc["updated_at"],
    )


def _parse_id(notice_id: str) -> ObjectId:
    try:
        return ObjectId(notice_id)
    except InvalidId:
        raise HTTPException(status_code=400, detail="Invalid notice id")


@router.post("", response_model=NoticeOut, status_code=201)
def create_notice(body: NoticeCreate):
    now = utcnow()
    document = body.model_dump()
    document["status"] = body.status.value
    document["recall_type"] = body.recall_type.value
    document["created_at"] = now
    document["updated_at"] = now
    result = get_notices().insert_one(document)
    saved = get_notices().find_one({"_id": result.inserted_id})
    return _to_out(saved)


@router.get("", response_model=List[NoticeOut])
def list_notices():
    cursor = get_notices().find().sort("created_at", -1)
    return [_to_out(doc) for doc in cursor]


@router.get("/{notice_id}", response_model=NoticeOut)
def get_notice(notice_id: str):
    doc = get_notices().find_one({"_id": _parse_id(notice_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Notice not found")
    return _to_out(doc)


@router.put("/{notice_id}", response_model=NoticeOut)
def update_notice(notice_id: str, body: NoticeUpdate):
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "status" in changes and changes["status"] is not None:
        changes["status"] = changes["status"].value
    if "recall_type" in changes and changes["recall_type"] is not None:
        changes["recall_type"] = changes["recall_type"].value
    changes["updated_at"] = utcnow()
    updated = get_notices().find_one_and_update(
        {"_id": _parse_id(notice_id)},
        {"$set": changes},
        return_document=ReturnDocument.AFTER,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Notice not found")
    return _to_out(updated)


@router.delete("/{notice_id}", status_code=204)
def delete_notice(notice_id: str):
    result = get_notices().delete_one({"_id": _parse_id(notice_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notice not found")
    return None
