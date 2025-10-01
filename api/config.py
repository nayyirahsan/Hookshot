from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://hookshot:hookshot@localhost:5432/hookshot"
    celery_task_always_eager: bool = False
    redis_url: str = "redis://localhost:6379/0"
    max_delivery_attempts: int = 8
    http_timeout_seconds: float = 10.0

    @property
    def database_url_async(self) -> str:
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def database_url_sync(self) -> str:
        url = self.database_url_async
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")


@lru_cache
def get_settings() -> Settings:
    return Settings()
