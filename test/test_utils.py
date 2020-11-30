import pytest

from egapro import utils, models


@pytest.mark.parametrize(
    "input,output",
    [("foo", "foo:*"), ("foo   bar", "foo & bar:*"), ("foo & bar", "foo & bar:*")],
)
def test_prepare_query(input, output):
    assert utils.prepare_query(input) == output


@pytest.mark.parametrize(
    "input,output",
    [
        (0, 0),
        (0.003, 0),
        (0.03, 0),
        (0.049, 0),
        (0.05, 1),
        (0.3, 1),
        (0.9, 1),
        (1, 1),
    ],
)
def test_official_round(input, output):
    assert utils.official_round(input) == output


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
    assert utils.compute_note(input, utils.REMUNERATIONS_THRESHOLDS) == output


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
    assert utils.compute_note(input, utils.CONGES_MATERNITE_THRESHOLDS) == output


def test_compute_augmentations_note():
    data = models.Data(
        {
            "déclaration": {},
            "indicateurs": {
                "augmentations_et_promotions": {"résultat": 5, "résultat_nombre_salariés": 6}
            },
        }
    )
    utils.compute_notes(data)
    assert data["indicateurs"]["augmentations_et_promotions"]["note"] == 25
    assert data["indicateurs"]["augmentations_et_promotions"]["note_nombre_salariés"] == 15
    assert data["indicateurs"]["augmentations_et_promotions"]["note_en_pourcentage"] == 25

    data = models.Data(
        {
            "déclaration": {},
            "indicateurs": {
                "augmentations_et_promotions": {"résultat": 5.05, "résultat_nombre_salariés": 2}
            },
        }
    )
    utils.compute_notes(data)
    assert data["indicateurs"]["augmentations_et_promotions"]["note"] == 35
    assert data["indicateurs"]["augmentations_et_promotions"]["note_nombre_salariés"] == 35
    assert data["indicateurs"]["augmentations_et_promotions"]["note_en_pourcentage"] == 15


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
    utils.compute_notes(data)
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
    utils.compute_notes(data)
    # rémuénrations.résultat == 0, this means equality, so whatever the value of
    # population_favorable, we do not follow it
    assert data["indicateurs"]["augmentations_et_promotions"]["note"] == 25


def test_compute_augmentations_hp_note_with_correction_measures_but_equality():
    data = models.Data({
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
    })
    utils.compute_notes(data)
    assert data["indicateurs"]["augmentations"]["note"] == 10


def test_flatten():
    assert utils.flatten({"x": {"a": "b", "c": [1, 2, 3]}}) == {
        "x.a": "b",
        "x.c": [1, 2, 3],
    }


def test_flatten_should_flatten_lists():
    assert utils.flatten({"x": {"a": "b", "c": [1, 2, 3]}}, flatten_lists=True) == {
        "x.a": "b",
        "x.c.0": 1,
        "x.c.1": 2,
        "x.c.2": 3,
    }
