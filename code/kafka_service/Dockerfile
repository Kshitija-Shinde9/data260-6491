FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/code:/app/code/web_application

WORKDIR /app

COPY code/kafka_service/requirements-kafka.txt /tmp/requirements-kafka.txt
RUN pip install --no-cache-dir -r /tmp/requirements-kafka.txt

COPY code/kafka_service /app/code/kafka_service
COPY code/web_application/routers/kafka_recalls.py /app/code/web_application/routers/kafka_recalls.py
COPY code/web_application/kafka_api.py /app/code/web_application/kafka_api.py
