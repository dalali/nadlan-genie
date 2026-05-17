from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import __version__
from .config import get_settings
from .logging_setup import configure_logging, get_logger
from .routers import cities, health
from .routers import results as results_router
from .routers import scan as scan_router
from .routers import transactions as tx_router

settings = get_settings()
configure_logging(settings.log_level)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", version=__version__, listing_source=settings.listing_source)
    yield
    log.info("shutdown")


app = FastAPI(
    title="nadlan-genie",
    version=__version__,
    description="Local-first MVP for finding undervalued Israeli residential listings.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    # Local-only app. Restrict to the frontend dev/prod localhost origins so a stray browser
    # tab on another site cannot trigger scans against this user's local backend.
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(cities.router)
app.include_router(scan_router.router)
app.include_router(results_router.router)
app.include_router(tx_router.router)
