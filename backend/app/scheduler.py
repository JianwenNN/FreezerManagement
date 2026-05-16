"""
Background scheduler — purges expired drawer reservations every minute.

Usage: import and call start_scheduler() from your FastAPI lifespan handler.

Example (main.py):
    from contextlib import asynccontextmanager
    from fastapi import FastAPI
    from app.scheduler import start_scheduler, stop_scheduler

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        start_scheduler()
        yield
        stop_scheduler()

    app = FastAPI(lifespan=lifespan)
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text

from app.database import SessionLocal

logger    = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def purge_expired_reservations() -> None:
    """
    Delete all drawer_reservation rows whose expires_at is in the past.
    Runs every minute. Each run is its own short transaction.
    """
    db = SessionLocal()
    try:
        result = db.execute(
            text("""
                DELETE FROM drawer_reservation
                WHERE expires_at < :now
            """),
            {"now": datetime.now(timezone.utc)}
        )
        db.commit()

        deleted = result.rowcount
        if deleted:
            logger.info("Purged %d expired drawer reservation(s).", deleted)

    except Exception:
        db.rollback()
        logger.exception("Failed to purge expired drawer reservations.")
    finally:
        db.close()


def start_scheduler() -> None:
    """Start the background scheduler. Call once at application startup."""
    scheduler.add_job(
        purge_expired_reservations,
        trigger  = "interval",
        minutes  = 1,
        id       = "purge_expired_reservations",
        replace_existing = True,
    )
    scheduler.start()
    logger.info("Background scheduler started.")


def stop_scheduler() -> None:
    """Gracefully shut down the scheduler. Call at application shutdown."""
    scheduler.shutdown(wait=False)
    logger.info("Background scheduler stopped.")
