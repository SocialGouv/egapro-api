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


def clean_digdash(d):
    if isinstance(d, list):
        [clean_digdash(v) for v in d]
    elif isinstance(d, dict):
        for key in list(d.keys()):
            value = d[key]
            if ":" in key:
                d[key.replace(":", "-")] = d.pop(key)
            clean_digdash(value)


async def digdash(dest):
    # Don't put all data in memory.
    dest.write("[")
    first = True
    for record in await db.declaration.completed():
        if not first:
            dest.write(",")
        first = False
        data = record.data.raw
        clean_digdash(data)
        dumped = utils.json_dumps(data)
        dest.write(dumped)
    dest.write("]")
