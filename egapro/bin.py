import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import minicli
import progressist
import ujson as json
from openpyxl import load_workbook

from egapro import config, db, dgt, exporter, models, schema
from egapro.exporter import dump  # noqa: expose to minicli
from egapro.solen import *  # noqa: expose to minicli
from egapro.utils import compute_notes, json_dumps


@minicli.cli
async def migrate_legacy(siren=[], year: int = None):
    conn = await asyncpg.connect(config.LEGACY_PSQL)
    rows = await conn.fetch("SELECT * FROM objects;")
    await conn.close()
    bar = progressist.ProgressBar(prefix="Importing…", total=len(rows), throttle=100)
    done = 0
    async with db.table.pool.acquire() as conn:
        for row in bar.iter(rows):
            data = json.loads(row["data"])
            if "data" not in data:
                continue
            uuid = row["id"]
            data["data"]["id"] = uuid
            data = models.Data(data["data"])
            modified_at = row["modified_at"]
            if siren and str(data.siren) not in siren:
                continue
            if year and data.year != year:
                continue
            if data.validated:
                try:
                    existing = await db.declaration.get(data.siren, data.year)
                except db.NoData:
                    current = None
                else:
                    current = existing["modified_at"]
                # Use dateDeclaration as modified_at for declaration, so we can decide
                # which to import between this or the same declaration from solen.
                old_modified_at = modified_at.replace(tzinfo=timezone.utc)
                modified_at = datetime.strptime(
                    data.path("declaration.dateDeclaration"),
                    "%d/%m/%Y %H:%M",
                )
                # Allow to compare aware datetimes.
                modified_at = modified_at.replace(tzinfo=timezone.utc)
                if not current or modified_at > current or current == old_modified_at:
                    await db.declaration.put(
                        data.siren, data.year, data.email, data, modified_at
                    )
            # Always import in simulation, so the redirect from OLD URLs can work.
            await db.simulation.put(uuid, data, modified_at)
            done += 1
    print(f"Imported {done} rows")


@minicli.cli
async def dump_dgt(path: Path, max_rows: int = None):
    wb = await dgt.as_xlsx(max_rows)
    print("Writing the XLSX to", path)
    wb.save(path)
    print("Done")


@minicli.cli
async def compute_duplicates(out: Path, current: Path, legacy: Path, *solen: Path):
    """Compute duplicates between solen and solen or solen and egapro.
    Should be removed as soon as we have integrated the solen form.


    :current:   Path to current consolidated export.
    :legacy:    Path to consolidated export from legacy.
    :solen:     Paths to solen export, in the form solen-YYYY.xlsx"""
    wb = await dgt.duplicates(current, legacy, *solen)
    print("Writing the XLSX to", out)
    wb.save(out)
    print("Done")


@minicli.cli
def compare_xlsx(old: Path, new: Path, max_rows: int = None, ignore=[]):
    """Compare two XLSX.

    :old:       Path to old version of the XLSX.
    :new:       Path to new version of the XLSX.
    :max_rows:  Only compute `max_rows` rows.
    :ignore:    A list of headers (columns) to ignore when comparing rows.
    """
    with old.open("rb") as f:
        old = list(load_workbook(f, read_only=True, data_only=True).active.values)
    with new.open("rb") as f:
        new = list(load_workbook(f, read_only=True, data_only=True).active.values)

    headers = old[0]
    if not headers == new[0]:
        print("Headers differ!")
        print(headers)
        print(old[0])
        sys.exit(1)

    print("Rows in each file:", len(old), "vs", len(new))

    old = {r[1]: r for r in old[1:] if r[0]}
    new = {r[1]: r for r in new[1:] if r[0]}

    old_ids = set(old.keys())
    new_ids = set(new.keys())
    print("Rows not in new", len(old_ids - new_ids))
    print("Rows not in old", len(new_ids - old_ids))

    for url, old_row in old.items():
        new_row = new[url]

        if old_row == new_row:
            sys.stdout.write(".")
            continue  # Rows are equal.
        to_break = False

        for idx in range(len(headers)):
            header = headers[idx]
            try:
                old_value = old_row[idx]
            except IndexError:
                old_value = None
            try:
                new_value = new_row[idx]
            except IndexError:
                new_value = None
            if old_value != new_value:
                # TODO: allow to type as tuple in minicli.
                if header.startswith(tuple(ignore)):
                    continue
                print(
                    f"{header}: {old_value!r} vs {new_value!r} for {old_row[19]}/{old_row[12]}"
                )
                to_break = True
        if to_break:
            break


@minicli.cli
async def search(q, verbose=False):
    rows = await db.declaration.search(q)
    for row in rows:
        data = models.Data(row)
        print(f"{data.siren} | {data.year} | {data.company}")
        if verbose:
            print(row)


@minicli.cli
async def export_public_data(path: Path):
    print("Writing the CSV to", path)
    with path.open("w") as f:
        await exporter.public_data(f)
    print("Done")


@minicli.cli
async def create_db():
    """Create PostgreSQL database."""
    await db.create()


@minicli.cli
async def create_indexes():
    """Create DB indexes."""
    await db.create_indexes()


@minicli.cli
async def reindex():
    """Reindex Full Text search."""
    await db.declaration.reindex()


@minicli.cli
def serve(reload=False):
    """Run a web server (for development only)."""
    from roll.extensions import simple_server

    from .views import app

    if reload:
        import hupper

        hupper.start_reloader("egapro.bin.serve")
    simple_server(app, port=2626)


@minicli.cli
async def migrate_effectif(source: Path):
    more_1000 = [l.split(";")[1] for l in source.read_text().split("\n") if l]
    await db.declaration.execute(
        """UPDATE declaration SET data = jsonb_set(data, '{informations,trancheEffectifs}', '"1000 et plus"') WHERE data->'informations'->>'trancheEffectifs'='Plus de 250' AND siren = any($1::text[])""",
        tuple(more_1000),
    )
    await db.declaration.execute(
        """UPDATE declaration SET data = jsonb_set(data, '{informations,trancheEffectifs}', '"251 à 999"') WHERE data->'informations'->>'trancheEffectifs'='Plus de 250'""",
    )


@minicli.cli
async def validate(pdb=False, verbose=False):
    from egapro.schema import validate, cross_validate
    from egapro.schema.legacy import from_legacy

    errors = set()
    for row in await db.declaration.all():
        data = row["data"] or row["legacy"]
        if "déclaration" not in data:
            data = from_legacy(row["legacy"])
        data = json.loads(json_dumps(data))
        try:
            validate(data)
            cross_validate(data)
        except ValueError as err:
            sys.stdout.write("×")
            errors.add(str(err))
            if verbose:
                print(f"\n\nERROR WITH {row['siren']}/{row['year']}\n")
                print(err)
            if pdb:
                breakpoint()
                break
            continue
        sys.stdout.write("·")
    print(errors)


@minicli.cli
async def compare_index(pdb=False, verbose=False):
    from egapro.schema.legacy import from_legacy

    records = await db.declaration.all()
    for record in records:
        legacy = {
            "index": record["data"]["declaration"].get("noteIndex"),
            "points": record["data"]["declaration"].get("totalPoint"),
            "max": record["data"]["declaration"].get("totalPointCalculable"),
            "indic1": record["data"]["indicateurUn"].get("noteFinale"),
            "indic2": record["data"].get("indicateurDeux", {}).get("noteFinale"),
            "indic2et3": record["data"]
            .get("indicateurDeuxTrois", {})
            .get("noteFinale"),
            "indic3": record["data"].get("indicateurTrois", {}).get("noteFinale"),
            "indic4": record["data"]["indicateurQuatre"].get("noteFinale"),
            "indic5": record["data"]["indicateurCinq"].get("noteFinale"),
        }
        data = models.Data(from_legacy(record["data"]))
        compute_notes(data)
        current = {
            "index": record["data"]["déclaration"].get("index"),
            "points": record["data"]["déclaration"].get("points"),
            "max": record["data"]["déclaration"].get("points_calculables"),
            "indic1": record["data"]["indicateurs"]["rémunérations"].get("note"),
            "indic2": record["data"]["indicateurs"][
                "augmentations_hors_promotions"
            ].get("note"),
            "indic2et3": record["data"]["indicateurs"]["augmentations"].get("note"),
            "indic3": record["data"]["indicateurs"]["promotions"].get("note"),
            "indic4": record["data"]["indicateurs"]["congés_maternité"].get("note"),
            "indic5": record["data"]["indicateurs"]["hautes_rémunérations"].get("note"),
        }
        if not legacy == current:
            sys.stdout.write("x")
            if verbose:
                print(data.siren, data.year)
                print(legacy)
                print(current)
            if pdb:
                breakpoint()
        else:
            sys.stdout.write(".")


@minicli.cli
async def migrate_schema(no_schema=False):
    from egapro.schema.legacy import from_legacy

    if not no_schema:
        async with db.table.pool.acquire() as conn:
            await conn.execute(
                """
                ALTER TABLE declaration RENAME COLUMN last_modified TO modified_at;
                ALTER TABLE simulation RENAME COLUMN last_modified TO modified_at;
                ALTER TABLE declaration ADD COLUMN declared_at TIMESTAMP WITH TIME ZONE;
                ALTER TABLE declaration RENAME COLUMN data TO legacy;
                ALTER TABLE declaration ADD COLUMN data JSONB;
                """,
            )
    records = await db.declaration.fetch("SELECT * FROM declaration")
    bar = progressist.ProgressBar(prefix="Migrating…", total=len(records), throttle=100)
    for record in bar.iter(records):
        data = record["legacy"]
        if "déclaration" not in data:
            data = from_legacy(data)
        date = data["déclaration"].get("date")
        declared_at = None
        if date:
            declared_at = datetime.fromisoformat(date)
        try:
            schema.validate(data)
        except ValueError as err:
            print(err)
            data = None
        except Exception:
            print(record)
        async with db.declaration.pool.acquire() as conn:
            await conn.execute(
                "UPDATE declaration "
                "SET data=$1, declared_at=$2, modified_at=$3 "
                "WHERE siren=$4 AND year=$5",
                data,
                declared_at,
                declared_at or record["modified_at"],
                record["siren"],
                record["year"],
            )


@minicli.cli
async def explore(*siren_year):
    """Explore déclarations

    Usage: egapro explore [siren, year[, siren, year…]]

    Without any arguments, will return metadata for last 10 déclarations.
    Otherwise, pass siren, year pairs to get déclarations détailled data.
    """
    if not siren_year:
        records = await db.declaration.fetch(
            "SELECT * FROM declaration ORDER BY modified_at LIMIT 10"
        )
        print("# Latest déclarations")
        print("| siren     | year | modified_at      | declared_at      | owner")
        for record in records:
            declared_at = (
                str(record["declared_at"])[:16] if record["declared_at"] else "-" * 16
            )
            print(
                f"| {record['siren']} | {record['year']} | {str(record['modified_at'])[:16]} | {declared_at} | {record['owner']}"
            )
        return
    for siren, year in zip(siren_year[::2], siren_year[1::2]):
        record = await db.declaration.get(siren, year)
        sep = "—" * 80
        print(f"Data for {siren} {year}")
        data = models.Data(record["data"])
        for root in [
            "indicateurs.hautes_rémunérations",
            "indicateurs.congés_maternité",
            "indicateurs.promotions",
            "indicateurs.augmentations",
            "indicateurs.augmentations_hors_promotions",
            "indicateurs.rémunérations",
            "entreprise",
            "déclaration",
        ]:
            print(sep)
            print(f"# {root}")
            sequence = data.path(root)
            if not sequence:
                print("—")
                continue
            for key, value in sequence.items():
                print(f"{key:<20} | {value}")
        print(sep)
        for key in ["modified_at", "declared_at", "owner"]:
            print(f"{key:<20} | {record[key]}")


@minicli.cli
def shell():
    """Run an ipython already connected to PSQL."""
    try:
        from IPython import start_ipython
    except ImportError:
        print('IPython is not installed. Type "pip install ipython"')
    else:
        start_ipython(
            argv=[],
            user_ns={
                "db": db,
                "config": config,
                "schema": schema,
            },
        )


@minicli.wrap
async def wrapper():
    try:
        await db.init()
    except RuntimeError as err:
        print(err)
    yield
    await db.terminate()


def main():
    minicli.run()
