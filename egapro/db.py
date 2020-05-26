import sqlite3
import uuid

import ujson as json

from . import config, utils


class NoData(Exception):
    pass


class table:

    conn = None

    @classmethod
    def fetchone(cls, sql, *params):
        with cls.conn as conn:
            cursor = conn.execute(sql, params,)
            row = cursor.fetchone()
        if not row:
            raise NoData
        return row[0]


class declaration(table):
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


class simulation(table):
    @classmethod
    def get(cls, uuid):
        return cls.fetchone("SELECT data FROM simulation WHERE uuid=?", uuid)

    @classmethod
    def put(cls, uuid, data):
        with cls.conn as conn:
            conn.execute(
                "INSERT OR REPLACE INTO simulation (uuid, at, data) VALUES (?, ?, ?)",
                (uuid, utils.utcnow(), json.dumps(data)),
            )

    @classmethod
    def create(cls, data):
        uid = str(uuid.uuid1())
        try:
            cls.get(uid)
        except NoData:
            cls.put(uid, data)
            return uid
        return cls.create(data)


def init():
    conn = sqlite3.connect(
        config.DBNAME, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    )
    table.conn = conn
    with conn as cursor:
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS declaration "
            "(siren TEXT, year INT, at TIMESTAMP, owner TEXT, data JSON)"
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS primary_key ON declaration(siren, year);"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS simulation "
            "(uuid TEXT PRIMARY KEY, at TIMESTAMP, data JSON)"
        )
