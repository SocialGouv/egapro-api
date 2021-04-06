import sys
import urllib.request
from importlib import import_module
from io import BytesIO
from pathlib import Path

import minicli
import progressist
import yaml
import ujson as json
from openpyxl import load_workbook

from egapro import (
    config,
    constants,
    db,
    dgt,
    emails,
    exporter,
    models,
    schema,
    tokens,
    loggers,
)
from egapro.emails.success import attachment
from egapro.exporter import dump  # noqa: expose to minicli
from egapro.solen import *  # noqa: expose to minicli
from egapro.utils import json_dumps


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
async def full(path: Path):
    """Create a full JSON export."""
    print("Writing to", path)
    with path.open("w") as f:
        await exporter.full(f)
    print("Done")


@minicli.cli
async def migrate(*migrations):
    ROOT = Path(__file__).parent / "migrations"

    if not migrations or migrations[0] == "list":
        for path in sorted(ROOT.iterdir()):
            if path.stem[0].isdigit():
                print(path.stem)
        sys.exit()

    for name in migrations:
        print(f"Running {name}")
        if (ROOT / f"{name}.py").exists():
            module = import_module(f"egapro.migrations.{name}")
            await module.main(db, loggers.logger)
        elif (ROOT / f"{name}.sql").exists():
            res = await db.table.execute((ROOT / f"{name}.sql").read_text())
            print(res)
        else:
            raise ValueError(f"There is no migration {name}")

        print(f"Done {name}")


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
    await db.search.truncate()
    records = await db.declaration.completed()
    bar = progressist.ProgressBar(prefix="Reindexing", total=len(records), throttle=100)
    for record in bar.iter(records):
        await db.search.index(record.data)


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
async def validate(pdb=False, verbose=False):
    from egapro.schema import validate, cross_validate

    errors = set()
    for row in await db.declaration.completed():
        data = json.loads(json_dumps(row.data.raw))
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
async def explore(*siren_year):
    """Explore déclarations

    Usage: egapro explore [siren, year[, siren, year…]]

    Without any arguments, will return metadata for last 10 déclarations.
    Otherwise, pass siren, year pairs to get déclarations détailled data.
    """
    if not siren_year:
        records = await db.declaration.fetch(
            "SELECT * FROM declaration ORDER BY modified_at DESC LIMIT 10"
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
        for root in [
            "indicateurs.hautes_rémunérations",
            "indicateurs.congés_maternité",
            "indicateurs.promotions",
            "indicateurs.augmentations_et_promotions",
            "indicateurs.augmentations",
            "indicateurs.rémunérations",
            "entreprise",
            "déclaration",
            "déclarant",
        ]:
            print(sep)
            print(f"# {root}")
            sequence = record.data.path(root)
            if not sequence:
                print("—")
                continue
            for key, value in sequence.items():
                print(f"{key:<20} | {value}")
        print(sep)
        for key in ["modified_at", "declared_at", "owner"]:
            print(f"{key:<20} | {record[key]}")


@minicli.cli
async def dump_one(siren, year, destination: Path = None):
    declaration = await db.declaration.get(siren, year)
    blob = yaml.dump(dict(declaration), default_flow_style=False, allow_unicode=True)
    if destination:
        destination.write_text(blob)
        print(f"Saved to {destination}!")
    else:
        print(blob)


@minicli.cli
async def load_one(path: Path):
    record = yaml.safe_load(path.read_text())
    siren = record["siren"]
    year = record["year"]
    owner = record["owner"]
    data = record.get("draft") or record["data"]
    await db.declaration.put(siren, year, owner, data)
    print("Done!")


@minicli.cli
async def set_owner(siren, year, owner):
    await db.declaration.own(siren, year, owner)
    print("Done!")


@minicli.cli
def read_token(token):
    print("—" * 20)
    print(tokens.read(token))
    print("—" * 20)


@minicli.cli
def compute_reply_to():
    URL = (
        "https://travail-emploi.gouv.fr/IMG/xlsx/referents_egalite_professionnelle.xlsx"
    )
    with urllib.request.urlopen(URL) as response:
        wb = load_workbook(BytesIO(response.read()))
    ws = wb.active
    referents = {}
    for line in ws.values:
        if line[1] and line[4] and "@" in line[4]:
            dep = line[1]
            if dep in referents:
                continue
            name = line[3].split("\n")[0].strip() if line[3] else f"Egapro {line[2]}"
            email = line[4]
            referents[dep] = f"{name} <{email}>"
    blob = yaml.dump(referents, default_flow_style=False, allow_unicode=True)
    destination = Path(__file__).parent / "emails/reply_to.yml"
    destination.write_text(blob)

    missing = set(constants.DEPARTEMENTS.keys()) - set(referents.keys())
    print(f"Missing departements: {missing}")


@minicli.cli
async def receipt(siren, year, destination=None):
    record = await db.declaration.get(siren, year)
    data = {"modified_at": record["modified_at"], **record.data}
    pdf, _ = attachment(data)
    print(pdf.output(destination) or f"Saved to {destination}")


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
    loggers.init()
    config.init()
    try:
        await db.init()
    except RuntimeError as err:
        print(err)
    yield
    await db.terminate()


def main():
    minicli.run()
