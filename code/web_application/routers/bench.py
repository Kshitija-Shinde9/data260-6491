from contextlib import contextmanager
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import event
from sqlalchemy.orm import Session as DBSession, selectinload

from database import engine, get_db
from models import Recall, RecallNote, User
from routers.api_auth import require_user

router = APIRouter(prefix="/api/bench", tags=["bench"])


class RecallNoteOut(BaseModel):
    id: int
    note: str
    created_at: datetime

    class Config:
        from_attributes = True


class RecallWithNotesOut(BaseModel):
    id: int
    product_name: str
    supplier: str
    notes: List[RecallNoteOut]


@contextmanager
def count_queries():
    count = 0

    def _on_execute(*args, **kwargs):
        nonlocal count
        count += 1

    event.listen(engine, "before_cursor_execute", _on_execute)
    try:
        yield lambda: count
    finally:
        event.remove(engine, "before_cursor_execute", _on_execute)


@router.get("/naive", response_model=List[RecallWithNotesOut])
async def list_recalls_naive(
    response: Response,
    page_size: int = Query(10, ge=1, le=1000),
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_user),
):
    with count_queries() as get_count:
        recalls = db.query(Recall).order_by(Recall.id).limit(page_size).all()

        results = []
        for recall in recalls:
            notes = db.query(RecallNote).filter(RecallNote.recall_id == recall.id).all()
            results.append({
                "id": recall.id,
                "product_name": recall.product_name,
                "supplier": recall.supplier,
                "notes": notes,
            })

    response.headers["X-Query-Count"] = str(get_count())
    return results

@router.get("/fixed", response_model=List[RecallWithNotesOut])
async def list_recalls_fixed(
    response: Response,
    page_size: int = Query(10, ge=1, le=1000),
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_user),
):
    with count_queries() as get_count:
        recalls = (
            db.query(Recall)
            .options(selectinload(Recall.notes))
            .order_by(Recall.id)
            .limit(page_size)
            .all()
        )

        results = [
            {
                "id": recall.id,
                "product_name": recall.product_name,
                "supplier": recall.supplier,
                "notes": recall.notes,
            }
            for recall in recalls
        ]

    response.headers["X-Query-Count"] = str(get_count())
    return results