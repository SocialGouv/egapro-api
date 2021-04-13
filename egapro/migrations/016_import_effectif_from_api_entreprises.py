import progressist

from egapro import helpers, schema

CACHE = {}


async def main(db, logger):

    records = await db.declaration.fetch(
        "SELECT data, owner, modified_at FROM declaration "
        "WHERE declared_at IS NOT NULL "
        "AND data->'entreprise'->'effectif'->'code' IS NULL"
    )
    bar = progressist.ProgressBar(prefix="Migrating…", total=len(records))
    skipped = []
    for record in bar.iter(records):
        data = record.data.raw
        siren = record.data.siren
        year = record.data.year
        if siren not in CACHE:
            CACHE[siren] = await helpers.load_from_api_entreprises(siren)
        extra = CACHE[siren]
        try:
            data["entreprise"]["effectif"]["code"] = extra["effectif"]
            schema.validate(data)
        except (ValueError, KeyError) as err:
            skipped.append((siren, year, err))
            continue
        await db.declaration.put(
            siren,
            year,
            owner=record["owner"],
            data=data,
            modified_at=record["modified_at"],
        )
    print("Skipped:", skipped)
