# Backend FastAPI (API JSON) para desplegar en Render/Railway.
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY SPEC.md CLAUDE.md ./

# Render/Railway inyectan $PORT. data/ se monta como disco persistente (SQLite + modelo).
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
