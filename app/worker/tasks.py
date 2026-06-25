import logging
from urllib.parse import urlparse

from arq.connections import RedisSettings
from sqlalchemy import select, update

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.transcript import Transcript
from app.services.memory_manager import process_transcript

logger = logging.getLogger(__name__)


async def process_transcript_job(ctx: dict, transcript_id: str) -> dict:
    """
    ARQ job: extract memories from a transcript and write them to MinIO.
    Idempotent — safe to retry. If the transcript is already completed, skips.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Transcript).where(Transcript.id == transcript_id))
        transcript = result.scalar_one_or_none()

        if transcript is None:
            raise ValueError(f"Transcript {transcript_id} not found")

        if transcript.status == "completed":
            logger.info("Transcript %s already completed, skipping", transcript_id)
            return {"skipped": True}

        await db.execute(
            update(Transcript)
            .where(Transcript.id == transcript_id)
            .values(status="processing")
        )
        await db.commit()

    try:
        written_paths = await process_transcript(transcript_id, transcript.content)

        async with AsyncSessionLocal() as db:
            await db.execute(
                update(Transcript)
                .where(Transcript.id == transcript_id)
                .values(status="completed", error=None)
            )
            await db.commit()

        logger.info("Transcript %s done — wrote %d memories", transcript_id, len(written_paths))
        return {"transcript_id": transcript_id, "memories_written": len(written_paths), "paths": written_paths}

    except Exception as e:
        logger.error("Transcript %s failed: %s", transcript_id, e, exc_info=True)
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Transcript).where(Transcript.id == transcript_id))
            transcript = result.scalar_one_or_none()
            retry_count = (transcript.retry_count or 0) + 1 if transcript else 1

            await db.execute(
                update(Transcript)
                .where(Transcript.id == transcript_id)
                .values(status="failed", error=str(e), retry_count=retry_count)
            )
            await db.commit()
        raise


def _redis_settings() -> RedisSettings:
    p = urlparse(settings.redis_url)
    return RedisSettings(
        host=p.hostname or "localhost",
        port=p.port or 6379,
        database=int((p.path or "/0").lstrip("/") or 0),
        password=p.password,
    )


class WorkerSettings:
    functions = [process_transcript_job]
    redis_settings = _redis_settings()
    max_tries = settings.max_retries
    job_timeout = settings.job_timeout
    keep_result = 3600
    on_startup = None
    on_shutdown = None
