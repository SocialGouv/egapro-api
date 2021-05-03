import uuid
from datetime import datetime

import asyncpg
from naf import DB as NAF
from asyncstdlib.functools import lru_cache
from asyncpg.exceptions import DuplicateDatabaseError, PostgresError
import ujson as json

from . import config, models, sql, utils, helpers
from .loggers import logger


class NoData(Exception):
    pass


class Record(asyncpg.Record):
    fields = []

    def __getattr__(self, key):
        return self.get(key)

    def as_resource(self):
        return {k: getattr(self, k) for k in self.fields}


class SimulationRecord(Record):
    fields = ["id", "data", "modified_at"]


class DeclarationRecord(Record):
    fields = ["siren", "year", "data", "modified_at", "declared_at"]

    @property
    def data(self):
        data = self.get("draft") or self.get("data")
        return models.Data(data)


class table:

    conn = None
    pool = None
    record_class = Record

    @classmethod
    async def fetch(cls, sql, *params):
        async with cls.pool.acquire() as conn:
            return await conn.fetch(sql, *params, record_class=cls.record_class)

    @classmethod
    async def fetchrow(cls, sql, *params):
        async with cls.pool.acquire() as conn:
            row = await conn.fetchrow(sql, *params, record_class=cls.record_class)
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
    async def execute(cls, sql, *params):
        async with cls.pool.acquire() as conn:
            return await conn.execute(sql, *params)


class declaration(table):
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
        ft = helpers.extract_ft(data)
        declared_at = await cls.get_declared_at(siren, year)
        if not declared_at and not data.is_draft():
            declared_at = modified_at
        if declared_at:
            data["déclaration"]["date"] = declared_at.isoformat()
        if data.is_draft():
            query = sql.insert_draft_declaration
            args = (siren, int(year), modified_at, owner, data.raw)
        else:
            await search.index(data)
            query = sql.insert_declaration
            args = (siren, year, modified_at, declared_at, owner, data.raw, ft)
        async with cls.pool.acquire() as conn:
            await conn.execute(query, *args)

    @classmethod
    async def owner(cls, siren, year):
        return await cls.fetchval(
            "SELECT owner FROM declaration WHERE siren=$1 AND year=$2 "
            "AND declared_at IS NOT NULL",
            siren,
            int(year),
        )

    @classmethod
    async def own(cls, siren, year, owner):
        await cls.execute(
            "UPDATE declaration SET owner=$3 WHERE siren=$1 AND year=$2",
            siren,
            int(year),
            owner,
        )

    @classmethod
    async def owned(cls, owner):
        return [
            cls.metadata(r)
            for r in await cls.fetch(
                "SELECT * FROM declaration WHERE owner=$1", owner
            )
        ]

    @classmethod
    def metadata(cls, record):
        return {
            "modified_at": record["modified_at"],
            "declared_at": record["declared_at"],
            "siren": record["siren"],
            "year": record["year"],
            "name": record.data.company,
        }

    @classmethod
    def public_data(cls, data):
        data = models.Data(data)
        raison_sociale = data.company
        siren = data.siren
        ues = data.path("entreprise.ues")
        if ues:
            ues["entreprises"].insert(
                0, {"raison_sociale": raison_sociale, "siren": siren}
            )
        out = {
            "entreprise": {
                "raison_sociale": raison_sociale,
                "siren": siren,
                "région": data.path("entreprise.région"),
                "département": data.path("entreprise.département"),
                "code_naf": data.path("entreprise.code_naf"),
                "ues": ues,
                "effectif": {"tranche": data.path("entreprise.effectif.tranche")},
            },
        }
        return out


class simulation(table):
    record_class = SimulationRecord

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


class search(table):
    @classmethod
    async def index(cls, data):
        if not data.is_public():
            return
        ft = helpers.extract_ft(data)
        siren = data.siren
        year = data.year
        region = data.path("entreprise.région")
        departement = data.path("entreprise.département")
        code_naf = data.path("entreprise.code_naf")
        section_naf = None
        if code_naf:
            try:
                section_naf = NAF[code_naf].section.code
            except KeyError:
                pass
        note = data.path("déclaration.index")
        declared_at = datetime.fromisoformat(data.path("déclaration.date"))
        async with cls.pool.acquire() as conn:
            try:
                await conn.execute(
                    sql.index_declaration,
                    siren,
                    year,
                    declared_at,
                    ft,
                    region,
                    departement,
                    section_naf,
                    note,
                )
            except PostgresError as err:
                logger.error(f"Cannot index {siren}/{year}: {err}")

    @classmethod
    async def run(cls, query=None, limit=10, offset=0, **filters):
        args = [limit, offset]
        args, where = cls.build_query(args, query, **filters)
        rows = await cls.fetch(sql.search.format(where=where), *args)
        return [
            {
                **declaration.public_data(row["data"][0]),
                "notes": row["notes"],
                "label": cls.compute_label(query, row["data"][0]),
            }
            for row in rows
        ]

    @classmethod
    @lru_cache(maxsize=128)
    async def stats(cls, year, **filters):
        args = [year]
        args, where = cls.build_query(args, **filters)
        return await cls.fetchrow(sql.search_stats.format(where=where), *args)

    @classmethod
    async def count(cls, query=None, **filters):
        tpl = "SELECT COUNT(DISTINCT(siren)) as count FROM search {where}"
        args, where = cls.build_query([], query, **filters)
        return await cls.fetchval(tpl.format(where=where), *args)

    @staticmethod
    def build_query(args, query=None, **filters):
        where = []
        if query and len(query) == 9 and query.isdigit():
            filters["siren"] = query
            query = None
        elif query:
            query = utils.prepare_query(query)
            args.append(query)
            where.append(f"search.ft @@ to_tsquery('ftdict', ${len(args)})")
        for name, value in filters.items():
            if value is not None:
                args.append(value)
                where.append(f"search.{name}=${len(args)}")
        if where:
            where = "WHERE " + " AND ".join(where)
        return args, where or ""

    @classmethod
    async def truncate(cls):
        await cls.execute("TRUNCATE table search")

    @classmethod
    def compute_label(cls, query, data):
        entreprise = data["entreprise"]
        declarante = entreprise.get("raison_sociale")
        ues = entreprise.get("ues", {})
        nom_ues = ues.get("nom")
        others = ues.get("entreprises")
        if not nom_ues or not others or not query:
            return declarante
        others = [o["raison_sociale"] for o in others]
        return helpers.compute_label(query, nom_ues, declarante, *others)


class archive(table):
    @classmethod
    async def put(cls, siren, year, data, by=None, ip=None):
        async with cls.pool.acquire() as conn:
            await conn.execute(sql.insert_archive, siren, year, data, by, ip)


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
        await conn.execute(sql.create_search_table)
        await conn.execute(sql.create_archive_table)


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
