import asyncio
import os

import pytest
from roll.testing import Client as BaseClient

from egapro import app as egapro_app
from egapro import config as egapro_config
from egapro import db, tokens


def pytest_configure(config):
    async def configure():
        os.environ["EGAPRO_DBNAME"] = "test_egapro"
        os.environ["EGAPRO_REQUIRE_TOKEN"] = "1"
        egapro_config.init()
        await db.init()
        async with db.declaration.pool.acquire() as conn:
            await conn.execute("DROP TABLE IF EXISTS declaration")
        await db.init()

    loop = asyncio.get_event_loop()
    loop.run_until_complete(configure())


def pytest_runtest_setup(item):
    async def setup():
        await db.init()
        # Make sure the current active database is the test one before deleting.
        async with db.declaration.pool.acquire() as conn:
            dbname = await conn.fetchval("SELECT current_database();")
        assert dbname == "test_egapro"

        # Ok, it's the test database, we can now delete the data.
        async with db.declaration.pool.acquire() as conn:
            await conn.execute("TRUNCATE TABLE declaration;")
            await conn.execute("TRUNCATE TABLE simulation;")
        await db.terminate()

    asyncio.get_event_loop().run_until_complete(setup())


@pytest.fixture(scope="session")
def event_loop():
    # Override default pytest-asyncio fixture in order to get the same loop on all the
    # tests and setup / teardown.
    loop = asyncio.get_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def app():  # Requested by Roll testing utilities.
    return egapro_app


class Client(BaseClient):
    headers = {}

    async def request(
        self, path, method="GET", body=b"", headers=None, content_type=None
    ):
        # TODO move this to Roll upstream?
        headers = headers or {}
        for key, value in self.headers.items():
            headers.setdefault(key, value)
        return await super().request(path, method, body, headers, content_type)

    def login(self, email):
        token = tokens.create(email)
        self.headers["API-Key"] = token.decode()

    def logout(self):
        try:
            del self.headers["API-Key"]
        except KeyError:
            pass


@pytest.fixture
def client(app, event_loop):
    app.loop = event_loop
    app.loop.run_until_complete(app.startup())
    c = Client(app)
    c.login("foo@bar.org")
    yield c
    c.logout()
    app.loop.run_until_complete(app.shutdown())
