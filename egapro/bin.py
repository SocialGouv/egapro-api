import asyncpg
import minicli
import progressist
import ujson as json

from egapro import db, models
from egapro.solen import import_solen  # noqa: expose to minicli
from egapro.exporter import dump  # noqa: expose to minicli


@minicli.cli
async def migrate_legacy():
    conn = await asyncpg.connect("postgresql://postgres@localhost/legacy_egapro")
    rows = await conn.fetch("SELECT * FROM objects;")
    await conn.close()
    bar = progressist.ProgressBar(prefix="Importing…", total=len(rows), throttle=100)
    async with db.table.pool.acquire() as conn:
        for row in bar.iter(rows):
            data = json.loads(row["data"])
            if "data" not in data:
                continue
            data = models.Data(data["data"])
            last_modified = row["last_modified"]
            if data.validated:
                await db.declaration.put(
                    data.siren, data.year, data.email, data, last_modified
                )
            else:
                uuid = row["id"]
                await db.simulation.put(uuid, data, last_modified)


@minicli.wrap
async def wrapper():
    await db.init()
    yield
    await db.terminate()


def main():
    minicli.run()
