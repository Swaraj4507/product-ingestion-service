from contextlib import contextmanager
from functools import lru_cache
from typing import AsyncIterator, Iterator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.settings import AppSettings, settings


class Base(DeclarativeBase):
    """Declarative base for ORM models."""


class Database:
    def __init__(self, config: AppSettings) -> None:
        self._config = config
        self._async_engine: AsyncEngine = create_async_engine(
            config.database_url,
            echo=config.database_echo,
            future=True,
        )
        self._async_session_factory = async_sessionmaker(
            bind=self._async_engine,
            expire_on_commit=False,
            autoflush=False,
        )

        self._sync_engine = create_engine(
            config.sync_database_url,
            echo=config.database_echo,
            future=True,
        )
        self._sync_session_factory = sessionmaker(
            bind=self._sync_engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    @property
    def async_engine(self) -> AsyncEngine:
        return self._async_engine

    @property
    def sync_engine(self):
        return self._sync_engine

    def async_session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._async_session_factory

    @contextmanager
    def sync_session(self) -> Iterator[Session]:
        session = self._sync_session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    async def get_async_session(self) -> AsyncIterator[AsyncSession]:
        async with self._async_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


@lru_cache(maxsize=1)
def get_database() -> Database:
    return Database(settings)


async def get_async_session() -> AsyncIterator[AsyncSession]:
    database = get_database()
    async for session in database.get_async_session():
        yield session

