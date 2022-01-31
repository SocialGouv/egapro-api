import pytest

from egapro import helpers, models

RECHERCHE_ENTREPRISE_SAMPLE = {
    "activitePrincipale": "Conseil informatique",
    "categorieJuridiqueUniteLegale": "5710",
    "dateCreationUniteLegale": "2004-12-15",
    "caractereEmployeurUniteLegale": "O",
    "conventions": [
        {
            "idcc": 1486,
            "etat": "VIGUEUR_ETEN",
            "id": "KALICONT000005635173",
            "mtime": 1556652289,
            "texte_de_base": "KALITEXT000005679895",
            "title": "Convention collective nationale des bureaux d'études techniques, des cabinets d'ingénieurs-conseils et des sociétés de conseils du 15 décembre 1987. ",
            "url": "https://www.legifrance.gouv.fr/affichIDCC.do?idConvention=KALICONT000005635173",
            "shortTitle": "Bureaux d'études techniques, cabinets d'ingénieurs-conseils et sociétés de conseils",
        }
    ],
    "etablissements": 5,
    "etatAdministratifUniteLegale": "A",
    "highlightLabel": "FOOBAR",
    "label": "FOOBAR",
    "matching": 2,
    "firstMatchingEtablissement": {
        "address": "2 RUE FOOBAR 75002 PARIS",
        "codeCommuneEtablissement": "75102",
        "codePostalEtablissement": "75002",
        "libelleCommuneEtablissement": "PARIS 2",
        "idccs": [],
        "categorieEntreprise": "PME",
        "siret": "48191299900037",
        "etatAdministratifEtablissement": "A",
        "etablissementSiege": True,
        "activitePrincipaleEtablissement": "62.02A",
    },
    "allMatchingEtablissements": [
        {
            "address": "275 RUE FOOBAR 75002 PARIS",
            "siret": "48191299900037",
            "activitePrincipaleEtablissement": "62.02A",
            "etablissementSiege": True,
            "codeCommuneEtablissement": "75102",
            "codePostalEtablissement": "75002",
            "libelleCommuneEtablissement": "PARIS 2",
        },
        {
            "address": "194 BOULEVARD DE FOOFOO 75003 PARIS",
            "siret": "48191299900052",
            "idccs": ["1486"],
            "activitePrincipaleEtablissement": "62.02A",
            "etablissementSiege": False,
            "codeCommuneEtablissement": "75103",
            "codePostalEtablissement": "75002",
            "libelleCommuneEtablissement": "PARIS 2",
        },
    ],
    "simpleLabel": "FOOBAR",
    "siren": "481912999",
}


@pytest.mark.parametrize(
    "query,selected,candidates",
    [
        (
            "foobar",
            "Réseau Foobar",
            [
                "Réseau Foobar",
                "FOOBAR TRANSACTION FRANCE",
                "FOOBAR AGENCE CENTRALE",
                "Foobar Immobibaz",
            ],
        ),
        (
            "immobibaz",
            "Réseau Foobar (Foobar Immobibaz)",
            [
                "Réseau Foobar",
                "FOOBAR TRANSACTION FRANCE",
                "FOOBAR AGENCE CENTRALE",
                "Foobar Immobibaz",
            ],
        ),
    ],
)
def test_compute_label(query, selected, candidates):
    assert helpers.compute_label(query, *candidates) == selected


@pytest.mark.parametrize(
    "input,output",
    [
        (None, None),
        (0, 40),
        (0.003, 40),
        (0.03, 40),
        (0.047, 40),
        (0.05, 39),
        (0.051, 39),
        (0.3, 39),
        (0.9, 39),
        (1, 39),
        (5.04, 35),
        (5.05, 34),
        (112, 0),
        ("NaN", 0),
        ("foobar", None),
    ],
)
def test_compute_remuneration_note(input, output):
    assert helpers.compute_note(input, helpers.REMUNERATIONS_THRESHOLDS) == output


@pytest.mark.parametrize(
    "input,output",
    [
        (0, 0),
        (1, 0),
        (33, 0),
        (99, 0),
        (100, 15),
    ],
)
def test_compute_conges_maternites_note(input, output):
    assert helpers.compute_note(input, helpers.CONGES_MATERNITE_THRESHOLDS) == output


def test_compute_augmentations_note():
    data = models.Data(
        {
            "déclaration": {},
            "indicateurs": {
                "augmentations_et_promotions": {
                    "résultat": 5,
                    "résultat_nombre_salariés": 6,
                }
            },
        }
    )
    helpers.compute_notes(data)
    assert data["indicateurs"]["augmentations_et_promotions"]["note"] == 25
    assert (
        data["indicateurs"]["augmentations_et_promotions"]["note_nombre_salariés"] == 15
    )
    assert (
        data["indicateurs"]["augmentations_et_promotions"]["note_en_pourcentage"] == 25
    )

    data = models.Data(
        {
            "déclaration": {},
            "indicateurs": {
                "augmentations_et_promotions": {
                    "résultat": 5.05,
                    "résultat_nombre_salariés": 2,
                }
            },
        }
    )
    helpers.compute_notes(data)
    assert data["indicateurs"]["augmentations_et_promotions"]["note"] == 35
    assert (
        data["indicateurs"]["augmentations_et_promotions"]["note_nombre_salariés"] == 35
    )
    assert (
        data["indicateurs"]["augmentations_et_promotions"]["note_en_pourcentage"] == 15
    )
    data["indicateurs"]["augmentations_et_promotions"]["non_calculable"] = "egvi40pcet"
    helpers.compute_notes(data)
    assert not data["indicateurs"]["augmentations_et_promotions"].get("note")
    assert not data["indicateurs"]["augmentations_et_promotions"].get(
        "note_nombre_salariés"
    )
    assert not data["indicateurs"]["augmentations_et_promotions"].get(
        "note_en_pourcentage"
    )


def test_compute_augmentations_note_with_correction_measures():
    data = models.Data(
        {
            "déclaration": {},
            "indicateurs": {
                "rémunérations": {"résultat": 5, "population_favorable": "hommes"},
                "augmentations_et_promotions": {
                    "résultat": 5,
                    "résultat_nombre_salariés": 6,
                    "population_favorable": "femmes",
                },
            },
        }
    )
    helpers.compute_notes(data)
    # Maximal note because this indicateur is favourable for the opposition population
    # of rémunérations indicateur
    assert data["indicateurs"]["augmentations_et_promotions"]["note"] == 35


def test_compute_augmentations_note_with_correction_measures_but_equality():
    data = models.Data(
        {
            "déclaration": {},
            "indicateurs": {
                "rémunérations": {"résultat": 0, "population_favorable": "hommes"},
                "augmentations_et_promotions": {
                    "résultat": 5,
                    "résultat_nombre_salariés": 6,
                    "population_favorable": "femmes",
                },
            },
        }
    )
    helpers.compute_notes(data)
    # rémuénrations.résultat == 0, this means equality, so whatever the value of
    # population_favorable, we do not follow it
    assert data["indicateurs"]["augmentations_et_promotions"]["note"] == 25


def test_compute_augmentations_hp_note_with_correction_measures_but_equality():
    data = models.Data(
        {
            "déclaration": {},
            "indicateurs": {
                "rémunérations": {
                    "note": 40,
                    "résultat": 0.0,
                    "population_favorable": "femmes",
                },
                "augmentations": {
                    "résultat": 4.0,
                    "population_favorable": "hommes",
                },
            },
        }
    )
    helpers.compute_notes(data)
    assert data["indicateurs"]["augmentations"]["note"] == 10


def test_extract_ft():
    data = {"entreprise": {"raison_sociale": "blablabar"}}
    assert helpers.extract_ft(models.Data(data)) == "blablabar"
    data = {"entreprise": {"raison_sociale": "blablabar", "ues": {"nom": "nom ues"}}}
    assert helpers.extract_ft(models.Data(data)) == "blablabar nom ues"
    data = {
        "entreprise": {
            "raison_sociale": "blablabar",
            "ues": {
                "nom": "nom ues",
                "entreprises": [
                    {"siren": "123456789", "raison_sociale": "entreprise une"},
                    {"siren": "123456780", "raison_sociale": "entreprise deux"},
                ],
            },
        }
    }
    assert (
        helpers.extract_ft(models.Data(data))
        == "blablabar nom ues entreprise une entreprise deux"
    )


@pytest.mark.asyncio
async def test_recherche_entreprise(monkeypatch):
    async def mock_get(*args, **kwargs):
        return RECHERCHE_ENTREPRISE_SAMPLE

    monkeypatch.setattr("egapro.helpers.get", mock_get)
    data = await helpers.load_from_recherche_entreprises("481912999")
    assert data == {
        "adresse": "2 RUE FOOBAR",
        "code_naf": "62.02A",
        "code_postal": "75002",
        "commune": "PARIS 2",
        "département": "75",
        "raison_sociale": "FOOBAR",
        "région": "11",
    }


@pytest.mark.asyncio
async def test_recherche_entreprise_with_date_radiation(monkeypatch):
    RECHERCHE_ENTREPRISE_SAMPLE["etatAdministratifUniteLegale"] = "C"

    async def mock_get(*args, **kwargs):
        return RECHERCHE_ENTREPRISE_SAMPLE

    monkeypatch.setattr("egapro.helpers.get", mock_get)
    with pytest.raises(ValueError) as info:
        await helpers.load_from_recherche_entreprises("481912999")
    assert str(info.value) == (
        "Le Siren saisi correspond à une entreprise fermée, "
        "veuillez vérifier votre saisie"
    )
    RECHERCHE_ENTREPRISE_SAMPLE["etatAdministratifUniteLegale"] = "A"


@pytest.mark.asyncio
async def test_recherche_entreprise_with_foreign_company(monkeypatch):
    RECHERCHE_ENTREPRISE_SAMPLE['firstMatchingEtablissement']["codePaysEtrangerEtablissement"] = "99131"

    async def mock_get(*args, **kwargs):
        return RECHERCHE_ENTREPRISE_SAMPLE

    monkeypatch.setattr("egapro.helpers.get", mock_get)
    with pytest.raises(ValueError) as info:
        await helpers.load_from_recherche_entreprises("481912999")
    assert str(info.value) == (
        "Le Siren saisi correspond à une entreprise étrangère, "
        "veuillez vérifier votre saisie"
    )
