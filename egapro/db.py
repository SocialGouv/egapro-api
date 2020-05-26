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
        return row

    @classmethod
    def fetchvalue(cls, sql, *params):
        return cls.fetchone(sql, *params)[0]


class declaration(table):
    @classmethod
    def get(cls, siren, year):
        return cls.fetchone(
            "SELECT * FROM declaration WHERE siren=? AND year=?", siren, year
        )

    @classmethod
    def put(cls, siren, year, owner, data):
        with cls.conn as conn:
            conn.execute(
                "INSERT OR REPLACE INTO declaration (siren, year, last_modified, owner, data) "
                "VALUES (?, ?, ?, ?, ?)",
                (siren, year, utils.utcnow(), owner, data),
            )

    @classmethod
    def owner(cls, siren, year):
        return cls.fetchvalue(
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
        return cls.fetchone("SELECT * FROM simulation WHERE id=?", uuid)

    @classmethod
    def put(cls, uuid, data):
        with cls.conn as conn:
            conn.execute(
                "INSERT OR REPLACE INTO simulation (id, last_modified, data) VALUES (?, ?, ?)",
                (uuid, utils.utcnow(), data),
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


def from_json(b):
    """Convert a json payload stored in sqlite to a proper python object."""
    return json.loads(b)


def to_json(obj):
    """Serialize a python object to a json string."""
    return json.dumps(obj)


sqlite3.register_converter("json", from_json)
sqlite3.register_adapter(dict, to_json)


def init():
    conn = sqlite3.connect(
        config.DBNAME, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
    )
    conn.row_factory = sqlite3.Row
    table.conn = conn
    with conn as cursor:
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS declaration "
            "(siren TEXT, year INT, last_modified TIMESTAMP, owner TEXT, data JSON)"
        )
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS primary_key ON declaration(siren, year);"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS simulation "
            "(id TEXT PRIMARY KEY, last_modified TIMESTAMP, data JSON)"
        )
