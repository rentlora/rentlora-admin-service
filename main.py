import asyncio
import logging
import time
import uuid

import models  # noqa: F401
from config import get_settings
from database import Base, engine
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from logging_config import setup_logging
from routes.admin import router as admin_router
from sqlalchemy import text

settings = get_settings()
setup_logging("admin-service")
logger = logging.getLogger("admin-service")

app = FastAPI(title="Rentlora Admin Service", version=settings.app_version)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start = time.perf_counter()

    response = await call_next(request)

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    status = response.status_code
    response.headers["X-Request-ID"] = request_id

    log_data = {
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status": status,
        "duration_ms": duration_ms,
    }

    if status >= 500:
        logger.error("request completed", extra=log_data)
    elif status >= 400:
        logger.warning("request completed", extra=log_data)
    else:
        logger.info("request completed", extra=log_data)

    return response


@app.on_event("startup")
async def startup():
    for attempt in range(5):
        try:
            async with engine.begin() as conn:
                await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                await conn.run_sync(Base.metadata.create_all)
                await conn.execute(text("SELECT 1"))
            break
        except Exception as e:
            if attempt == 4:
                logger.error("Failed to initialize database after 5 attempts")
                raise e
            logger.warning(f"Database initialization attempt {attempt + 1} failed. Retrying in 2 seconds...")
            await asyncio.sleep(2)
    logger.info("admin-service started on port 8004")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "admin-service", "db": "connected"}


@app.get("/healthz")
async def healthz():
    """Liveness probe — cheap, no dependencies."""
    return {"status": "ok"}


@app.get("/ready")
async def ready():
    """Readiness probe — verifies the database is reachable."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as e:
        logger.warning(f"readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="not ready")


app.include_router(admin_router, prefix="/api")
