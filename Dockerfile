# syntax=docker/dockerfile:1
FROM python:3.12-slim

# ---- metadata ----
LABEL maintainer="rockauto-closeout-watcher"
LABEL description="Monitors RockAuto closeout listings for Nissan 370Z Sport brake calipers"

# ---- system deps ----
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ---- working directory ----
WORKDIR /app

# ---- install Python dependencies first (layer cache) ----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- copy application code ----
COPY app/       ./app/
COPY monitor.py .
COPY config.yaml .

# ---- create runtime directories ----
RUN mkdir -p data/logs data

# ---- non-root user for security ----
RUN adduser --disabled-password --gecos "" watcher \
    && chown -R watcher:watcher /app
USER watcher

# ---- default command: watch mode ----
CMD ["python", "monitor.py", "--watch"]
