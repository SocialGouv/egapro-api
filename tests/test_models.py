from egapro.models import Data


def test_data_validated():
    data = Data()
    assert not data.validated
    data = Data({"declaration": {"formValidated": None}})
    assert not data.validated
    data = Data({"declaration": {"formValidated": "Invalid"}})
    assert not data.validated
    data = Data({"declaration": {"formValidated": "Valid"}})
    assert data.validated


def test_data_year():
    data = Data()
    assert data.year is None
    data = Data({"informations": {"anneeDeclaration": 2020}})
    assert data.year == 2020
    data = Data({"informations": {"finPeriodeReference": "01/02/2019"}})
    assert data.year == 2019
