import os

import pytest
from roll.testing import Client as BaseClient

from egapro import app as egapro_app
from egapro import config as egapro_config
from egapro import db, tokens


def pytest_configure(config):
    os.environ["EGAPRO_DBNAME"] = "test_egapro.db"
    os.environ["EGAPRO_REQUIRE_TOKEN"] = "1"
    egapro_config.init()
    db.init()
    with db.declaration.conn as cursor:
        cursor.execute("DROP TABLE IF EXISTS declaration")
    db.init()


def pytest_runtest_setup(item):
    # Make sure the current active database is the test one before deleting.
    with db.declaration.conn as conn:
        cursor = conn.execute("PRAGMA database_list;")
        dbname = cursor.fetchone()[2]
    assert dbname.endswith("test_egapro.db")

    # Ok, it's the test database, we can now delete the data.
    with db.declaration.conn as conn:
        conn.execute("DELETE FROM declaration;")
        conn.execute("DELETE FROM simulation;")


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
