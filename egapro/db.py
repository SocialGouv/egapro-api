import sys
import uuid

import asyncpg
from asyncpg.exceptions import PostgresError
import ujson as json

from . import config, models, utils


class NoData(Exception):
    pass


class table:

    conn = None
    fields = []

    @classmethod
    async def fetch(cls, sql, *params):
        async with cls.pool.acquire() as conn:
            return await conn.fetch(sql, *params)

    @classmethod
    async def fetchrow(cls, sql, *params):
        async with cls.pool.acquire() as conn:
            row = await conn.fetchrow(sql, *params)
        if not row:
            raise NoData
        return row

    @classmethod
    async def fetchval(cls, sql, *params):
        async with cls.pool.acquire() as conn:
            row = await conn.fetchval(sql, *params)
        if row is None:
            raise NoData
        return row

    @classmethod
    def as_resource(cls, row):
        return {k: v for k, v in row.items() if k in cls.fields}


class declaration(table):
    fields = ["siren", "year", "data", "last_modified"]

    @classmethod
    async def all(cls):
        # TODO ORDER BY ?
        return await cls.fetch("SELECT * FROM declaration")

    @classmethod
    async def get(cls, siren, year):
        return await cls.fetchrow(
            "SELECT * FROM declaration WHERE siren=$1 AND year=$2", siren, int(year)
        )

    @classmethod
    async def put(cls, siren, year, owner, data, last_modified=None):
        # Allow to force last_modified, eg. during migrations.
        if last_modified is None:
            last_modified = utils.utcnow()
        ft = data.get("informationsEntreprise", {}).get("nomEntreprise")
        async with cls.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO declaration (siren, year, last_modified, owner, data, ft) "
                "VALUES ($1, $2, $3, $4, $5, to_tsvector('french', $6)) "
                "ON CONFLICT (siren, year) DO UPDATE "
                "SET last_modified=$3, owner=$4, data=$5, ft=to_tsvector('french', $6)",
                siren,
                int(year),
                last_modified,
                owner,
                data,
                ft,
            )

    @classmethod
    async def owner(cls, siren, year):
        return await cls.fetchval(
            "SELECT owner FROM declaration WHERE siren=$1 AND year=$2", siren, int(year)
        )

    @classmethod
    async def own(cls, siren, year, owner):
        async with cls.pool.acquire() as conn:
            conn.execute(
                "UPDATE declaration SET owner=$1 WHERE siren=$2 AND year=$3",
                siren,
                int(year),
                owner,
            )

    @classmethod
    async def search(cls, query, limit=10):
        async with cls.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT data FROM declaration WHERE ft @@ to_tsquery('french', $1) "
                "LIMIT $2",
                utils.prepare_query(query),
                limit
            )
        return [cls.public_data(row["data"]) for row in rows]

    @classmethod
    def public_data(cls, data):
        data = models.Data(data)
        out = {
            "id": data.get("id"),
            "declaration": {"noteIndex": data.path("declaration.noteIndex")},
            "informationsEntreprise": data.get("informationsEntreprise", {}),
            "informations": {
                "anneeDeclaration": data.path("informations.anneeDeclaration")
            },
        }
        return out


class simulation(table):
    fields = ["id", "data", "last_modified"]

    @classmethod
    async def get(cls, uuid):
        return await cls.fetchrow("SELECT * FROM simulation WHERE id=$1", uuid)

    @classmethod
    async def put(cls, uuid, data, last_modified=None):
        # Allow to force last_modified, eg. during migrations.
        if last_modified is None:
            last_modified = utils.utcnow()
        async with cls.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO simulation (id, last_modified, data) VALUES ($1, $2, $3) "
                "ON CONFLICT (id) DO UPDATE SET last_modified = $2, data = $3",
                uuid,
                last_modified,
                data,
            )

    @classmethod
    async def create(cls, data):
        uid = str(uuid.uuid1())
        try:
            await cls.get(uid)
        except NoData:
            await cls.put(uid, data)
            return uid
        return await cls.create(data)


async def set_type_codecs(conn):
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )
    await conn.set_type_codec("uuid", encoder=str, decoder=str, schema="pg_catalog")


async def init():
    try:
        table.pool = await asyncpg.create_pool(
            database=config.DBNAME,
            host=config.DBHOST,
            user=config.DBUSER,
            password=config.DBPASS,
            max_size=config.DBMAXSIZE,
            init=set_type_codecs,
        )
    except (OSError, PostgresError) as err:
        sys.exit(f"Cannot connect to DB: {err}")
    async with table.pool.acquire() as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS declaration "
            "(siren TEXT, year INT, last_modified TIMESTAMP WITH TIME ZONE, owner TEXT, data JSONB, ft TSVECTOR, "
            "PRIMARY KEY (siren, year));"
            "CREATE INDEX IF NOT EXISTS idx_effectifs ON declaration ((data->'informations'->'trancheEffectifs'));"
            "CREATE INDEX IF NOT EXISTS idx_ft ON declaration USING GIN (ft);"
            "CREATE TABLE IF NOT EXISTS simulation "
            "(id uuid PRIMARY KEY, last_modified TIMESTAMP WITH TIME ZONE, data JSONB);"
        )


async def terminate():
    table.pool.terminate()
