from functools import lru_cache

import redis
from redis.asyncio import Redis as AsyncRedis

from app.core.settings import AppSettings, settings


class RedisClient:
    def __init__(self, config: AppSettings) -> None:
        self._config = config
        self._async_client = AsyncRedis.from_url(config.redis_url, decode_responses=True)
        self._sync_client = redis.Redis.from_url(config.redis_url, decode_responses=True)

    @property
    def config(self) -> AppSettings:
        return self._config

    def get_async_client(self) -> AsyncRedis:
        return self._async_client

    def get_sync_client(self) -> redis.Redis:
        return self._sync_client

    async def close(self) -> None:
        await self._async_client.close()

    def close_sync(self) -> None:
        self._sync_client.close()


@lru_cache(maxsize=1)
def get_redis_client() -> RedisClient:
    return RedisClient(settings)

