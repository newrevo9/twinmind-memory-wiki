import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.memories import router as memories_router
from app.api.transcripts import router as transcripts_router
from app.database import engine
from app.models.transcript import Base
from app.services.storage import ensure_bucket_exists

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    ensure_bucket_exists()
    logger.info("Memory Wiki API ready")
    yield
    await engine.dispose()


app = FastAPI(
    title="Memory Wiki",
    description=(
        "Ingest conversation transcripts, extract memories via LLM, "
        "and navigate them through a unix-style file tree API."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(transcripts_router)
app.include_router(memories_router)


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}
