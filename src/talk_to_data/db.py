from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
AsyncConnection,
create_async_engine
)

from src.talk_to_data.config import settings


if not settings.database_url:
    raise RuntimeError("DATABASE_URL is not set")
engine = create_async_engine(settings.database_url,pool_pre_ping=True)

async def get_connection() -> AsyncIterator[AsyncConnection]:
    async with engine.connect() as connection:
        await connection.execute(
            text("SET default_transaction_read_only = on")
        )
        await connection.execute(
            text("SET statement_timeout = '5s'")
        )
        yield connection