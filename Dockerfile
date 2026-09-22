FROM python:3.12-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv==0.8.22 \
    && uv sync --frozen --no-dev --no-install-project

COPY app ./app
COPY scripts ./scripts
COPY web ./web
COPY data/index.json ./data/index.json

RUN uv sync --frozen --no-dev --no-editable

RUN addgroup --system app && adduser --system --ingroup app app \
    && mkdir -p /app/data/audit \
    && chown -R app:app /app
USER app

EXPOSE 8080
CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
