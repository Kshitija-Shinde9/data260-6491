import sys
import threading
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Body, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from kafka_service.config import CREATE_OPERATION, GET_OPERATION  # noqa: E402
from kafka_service.flow_log import log_flow  # noqa: E402

router = APIRouter(prefix="/api/kafka", tags=["kafka-recalls"])

_client = None
_client_lock = threading.Lock()


class KafkaRequestIn(BaseModel):
    operation: str = Field(min_length=1)
    data: dict[str, Any] = Field(default_factory=dict)


def get_kafka_client():
    global _client
    with _client_lock:
        if _client is None:
            from kafka_service.kafka_client import RecallKafkaClient

            _client = RecallKafkaClient(component="API").start()
        return _client


def close_kafka_client() -> None:
    global _client
    with _client_lock:
        if _client is not None:
            _client.close()
            _client = None


def _status_for(response: dict, success_status: int) -> int:
    if response.get("success"):
        return success_status
    error = str(response.get("error", ""))
    if error.startswith("Timed out"):
        return 504
    if error.endswith("not found"):
        return 404
    return 400


def forward_to_worker(
    operation: str,
    data: dict,
    correlation_id: Optional[str],
    http_route: str,
    success_status: int = 200,
) -> JSONResponse:
    from kafka_service.kafka_client import new_correlation_id

    correlation_id = (correlation_id or "").strip() or new_correlation_id()
    log_flow("API", "HTTP-IN", f"corr={correlation_id} op={operation} {http_route}", {"data": data})
    response = get_kafka_client().request(operation, data, correlation_id=correlation_id)
    status_code = _status_for(response, success_status)
    log_flow("API", "HTTP-OUT", f"corr={correlation_id} op={operation} status={status_code}")
    return JSONResponse(
        status_code=status_code,
        content=response,
        headers={"X-Correlation-ID": correlation_id},
    )


@router.get("/health")
def kafka_health():
    client = get_kafka_client()
    return {"ok": True, "component": client.component, "bootstrap": client.bootstrap}


@router.post("/requests")
def send_raw_request(
    body: KafkaRequestIn,
    x_correlation_id: Optional[str] = Header(default=None),
):
    return forward_to_worker(
        body.operation.strip(), body.data, x_correlation_id, "POST /api/kafka/requests"
    )


@router.post("/recalls")
def create_recall_over_kafka(
    data: dict[str, Any] = Body(...),
    x_correlation_id: Optional[str] = Header(default=None),
):
    return forward_to_worker(
        CREATE_OPERATION, data, x_correlation_id, "POST /api/kafka/recalls", success_status=201
    )


@router.get("/recalls/{recall_id}")
def get_recall_over_kafka(
    recall_id: str,
    x_correlation_id: Optional[str] = Header(default=None),
):
    return forward_to_worker(
        GET_OPERATION,
        {"recall_id": recall_id},
        x_correlation_id,
        f"GET /api/kafka/recalls/{recall_id}",
    )
