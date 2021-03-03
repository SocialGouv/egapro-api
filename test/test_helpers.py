import pytest

from egapro import helpers, models


@pytest.mark.parametrize(
    "input,output",
    [
        (None, None),
        (0, 40),
        (0.003, 40),
        (0.03, 40),
        (0.05, 39),
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
async def test_api_entreprise(monkeypatch):
    async def mock_get(*args, **kwargs):
        return {
            "entreprise": {
                "siren": "481912999",
                "capital_social": 100000,
                "numero_tva_intracommunautaire": "FR94481912999",
                "forme_juridique": "SAS, société par actions simplifiée",
                "forme_juridique_code": "5710",
                "nom_commercial": "FOOBAR",
                "procedure_collective": False,
                "enseigne": None,
                "libelle_naf_entreprise": "Conseil en systèmes et logiciels informatiques",
                "naf_entreprise": "6202A",
                "raison_sociale": "FOOBAR",
                "siret_siege_social": "48191290000099",
                "code_effectif_entreprise": "03",
                "date_creation": 1103065200,
                "nom": None,
                "prenom": None,
                "date_radiation": None,
                "categorie_entreprise": "PME",
                "tranche_effectif_salarie_entreprise": {
                    "de": 6,
                    "a": 9,
                    "code": "03",
                    "date_reference": "2018",
                    "intitule": "6 à 9 salariés",
                },
                "mandataires_sociaux": [
                    {
                        "nom": "FOO",
                        "prenom": "BAR",
                        "fonction": "PRESIDENT",
                        "date_naissance": "1979-08-06",
                        "date_naissance_timestamp": 302738400,
                        "dirigeant": True,
                        "raison_sociale": "",
                        "identifiant": "",
                        "type": "PP",
                    },
                ],
                "etat_administratif": {"value": "A", "date_cessation": None},
            },
            "etablissement_siege": {
                "siege_social": True,
                "siret": "48191299000099",
                "naf": "6202A",
                "libelle_naf": "Conseil en systèmes et logiciels informatiques",
                "date_mise_a_jour": 1598343993,
                "tranche_effectif_salarie_etablissement": {
                    "de": 6,
                    "a": 9,
                    "code": "03",
                    "date_reference": "2018",
                    "intitule": "6 à 9 salariés",
                },
                "date_creation_etablissement": 1485903600,
                "region_implantation": {"code": "11", "value": "Île-de-France"},
                "commune_implantation": {
                    "code": "75102",
                    "value": "Paris 2e Arrondissement",
                },
                "pays_implantation": {"code": "FR", "value": "FRANCE"},
                "diffusable_commercialement": True,
                "enseigne": None,
                "adresse": {
                    "l1": "FOOBAR",
                    "l2": None,
                    "l3": None,
                    "l4": "2 RUE FOOBAR",
                    "l5": None,
                    "l6": "75002 PARIS 2",
                    "l7": "FRANCE",
                    "numero_voie": "2",
                    "type_voie": "RUE",
                    "nom_voie": "FOOBAR",
                    "complement_adresse": None,
                    "code_postal": "75002",
                    "localite": "PARIS 2",
                    "code_insee_localite": "75102",
                    "cedex": None,
                },
                "etat_administratif": {"value": "A", "date_fermeture": None},
            },
            "gateway_error": False,
        }

    monkeypatch.setattr("egapro.config.API_ENTREPRISES", "foobar")
    monkeypatch.setattr("egapro.helpers.get", mock_get)
    data = await helpers.load_from_api_entreprises("481912999")
    assert data == {
        "adresse": "2 RUE FOOBAR",
        "code_naf": "6202A",
        "code_postal": "75002",
        "commune": "PARIS 2",
        "département": "75",
        "raison_sociale": "FOOBAR",
        "région": "11",
    }
