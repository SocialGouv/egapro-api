"""Export data from DB."""

import csv
from pathlib import Path

import minicli
import ujson as json

from egapro import db, models


@minicli.cli
async def dump(path: Path):
    """Export des données Egapro.

    :path:          chemin vers le fichier d'export
    """

    records = await db.declaration.all()
    print("Number of records", len(records))
    with path.open("w") as f:
        json.dump([r["data"] for r in records], f, ensure_ascii=False)


@minicli.cli
async def public_data(path: Path):
    """Export des données Egapro publiques au format CSV.

    :path:          chemin vers le fichier d'export
    """

    records = await db.declaration.fetch(
        """
        SELECT data FROM declaration
        WHERE
            data->'informations'->>'trancheEffectifs' = '1000 et plus'
                OR (
                    (data->'informations'->'anneeDeclaration')::int=2018
                    AND data->'informations'->>'trancheEffectifs' = 'Plus de 250'
                    AND (data->'effectif'->'nombreSalariesTotal')::int >= 1000
                    )
        ;"""
    )
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
        data = models.Data(record["data"])
        ues = ",".join(
            [
                f"{company['nom']} ({company['siren']})"
                for company in data.path("informationsEntreprise.entreprisesUES") or []
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
                data.region,
                data.departement,
            ]
        )
    writer.writerows(rows)
