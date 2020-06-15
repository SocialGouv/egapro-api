import json
from pathlib import Path

import pytest

from egapro import db, exporter, dgt

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def init_db():
    await db.init()
    yield
    await db.terminate()


async def test_dump():
    await db.declaration.put("12345678", 2020, "foo@bar.com", {"foo": "baré"})
    await db.declaration.put("87654321", 2020, "foo@baz.com", {"foo": "bazé"})
    path = Path("/tmp/test_dump_egapro.json")
    await exporter.dump(path)
    assert json.loads(path.read_text()) == [{"foo": "baré"}, {"foo": "bazé"}]


async def test_dgt_dump_should_compute_declaration_url():
    await db.declaration.put(
        "12345678",
        2020,
        "foo@bar.com",
        {
            "id": "12345678-1234-5678-9012-123456789012",
            "informationsEntreprise": {"nombreEntreprises": 0},
            "indicateurUn": {"nombreCoefficients": 0},
        },
    )
    workbook = await dgt.as_xlsx(debug=True)
    sheet = workbook.active
    assert sheet["B1"].value == "URL_declaration"
    assert sheet["B2"].value == "'https://index-egapro.travail.gouv.fr/simulateur/12345678-1234-5678-9012-123456789012"


async def test_dgt_dump_should_compute_declaration_url_for_solen_data():
    await db.declaration.put(
        "12345678",
        2020,
        "foo@bar.com",
        {
            "source": "solen-2019",
            "id": "123456781234-123456789012",
            "informationsEntreprise": {"nombreEntreprises": 0},
            "indicateurUn": {"nombreCoefficients": 0},
        },
    )
    workbook = await dgt.as_xlsx(debug=True)
    sheet = workbook.active
    assert sheet["B1"].value == "URL_declaration"
    assert sheet["B2"].value == "'https://solen1.enquetes.social.gouv.fr/cgi-bin/HE/P?P=123456781234-123456789012"
