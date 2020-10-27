import pytest

from egapro import utils


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
    assert utils.compute_remunerations_note(input) == output
