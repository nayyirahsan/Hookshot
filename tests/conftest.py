import os
from collections.abc import AsyncGenerator, Generator
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://hookshot:hookshot@localhost:5432/hookshot",
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["HTTP_TIMEOUT_SECONDS"] = "2"
os.environ["MAX_DELIVERY_ATTEMPTS"] = "8"

from alembic import command
from alembic.config import Config

from api.config import get_settings
from api.database import Base, SyncSessionLocal
from api.deps import get_db
from api.main import app

get_settings.cache_clear()


@pytest.fixture(scope="session")
def setup_database() -> Generator[None, None, None]:
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    yield


@pytest_asyncio.fixture
async def db_session(setup_database) -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(get_settings().database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            await conn.execute(text(f"TRUNCATE TABLE {table.name} RESTART IDENTITY CASCADE"))
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def truncate_sync_tables(request) -> Generator[None, None, None]:
    if "client" not in request.fixturenames:
        yield
        return
    yield
    with SyncSessionLocal() as session:
        for table in reversed(Base.metadata.sorted_tables):
            session.execute(text(f"TRUNCATE TABLE {table.name} RESTART IDENTITY CASCADE"))
        session.commit()


@pytest.fixture
def mock_httpx():
    with patch("worker.tasks.httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        yield mock_client
