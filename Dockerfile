FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=prod \
    PORT=8000 \
    DB_PATH=/app/db/location_scout.db

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/db
VOLUME ["/app/db"]

EXPOSE 8000
CMD ["python", "main.py"]
