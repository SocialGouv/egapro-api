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
        sys.exit(1)

    print("Rows in each file:", len(old), "vs", len(new))

    old_ids = set([r[1] for r in old if r[0]])
    new_ids = set([r[1] for r in new if r[0]])
    print("Rows not in new", len(old_ids - new_ids))
    print("Rows not in old", len(new_ids - old_ids))

    skipped = 0
    for row_idx in range(max_rows or len(old)):
        try:
            old_row = old[row_idx + skipped]
        except IndexError:
            break
        if old_row[0] is None:
            # Empty row. EOF?
            break
        new_row = new[row_idx]

        # URL differs, so IDs differs, let's try to compare with next old row instead.
        if not old_row[1] == new_row[1]:
            skipped += 1
            continue

        if old_row == new_row:
            continue  # Rows are equal.

        for idx in range(len(headers)):
            header = headers[idx]
            if old_row[idx] != new_row[idx]:
                # TODO: allow to type as tuple in minicli.
                if header.startswith(tuple(ignore)):
                    continue
                print(
                    f"{header}: {old_row[idx]!r} vs {new_row[idx]!r} for {old_row[1]}"
                )
    print("Skipped", skipped, "rows")


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
async def fix_total_salaries():
    """Reindex Full Text search."""
    records = await db.declaration.fetch(
        "SELECT * FROM declaration WHERE data->'effectif'->'nombreSalariesTotal' IS NULL"
    )
    for record in records:
        total = 0
        for category in record["data"]["effectif"].pop("nombreSalaries", []):
            for tranche in category["tranchesAges"]:
                total += tranche.get("nombreSalariesFemmes") or 0
                total += tranche.get("nombreSalariesHommes") or 0
        if not total:
            print(f"Cannot set total for {record['siren']}/{record['year']}")
            continue
        await db.declaration.execute(
            "UPDATE declaration SET data = jsonb_set(data, '{effectif,nombreSalariesTotal}', $1) WHERE siren=$2 AND year=$3",
            total,
            record["siren"],
            record["year"],
        )


@minicli.cli
def serve(reload=False):
    """Run a web server (for development only)."""
    from roll.extensions import simple_server

    from .views import app

    if reload:
        import hupper

        hupper.start_reloader("egapro.bin.serve")
    simple_server(app, port=2626)


@minicli.wrap
async def wrapper():
    await db.init()
    yield
    await db.terminate()


def main():
    minicli.run()
