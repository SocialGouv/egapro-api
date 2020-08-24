import pytest

from egapro import utils


@pytest.mark.parametrize(
    "input,output",
    [("foo", "foo:*"), ("foo   bar", "foo & bar:*"), ("foo & bar", "foo & bar:*")],
)
def test_prepare_query(input, output):
    assert utils.prepare_query(input) == output
