# Multi-stage Dockerfile for Product Ingestion Service
# 
# This Dockerfile has 3 stages:
# 1. "base" - Common setup (Python, dependencies, app code)
# 2. "api" - FastAPI/UVicorn server (built with --target api)
# 3. "celery" - Celery worker (built with --target celery)
#
# To build API image: docker build --target api -t my-image:api .
# To build Celery image: docker build --target celery -t my-image:celery .
#
# Each stage creates a SEPARATE Docker image with different CMD

# ============================================
# STAGE 1: Base (common setup for both containers)
# ============================================
FROM python:3.11-slim as base

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create uploads directory
RUN mkdir -p /tmp/uploads && chmod 777 /tmp/uploads

# ============================================
# STAGE 2: API Server Image
# ============================================
FROM base as api
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# ============================================
# STAGE 3: Celery Worker Image
# ============================================
FROM base as celery
CMD ["celery", "-A", "app.core.celery_app", "worker", "--loglevel=info", "--concurrency=2"]

