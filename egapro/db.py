import uuid

import asyncpg
from asyncpg.exceptions import DuplicateDatabaseError, PostgresError
import ujson as json

from . import config, models, sql, utils
from .schema.legacy import from_legacy


class NoData(Exception):
    pass


class Record(dict):
    def __getattr__(self, key):
        return self.get(key)


class DeclarationRecord(Record):
    @property
    def data(self):
        data = self.get("draft") or self.get("data") or self.get("legacy")
        if "déclaration" not in data:
            data = from_legacy(data)
        return models.Data(data)


class table:

    conn = None
    pool = None
    fields = []
    record_class = Record

    @classmethod
    async def fetch(cls, sql, *params):
        async with cls.pool.acquire() as conn:
            return [cls.record_class(r) for r in await conn.fetch(sql, *params)]

    @classmethod
    async def fetchrow(cls, sql, *params):
        async with cls.pool.acquire() as conn:
            row = await conn.fetchrow(sql, *params)
        if not row:
            raise NoData
        return cls.record_class(row)

    @classmethod
    async def fetchval(cls, sql, *params):
        async with cls.pool.acquire() as conn:
            row = await conn.fetchval(sql, *params)
        if row is None:
            raise NoData
        return row

    @classmethod
    def as_resource(cls, row):
        return {k: getattr(row, k) for k in cls.fields}

    @classmethod
    async def execute(cls, sql, *params):
        async with cls.pool.acquire() as conn:
            return await conn.execute(sql, *params)


class declaration(table):
    fields = ["siren", "year", "data", "modified_at", "declared_at"]
    record_class = DeclarationRecord

    @classmethod
    async def all(cls):
        return await cls.fetch("SELECT * FROM declaration")

    @classmethod
    async def completed(cls):
        # Do not select draft in this request, as it must reflect the declarations state
        return await cls.fetch(
            "SELECT data, legacy, modified_at FROM declaration "
            "WHERE declared_at IS NOT NULL ORDER BY declared_at DESC"
        )

    @classmethod
    async def get(cls, siren, year):
        return await cls.fetchrow(
            "SELECT * FROM declaration WHERE siren=$1 AND year=$2", siren, int(year)
        )

    @classmethod
    async def get_declared_at(cls, siren, year):
        try:
            return await cls.fetchval(
                "SELECT declared_at FROM declaration WHERE siren=$1 AND year=$2",
                siren,
                int(year),
            )
        except NoData:
            return None

    @classmethod
    async def put(cls, siren, year, owner, data, modified_at=None):
        data = models.Data(data)
        # Allow to force modified_at, eg. during migrations.
        if modified_at is None:
            modified_at = utils.utcnow()
        year = int(year)
        data.setdefault("déclaration", {})
        data["déclaration"]["année_indicateurs"] = year
        data.setdefault("entreprise", {})
        data["entreprise"]["siren"] = siren
        ft = data.get("entreprise", {}).get("raison_sociale")
        declared_at = await cls.get_declared_at(siren, year)
        if not declared_at and not data.is_draft():
            declared_at = modified_at
        if declared_at:
            data["déclaration"]["date"] = declared_at.isoformat()
        if data.is_draft():
            query = sql.insert_draft_declaration
            args = (siren, int(year), modified_at, owner, data.raw)
        else:
            query = sql.insert_declaration
            args = (siren, year, modified_at, declared_at, owner, data.raw, ft)
        async with cls.pool.acquire() as conn:
            await conn.execute(query, *args)

    @classmethod
    async def owner(cls, siren, year):
        return await cls.fetchval(
            "SELECT owner FROM declaration WHERE siren=$1 AND year=$2", siren, int(year)
        )

    @classmethod
    async def own(cls, siren, year, owner):
        await cls.execute(
            "UPDATE declaration SET owner=$1 WHERE siren=$2 AND year=$3",
            siren,
            int(year),
            owner,
        )

    @classmethod
    async def search(cls, query, limit=10):
        async with cls.pool.acquire() as conn:
            rows = await conn.fetch(
                sql.search,
                utils.prepare_query(query),
                limit,
            )
        return [cls.public_data(row["data"]) for row in rows]

    @classmethod
    async def reindex(cls):
        async with cls.pool.acquire() as conn:
            # TODO use a generated column (PSQL >= 12 only)
            await conn.execute(
                "UPDATE declaration SET ft=to_tsvector('ftdict', data->'entreprise'->>'raison_sociale')"
            )

    @classmethod
    def public_data(cls, data):
        # Keep old schema for now, as it's used only by egapro
        data = models.Data(data)
        out = {
            "id": data.get("id"),
            "declaration": {"noteIndex": data.path("déclaration.index")},
            "informationsEntreprise": {
                "nomEntreprise": data.path("entreprise.raison_sociale"),
                "siren": data.path("entreprise.siren"),
                "region": data.path("entreprise.région"),
                "departement": data.path("entreprise.département"),
                "structure": data.structure,
                "nomUES": data.path("entreprise.ues.raison_sociale"),
                "entreprisesUES": [
                    {"nom": e["raison_sociale"], "siren": e["siren"]}
                    for e in data.path("entreprise.ues.entreprises") or []
                ],
            },
            "informations": {
                "anneeDeclaration": data.path("déclaration.année_indicateurs")
            },
        }
        return out


class simulation(table):
    fields = ["id", "data", "modified_at"]

    @classmethod
    async def get(cls, uuid):
        return await cls.fetchrow("SELECT * FROM simulation WHERE id=$1", uuid)

    @classmethod
    async def put(cls, uuid, data, modified_at=None):
        # Allow to force modified_at, eg. during migrations.
        if modified_at is None:
            modified_at = utils.utcnow()
        async with cls.pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO simulation (id, modified_at, data) VALUES ($1, $2, $3) "
                "ON CONFLICT (id) DO UPDATE SET modified_at = $2, data = $3",
                uuid,
                modified_at,
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
            min_size=config.DBMINSIZE,
            max_size=config.DBMAXSIZE,
            init=set_type_codecs,
            ssl=config.DBSSL,
        )
    except (OSError, PostgresError) as err:
        raise RuntimeError(f"CRITICAL Cannot connect to DB: {err}")
    async with table.pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
        await conn.execute(sql.create_ftdict)
        await conn.execute(sql.create_declaration_table)
        await conn.execute(sql.create_simulation_table)


async def create_indexes():
    async with table.pool.acquire() as conn:
        await conn.execute(sql.create_indexes)


async def create():
    conn = await asyncpg.connect(
        database="template1",
        host=config.DBHOST,
        user=config.DBUSER,
        password=config.DBPASS,
        ssl=config.DBSSL,
    )
    # Asure username is in the form user@servername.
    user = config.DBUSER.split("@")[0]
    try:
        await conn.fetch(f"CREATE DATABASE {config.DBNAME} OWNER {user};")
    except DuplicateDatabaseError as err:
        print(err)
    else:
        print(f"Created database {config.DBNAME} for user {user}")
    await conn.close()


async def terminate():
    try:
        await table.pool.close()
        print("Closing DB pool.")
    except AttributeError:
        print("DB not initialized, nothing to do.")
