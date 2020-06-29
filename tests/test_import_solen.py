from pathlib import Path

import pytest

from egapro import db, solen, models

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def init_db():
    await db.init()
    yield
    await db.terminate()


async def test_basic_solen_import():
    await solen.main(Path(__file__).parent / "data/solen.xlsx", year=2018)
    assert await db.declaration.fetchval("SELECT COUNT(*) FROM declaration") == 1
    declaration = await db.declaration.get("783247548", 2018)
    data = models.Data(declaration["data"])
    assert data.siren == "783247548"
    assert data["source"] == "solen-2018"
    assert data.path("effectif.nombreSalariesTotal") == 76
    assert data.path("declaration.datePublication") == "03/06/2020"
    assert data.validated
    assert data.grade == 80
    assert data.email == "baar@baaz.org"


async def test_solen_import_with_ues():
    await solen.main(Path(__file__).parent / "data/solen_ues.xlsx", year=2018)
    assert await db.declaration.fetchval("SELECT COUNT(*) FROM declaration") == 1
    declaration = await db.declaration.get("775701488", 2018)
    data = models.Data(declaration["data"])
    assert data.siren == "775701488"
    assert data.path("informationsEntreprise.nomUES") == "BazBaz"
    assert data.path("informationsEntreprise.nomEntreprise") == "BazBaz SA"
    assert (
        data.path("informationsEntreprise.structure")
        == "Unité Economique et Sociale (UES)"
    )
    assert data.path("informationsEntreprise.nombreEntreprises") == 11
    assert data.path("informationsEntreprise.entreprisesUES") == [
        {"nom": "BazBaz One", "siren": "423499322"},
        {"nom": "BazBaz Two", "siren": "344898355"},
        {"nom": "BazBaz Three", "siren": "775701488"},
        {"nom": "BazBaz Four", "siren": "500425666"},
        {"nom": "BazBaz Five", "siren": "499203222"},
        {"nom": "BazBaz Six", "siren": "434044000"},
        {"nom": "BazBaz Seven", "siren": "487597555"},
        {"nom": "BazBaz eight", "siren": "493147000"},
        {"nom": "BazBaz Nine", "siren": "434243333"},
        {"nom": "BazBaz Ten", "siren": "513866666"},
    ]
    print(data)
