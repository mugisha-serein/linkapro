import asyncio
from fastapi_app.database import engine
from fastapi_app.marketplace.models import Base
from fastapi_app.migrations.marketplace_search import apply_marketplace_search_schema

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await apply_marketplace_search_schema(conn)

if __name__ == "__main__":
    asyncio.run(main())
