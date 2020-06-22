import sys
from pathlib import Path

import asyncpg
import minicli
from openpyxl import load_workbook
import progressist
import ujson as json

from egapro import db, models
from egapro.solen import import_solen  # noqa: expose to minicli
from egapro.exporter import dump  # noqa: expose to minicli
from egapro import dgt


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
            uuid = row["id"]
            data["data"]["id"] = uuid
            data = models.Data(data["data"])
            last_modified = row["last_modified"]
            if data.validated:
                await db.declaration.put(
                    data.siren, data.year, data.email, data, last_modified
                )
            else:
                await db.simulation.put(uuid, data, last_modified)


@minicli.cli
async def dump_dgt(path: Path, max_rows: int = None):
    wb = await dgt.as_xlsx(max_rows)
    print("Writing the XLSX to", path)
    wb.save(path)
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


@minicli.wrap
async def wrapper():
    await db.init()
    yield
    await db.terminate()


def main():
    minicli.run()
