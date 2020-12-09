import asyncio
import os
import uuid
from datetime import datetime

import pytest
from roll.testing import Client as BaseClient

from egapro.views import app as egapro_app
from egapro import config as egapro_config
from egapro import db, tokens


def pytest_configure(config):
    async def configure():
        os.environ["EGAPRO_DBNAME"] = "test_egapro"
        egapro_config.init()
        await db.init()
        async with db.declaration.pool.acquire() as conn:
            await conn.execute("DROP TABLE IF EXISTS declaration")
            await conn.execute("DROP TABLE IF EXISTS simulation")
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


@pytest.fixture
def declaration():
    async def factory(
        siren="12345678",
        year=2020,
        owner="foo@bar.com",
        company="Total Recall",
        departement="26",
        region="84",
        grade=26,
        uid=str(uuid.uuid1()),
        **data,
    ):
        data.setdefault("entreprise", {})
        data.setdefault("déclaration", {})
        data.setdefault("déclarant", {})
        data.setdefault("indicateurs", {})
        data.setdefault("id", uid)
        data["entreprise"].setdefault("raison_sociale", company)
        data["entreprise"].setdefault("département", departement)
        data["entreprise"].setdefault("région", region)
        data["entreprise"].setdefault("siren", siren)
        data["entreprise"].setdefault("effectif", {"tranche": "50:250", "total": 149})
        data["déclaration"].setdefault("année_indicateurs", year)
        data["déclaration"].setdefault("index", grade)
        data["déclaration"].setdefault(
            "date", datetime(2020, 11, 4, 10, 37, 6).isoformat()
        )
        data["déclaration"].setdefault("statut", "final")
        data["déclaration"].setdefault(
            "période_référence", ["2019-01-01", "2019-12-31"]
        )
        data["déclarant"].setdefault("email", owner)
        data["déclarant"].setdefault("prénom", "Martin")
        data["déclarant"].setdefault("nom", "Martine")
        data["indicateurs"].setdefault("rémunérations", {"mode": "csp"})
        await db.declaration.put(siren, year, owner, data)
        return data

    return factory


class Client(BaseClient):
    def login(self, email):
        token = tokens.create(email)
        self.default_headers["API-Key"] = token.decode()

    def logout(self):
        try:
            del self.default_headers["API-Key"]
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
