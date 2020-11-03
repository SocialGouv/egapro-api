import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import minicli
from openpyxl import load_workbook
import progressist
import ujson as json

from egapro import config, db, exporter, models
from egapro.solen import *  # noqa: expose to minicli
from egapro.exporter import dump  # noqa: expose to minicli
from egapro.utils import json_dumps, compute_notes
from egapro import dgt


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
            last_modified = row["last_modified"]
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
                    current = existing["last_modified"]
                # Use dateDeclaration as last_modified for declaration, so we can decide
                # which to import between this or the same declaration from solen.
                old_last_modified = last_modified.replace(tzinfo=timezone.utc)
                last_modified = datetime.strptime(
                    data.path("declaration.dateDeclaration"),
                    "%d/%m/%Y %H:%M",
                )
                # Allow to compare aware datetimes.
                last_modified = last_modified.replace(tzinfo=timezone.utc)
                if (
                    not current
                    or last_modified > current
                    or current == old_last_modified
                ):
                    await db.declaration.put(
                        data.siren, data.year, data.email, data, last_modified
                    )
            # Always import in simulation, so the redirect from OLD URLs can work.
            await db.simulation.put(uuid, data, last_modified)
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
async def validate(pdb=False):
    from egapro.schema import JSON_SCHEMA
    from egapro.schema.legacy import from_legacy
    from jsonschema_rs import ValidationError

    for row in await db.declaration.all():
        data = from_legacy(row["data"])
        try:
            JSON_SCHEMA.validate(json.loads(json_dumps(data)))
        except ValidationError as err:
            print(f"\n\nERROR WITH {row['siren']}/{row['year']}\n")
            print(err)
            if pdb:
                breakpoint()
                break
        sys.stdout.write(".")


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
