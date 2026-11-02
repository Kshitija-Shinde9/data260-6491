import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "code"))
sys.path.insert(0, str(REPO / "code" / "web_application"))

from kafka_service.config import (  # noqa: E402
    CREATE_OPERATION,
    GET_OPERATION,
    REQUEST_TOPIC,
    RESPONSE_TOPIC,
)
from kafka_service.worker import handle_request  # noqa: E402

VALID_RECALL = {
    "product_name": "Trader Joe's Organic Frozen Blueberries, 16oz",
    "supplier": "Trader Joe's (Stevens Creek location)",
    "recall_code": "REC-0101",
    "recall_type": "Packaging / Seal Failure",
    "description": "Small tear near the top seal let frost build up on the berries.",
    "affected_units": 120,
}


def request(operation, data, correlation_id=None, reply_to=RESPONSE_TOPIC):
    return {
        "correlation_id": correlation_id or str(uuid.uuid4()),
        "reply_to": reply_to,
        "operation": operation,
        "data": data,
    }


def test_topic_names_use_prefix():
    assert REQUEST_TOPIC == "s6491_recall_requests"
    assert RESPONSE_TOPIC == "s6491_recall_responses"


def test_create_then_get_preserves_correlation_id():
    store = {}
    corr = str(uuid.uuid4())
    topic, created = handle_request(request(CREATE_OPERATION, VALID_RECALL, corr), store)
    assert topic == RESPONSE_TOPIC
    assert created["success"] is True and created["correlation_id"] == corr
    assert created["message"] == "Recall created"
    recall_id = created["recall_id"]
    assert str(uuid.UUID(recall_id)) == recall_id

    topic, fetched = handle_request(request(GET_OPERATION, {"recall_id": recall_id}, corr), store)
    assert fetched["success"] is True and fetched["correlation_id"] == corr
    assert fetched["recall"]["recall_id"] == recall_id
    assert fetched["recall"]["product_name"] == VALID_RECALL["product_name"]


def test_each_create_gets_a_new_uuid():
    store = {}
    first = handle_request(request(CREATE_OPERATION, VALID_RECALL), store)[1]
    second = handle_request(
        request(CREATE_OPERATION, {**VALID_RECALL, "recall_code": "REC-0102"}), store
    )[1]
    assert first["recall_id"] != second["recall_id"] and len(store) == 2


def test_validation_rejects_missing_empty_and_invalid_values():
    bad_inputs = {
        "missing field": {k: v for k, v in VALID_RECALL.items() if k != "supplier"},
        "empty product": {**VALID_RECALL, "product_name": "   "},
        "short description": {**VALID_RECALL, "description": "too short"},
        "bad recall_type": {**VALID_RECALL, "recall_type": "Other"},
        "bad recall_code": {**VALID_RECALL, "recall_code": "R-1"},
        "negative units": {**VALID_RECALL, "affected_units": -1},
        "bool units": {**VALID_RECALL, "affected_units": True},
        "user-specific field": {**VALID_RECALL, "email": "someone@example.com"},
        "data not an object": ["not", "a", "dict"],
    }
    for label, data in bad_inputs.items():
        corr = str(uuid.uuid4())
        store = {}
        _, response = handle_request(request(CREATE_OPERATION, data, corr), store)
        assert response["success"] is False, label
        assert response["correlation_id"] == corr, label
        assert response["error"], label
        assert store == {}, label


def test_duplicate_recall_code_is_rejected():
    store = {}
    handle_request(request(CREATE_OPERATION, VALID_RECALL), store)
    _, response = handle_request(request(CREATE_OPERATION, VALID_RECALL), store)
    assert response["success"] is False and "already exists" in response["error"]


def test_unknown_operation_and_unknown_id():
    corr = str(uuid.uuid4())
    _, unknown_op = handle_request(request("DELETE_RECALL", {}, corr), {})
    assert unknown_op == {
        "correlation_id": corr,
        "operation": "DELETE_RECALL",
        "success": False,
        "error": "Unknown operation",
    }
    _, missing = handle_request(request(GET_OPERATION, {"recall_id": "nope"}, corr), {})
    assert missing["success"] is False and missing["error"] == "Recall not found"
    assert missing["correlation_id"] == corr


def test_bad_envelopes():
    assert handle_request("not a dict", {}) == (None, None)
    assert handle_request({"operation": GET_OPERATION, "data": {}}, {}) == (None, None)
    topic, response = handle_request(request(GET_OPERATION, {}, reply_to="other_topic"), {})
    assert topic == RESPONSE_TOPIC and response["success"] is False
    corr = str(uuid.uuid4())
    topic, response = handle_request(
        {"correlation_id": corr, "reply_to": RESPONSE_TOPIC, "operation": GET_OPERATION}, {}
    )
    assert response == {
        "correlation_id": corr,
        "operation": GET_OPERATION,
        "success": False,
        "error": "data is required",
    }


class FakeKafkaClient:
    """Runs the worker logic in-process so the API wrapper can be tested without a broker."""

    component = "API"
    bootstrap = "in-memory"

    def __init__(self):
        self.store = {}
        self.sent = []

    def request(self, operation, data, correlation_id=None):
        message = request(operation, data, correlation_id)
        self.sent.append(message)
        return handle_request(message, self.store)[1]


def test_api_wrapper_forwards_and_preserves_correlation_id():
    try:
        from fastapi.testclient import TestClient
    except ImportError:
        print("  (skipped: fastapi/httpx not installed)")
        return
    import routers.kafka_recalls as kafka_recalls
    from fastapi import FastAPI

    fake = FakeKafkaClient()
    kafka_recalls._client = fake
    app = FastAPI()
    app.include_router(kafka_recalls.router)
    http = TestClient(app)

    corr = str(uuid.uuid4())
    created = http.post("/api/kafka/recalls", json=VALID_RECALL, headers={"X-Correlation-ID": corr})
    assert created.status_code == 201, created.text
    assert created.json()["correlation_id"] == corr
    assert created.headers["x-correlation-id"] == corr
    assert fake.sent[-1]["correlation_id"] == corr

    recall_id = created.json()["recall_id"]
    fetched = http.get(f"/api/kafka/recalls/{recall_id}", headers={"X-Correlation-ID": corr})
    assert fetched.status_code == 200 and fetched.json()["recall"]["recall_id"] == recall_id

    assert http.get("/api/kafka/recalls/unknown-id").status_code == 404
    bad = http.post("/api/kafka/requests", json={"operation": "DELETE_RECALL", "data": {}})
    assert bad.status_code == 400 and bad.json()["error"] == "Unknown operation"
    generated = bad.json()["correlation_id"]
    assert bad.headers["x-correlation-id"] == generated
    kafka_recalls._client = None


def main() -> int:
    tests = [value for name, value in globals().items() if name.startswith("test_")]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            failures += 1
            print(f"FAIL {test.__name__}: {exc}")
    print(f"\n{len(tests) - failures}/{len(tests)} tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
