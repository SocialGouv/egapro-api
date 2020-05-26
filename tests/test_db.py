import json

import pytest

from egapro import db, config

pytestmark = pytest.mark.asyncio


async def test_table_fetchone():
    # Given
    uuid = db.simulation.create({"foo": "baré"})
    # When
    record = db.simulation.get(uuid)
    # Then
    assert list(record.keys()) == ["id", "last_modified", "data"]
    assert record["data"] == {"foo": "baré"}
