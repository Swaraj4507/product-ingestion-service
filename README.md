# Product Ingestion Service

FastAPI + Celery based backend for large-scale product ingestion, CSV imports with progress tracking, webhook configuration, and product management APIs.

## Features
- FastAPI REST APIs with object-oriented service/repository layering.
- CSV uploads processed asynchronously via Celery + Redis with task progress stored in Postgres and Redis.
- Product CRUD APIs with filtering, pagination, and SKU override logic.
- Bulk product delete workflow powered by Celery tasks.
- Webhook management with event dispatching and test endpoint.
- UUID-based models, Postgres (SQLAlchemy async+sync), and centralized DI container.

## Documentation
Full documentation is maintained in Google Docs:  
https://docs.google.com/document/d/1TKPrWTCeNwRhLXdnCiwPwbW6rC0E0rvYBDfRlYYKVuc/edit?usp=sharing

## Getting Started
1. Install dependencies: `pip install -r requirements.txt`
2. Run FastAPI locally: `uvicorn app.main:app --reload`
3. Start Celery worker: `celery -A app.core.celery_app worker --loglevel=info`

## Deployment
- Multi-stage Dockerfile builds separate images for API and Celery worker (`--target api` / `--target celery`).
- Use the provided `.env` file to configure Postgres and Redis URLs.
- Recommended to deploy API and Celery containers separately (e.g., on Azure VM).


