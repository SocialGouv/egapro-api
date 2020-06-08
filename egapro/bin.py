import asyncpg
import progressist
import ujson as json

from egapro import db


async def migrate_from_legacy():
    await db.init()
    conn = await asyncpg.connect("postgresql://postgres@localhost/legacy_egapro")
    rows = await conn.fetch("SELECT * FROM objects;")
    await conn.close()
    bar = progressist.ProgressBar(prefix="Importing…", total=len(rows), throttle=100)
    async with db.table.pool.acquire() as conn:
        for row in bar.iter(rows):
            data = json.loads(row["data"])
            if "data" not in data:
                continue
            data = data["data"]
            validated = data.get("declaration", {}).get("formValidated") == "Valid"
            last_modified = row["last_modified"]
            if validated:
                siren = data["informationsEntreprise"]["siren"]
                owner = data["informationsDeclarant"]["email"]
                try:
                    year = data["informations"]["anneeDeclaration"]
                except KeyError:
                    year = data["informations"]["debutPeriodeReference"][-4:]
                await db.declaration.put(siren, year, owner, data, last_modified)
            else:
                uuid = row["id"]
                await db.simulation.put(uuid, data, last_modified)
