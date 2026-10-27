"""Run the OpenAI collector at the top of each hour in Shanghai time."""

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text

from app.collectors.openai_news import month_start
from app.core.config import settings
from scripts.collect_openai_news import collect

LOGGER = logging.getLogger("ai_signal.hourly_collector")
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
COLLECTION_LOCK_ID = 8_107_012_026


def next_hourly_run(now: datetime | None = None) -> datetime:
    current = (now or datetime.now(SHANGHAI_TZ)).astimezone(SHANGHAI_TZ)
    return current.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def run_collection_once() -> tuple[int, list[str]] | None:
    """Use a PostgreSQL session lock so multiple worker replicas cannot overlap."""
    engine = create_engine(settings.sync_database_url, pool_pre_ping=True)
    try:
        with engine.connect() as lock_connection:
            acquired = lock_connection.execute(
                text("SELECT pg_try_advisory_lock(:lock_id)"), {"lock_id": COLLECTION_LOCK_ID}
            ).scalar_one()
            lock_connection.commit()
            if not acquired:
                LOGGER.info("Another collector holds the hourly collection lock; skipping run")
                return None
            try:
                result = collect(month_start())
                saved, errors = result
                LOGGER.info(
                    "OpenAI hourly collection finished: %s saved, %s failed",
                    saved,
                    len(errors),
                )
                return result
            finally:
                lock_connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"), {"lock_id": COLLECTION_LOCK_ID}
                )
                lock_connection.commit()
    finally:
        engine.dispose()


async def run_hourly_collector() -> None:
    while True:
        scheduled_at = next_hourly_run()
        seconds = max((scheduled_at - datetime.now(SHANGHAI_TZ)).total_seconds(), 0)
        LOGGER.info("Next OpenAI collection scheduled at %s", scheduled_at.isoformat())
        await asyncio.sleep(seconds)
        try:
            await asyncio.to_thread(run_collection_once)
        except Exception:
            LOGGER.exception("OpenAI hourly collection crashed; it will retry at the next hour")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if not settings.openai_cookie:
        LOGGER.warning(
            "OPENAI_COOKIE is empty; Cloudflare may block article pages. "
            "Failed pages will be recorded and retried at the next hour."
        )
    asyncio.run(run_hourly_collector())


if __name__ == "__main__":
    main()
