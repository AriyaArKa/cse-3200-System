FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgl1 \
    libglib2.0-0 \
    libjpeg62-turbo \
    libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/ /app/backend/

RUN python -m pip install --upgrade pip setuptools wheel && \
    python -m pip install -e ".[dev]"

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "bangladoc_ocr.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
