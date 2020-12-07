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
