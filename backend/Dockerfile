# Xynect backend — FastAPI on Cloud Run.
# Build context: ./backend
FROM python:3.11-slim

# - PYTHONUNBUFFERED: stream logs straight to stdout for Cloud Logging.
# - PYTHONDONTWRITEBYTECODE: no .pyc clutter in the image.
# - PIP_NO_CACHE_DIR: smaller image, no pip wheel cache.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first so the layer caches across code changes.
# All runtime deps (PyMuPDF, pandas, psycopg2-binary, Pillow) ship manylinux
# wheels, so no system build toolchain is required.
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Application code, migrations, and Alembic config.
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

# Upload dir default is ./storage/uploads (relative to WORKDIR). Cloud Run's
# filesystem is writable but ephemeral; this just guarantees the path exists.
RUN mkdir -p storage/uploads

# Cloud Run injects $PORT (8080); fall back to 8000 for plain `docker run`.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
