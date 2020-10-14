import io
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
            "entreprise": {"effectif": {"tranche": "50:250"}},
            "indicateurs": {
                "rémunérations": {
                    "catégories": [{"nom": "xxx", "tranches": {":29": 0.7}}]
                }
            },
            "déclaration": {"date": "28/02/2020 10:41"},
        },
    )
    workbook = await dgt.as_xlsx(debug=True)
    sheet = workbook.active
    assert sheet["B1"].value == "URL_declaration"
    assert (
        sheet["B2"].value
        == "'https://index-egapro.travail.gouv.fr/simulateur/12345678-1234-5678-9012-123456789012"
    )


async def test_dgt_dump_should_compute_declaration_url_for_solen_data():
    await db.declaration.put(
        "12345678",
        2020,
        "foo@bar.com",
        {
            "source": "solen-2019",
            "id": "123456781234-123456789012",
            "entreprise": {"effectif": {"tranche": "50:250"}},
            "indicateurs": {"rémunérations": {"catégories": []}},
            "déclaration": {"date": "28/02/2020 10:41"},
        },
    )
    workbook = await dgt.as_xlsx(debug=True)
    sheet = workbook.active
    assert sheet["B1"].value == "URL_declaration"
    assert (
        sheet["B2"].value
        == "'https://solen1.enquetes.social.gouv.fr/cgi-bin/HE/P?P=123456781234-123456789012"
    )


async def test_export_public_data(declaration):
    await declaration(
        company="Mirabar",
        siren="87654321",
        entreprise={"effectif": {"tranche": "1000:"}},
    )
    await declaration(
        company="FooBar",
        siren="87654322",
        year=2018,
        entreprise={"effectif": {"tranche": "1000:", "total": 1000}},
    )
    # Small entreprise, should not be exported.
    await declaration(
        company="MiniBar",
        siren="87654323",
        entreprise={"effectif": {"tranche": "251:999"}},
    )
    out = io.StringIO()
    await exporter.public_data(out)
    out.seek(0)
    assert out.read() == (
        "Raison Sociale;SIREN;Année;Note;Structure;Nom UES;Entreprises UES (SIREN);Région;Département\r\n"
        "Mirabar;87654321;2020;26;Entreprise;;;Auvergne-Rhône-Alpes;Drôme\r\n"
        "FooBar;87654322;2018;26;Entreprise;;;Auvergne-Rhône-Alpes;Drôme\r\n"
    )


async def test_export_ues_public_data(declaration):
    await declaration(
        company="Mirabar",
        siren="87654321",
        entreprise={
            "ues": {
                "raison_sociale": "MiraFoo",
                "entreprises": [
                    {"raison_sociale": "MiraBaz", "siren": "315710251"},
                    {"raison_sociale": "MiraPouet", "siren": "315710251"},
                ],
            },
            "effectif": {"tranche": "1000:"}
        }
    )
    out = io.StringIO()
    await exporter.public_data(out)
    out.seek(0)
    assert out.read() == (
        "Raison Sociale;SIREN;Année;Note;Structure;Nom UES;Entreprises UES (SIREN);Région;Département\r\n"
        "Mirabar;87654321;2020;26;Unité Economique et Sociale (UES);MiraFoo;MiraBaz (315710251),MiraPouet (315710251);Auvergne-Rhône-Alpes;Drôme\r\n"
    )
