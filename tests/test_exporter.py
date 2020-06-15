import json
from pathlib import Path

import pytest

from egapro import db, exporter

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def init_db():
    await db.init()


async def test_dump():
    await db.declaration.put("12345678", 2020, "foo@bar.com", {"foo": "baré"})
    await db.declaration.put("87654321", 2020, "foo@baz.com", {"foo": "bazé"})
    path = Path("/tmp/test_dump_egapro.json")
    await exporter.dump(path)
    assert json.loads(path.read_text()) == [{"foo": "baré"}, {"foo": "bazé"}]
