from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from database import get_db
from models import Recall, User
from routers.api_auth import require_user

router = APIRouter(prefix="/api/recalls", tags=["recalls"])


class RecallNotice(BaseModel):
    id: int
    product_name: str
    supplier: str
    email: str = ""
    description: str = ""
    recall_type: str = ""

    class Config:
        from_attributes = True


class RecallCreate(BaseModel):
    product_name: str
    supplier: str
    email: str = ""
    description: str = ""
    recall_type: str = ""


class RecallUpdate(BaseModel):
    product_name: str
    supplier: str


@router.get("", response_model=List[RecallNotice])
async def get_recalls(
    response: Response,
    search: str = "",
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_user),
):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"

    query = db.query(Recall)
    term = search.strip().lower()
    if not term:
        return query.all()

    return [
        recall for recall in query.all()
        if term in recall.product_name.lower() or term in recall.supplier.lower()
    ]


@router.delete("/highest", status_code=204)
async def delete_highest_recall(
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_user),
):
    highest = db.query(Recall).order_by(Recall.id.desc()).first()
    if not highest:
        raise HTTPException(status_code=404, detail="There are no recall notices to delete")

    db.delete(highest)
    db.commit()

    print(f"Deleted highest-ID recall notice: {highest.id}")
    return None


@router.get("/{recall_id}", response_model=RecallNotice)
async def get_recall(
    recall_id: int,
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_user),
):
    recall = db.get(Recall, recall_id)
    if not recall:
        raise HTTPException(status_code=404, detail="Recall notice not found")
    return recall


@router.post("", response_model=RecallNotice, status_code=201)
async def create_recall(
    recall_data: RecallCreate,
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_user),
):
    if not recall_data.product_name.strip():
        raise HTTPException(status_code=400, detail="Product name is required")
    if not recall_data.supplier.strip():
        raise HTTPException(status_code=400, detail="Supplier / brand is required")

    new_recall = Recall(**recall_data.model_dump())
    db.add(new_recall)
    db.commit()
    db.refresh(new_recall)

    print(f"Created recall notice: {new_recall.id}")
    return new_recall


@router.put("/{recall_id}", response_model=RecallNotice)
async def update_recall(
    recall_id: int,
    recall_data: RecallUpdate,
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_user),
):
    recall = db.get(Recall, recall_id)

    if not recall:
        raise HTTPException(status_code=404, detail="Recall notice not found")

    if not recall_data.product_name.strip():
        raise HTTPException(status_code=400, detail="Product name is required")
    if not recall_data.supplier.strip():
        raise HTTPException(status_code=400, detail="Supplier / brand is required")

    recall.product_name = recall_data.product_name
    recall.supplier = recall_data.supplier
    db.commit()
    db.refresh(recall)

    print(f"Updated recall notice: {recall.id}")
    return recall


@router.delete("/{recall_id}", status_code=204)
async def delete_recall(
    recall_id: int,
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_user),
):
    recall = db.get(Recall, recall_id)

    if not recall:
        raise HTTPException(status_code=404, detail="Recall notice not found")

    db.delete(recall)
    db.commit()
    print(f"Deleted recall notice: {recall_id}")
    return None
