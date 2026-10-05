from contextlib import contextmanager
from typing import List

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import event
from sqlalchemy.orm import Session as DBSession, selectinload

from database import engine, get_db
from models import Recall, User
from routers.api_auth import require_user

router = APIRouter(prefix="/api/bench", tags=["bench"])


class RecallBenchOut(BaseModel):
    id: int
    product_name: str
    supplier: str
    notes: List[str] = []


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


@router.get("/naive", response_model=List[RecallBenchOut])
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
            supplier = recall.supplier
            results.append({
                "id": recall.id,
                "product_name": recall.product_name,
                "supplier": supplier.name if supplier else "",
                "notes": [],
            })

    response.headers["X-Query-Count"] = str(get_count())
    return results


@router.get("/fixed", response_model=List[RecallBenchOut])
async def list_recalls_fixed(
    response: Response,
    page_size: int = Query(10, ge=1, le=1000),
    db: DBSession = Depends(get_db),
    _user: User = Depends(require_user),
):
    with count_queries() as get_count:
        recalls = (
            db.query(Recall)
            .options(selectinload(Recall.supplier))
            .order_by(Recall.id)
            .limit(page_size)
            .all()
        )

        results = [
            {
                "id": recall.id,
                "product_name": recall.product_name,
                "supplier": recall.supplier.name if recall.supplier else "",
                "notes": [],
            }
            for recall in recalls
        ]

    response.headers["X-Query-Count"] = str(get_count())
    return results
