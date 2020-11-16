import io
import json
from datetime import datetime
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
    await db.declaration.put(
        "12345678",
        2020,
        "foo@bar.com",
        {"déclaration": {"date": datetime(2020, 10, 24, 10, 11, 12)}},
    )
    await db.declaration.put(
        "87654321",
        2020,
        "foo@baz.com",
        {"déclaration": {"date": datetime(2020, 10, 24, 10, 11, 13)}},
    )
    await db.declaration.put(
        "87654331",
        2020,
        "foo@baz.com",
        {"déclaration": {"date": None}},
    )
    path = Path("/tmp/test_dump_egapro.json")
    await exporter.dump(path)
    assert json.loads(path.read_text()) == [
        {"déclaration": {"date": 1603534272}},
        {"déclaration": {"date": 1603534273}},
    ]


async def test_dgt_dump(declaration):
    await declaration(
        siren="12345678",
        year=2020,
        uid="12345678-1234-5678-9012-123456789012",
        entreprise={"code_naf": "47.25Z", "région": "11", "département": "77"},
    )
    workbook = await dgt.as_xlsx(debug=True)
    sheet = workbook.active
    # Calculable
    assert sheet["AA1"].value == "Indic1_calculable"
    assert sheet["AA2"].value is True

    # Code NAF
    assert sheet["U1"].value == "Code_NAF"
    assert sheet["U2"].value == (
        "47.25Z - Commerce de détail de boissons en magasin spécialisé"
    )

    # Région
    assert sheet["H1"].value == "Region"
    assert sheet["H2"].value == "Île-de-France"
    assert sheet["I1"].value == "Departement"
    assert sheet["I2"].value == "Seine-et-Marne"

    # Dates
    assert sheet["M1"].value == "Annee_indicateurs"
    assert sheet["M2"].value == 2020
    assert sheet["N1"].value == "Date_debut_periode"
    assert sheet["N2"].value == datetime(2019, 1, 1)
    assert sheet["O1"].value == "Date_fin_periode"
    assert sheet["O2"].value == datetime(2019, 12, 31)

    # URL
    assert sheet["B1"].value == "URL_declaration"
    assert (
        sheet["B2"].value
        == "'https://index-egapro.travail.gouv.fr/simulateur/12345678-1234-5678-9012-123456789012"
    )


async def test_dgt_dump_should_compute_declaration_url_for_solen_data(declaration):
    await declaration(
        siren="12345678",
        year=2020,
        uid="123456781234-123456789012",
        source="solen-2019",
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
            "effectif": {"tranche": "1000:"},
        },
    )
    out = io.StringIO()
    await exporter.public_data(out)
    out.seek(0)
    assert out.read() == (
        "Raison Sociale;SIREN;Année;Note;Structure;Nom UES;Entreprises UES (SIREN);Région;Département\r\n"
        "Mirabar;87654321;2020;26;Unité Economique et Sociale (UES);MiraFoo;MiraBaz (315710251),MiraPouet (315710251);Auvergne-Rhône-Alpes;Drôme\r\n"
    )
