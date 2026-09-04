FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ /app/backend/
COPY scanner/ /app/scanner/

EXPOSE 8000

ENV SCANNER_PATH=/app
ENV DATABASE_URL=postgresql://ecdat:ecdat@db:5432/ecdat

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
