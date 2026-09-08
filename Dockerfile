FROM node:24-alpine AS web
WORKDIR /build/apps/web
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/ ./
RUN npm run build

FROM python:3.12-slim AS runtime
COPY --from=ghcr.io/astral-sh/uv:0.12.3 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ backend/
COPY fixtures/ fixtures/
COPY --from=web /build/apps/web/out/ apps/web/out/
ENV PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/backend PYTHONUNBUFFERED=1 PORT=8000
RUN useradd --uid 10001 --create-home demo && chown -R demo:demo /app
USER demo
EXPOSE 8000
CMD ["sh", "-c", "uvicorn marketbridge.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
