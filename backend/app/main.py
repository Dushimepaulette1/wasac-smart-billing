"""The app: start-up, the guards every request passes, and the routes. Run with `uvicorn app.main:app`.

    start-up   create missing tables (app/db/init_db.py), load the three models once (app/vision/models.py)
    guards     upload_guard (size and rate limits, app/core/ratelimit.py), then CORS (app/core/config.py)
    routes     app/api/ (one file per area in app/api/routes/)
"""
import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import cors_origin_regex, cors_origins
from app.core.ratelimit import upload_guard
from app.db.init_db import init_db
from app.services.maintenance import clean_photos_periodically
from app.vision.models import registry as model_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    model_registry.load()
    cleanup = asyncio.create_task(clean_photos_periodically())
    try:
        yield
    finally:
        cleanup.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup


app = FastAPI(
    title="Mubazi API (WASAC water billing)",
    description=(
        "AI-assisted water meter reading and billing for Kigali, Rwanda. "
        "Pipeline: YOLOv8 number-window crop → MobileNetV2 quality gate → "
        "ResNet18+BiGRU (CTC) digit reader → rule-based reading checks and human review. "
        "Isolation Forest is an offline experiment, not the deployed detector."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Added before CORS, so CORS wraps it (the last middleware added is the outermost): a refused
# upload never reaches the routes or has its body read, and its 413/429 still carries CORS
# headers, so the browser can read the message.
app.middleware("http")(upload_guard)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_origin_regex=cors_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
