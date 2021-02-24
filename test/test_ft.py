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
            2019,
            "foo@bar.org",
            {
                "entreprise": {
                    "raison_sociale": nom,
                    "effectif": {"tranche": "1000:"},
                    "code_naf": "33.11Z",
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
        "entreprise": {
            "raison_sociale": "Total",
            "département": "77",
            "région": "11",
            "siren": "12345671",
            "ues": {
                "entreprises": [{"raison_sociale": "foobabar", "siren": "987654321"}],
                "nom": "Nom UES",
            },
            "code_naf": "33.11Z",
            "effectif": {"tranche": "1000:"},
        },
        "notes": {"2019": None},
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
        year=2019,
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
    assert len(results) == 1
    names = {r["entreprise"]["raison_sociale"] for r in results}
    assert names == {"Mala Bar"}


async def test_search_from_ues_name(client):
    await db.declaration.put(
        "12345671",
        2019,
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
        "entreprise": {
            "raison_sociale": "Babar",
            "département": "77",
            "région": "11",
            "siren": "12345671",
            "code_naf": None,
            "effectif": {"tranche": "1000:"},
            "ues": {
                "entreprises": [{"raison_sociale": "foobabar", "siren": "987654321"}],
                "nom": "Nom UES",
            },
        },
        "notes": {"2019": None},
    }


async def test_search_from_ues_member_name(client):
    await db.declaration.put(
        "12345671",
        2019,
        "foo@bar.org",
        {
            "entreprise": {
                "raison_sociale": "Babar",
                "département": "77",
                "région": "11",
                "ues": {
                    "nom": "Nom UES",
                    "entreprises": [
                        {"siren": "987654321", "raison_sociale": "foobabar"}
                    ],
                },
                "effectif": {"tranche": "1000:"},
            },
            "déclaration": {"date": datetime.now()},
            "notes": {"2019": None},
        },
    )
    results = await db.search.run("foo")
    assert len(results) == 1
    assert results[0] == {
        "entreprise": {
            "raison_sociale": "Babar",
            "département": "77",
            "région": "11",
            "siren": "12345671",
            "ues": {
                "entreprises": [{"raison_sociale": "foobabar", "siren": "987654321"}],
                "nom": "Nom UES",
            },
            "code_naf": None,
            "effectif": {"tranche": "1000:"},
        },
        "notes": {"2019": None},
    }


async def test_search_with_filters(client):
    await db.declaration.put(
        "12345671",
        2019,
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
        2019,
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
        "entreprise": {
            "département": "78",
            "ues": None,
            "raison_sociale": "Open Bar",
            "région": "11",
            "siren": "987654321",
            "code_naf": None,
            "effectif": {"tranche": "1000:"},
        },
        "notes": {"2019": None},
    }


async def test_filters_without_query(client):
    await db.declaration.put(
        "12345671",
        2019,
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
        2019,
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
        "entreprise": {
            "département": "78",
            "ues": None,
            "raison_sociale": "Open Bar",
            "région": "11",
            "code_naf": None,
            "effectif": {"tranche": "1000:"},
            "siren": "987654321",
        },
        "notes": {"2019": None},
    }


async def test_search_with_offset(client):
    await db.declaration.put(
        "12345671",
        2019,
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
        2019,
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
        "entreprise": {
            "département": "78",
            "ues": None,
            "raison_sociale": "Open Bar",
            "code_naf": None,
            "région": "11",
            "siren": "987654321",
            "effectif": {"tranche": "1000:"},
        },
        "notes": {"2019": None},
    }
    results = await db.search.run(region="11", limit=1, offset=1)
    assert len(results) == 1
    assert results[0] == {
        "entreprise": {
            "département": "77",
            "ues": None,
            "raison_sociale": "Oran Bar",
            "région": "11",
            "siren": "12345671",
            "code_naf": None,
            "effectif": {"tranche": "1000:"},
        },
        "notes": {"2019": None},
    }


async def test_search_with_siren(declaration):
    await declaration("123456712", year=2019, entreprise={"effectif": {"tranche": "1000:"}})
    await declaration("987654321", year=2019, entreprise={"effectif": {"tranche": "1000:"}})
    results = await db.search.run("987654321")
    assert len(results) == 1
    assert results[0]["entreprise"]["siren"] == "987654321"
