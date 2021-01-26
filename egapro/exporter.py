"""Export data from DB."""

import csv
from pathlib import Path

import ujson as json

from egapro import constants, db, sql, utils


async def dump(path: Path):
    """Export des données Egapro.

    :path:          chemin vers le fichier d'export
    """

    records = await db.declaration.completed()
    print("Number of records", len(records))
    with path.open("w") as f:
        json.dump([r["data"] for r in records], f, ensure_ascii=False)


async def public_data(path: Path):
    """Export des données Egapro publiques au format CSV.

    :path:          chemin vers le fichier d'export
    """

    records = await db.declaration.fetch(sql.public_declarations)
    writer = csv.writer(path, delimiter=";")
    writer.writerow(
        [
            "Raison Sociale",
            "SIREN",
            "Année",
            "Note",
            "Structure",
            "Nom UES",
            "Entreprises UES (SIREN)",
            "Région",
            "Département",
        ]
    )
    rows = []
    for record in records:
        data = record.data
        ues = ",".join(
            [
                f"{company['raison_sociale']} ({company['siren']})"
                for company in data.path("entreprise.ues.entreprises") or []
            ]
        )
        rows.append(
            [
                data.company,
                data.siren,
                data.year,
                data.grade,
                data.structure,
                data.ues,
                ues,
                constants.REGIONS[data.region],
                constants.DEPARTEMENTS[data.departement],
            ]
        )
    writer.writerows(rows)


async def digdash(dest):
    # Don't put all data in memory.
    dest.write("[")
    first = True
    for record in await db.declaration.completed():
        if not first:
            dest.write(",")
        first = False
        data = record.data.raw
        dest.write(utils.json_dumps(data))
    dest.write("]")
