import uuid

from fastapi import APIRouter, HTTPException

from memory import ModelUnavailable, aggregate_view, memory_view, run_chat_turn
from memory_schemas import AggregateOut, ChatIn, ChatOut, MemoryOut

router = APIRouter(prefix="/api", tags=["memory"])


@router.post("/chat", response_model=ChatOut)
def post_chat(body: ChatIn):
    session_id = body.session_id or f"sess-{uuid.uuid4().hex[:8]}"
    try:
        return run_chat_turn(body.user_id, session_id, body.message.strip())
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/memory/{user_id}", response_model=MemoryOut)
def get_memory(user_id: str):
    return memory_view(user_id)


@router.get("/aggregate/{user_id}", response_model=AggregateOut)
def get_aggregate(user_id: str):
    return aggregate_view(user_id)
