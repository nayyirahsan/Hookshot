from contextlib import asynccontextmanager

from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis

from api.config import get_settings
from api.routers import dead_letters, deliveries, endpoints, events, health

settings = get_settings()


def run_migrations() -> None:
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    redis = Redis.from_url(settings.redis_url)
    redis.ping()
    redis.close()
    yield


app = FastAPI(title="Hookshot", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
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
