FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml /app/pyproject.toml
COPY last_try_OCR /app/last_try_OCR

RUN pip install --no-cache-dir -e .

EXPOSE 8000
CMD ["uvicorn", "last_try_OCR.server.app:app", "--host", "0.0.0.0", "--port", "8000"]
