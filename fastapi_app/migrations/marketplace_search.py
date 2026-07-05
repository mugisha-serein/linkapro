from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def apply_marketplace_search_schema(connection: AsyncConnection) -> None:
    await connection.execute(text(
        "ALTER TABLE marketplace_vendorlisting "
        "ADD COLUMN IF NOT EXISTS tags TEXT"
    ))
    await connection.execute(text(
        "ALTER TABLE marketplace_vendorlisting "
        "ADD COLUMN IF NOT EXISTS external_id VARCHAR(128)"
    ))
    await connection.execute(text(
        "ALTER TABLE marketplace_vendorlisting "
        "ADD COLUMN IF NOT EXISTS search_rank_score DOUBLE PRECISION DEFAULT 0.0"
    ))
    await connection.execute(text(
        "ALTER TABLE marketplace_vendorlisting "
        "ADD COLUMN IF NOT EXISTS approval_status VARCHAR(20)"
    ))
    await connection.execute(text(
        "ALTER TABLE marketplace_vendorlisting "
        "ADD COLUMN IF NOT EXISTS starting_price NUMERIC(12, 2)"
    ))
    await connection.execute(text(
        "ALTER TABLE marketplace_vendorlisting "
        "ADD COLUMN IF NOT EXISTS min_package_price NUMERIC(12, 2)"
    ))
    await connection.execute(text(
        "ALTER TABLE marketplace_vendorlisting "
        "ADD COLUMN IF NOT EXISTS max_package_price NUMERIC(12, 2)"
    ))
    await connection.execute(text(
        "ALTER TABLE marketplace_vendorlisting "
        "ADD COLUMN IF NOT EXISTS currency VARCHAR(10)"
    ))
    await connection.execute(text(
        "ALTER TABLE marketplace_vendorlisting "
        "ADD COLUMN IF NOT EXISTS search_vector TSVECTOR "
        "GENERATED ALWAYS AS ("
        "to_tsvector('simple', "
        "coalesce(business_name, '') || ' ' || "
        "coalesce(description, '') || ' ' || "
        "coalesce(category, '') || ' ' || "
        "coalesce(tags, '') || ' ' || "
        "coalesce(service_area, '')"
        ")) STORED"
    ))
    await connection.execute(text(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_marketplace_vendorlisting_external_id "
        "ON marketplace_vendorlisting (external_id)"
    ))
    await connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_marketplace_vendorlisting_category "
        "ON marketplace_vendorlisting (category)"
    ))
    await connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_marketplace_vendorlisting_service_area "
        "ON marketplace_vendorlisting (service_area)"
    ))
    await connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_marketplace_vendorlisting_average_rating "
        "ON marketplace_vendorlisting (average_rating)"
    ))
    await connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_marketplace_vendorlisting_approval_status "
        "ON marketplace_vendorlisting (approval_status)"
    ))
    await connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_marketplace_vendorlisting_min_package_price "
        "ON marketplace_vendorlisting (min_package_price)"
    ))
    await connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_marketplace_vendorlisting_max_package_price "
        "ON marketplace_vendorlisting (max_package_price)"
    ))
    await connection.execute(text(
        "CREATE INDEX IF NOT EXISTS idx_marketplace_search_vector "
        "ON marketplace_vendorlisting USING GIN (search_vector)"
    ))