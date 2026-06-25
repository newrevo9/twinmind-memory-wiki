import logging

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.transcript import Transcript
from app.schemas.transcript import TranscriptCreate, TranscriptResponse

router = APIRouter(prefix="/transcripts", tags=["transcripts"])
logger = logging.getLogger(__name__)


def _redis_settings() -> RedisSettings:
    from urllib.parse import urlparse

    p = urlparse(settings.redis_url)
    return RedisSettings(
        host=p.hostname or "localhost",
        port=p.port or 6379,
        database=int((p.path or "/0").lstrip("/") or 0),
        password=p.password,
    )


@router.post("", response_model=TranscriptResponse, status_code=201)
async def create_transcript(body: TranscriptCreate, db: AsyncSession = Depends(get_db)):
    transcript = Transcript(content=body.content)
    db.add(transcript)
    await db.commit()
    await db.refresh(transcript)

    try:
        redis = await create_pool(_redis_settings())
        job = await redis.enqueue_job("process_transcript_job", str(transcript.id))
        transcript.job_id = job.job_id
        await db.commit()
        await db.refresh(transcript)
    except Exception:
        logger.error("Failed to enqueue job for transcript %s", transcript.id, exc_info=True)

    return transcript


@router.get("/{transcript_id}", response_model=TranscriptResponse)
async def get_transcript(transcript_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Transcript).where(Transcript.id == transcript_id))
    transcript = result.scalar_one_or_none()
    if transcript is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return transcript
