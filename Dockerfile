# syntax=docker/dockerfile:1.7

FROM python:3.12-alpine AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PIP_NO_CACHE_DIR=1

WORKDIR /app

# Build dependencies are only needed in the builder stage.
RUN apk add --no-cache build-base linux-headers

COPY requirements.txt ./
RUN python -m venv /opt/venv && \
	/opt/venv/bin/pip install --upgrade pip && \
	/opt/venv/bin/pip install -r requirements.txt

COPY main.py ./
COPY src ./src
COPY config.py.example ./

FROM python:3.12-alpine AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
	PYTHONUNBUFFERED=1 \
	PATH="/opt/venv/bin:$PATH"

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/main.py /app/main.py
COPY --from=builder /app/src /app/src
COPY --from=builder /app/config.py.example /app/config.py.example

CMD ["python", "main.py"]
