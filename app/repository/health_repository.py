class HealthRepository:
    async def fetch_status(self) -> dict[str, str]:
        return {"status": "ok"}


