# --- Stage 1: build the Mini App static frontend ---
FROM node:20-slim AS frontend-build
WORKDIR /app/webapp/frontend
COPY webapp/frontend/package.json ./
RUN npm install
COPY webapp/frontend/ ./
RUN npm run build

# --- Stage 2: python runtime for both the bot and the FastAPI backend ---
FROM python:3.11-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/
COPY webapp/backend/ ./webapp/backend/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY --from=frontend-build /app/webapp/frontend/dist ./webapp/frontend/dist

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

EXPOSE 3013

CMD ["uvicorn", "webapp.backend.main:app", "--host", "0.0.0.0", "--port", "3013"]
