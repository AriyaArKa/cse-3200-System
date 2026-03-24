"""FastAPI app bootstrap for BanglaDOC Surya-clean implementation."""

import asyncio
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from bangladoc_ocr import config
from bangladoc_ocr.core.ocr_engine import _init_easyocr
from bangladoc_ocr.core.surya_engine import load as load_surya
from bangladoc_ocr.db.base import Base
from bangladoc_ocr.db.session import engine
from bangladoc_ocr.server.paths import STATIC_DIR, UPLOAD_DIR
from bangladoc_ocr.server.rate_limit import limiter
from bangladoc_ocr.server.routes import register_routes

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BanglaDOC Surya Clean",
    description="Surya-first Bangla + English OCR with clean fallback chain",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
register_routes(app)


@app.on_event("startup")
async def warmup() -> None:
    """Warm OCR engines and ensure DB/tables exist."""
    config.refresh_config()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Warming up OCR engines")
    await asyncio.to_thread(_init_easyocr)
    if config.SURYA_ENABLED:
        await asyncio.to_thread(load_surya)
    logger.info("Warmup done")


def start_server(host: str = "0.0.0.0", port: int = 8000) -> None:
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
