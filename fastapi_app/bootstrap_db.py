import asyncio
from fastapi_app.database import engine
from fastapi_app.marketplace.models import Base

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(main())