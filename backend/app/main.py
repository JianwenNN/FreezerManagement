"""
Application entry point.

Run with:
    uvicorn app.main:app --reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.api import api_router
from app.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup and shutdown events.
    - Starts the background scheduler on startup (purges expired reservations every minute).
    - Gracefully stops it on shutdown.
    """
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title       = "Freezer Management System",
    description = "API for managing laboratory freezer storage and sample allocation.",
    version     = "1.0.0",
    lifespan    = lifespan,
)

app.include_router(api_router, prefix="/api/v1")
