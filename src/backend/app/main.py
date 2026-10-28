import asyncio
import contextlib
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import Base, SessionLocal, engine
from .routers import common, instructor, student
from .seed import seed_if_empty
from .services.bandit import apply_finalized

log = logging.getLogger("writing_tutor")
BANDIT_UPDATE_SECONDS = int(os.getenv("BANDIT_UPDATE_SECONDS", "600"))


async def _bandit_scheduler():
    """MAB7: periodically fold finalized rewards (incl. instructor-timeout fallbacks) into the bandit."""
    while True:
        await asyncio.sleep(BANDIT_UPDATE_SECONDS)
        with SessionLocal() as db:
            try:
                applied = apply_finalized(db)
                if applied:
                    log.info("bandit update applied to %d arm(s)", len(applied))
            except Exception:  # keep the scheduler alive
                log.exception("bandit update failed")


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    if os.getenv("SEED", "1") == "1":
        with SessionLocal() as db:
            seed_if_empty(db)
    task = asyncio.create_task(_bandit_scheduler()) if BANDIT_UPDATE_SECONDS > 0 else None
    yield
    if task:
        task.cancel()


app = FastAPI(title="Adaptive Writing Tutor API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(common.router)
app.include_router(student.router)
app.include_router(instructor.router)
