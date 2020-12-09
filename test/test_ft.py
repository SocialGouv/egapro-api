from datetime import datetime

import pytest

from egapro import db

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def init_db():
    await db.init()
    yield
    await db.terminate()


async def test_search(client):
    rows = [
        ("12345671", "Total"),
        ("12345672", "Somme"),
        ("12345673", "Biocoop"),
        ("12345674", "Bio c bon"),
        ("12345675", "Bio c pas bon"),
        ("12345676", "Pyrénées"),
        ("12345677", "Decathlon"),
    ]
    for siren, nom in rows:
        await db.declaration.put(
            siren,
            2020,
            "foo@bar.org",
            {
                "entreprise": {
                    "raison_sociale": nom,
                    "effectif": {"tranche": "1000:"},
                    "département": "77",
                    "région": "11",
                    "ues": {
                        "raison_sociale": "Nom UES",
                        "entreprises": [
                            {"siren": "987654321", "raison_sociale": "foobabar"}
                        ],
                    },
                },
                "déclaration": {"statut": "final", "date": datetime.now()},
            },
        )
    results = await db.declaration.search("total")
    assert len(results) == 1
    assert results[0] == {
        "declaration": {"noteIndex": None},
        "id": None,
        "informationsEntreprise": {
            "nomEntreprise": "Total",
            "nomUES": "Nom UES",
            "departement": "77",
            "region": "11",
            "siren": "12345671",
            "structure": "Unité Economique et Sociale (UES)",
            "entreprisesUES": [{"nom": "foobabar", "siren": "987654321"}],
        },
        "informations": {"anneeDeclaration": 2020},
    }
    results = await db.declaration.search("pyrenées")
    assert len(results) == 1
    results = await db.declaration.search("décathlon")
    assert len(results) == 1
    results = await db.declaration.search("bio")
    assert len(results) == 3
    results = await db.declaration.search("bio", limit=1)
    assert len(results) == 1
