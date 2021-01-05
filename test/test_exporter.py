import io
import json
from datetime import date, datetime
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
        {
            "déclaration": {
                "date": datetime(2020, 10, 24, 10, 11, 12),
            }
        },
    )
    await db.declaration.put(
        "87654321",
        2020,
        "foo@baz.com",
        {
            "déclaration": {
                "date": datetime(2020, 10, 24, 10, 11, 13),
            },
        },
    )
    await db.declaration.put(
        "87654331",
        2020,
        "foo@baz.com",
        {
            "déclaration": {
                "date": datetime(2020, 10, 24, 10, 11, 13),
                "brouillon": True,
            }
        },
    )
    path = Path("/tmp/test_dump_egapro.json")
    await exporter.dump(path)
    data = json.loads(path.read_text())
    for declaration in data:
        assert declaration["déclaration"]["date"]
        del declaration["déclaration"]["date"]
    assert data == [
        {
            "déclaration": {
                "année_indicateurs": 2020,
            },
            "entreprise": {"siren": "87654321"},
        },
        {
            "déclaration": {
                "année_indicateurs": 2020,
            },
            "entreprise": {"siren": "12345678"},
        },
    ]


async def test_dgt_dump(declaration):
    await declaration(
        siren="12345678",
        year=2020,
        compute_notes=True,
        uid="12345678-1234-5678-9012-123456789012",
        entreprise={"code_naf": "47.25Z", "région": "11", "département": "77"},
        indicateurs={
            "augmentations": {
                "note": 20,
                "résultat": 1.08,
                "catégories": [0.1, 10.5, 10.3, 11.0],
                "population_favorable": "femmes",
            },
            "promotions": {
                "note": 15,
                "résultat": 0.5,
                "catégories": [None, 0.1, -0.3, -0.4],
                "population_favorable": "femmes",
            },
            "rémunérations": {
                "catégories": [
                    {
                        "nom": "tranche 0",
                        "tranches": {
                            "30:39": -0.03,
                            "40:49": 1.5,
                            "50:": 3.7,
                            ":29": 2.8,
                        },
                    },
                    {
                        "nom": "tranche 1",
                        "tranches": {
                            "30:39": 0.1,
                            "40:49": -11.3,
                            "50:": 11.1,
                            ":29": -10.8,
                        },
                    },
                    {
                        "nom": "tranche 2",
                        "tranches": {
                            "30:39": 2.3,
                            "40:49": 2.8,
                            "50:": 0.2,
                            ":29": 5.0,
                        },
                    },
                    {
                        "nom": "tranche 3",
                        "tranches": {
                            "30:39": 5.2,
                            "40:49": 7.1,
                            "50:": 12.2,
                            ":29": 1.1,
                        },
                    },
                ],
                "mode": "csp",
                "note": 40,
                "population_favorable": "femmes",
                "résultat": 0.0,
            },
            "congés_maternité": {"note": 0, "résultat": 57.0},
            "hautes_rémunérations": {
                "note": 5,
                "résultat": 3,
                "population_favorable": "hommes",
            },
        },
    )
    workbook = await dgt.as_xlsx(debug=True)
    sheet = workbook.active
    # Calculable
    assert sheet["AB1"].value == "Indic1_calculable"
    assert sheet["AB2"].value is True

    # Code NAF
    assert sheet["V1"].value == "Code_NAF"
    assert sheet["V2"].value == (
        "47.25Z - Commerce de détail de boissons en magasin spécialisé"
    )

    # Région
    assert sheet["I1"].value == "Region"
    assert sheet["I2"].value == "Île-de-France"
    assert sheet["J1"].value == "Departement"
    assert sheet["J2"].value == "Seine-et-Marne"

    # Dates
    assert sheet["N1"].value == "Annee_indicateurs"
    assert sheet["N2"].value == 2020
    assert sheet["O1"].value == "Date_debut_periode"
    assert sheet["O2"].value == date(2019, 1, 1)
    assert sheet["P1"].value == "Date_fin_periode"
    assert sheet["P2"].value == date(2019, 12, 31)

    # URL
    assert sheet["B1"].value == "URL_declaration"
    assert (
        sheet["B2"].value
        == "'https://index-egapro.travail.gouv.fr/declaration/?siren=12345678&year=2020"
    )

    # Indicateurs rémunérations
    assert sheet["AG1"].value == "Indic1_Ouv"
    assert sheet["AH1"].value == "Indic1_Emp"
    assert sheet["AI1"].value == "Indic1_TAM"
    assert sheet["AJ1"].value == "Indic1_IC"
    assert sheet["AG2"].value == "2.8;-0.03;1.5;3.7"
    assert sheet["AH2"].value == "-10.8;0.1;-11.3;11.1"
    assert sheet["AI2"].value == "5;2.3;2.8;0.2"
    assert sheet["AJ2"].value == "1.1;5.2;7.1;12.2"

    # Global notes
    assert sheet["BQ1"].value == "Indicateur_1"
    assert sheet["BQ2"].value == 40
    assert sheet["BR1"].value == "Indicateur_2"
    assert sheet["BR2"].value == 20
    assert sheet["BS1"].value == "Indicateur_3"
    assert sheet["BS2"].value == 15
    assert sheet["BT1"].value == "Indicateur_2et3"
    assert sheet["BT2"].value == "nc"
    assert sheet["BU1"].value == "Indicateur_2et3_PourCent"
    assert sheet["BU2"].value == "nc"
    assert sheet["BV1"].value == "Indicateur_2et3_ParSal"
    assert sheet["BV2"].value == "nc"
    assert sheet["BW1"].value == "Indicateur_4"
    assert sheet["BW2"].value == 0
    assert sheet["BX1"].value == "Indicateur_5"
    assert sheet["BX2"].value == 5
    assert sheet["BY1"].value == "Nombre_total_points obtenus"
    assert sheet["BY2"].value == 80
    assert sheet["BZ1"].value == "Nombre_total_points_pouvant_etre_obtenus"
    assert sheet["BZ2"].value == 100
    assert sheet["CA1"].value == "Resultat_final_sur_100_points"
    assert sheet["CA2"].value == 80
    assert sheet["CB1"].value == "Mesures_correction"
    assert sheet["CB2"].value is None


async def test_dgt_dump_with_coef_mode(declaration):
    await declaration(
        siren="12345678",
        year=2020,
        uid="12345678-1234-5678-9012-123456789012",
        entreprise={"code_naf": "47.25Z", "région": "11", "département": "77"},
        indicateurs={
            "rémunérations": {
                "mode": "niveau_branche",
                "note": 25,
                "résultat": 10.6,
                "catégories": [
                    {
                        "nom": "tranche 0",
                        "tranches": {"50:": 0, ":29": 0, "30:39": 0, "40:49": 0},
                    },
                    {
                        "nom": "tranche 1",
                        "tranches": {"50:": 0, ":29": 0, "30:39": 0, "40:49": 0},
                    },
                    {
                        "nom": "tranche 2",
                        "tranches": {"50:": 56.5, ":29": 0.0, "30:39": 1.4, "40:49": 0},
                    },
                    {
                        "nom": "tranche 3",
                        "tranches": {"50:": -43.9, ":29": 0, "30:39": 0, "40:49": 0},
                    },
                    {
                        "nom": "tranche 4",
                        "tranches": {
                            "50:": -17.0,
                            ":29": -20.1,
                            "30:39": 0,
                            "40:49": 22.9,
                        },
                    },
                    {
                        "nom": "tranche 5",
                        "tranches": {
                            "50:": 6.8,
                            ":29": 7.6,
                            "40:49": 36.2,
                        },
                    },
                    {
                        "nom": "tranche 6",
                        "tranches": {
                            "50:": -3.8,
                            ":29": -13.0,
                            "30:39": 21.4,
                            "40:49": 0,
                        },
                    },
                    {
                        "nom": "tranche 7",
                        "tranches": {
                            "50:": 4.5,
                            ":29": 0,
                            "30:39": 39.6,
                            "40:49": 17.9,
                        },
                    },
                    {
                        "nom": "tranche 8",
                        "tranches": {
                            "50:": 5.0,
                            ":29": 4.2,
                            "30:39": 8.6,
                            "40:49": 59.5,
                        },
                    },
                    {
                        "nom": "tranche 9",
                        "tranches": {
                            "50:": 23.2,
                            ":29": 0,
                            "30:39": 20.0,
                            "40:49": 6.8,
                        },
                    },
                    {
                        "nom": "tranche 10",
                        "tranches": {
                            "50:": 12.0,
                            ":29": -4.8,
                            "30:39": 6.6,
                            "40:49": 16.4,
                        },
                    },
                    {
                        "nom": "tranche 11",
                        "tranches": {
                            "50:": 16.3,
                            ":29": 0,
                            "30:39": 36.6,
                            "40:49": 2.6,
                        },
                    },
                    {
                        "nom": "tranche 12",
                        "tranches": {"50:": 20.9, ":29": 0, "30:39": 0, "40:49": 7.5},
                    },
                    {
                        "nom": "tranche 13",
                        "tranches": {"50:": -22.3, ":29": 0, "30:39": 0, "40:49": 20.1},
                    },
                ],
                "population_favorable": "hommes",
            }
        },
    )
    workbook = await dgt.as_xlsx(debug=True)
    sheet = workbook.active

    # Calculable
    assert sheet["AB1"].value == "Indic1_calculable"
    assert sheet["AB2"].value is True
    assert sheet["AD1"].value == "Indic1_modalite_calcul"
    assert sheet["AD2"].value == "niveau_branche"

    # Indicateurs rémunérations for CSP should be empty
    assert sheet["AG1"].value == "Indic1_Ouv"
    assert sheet["AG2"].value is None
    assert sheet["AH1"].value == "Indic1_Emp"
    assert sheet["AH2"].value is None
    assert sheet["AI1"].value == "Indic1_TAM"
    assert sheet["AI2"].value is None
    assert sheet["AJ1"].value == "Indic1_IC"
    assert sheet["AJ2"].value is None
    assert sheet["AK1"].value == "Indic1_Niv0"
    assert sheet["AK2"].value == "0;0;0;0"
    assert sheet["AL1"].value == "Indic1_Niv1"
    assert sheet["AL2"].value == "0;0;0;0"
    assert sheet["AM1"].value == "Indic1_Niv2"
    assert sheet["AM2"].value == "0;1.4;0;56.5"
    assert sheet["AN1"].value == "Indic1_Niv3"
    assert sheet["AN2"].value == "0;0;0;-43.9"
    assert sheet["AO1"].value == "Indic1_Niv4"
    assert sheet["AO2"].value == "-20.1;0;22.9;-17"
    assert sheet["AP1"].value == "Indic1_Niv5"
    assert sheet["AP2"].value == "7.6;nc;36.2;6.8"
    assert sheet["AQ1"].value == "Indic1_Niv6"
    assert sheet["AQ2"].value == "-13;21.4;0;-3.8"
    assert sheet["AR1"].value == "Indic1_Niv7"
    assert sheet["AR2"].value == "0;39.6;17.9;4.5"
    assert sheet["AS1"].value == "Indic1_Niv8"
    assert sheet["AS2"].value == "4.2;8.6;59.5;5"
    assert sheet["AT1"].value == "Indic1_Niv9"
    assert sheet["AT2"].value == "0;20;6.8;23.2"
    assert sheet["AU1"].value == "Indic1_Niv10"
    assert sheet["AU2"].value == "-4.8;6.6;16.4;12"
    assert sheet["AV1"].value == "Indic1_Niv11"
    assert sheet["AV2"].value == "0;36.6;2.6;16.3"
    assert sheet["AW1"].value == "Indic1_Niv12"
    assert sheet["AW2"].value == "0;0;7.5;20.9"


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
        == "'https://index-egapro.travail.gouv.fr/declaration/?siren=12345678&year=2020"
    )


async def test_dgt_dump_should_list_UES_in_dedicated_sheet(declaration):
    await declaration(
        company="Mirabar",
        siren="87654321",
        entreprise={
            "ues": {
                "nom": "MiraFoo",
                "entreprises": [
                    {"raison_sociale": "MiraBaz", "siren": "315710251"},
                    {"raison_sociale": "MiraPouet", "siren": "315710251"},
                ],
            },
            "effectif": {"tranche": "1000:"},
        },
    )
    workbook = await dgt.as_xlsx(debug=True)
    sheet = workbook["BDD UES détail entreprises"]
    assert list(sheet.values) == [
        (
            "Annee_indicateurs",
            "Region",
            "Departement",
            "Adresse",
            "CP",
            "Commune",
            "Tranche_effectif",
            "Nom_UES",
            "Siren_entreprise_declarante",
            "Nom_entreprise_declarante",
            "Nom_entreprise",
            "Siren",
        ),
        (
            2020,
            "Auvergne-Rhône-Alpes",
            "Drôme",
            None,
            None,
            None,
            "1000 et plus",
            "MiraFoo",
            "87654321",
            "Mirabar",
            "MiraBaz",
            "315710251",
        ),
        (
            2020,
            "Auvergne-Rhône-Alpes",
            "Drôme",
            None,
            None,
            None,
            "1000 et plus",
            "MiraFoo",
            "87654321",
            "Mirabar",
            "MiraPouet",
            "315710251",
        ),
    ]


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
