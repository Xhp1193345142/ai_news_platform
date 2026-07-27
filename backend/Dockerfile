ARG PYTHON_IMAGE=python:3.12-slim
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv/ai-signal

COPY . .
RUN if [ -x /app/.venv/bin/pip ]; then \
      /app/.venv/bin/pip install --no-cache-dir ".[dev]"; \
    else \
      pip install --upgrade pip && pip install --no-cache-dir ".[dev]"; \
    fi

ENV PYTHONPATH=/srv/ai-signal

EXPOSE 8000

CMD ["sh", "-c", "if [ -x /app/.venv/bin/python ]; then exec /app/.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000; else exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000; fi"]
