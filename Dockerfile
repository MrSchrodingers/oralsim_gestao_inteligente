# ─── BUILD ─────────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS builder

ARG POETRY_VERSION=2.1.3
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    POETRY_HOME="/usr/local" \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH="${POETRY_HOME}/bin:${PATH}"

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential libpq-dev curl libpq5 tini && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    poetry --version && \
    poetry config virtualenvs.create false && \
    mkdir -p /tmp/prometheus && \
    chmod 0777 /tmp/prometheus 

COPY libs/oralsin_core ./libs/oralsin_core
COPY pyproject.toml poetry.lock ./
RUN poetry install --no-interaction --no-ansi --only main --no-root

# ─── RUNTIME ───────────────────────────────────────────────────────────────────
FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus \
    PYTHONPATH=/app/src:/app/libs \
    PATH="/usr/local/bin:${PATH}"

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 tini curl && \
    mkdir -p /tmp/prometheus && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

COPY --from=builder /usr/local/lib/python3.13/site-packages \
                  /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY libs/oralsin_core ./libs/oralsin_core
COPY config/      config/
COPY src/         src/
COPY tests/       tests/
COPY bin/         bin/
COPY manage.py    manage.py
COPY README.md    README.md
COPY docker-compose.yml docker-compose.yml

COPY docker-entrypoint.sh docker-entrypoint.sh
RUN chmod +x docker-entrypoint.sh

RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app && \
    chown -R appuser:appuser /tmp/prometheus

USER appuser

EXPOSE 8000 9108

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "cobranca_inteligente_api.asgi:application"]