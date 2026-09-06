FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

RUN groupadd --gid 10001 ecdat \
    && useradd --uid 10001 --gid ecdat --no-create-home --shell /usr/sbin/nologin ecdat

COPY --chown=10001:10001 backend/ /app/backend/
COPY --chown=10001:10001 scanner/ /app/scanner/

USER 10001:10001

EXPOSE 8000

ENV SCANNER_PATH=/app

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
