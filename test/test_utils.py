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
