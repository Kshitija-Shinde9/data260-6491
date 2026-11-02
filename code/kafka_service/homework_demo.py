import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kafka_service.config import (
    CREATE_OPERATION,
    GET_OPERATION,
    PORT_BASE,
    REQUEST_TOPIC,
    RESPONSE_TOPIC,
)
from kafka_service.flow_log import read_flow_lines

API_URL = os.getenv("API_URL", f"http://127.0.0.1:{PORT_BASE}")


def banner(step: int, text: str) -> None:
    print(f"\n===== STEP {step}: {text} =====", flush=True)


def pretty(payload: dict) -> str:
    return json.dumps(payload, indent=2)


def sample_recall() -> dict:
    return {
        "product_name": "Trader Joe's Organic Frozen Blueberries, 16oz",
        "supplier": "Trader Joe's (Stevens Creek location)",
        "recall_code": f"REC-{int(time.time()) % 10000:04d}",
        "recall_type": "Packaging / Seal Failure",
        "description": "Small tear near the top seal let frost build up on the berries near the opening.",
        "affected_units": 120,
    }


class DirectKafkaCaller:
    label = "Kafka client (homework_demo.py)"

    def __init__(self):
        from kafka_service.kafka_client import RecallKafkaClient

        self.client = RecallKafkaClient(component="CLIENT").start()

    def call(self, operation: str, data: dict, correlation_id: str) -> dict:
        return self.client.request(operation, data, correlation_id=correlation_id)

    def close(self) -> None:
        self.client.close()


class ApiCaller:
    label = f"FastAPI wrapper at {API_URL}"

    def call(self, operation: str, data: dict, correlation_id: str) -> dict:
        body = json.dumps({"operation": operation, "data": data}).encode("utf-8")
        request = urllib.request.Request(
            f"{API_URL}/api/kafka/requests",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "X-Correlation-ID": correlation_id},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            return json.loads(exc.read().decode("utf-8"))

    def close(self) -> None:
        pass


def show_worker_side(correlation_id: str, operation: str) -> None:
    lines = [line for line in read_flow_lines(correlation_id) if f"op={operation}" in line]
    if not lines:
        print(
            "(shared flow log not mounted; see `docker compose logs worker` for the worker lines)"
        )
        return
    print("Message-flow lines for this request (client / API / worker, in time order):")
    for line in lines:
        print("  " + line)


def run_error_cases(caller) -> None:
    from kafka_service.kafka_client import new_correlation_id

    cases = [
        ("Unknown operation", "DELETE_RECALL", {"recall_id": "anything"}),
        ("Missing required field", CREATE_OPERATION, {"product_name": "Only a name"}),
        ("Invalid recall_type", CREATE_OPERATION, {**sample_recall(), "recall_type": "Bad Type"}),
        ("Unknown recall_id", GET_OPERATION, {"recall_id": "00000000-0000-0000-0000-000000000000"}),
    ]
    print("\n===== EXTRA: error responses keep the correlation_id =====")
    for title, operation, data in cases:
        correlation_id = new_correlation_id()
        response = caller.call(operation, data, correlation_id)
        print(f"\n--- {title} ({operation}) ---")
        print(pretty(response))
        print(f"correlation_id preserved: {response.get('correlation_id') == correlation_id}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--via-api", action="store_true", help="send through the FastAPI wrapper")
    parser.add_argument("--with-errors", action="store_true", help="also show the error responses")
    args = parser.parse_args()

    from kafka_service.kafka_client import new_correlation_id

    caller = ApiCaller() if args.via_api else DirectKafkaCaller()
    print(f"Request topic : {REQUEST_TOPIC}")
    print(f"Response topic: {RESPONSE_TOPIC}")
    print(f"Caller        : {caller.label}")

    try:
        banner(1, "create one correlation_id")
        correlation_id = new_correlation_id()
        print(f"correlation_id = {correlation_id}")

        banner(2, f"send {CREATE_OPERATION} to {REQUEST_TOPIC}")
        recall_data = sample_recall()
        print("data =", pretty(recall_data))

        banner(3, "log the message sent to the request topic  (CLIENT/API SEND line)")
        create_response = caller.call(CREATE_OPERATION, recall_data, correlation_id)

        banner(4, "worker receives and processes the request  (WORKER RECEIVE / PROCESS)")
        banner(5, f"worker sends the response to {RESPONSE_TOPIC}  (WORKER REPLY)")
        banner(6, "response received by the client  (CLIENT/API RESPONSE)")
        show_worker_side(correlation_id, CREATE_OPERATION)
        print(f"\n{CREATE_OPERATION} response:\n{pretty(create_response)}")
        if not create_response.get("success"):
            print(f"{CREATE_OPERATION} failed, stopping the demo.")
            return 1

        banner(7, "extract the generated recall_id")
        recall_id = create_response["recall_id"]
        print(f"recall_id = {recall_id}")

        banner(8, f"send {GET_OPERATION} with that recall_id (same correlation_id)")
        get_response = caller.call(GET_OPERATION, {"recall_id": recall_id}, correlation_id)

        banner(9, f"full {GET_OPERATION} send / receive / process / reply / client-response")
        show_worker_side(correlation_id, GET_OPERATION)
        print(f"\n{GET_OPERATION} response:\n{pretty(get_response)}")

        banner(10, "retrieved recall and correlation_id check")
        print(pretty(get_response.get("recall") or {}))
        create_ok = create_response.get("correlation_id") == correlation_id
        get_ok = get_response.get("correlation_id") == correlation_id
        print(f"correlation_id sent           : {correlation_id}")
        print(
            f"{CREATE_OPERATION} response echoed : {create_response.get('correlation_id')}  preserved={create_ok}"
        )
        print(
            f"{GET_OPERATION} response echoed    : {get_response.get('correlation_id')}  preserved={get_ok}"
        )
        print(
            f"retrieved recall_id matches   : {(get_response.get('recall') or {}).get('recall_id') == recall_id}"
        )

        if args.with_errors:
            run_error_cases(caller)
        return 0 if (create_ok and get_ok and get_response.get("success")) else 1
    finally:
        caller.close()


if __name__ == "__main__":
    sys.exit(main())
