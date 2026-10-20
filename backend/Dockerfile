FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /uvx /bin/
WORKDIR /srv/backend
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend /srv/backend
COPY data/demo /srv/data/demo
RUN uv sync --frozen --no-dev
ENV PATH="/srv/backend/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    APP_ENV=demo \
    API_HOST=0.0.0.0 \
    API_PORT=8101 \
    ALLOW_NETWORK_BIND=true \
    DATABASE_URL=postgresql+psycopg://hr:hr@db:5432/hrpolicy \
    QDRANT_MODE=server \
    QDRANT_URL=http://qdrant:6333 \
    QDRANT_WAIT=true \
    MODEL_DIR=/srv/models/all-MiniLM-L6-v2 \
    DEMO_DATA_DIR=/srv/data/demo \
    UPLOAD_DIR=/srv/data/uploads \
    SEED_ON_STARTUP=true \
    HF_HUB_OFFLINE=0
RUN python -m app.download_model
ENV HF_HUB_OFFLINE=1
EXPOSE 8101
CMD ["python", "-m", "app"]
