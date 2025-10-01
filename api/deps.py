from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_async_session


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_async_session():
        yield session
