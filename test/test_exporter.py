import io
import json
from datetime import date, datetime, timezone
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
    assert sheet["Q1"].value == "Structure"
    assert sheet["Q2"].value == "Entreprise"

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
    assert sheet["BT2"].value is None
    assert sheet["BU1"].value == "Indicateur_2et3_PourCent"
    assert sheet["BU2"].value is None
    assert sheet["BV1"].value == "Indicateur_2et3_ParSal"
    assert sheet["BV2"].value is None
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


async def test_dgt_dump_with_effectif_50_250(declaration):
    await declaration(
        siren="12345678",
        year=2020,
        uid="12345678-1234-5678-9012-123456789012",
        entreprise={
            "code_naf": "47.25Z",
            "région": "11",
            "département": "77",
            "effectif": {"tranche": "50:250", "total": 173},
        },
        indicateurs={
            "promotions": {},
            "augmentations": {},
            "rémunérations": {
                "mode": "niveau_autre",
                "note": 36,
                "résultat": 3.0781,
                "catégories": [
                    {"nom": "tranche 0", "tranches": {"50:": -3.7963161277}},
                    {"nom": "tranche 1", "tranches": {"50:": 17.649030204}},
                    {"nom": "tranche 2", "tranches": {}},
                    {"nom": "tranche 3", "tranches": {}},
                    {"nom": "tranche 4", "tranches": {}},
                ],
                "population_favorable": "hommes",
                "date_consultation_cse": "2020-01-27",
            },
            "congés_maternité": {"non_calculable": "absrcm"},
            "hautes_rémunérations": {"note": 10, "résultat": 5},
            "augmentations_et_promotions": {
                "note": 35,
                "résultat": 3.7625,
                "note_en_pourcentage": 25,
                "population_favorable": "hommes",
                "note_nombre_salariés": 35,
                "résultat_nombre_salariés": 1.4,
            },
        },
        déclaration={
            "date": "2020-02-07T13:27:00+00:00",
            "index": 95,
            "points": 81,
            "publication": {
                "date": "2020-02-07",
                "modalités": "Affichage dans les locaux",
            },
            "année_indicateurs": 2019,
            "points_calculables": 85,
            "fin_période_référence": "2019-12-31",
        },
    )
    workbook = await dgt.as_xlsx(debug=True)
    sheet = workbook.active

    # Calculable
    assert sheet["AB1"].value == "Indic1_calculable"
    assert sheet["AB2"].value is True
    assert sheet["AD1"].value == "Indic1_modalite_calcul"
    assert sheet["AD2"].value == "niveau_autre"

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
    assert sheet["AK2"].value == "nc;nc;nc;-3.8"
    assert sheet["AL1"].value == "Indic1_Niv1"
    assert sheet["AL2"].value == "nc;nc;nc;17.65"
    assert sheet["AM1"].value == "Indic1_Niv2"
    assert sheet["AM2"].value == "nc;nc;nc;nc"
    assert sheet["AN1"].value == "Indic1_Niv3"
    assert sheet["AN2"].value == "nc;nc;nc;nc"
    assert sheet["AO1"].value == "Indic1_Niv4"
    assert sheet["AO2"].value == "nc;nc;nc;nc"
    assert sheet["AP1"].value == "Indic1_resultat"
    assert sheet["AP2"].value == 3.0781
    assert sheet["AQ1"].value == "Indic1_population_favorable"
    assert sheet["AQ2"].value == "hommes"
    assert sheet["AR1"].value == "Indic2_calculable"
    assert sheet["AR2"].value is None
    assert sheet["AS1"].value == "Indic2_motif_non_calculable"
    assert sheet["AS2"].value is None
    assert sheet["AX1"].value == "Indic2_resultat"
    assert sheet["AX2"].value is None
    assert sheet["AY1"].value == "Indic2_population_favorable"
    assert sheet["AY2"].value is None
    assert sheet["AZ1"].value == "Indic3_calculable"
    assert sheet["AZ2"].value is None
    assert sheet["BA1"].value == "Indic3_motif_non_calculable"
    assert sheet["BA2"].value is None
    assert sheet["BF1"].value == "Indic3_resultat"
    assert sheet["BF2"].value is None
    assert sheet["BG1"].value == "Indic3_population_favorable"
    assert sheet["BG2"].value is None
    assert sheet["BH1"].value == "Indic2et3_calculable"
    assert sheet["BH2"].value is True
    assert sheet["BI1"].value == "Indic2et3_motif_non_calculable"
    assert sheet["BI2"].value is None
    assert sheet["BJ1"].value == "Indic2et3_resultat_pourcent"
    assert sheet["BJ2"].value == 3.7625
    assert sheet["BK1"].value == "Indic2et3_resultat_nb_sal"
    assert sheet["BK2"].value == 1.4
    assert sheet["BL1"].value == "Indic2et3_population_favorable"
    assert sheet["BL2"].value == "hommes"
    assert sheet["BM1"].value == "Indic4_calculable"
    assert sheet["BM2"].value is False
    assert sheet["BN1"].value == "Indic4_motif_non_calculable"
    assert sheet["BN2"].value == "absrcm"
    assert sheet["BO1"].value == "Indic4_resultat"
    assert sheet["BO2"].value is None
    assert sheet["BP1"].value == "Indic5_resultat"
    assert sheet["BP2"].value == 5
    assert sheet["BQ1"].value == "Indic5_sexe_sur_represente"
    assert sheet["BQ2"].value is None
    assert sheet["BR1"].value == "Indicateur_1"
    assert sheet["BR2"].value == 36
    assert sheet["BS1"].value == "Indicateur_2"
    assert sheet["BS2"].value is None
    assert sheet["BT1"].value == "Indicateur_3"
    assert sheet["BT2"].value is None
    assert sheet["BU1"].value == "Indicateur_2et3"
    assert sheet["BU2"].value == 35
    assert sheet["BV1"].value == "Indicateur_2et3_PourCent"
    assert sheet["BV2"].value == 25
    assert sheet["BW1"].value == "Indicateur_2et3_ParSal"
    assert sheet["BW2"].value == 35
    assert sheet["BX1"].value == "Indicateur_4"
    assert sheet["BX2"].value == "nc"
    assert sheet["BY1"].value == "Indicateur_5"
    assert sheet["BY2"].value == 10
    assert sheet["BZ1"].value == "Nombre_total_points obtenus"
    assert sheet["BZ2"].value == 81
    assert sheet["CA1"].value == "Nombre_total_points_pouvant_etre_obtenus"
    assert sheet["CA2"].value == 85
    assert sheet["CB1"].value == "Resultat_final_sur_100_points"
    assert sheet["CB2"].value == 95
    assert sheet["CC1"].value == "Mesures_correction"
    assert sheet["CC2"].value is None


async def test_dgt_dump_with_0_index(declaration):
    await declaration(
        siren="12345678",
        year=2020,
        uid="12345678-1234-5678-9012-123456789012",
        entreprise={
            "code_naf": "47.25Z",
            "région": "11",
            "département": "77",
            "effectif": {"tranche": "50:250", "total": 173},
        },
        indicateurs={
            "rémunérations": {
                "mode": "csp",
                "note": 0,
                "résultat": 21,
                "catégories": [
                    {
                        "nom": "ouv",
                        "tranches": {
                            "50:": 5.5,
                            ":29": 31.5,
                            "30:39": 38,
                            "40:49": 48.6,
                        },
                    },
                    {
                        "nom": "emp",
                        "tranches": {
                            "50:": 29.3,
                            ":29": -39.2,
                            "30:39": 47.1,
                            "40:49": 55.9,
                        },
                    },
                    {
                        "nom": "tam",
                        "tranches": {
                            "50:": 40.5,
                            ":29": 0,
                            "30:39": 9.6,
                            "40:49": -124.8,
                        },
                    },
                    {
                        "nom": "ic",
                        "tranches": {"50:": 74, ":29": 0, "30:39": 0, "40:49": 39.4},
                    },
                ],
                "population_favorable": "hommes",
            },
            "congés_maternité": {"non_calculable": "absrcm"},
            "hautes_rémunérations": {
                "note": 0,
                "résultat": 1,
                "population_favorable": "hommes",
            },
            "augmentations_et_promotions": {
                "note": 0,
                "résultat": 22,
                "note_en_pourcentage": 0,
                "population_favorable": "hommes",
                "note_nombre_salariés": 0,
                "résultat_nombre_salariés": 15.8,
            },
        },
        déclaration={
            "date": "2021-02-23T10:15:07.732273+00:00",
            "index": 0,
            "points": 0,
            "brouillon": False,
            "publication": {
                "date": "2021-03-08",
                "modalités": "Information aux membres du CSE le 8 mars 2021 et courrier d'information aux salariés joint avec le bulletin de paie de mars 2021. ",
            },
            "année_indicateurs": 2020,
            "points_calculables": 85,
            "mesures_correctives": "me",
            "fin_période_référence": "2020-12-31",
        },
    )
    workbook = await dgt.as_xlsx(debug=True)
    sheet = workbook.active

    # Calculable
    assert sheet["AB1"].value == "Indic1_calculable"
    assert sheet["AB2"].value is True
    assert sheet["AD1"].value == "Indic1_modalite_calcul"
    assert sheet["AD2"].value == "csp"

    # Indicateurs rémunérations for CSP should be empty
    assert sheet["AG1"].value == "Indic1_Ouv"
    assert sheet["AG2"].value == "31.5;38;48.6;5.5"
    assert sheet["AH1"].value == "Indic1_Emp"
    assert sheet["AH2"].value == "-39.2;47.1;55.9;29.3"
    assert sheet["AI1"].value == "Indic1_TAM"
    assert sheet["AI2"].value == "0;9.6;-124.8;40.5"
    assert sheet["AJ1"].value == "Indic1_IC"
    assert sheet["AJ2"].value == "0;0;39.4;74"
    assert sheet["AO1"].value == "Indic1_resultat"
    assert sheet["AO2"].value == 21
    assert sheet["AP1"].value == "Indic1_population_favorable"
    assert sheet["AP2"].value == "hommes"
    assert sheet["BG1"].value == "Indic2et3_calculable"
    assert sheet["BG2"].value is True
    assert sheet["BH1"].value == "Indic2et3_motif_non_calculable"
    assert sheet["BH2"].value is None
    assert sheet["BI1"].value == "Indic2et3_resultat_pourcent"
    assert sheet["BI2"].value == 22
    assert sheet["BJ1"].value == "Indic2et3_resultat_nb_sal"
    assert sheet["BJ2"].value == 15.8
    assert sheet["BK1"].value == "Indic2et3_population_favorable"
    assert sheet["BK2"].value == "hommes"
    assert sheet["BL1"].value == "Indic4_calculable"
    assert sheet["BL2"].value is False
    assert sheet["BM1"].value == "Indic4_motif_non_calculable"
    assert sheet["BM2"].value == "absrcm"
    assert sheet["BN1"].value == "Indic4_resultat"
    assert sheet["BN2"].value is None
    assert sheet["BO1"].value == "Indic5_resultat"
    assert sheet["BO2"].value == 1
    assert sheet["BP1"].value == "Indic5_sexe_sur_represente"
    assert sheet["BP2"].value == "hommes"
    assert sheet["BQ1"].value == "Indicateur_1"
    assert sheet["BQ2"].value == 0
    assert sheet["BR1"].value == "Indicateur_2"
    assert sheet["BR2"].value is None
    assert sheet["BS1"].value == "Indicateur_3"
    assert sheet["BS2"].value is None
    assert sheet["BT1"].value == "Indicateur_2et3"
    assert sheet["BT2"].value == 0
    assert sheet["BU1"].value == "Indicateur_2et3_PourCent"
    assert sheet["BU2"].value == 0
    assert sheet["BV1"].value == "Indicateur_2et3_ParSal"
    assert sheet["BV2"].value == 0
    assert sheet["BW1"].value == "Indicateur_4"
    assert sheet["BW2"].value == "nc"
    assert sheet["BX1"].value == "Indicateur_5"
    assert sheet["BX2"].value == 0
    assert sheet["BY1"].value == "Nombre_total_points obtenus"
    assert sheet["BY2"].value == 0
    assert sheet["BZ1"].value == "Nombre_total_points_pouvant_etre_obtenus"
    assert sheet["BZ2"].value == 85
    assert sheet["CA1"].value == "Resultat_final_sur_100_points"
    assert sheet["CA2"].value == 0
    assert sheet["CB1"].value == "Mesures_correction"
    assert sheet["CB2"].value == "me"


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


async def test_dgt_dump_with_non_ascii_chars(declaration):
    await declaration(
        siren="123456782",
        year=2020,
        uid="123456781234-123456789012",
        source="solen-2019",
        entreprise={
            "siren": "123456782",
            "adresse": "ZI DU FOO BAR BP 658 \x01",
            "commune": "QUIMPER",
            "région": "53",
            "code_naf": "28.29B",
            "effectif": {"total": 401, "tranche": "251:999"},
            "code_postal": "29556",
            "département": "29",
            "raison_sociale": "FOOBAR",
        },
    )

    workbook = await dgt.as_xlsx(debug=True)
    sheet = workbook.active
    assert sheet["K1"].value == "Adresse"
    assert sheet["K2"].value == "ZI DU FOO BAR BP 658"


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
        indicateurs={
            "promotions": {
                "note": 15,
                "résultat": 0.5,
                "catégories": [None, 0.1, -0.3, -0.4],
                "population_favorable": "femmes",
            },
            "augmentations": {},
        },
    )
    # Not an UES, should not be in the UES tab.
    await declaration(
        siren="12345678",
        year=2020,
    )
    workbook = await dgt.as_xlsx(debug=True)
    sheet = workbook["BDD REPONDANTS"]
    assert sheet["Q1"].value == "Structure"
    assert sheet["Q3"].value == "Unité Economique et Sociale (UES)"
    assert sheet["X1"].value == "Nb_ets_UES"
    assert sheet["X3"].value == 3
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
            "Mirabar",
            "87654321",
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
        year=2019,
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
        entreprise={"effectif": {"tranche": "50:250"}},
        year=2019,
    )
    # Starting from 2020, 251:999 companies index are public.
    await declaration(
        company="KaramBar",
        siren="87654324",
        entreprise={"effectif": {"tranche": "251:999"}},
        year=2020,
    )
    out = io.StringIO()
    await exporter.public_data(out)
    out.seek(0)
    assert out.read() == (
        "Raison Sociale;SIREN;Année;Note;Structure;Nom UES;Entreprises UES (SIREN);Région;Département\r\n"
        "Mirabar;87654321;2019;26;Entreprise;;;Auvergne-Rhône-Alpes;Drôme\r\n"
        "FooBar;87654322;2018;26;Entreprise;;;Auvergne-Rhône-Alpes;Drôme\r\n"
        # "KaramBar;87654324;2020;26;Entreprise;;;Auvergne-Rhône-Alpes;Drôme\r\n"
    )


async def test_export_ues_public_data(declaration):
    await declaration(
        company="Mirabar",
        siren="87654321",
        year=2019,
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
        "Mirabar;87654321;2019;26;Unité Economique et Sociale (UES);MiraFoo;MiraBaz (315710251),MiraPouet (315710251);Auvergne-Rhône-Alpes;Drôme\r\n"
    )
