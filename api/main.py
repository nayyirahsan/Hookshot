import logging
from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis

from api.config import get_settings
from api.routers import dead_letters, deliveries, endpoints, events, health

settings = get_settings()
logger = logging.getLogger("hookshot.startup")


def run_migrations() -> None:
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        run_migrations()
    except Exception:
        logger.exception("Alembic migration failed during startup")
        raise
    try:
        redis = Redis.from_url(settings.redis_url)
        redis.ping()
        redis.close()
    except Exception:
        logger.exception("Redis connectivity check failed during startup")
        raise
    yield


app = FastAPI(title="Hookshot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(endpoints.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(deliveries.router, prefix="/api")
app.include_router(dead_letters.router, prefix="/api")
app.include_router(health.router)
app.include_router(health.router, prefix="/api")
