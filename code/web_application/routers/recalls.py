from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

from database import get_db
from models import Recall, Supplier, User
from routers.api_auth import require_user
from schemas import RecallCreate, RecallOut, RecallUpdate

router = APIRouter(prefix="/api/recalls", tags=["recalls"])


def _get_recall_or_404(db: DBSession, recall_id: int) -> Recall:
    recall = db.get(Recall, recall_id)
    if not recall:
        raise HTTPException(status_code=404, detail="Recall notice not found")
    return recall


def _require_supplier(db: DBSession, supplier_id: int) -> Supplier:
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="supplier_id does not match any supplier")
    return supplier


@router.get("", response_model=List[RecallOut])
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
    rows = query.order_by(Recall.id).all()
    if not term:
        return rows
    return [
        r for r in rows
        if term in r.product_name.lower() or term in (r.recall_code or "").lower()
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
    return None


@router.get("/{recall_id}", response_model=RecallOut)
async def get_recall(
    recall_id: int,
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_user),
):
    return _get_recall_or_404(db, recall_id)


@router.post("", response_model=RecallOut, status_code=201)
async def create_recall(
    recall_data: RecallCreate,
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_user),
):
    _require_supplier(db, recall_data.supplier_id)
    new_recall = Recall(
        product_name=recall_data.product_name.strip(),
        recall_code=recall_data.recall_code.strip().upper(),
        affected_units=recall_data.affected_units,
        supplier_id=recall_data.supplier_id,
        email=recall_data.email,
        description=recall_data.description,
        recall_type=recall_data.recall_type,
    )
    db.add(new_recall)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="recall_code already exists")
    db.refresh(new_recall)
    return new_recall


@router.put("/{recall_id}", response_model=RecallOut)
async def update_recall(
    recall_id: int,
    recall_data: RecallUpdate,
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_user),
):
    recall = _get_recall_or_404(db, recall_id)
    data = recall_data.model_dump(exclude_unset=True)
    if "supplier_id" in data:
        _require_supplier(db, data["supplier_id"])
        recall.supplier_id = data["supplier_id"]
    if "product_name" in data:
        recall.product_name = data["product_name"].strip()
    if "recall_code" in data:
        recall.recall_code = data["recall_code"].strip().upper()
    if "affected_units" in data:
        recall.affected_units = data["affected_units"]
    for field in ("email", "description", "recall_type"):
        if field in data and data[field] is not None:
            setattr(recall, field, data[field])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="recall_code already exists")
    db.refresh(recall)
    return recall


@router.delete("/{recall_id}", status_code=204)
async def delete_recall(
    recall_id: int,
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_user),
):
    recall = _get_recall_or_404(db, recall_id)
    db.delete(recall)
    db.commit()
    return None
