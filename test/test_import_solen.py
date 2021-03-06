from datetime import datetime, timezone
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
    await solen.main(Path(__file__).parent / "data/solen.xlsx")
    assert await db.declaration.fetchval("SELECT COUNT(*) FROM declaration") == 1
    declaration = await db.declaration.get("783247548", 2018)
    data = models.Data(declaration["data"])
    assert data.siren == "783247548"
    assert data["source"] == "solen"
    assert declaration["modified_at"] == datetime(
        2020, 6, 2, 13, 20, tzinfo=timezone.utc
    )
    assert data.path("entreprise.effectif.total") == 76
    # FIXME date is stored as timestamp, we want an iso format
    # assert data.path("déclaration.date") == "03/06/2020"
    assert data.validated
    assert data.grade == 80
    assert data.email == "baar@baaz.org"


async def test_solen_import_with_ues():
    await solen.main(Path(__file__).parent / "data/solen_ues.xlsx")
    assert await db.declaration.fetchval("SELECT COUNT(*) FROM declaration") == 1
    declaration = await db.declaration.get("775701485", 2018)
    data = models.Data(declaration["data"])
    assert data.siren == "775701485"
    assert data.path("entreprise.ues.nom") == "BazBaz"
    assert data.path("entreprise.raison_sociale") == "BazBaz SA"
    assert data.path("entreprise.ues.entreprises") == [
        {"raison_sociale": "BazBaz SA", "siren": "775701485"},
        {"raison_sociale": "BazBaz One", "siren": "423499326"},
        {"raison_sociale": "BazBaz Two", "siren": "344898358"},
        {"raison_sociale": "BazBaz Four", "siren": "500425665"},
        {"raison_sociale": "BazBaz Five", "siren": "499203222"},
        {"raison_sociale": "BazBaz Six", "siren": "434044004"},
        {"raison_sociale": "BazBaz Seven", "siren": "487597551"},
        {"raison_sociale": "BazBaz eight", "siren": "493147003"},
        {"raison_sociale": "BazBaz Nine", "siren": "434243333"},
        {"raison_sociale": "BazBaz Ten", "siren": "513866665"},
    ]
    print(data)
