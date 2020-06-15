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


async def test_declaration_all():
    # Given
    await db.declaration.put("12345678", 2020, "foo@bar.com", {"foo": "baré"})
    await db.declaration.put("87654321", 2020, "foo@baz.com", {"foo": "bazé"})

    records = await db.declaration.all()
    assert len(records) == 2
    assert records[0]["siren"] == "12345678"
    assert records[1]["siren"] == "87654321"
