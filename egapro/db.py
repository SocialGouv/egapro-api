import uuid

import asyncpg
import ujson as json

from . import config, utils


class NoData(Exception):
    pass


class table:

    conn = None

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
        if not row:
            raise NoData
        return row


class declaration(table):
    @classmethod
    async def get(cls, siren, year):
        return await cls.fetchrow(
            "SELECT * FROM declaration WHERE siren=$1 AND year=$2", siren, int(year)
        )

    @classmethod
    async def put(cls, siren, year, owner, data):
        async with cls.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO declaration (siren, year, last_modified, owner, data) "
                "VALUES ($1, $2, $3, $4, $5) ON CONFLICT (siren, year) DO UPDATE "
                "SET last_modified=$3, owner=$4, data=$5",
                siren,
                int(year),
                utils.utcnow(),
                owner,
                data,
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


class simulation(table):
    @classmethod
    async def get(cls, uuid):
        return await cls.fetchrow("SELECT * FROM simulation WHERE id=$1", uuid)

    @classmethod
    async def put(cls, uuid, data):
        async with cls.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO simulation (id, last_modified, data) VALUES ($1, $2, $3) "
                "ON CONFLICT (id) DO UPDATE SET last_modified = $2, data = $3",
                uuid,
                utils.utcnow(),
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
    table.pool = await asyncpg.create_pool(
        database=config.DBNAME,
        host=config.DBHOST,
        user=config.DBUSER,
        password=config.DBPASS,
        max_size=config.DBMAXSIZE,
        init=set_type_codecs,
    )
    async with table.pool.acquire() as conn:
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS declaration "
            "(siren TEXT, year INT, last_modified TIMESTAMP WITH TIME ZONE, owner TEXT, data JSONB,"
            "PRIMARY KEY (siren, year))"
        )
        await conn.execute(
            "CREATE TABLE IF NOT EXISTS simulation "
            "(id uuid PRIMARY KEY, last_modified TIMESTAMP WITH TIME ZONE, data JSONB)"
        )


async def terminate():
    table.pool.terminate()
