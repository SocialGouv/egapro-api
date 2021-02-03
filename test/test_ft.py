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
                        "nom": "Nom UES",
                        "entreprises": [
                            {"siren": "987654321", "raison_sociale": "foobabar"}
                        ],
                    },
                },
                "déclaration": {"date": datetime.now()},
            },
        )
    results = await db.search.run("total")
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
    results = await db.search.run("pyrenées")
    assert len(results) == 1
    results = await db.search.run("décathlon")
    assert len(results) == 1
    results = await db.search.run("bio")
    assert len(results) == 3
    results = await db.search.run("bio", limit=1)
    assert len(results) == 1


async def test_small_companies_are_not_searchable(declaration):
    await declaration(
        company="Mala Bar",
        siren="87654321",
        entreprise={"effectif": {"tranche": "1000:"}},
    )
    # Small entreprise, should not be exported.
    await declaration(
        company="Mini Bar",
        siren="87654323",
        entreprise={"effectif": {"tranche": "50:250"}},
        year=2019,
    )
    # Starting from 2020, 251:999 companies index are public.
    await declaration(
        company="Karam Bar",
        siren="87654324",
        entreprise={"effectif": {"tranche": "251:999"}},
        year=2020,
    )
    results = await db.search.run("bar")
    assert len(results) == 2
    names = {r["informationsEntreprise"]["nomEntreprise"] for r in results}
    assert names == {"Mala Bar", "Karam Bar"}


async def test_search_from_ues_name(client):
    await db.declaration.put(
        "12345671",
        2020,
        "foo@bar.org",
        {
            "entreprise": {
                "raison_sociale": "Babar",
                "effectif": {"tranche": "1000:"},
                "département": "77",
                "région": "11",
                "ues": {
                    "nom": "Nom UES",
                    "entreprises": [
                        {"siren": "987654321", "raison_sociale": "foobabar"}
                    ],
                },
            },
            "déclaration": {"date": datetime.now()},
        },
    )
    results = await db.search.run("ues")
    assert len(results) == 1
    assert results[0] == {
        "declaration": {"noteIndex": None},
        "id": None,
        "informationsEntreprise": {
            "nomEntreprise": "Babar",
            "nomUES": "Nom UES",
            "departement": "77",
            "region": "11",
            "siren": "12345671",
            "structure": "Unité Economique et Sociale (UES)",
            "entreprisesUES": [{"nom": "foobabar", "siren": "987654321"}],
        },
        "informations": {"anneeDeclaration": 2020},
    }


async def test_search_from_ues_member_name(client):
    await db.declaration.put(
        "12345671",
        2020,
        "foo@bar.org",
        {
            "entreprise": {
                "raison_sociale": "Babar",
                "effectif": {"tranche": "1000:"},
                "département": "77",
                "région": "11",
                "ues": {
                    "nom": "Nom UES",
                    "entreprises": [
                        {"siren": "987654321", "raison_sociale": "foobabar"}
                    ],
                },
            },
            "déclaration": {"date": datetime.now()},
        },
    )
    results = await db.search.run("foo")
    assert len(results) == 1
    assert results[0] == {
        "declaration": {"noteIndex": None},
        "id": None,
        "informationsEntreprise": {
            "nomEntreprise": "Babar",
            "nomUES": "Nom UES",
            "departement": "77",
            "region": "11",
            "siren": "12345671",
            "structure": "Unité Economique et Sociale (UES)",
            "entreprisesUES": [{"nom": "foobabar", "siren": "987654321"}],
        },
        "informations": {"anneeDeclaration": 2020},
    }


async def test_search_with_filters(client):
    await db.declaration.put(
        "12345671",
        2020,
        "foo@bar.org",
        {
            "entreprise": {
                "raison_sociale": "Oran Bar",
                "effectif": {"tranche": "1000:"},
                "département": "77",
                "région": "11",
            },
            "déclaration": {"date": datetime.now()},
        },
    )
    await db.declaration.put(
        "987654321",
        2020,
        "foo@bar.org",
        {
            "entreprise": {
                "raison_sociale": "Open Bar",
                "effectif": {"tranche": "1000:"},
                "département": "78",
                "région": "11",
            },
            "déclaration": {"date": datetime.now()},
        },
    )
    results = await db.search.run("bar", departement="78", region="11")
    assert len(results) == 1
    assert results[0] == {
        "declaration": {"noteIndex": None},
        "id": None,
        "informations": {"anneeDeclaration": 2020},
        "informationsEntreprise": {
            "departement": "78",
            "entreprisesUES": [],
            "nomEntreprise": "Open Bar",
            "nomUES": None,
            "region": "11",
            "siren": "987654321",
            "structure": "Entreprise",
        },
    }


async def test_filters_without_query(client):
    await db.declaration.put(
        "12345671",
        2020,
        "foo@bar.org",
        {
            "entreprise": {
                "raison_sociale": "Oran Bar",
                "effectif": {"tranche": "1000:"},
                "département": "77",
                "région": "11",
            },
            "déclaration": {"date": datetime.now()},
        },
    )
    await db.declaration.put(
        "987654321",
        2020,
        "foo@bar.org",
        {
            "entreprise": {
                "raison_sociale": "Open Bar",
                "effectif": {"tranche": "1000:"},
                "département": "78",
                "région": "11",
            },
            "déclaration": {"date": datetime.now()},
        },
    )
    results = await db.search.run(departement="78", region="11")
    assert len(results) == 1
    assert results[0] == {
        "declaration": {"noteIndex": None},
        "id": None,
        "informations": {"anneeDeclaration": 2020},
        "informationsEntreprise": {
            "departement": "78",
            "entreprisesUES": [],
            "nomEntreprise": "Open Bar",
            "nomUES": None,
            "region": "11",
            "siren": "987654321",
            "structure": "Entreprise",
        },
    }


async def test_search_with_offset(client):
    await db.declaration.put(
        "12345671",
        2020,
        "foo@bar.org",
        {
            "entreprise": {
                "raison_sociale": "Oran Bar",
                "effectif": {"tranche": "1000:"},
                "département": "77",
                "région": "11",
            },
            "déclaration": {"date": datetime.now()},
        },
    )
    await db.declaration.put(
        "987654321",
        2020,
        "foo@bar.org",
        {
            "entreprise": {
                "raison_sociale": "Open Bar",
                "effectif": {"tranche": "1000:"},
                "département": "78",
                "région": "11",
            },
            "déclaration": {"date": datetime.now()},
        },
    )
    results = await db.search.run(region="11")
    assert len(results) == 2
    results = await db.search.run(region="11", limit=1)
    assert len(results) == 1
    assert results[0] == {
        "declaration": {"noteIndex": None},
        "id": None,
        "informations": {"anneeDeclaration": 2020},
        "informationsEntreprise": {
            "departement": "78",
            "entreprisesUES": [],
            "nomEntreprise": "Open Bar",
            "nomUES": None,
            "region": "11",
            "siren": "987654321",
            "structure": "Entreprise",
        },
    }
    results = await db.search.run(region="11", limit=1, offset=1)
    assert len(results) == 1
    assert results[0] == {
        "declaration": {"noteIndex": None},
        "id": None,
        "informations": {"anneeDeclaration": 2020},
        "informationsEntreprise": {
            "departement": "77",
            "entreprisesUES": [],
            "nomEntreprise": "Oran Bar",
            "nomUES": None,
            "region": "11",
            "siren": "12345671",
            "structure": "Entreprise",
        },
    }
