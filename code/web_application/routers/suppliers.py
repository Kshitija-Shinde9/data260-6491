from typing import List

from database import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from models import Recall, Supplier, User
from routers.jwt_auth import get_current_user, require_roles
from schemas import RecallOut, SupplierCreate, SupplierOut, SupplierUpdate
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DBSession

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.post("", response_model=SupplierOut, status_code=201)
def create_supplier(
    payload: SupplierCreate,
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_roles("writer", "moderator")),
):
    supplier = Supplier(
        name=payload.name.strip(),
        headquarters=payload.headquarters.strip(),
        supplier_code=payload.supplier_code.strip().upper(),
    )
    db.add(supplier)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="supplier_code already exists")
    db.refresh(supplier)
    return supplier


@router.get("", response_model=List[SupplierOut])
def list_suppliers(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: DBSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return db.query(Supplier).order_by(Supplier.id).offset(skip).limit(limit).all()


@router.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier(
    supplier_id: int,
    db: DBSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.put("/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: int,
    payload: SupplierUpdate,
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_roles("writer", "moderator")),
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        supplier.name = data["name"].strip()
    if "headquarters" in data:
        supplier.headquarters = data["headquarters"].strip()
    if "supplier_code" in data:
        supplier.supplier_code = data["supplier_code"].strip().upper()

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="supplier_code already exists")
    db.refresh(supplier)
    return supplier


@router.delete("/{supplier_id}", status_code=204)
def delete_supplier(
    supplier_id: int,
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_roles("moderator")),
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    child_count = db.query(Recall).filter(Recall.supplier_id == supplier_id).count()
    if child_count:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot delete supplier {supplier_id}: {child_count} recall(s) still reference it",
        )

    db.delete(supplier)
    db.commit()
    return None


@router.get("/{supplier_id}/recalls", response_model=List[RecallOut])
def list_recalls_for_supplier(
    supplier_id: int,
    db: DBSession = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    supplier = db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return db.query(Recall).filter(Recall.supplier_id == supplier_id).order_by(Recall.id).all()
