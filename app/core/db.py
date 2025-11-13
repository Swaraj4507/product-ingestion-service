from functools import lru_cache
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import settings


class Database:
    def __init__(self, url: str, echo: bool = False) -> None:
        self._engine: AsyncEngine = create_async_engine(url, echo=echo)
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            expire_on_commit=False,
        )

    @property
    def engine(self) -> AsyncEngine:
        return self._engine

    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory

    async def get_session(self) -> AsyncIterator[AsyncSession]:
        async with self._session_factory() as session:
            yield session


@lru_cache(maxsize=1)
def get_database() -> Database:
    return Database(settings.database_url)

