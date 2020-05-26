import sqlite3

import ujson as json

from . import config, utils


class NoData(Exception):
    pass


class declaration:

    conn = None

    @classmethod
    def fetchone(cls, sql, *params):
        with cls.conn as conn:
            cursor = conn.execute(sql, params,)
            row = cursor.fetchone()
        if not row:
            raise NoData
        return row[0]

    @classmethod
    def get(cls, siren, year):
        return cls.fetchone(
            "SELECT data FROM declaration WHERE siren=? AND year=?", siren, year
        )

    @classmethod
    def put(cls, siren, year, owner, data):
        with cls.conn as conn:
            conn.execute(
                "INSERT OR REPLACE INTO declaration (siren, year, at, owner, data) "
                "VALUES (?, ?, ?, ?, ?)",
                (siren, year, utils.utcnow(), owner, json.dumps(data)),
            )

    @classmethod
    def owner(cls, siren, year):
        return cls.fetchone(
            "SELECT owner FROM declaration WHERE siren=? AND year=?", siren, year
        )

    @classmethod
    def own(cls, siren, year, owner):
        with cls.conn as conn:
            conn.execute(
                "UPDATE declaration SET owner=? WHERE siren=? AND year=?",
                (siren, year, owner),
            )


def init():
    conn = sqlite3.connect(
        config.DBNAME, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    )
    declaration.conn = conn
    with conn as cursor:
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS declaration "
            "(siren TEXT, year INT, at TIMESTAMP, owner TEXT, data JSON)"
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS primary_key ON declaration(siren, year);"
        )
