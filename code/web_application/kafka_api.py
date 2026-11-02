import os
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kafka_service.config import PORT_BASE, REQUEST_TOPIC, RESPONSE_TOPIC
from routers.kafka_recalls import close_kafka_client, get_kafka_client
from routers.kafka_recalls import router as kafka_recalls_router

BIND_HOST = os.getenv("BIND_HOST", "127.0.0.1")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    get_kafka_client()
    print(f"FastAPI server started at http://127.0.0.1:{PORT_BASE}", flush=True)
    print(f"Kafka topics: requests={REQUEST_TOPIC} responses={RESPONSE_TOPIC}", flush=True)
    yield
    close_kafka_client()


app = FastAPI(title="s6491 Recall Kafka API wrapper", version="8.0.0", lifespan=lifespan)
app.include_router(kafka_recalls_router)


if __name__ == "__main__":
    # In Docker BIND_HOST is 0.0.0.0 so the published port 127.0.0.1:8191 reaches the container.
    uvicorn.run(app, host=BIND_HOST, port=PORT_BASE)
