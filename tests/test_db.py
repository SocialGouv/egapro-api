import pytest

from egapro import db

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def init_db():
    await db.init()


async def test_simulation_fetchval():
    assert await db.table.fetchval("SELECT current_database();") == "test_egapro"


async def test_simulation_fetchrow():
    row = await db.table.fetchrow("SELECT current_database();")
    assert row["current_database"] == "test_egapro"


async def test_simulation_create():
    # Given
    uuid = await db.simulation.create({"foo": "baré"})

    async with db.table.pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM simulation WHERE id=$1", uuid)
    assert count == 1


async def test_simulation_get():
    # Given
    uuid = await db.simulation.create({"foo": "baré"})
    # When
    record = await db.simulation.get(uuid)
    # Then
    assert list(record.keys()) == ["id", "last_modified", "data"]
    assert record["data"] == {"foo": "baré"}
