import json

import pytest

from egapro import db

pytestmark = pytest.mark.asyncio


async def test_request_token(client, monkeypatch):
    calls = 0

    def mock_send(to, subject, body):
        assert to == "foo@bar.org"
        assert "/?token=" in body
        nonlocal calls
        calls += 1

    client.logout()
    monkeypatch.setattr("egapro.emails.send", mock_send)
    resp = await client.post("/token", body={"email": "foo@bar.org"})
    assert resp.status == 204
    assert calls == 1


async def test_search_endpoint(client):
    await db.declaration.put(
        "12345671",
        2019,
        "foo@bar.org",
        {
            "déclaration": {"index": 95, "année_indicateurs": 2019},
            "id": "12345678-1234-5678-9012-123456789013",
            "entreprise": {
                "raison_sociale": "Bio c Bon",
                "effectif": {"tranche": "1000:"},
            },
        },
    )
    await db.declaration.put(
        "12345672",
        2019,
        "foo@bar.org",
        {
            "déclaration": {"index": 93, "année_indicateurs": 2019},
            "id": "12345678-1234-5678-9012-123456789012",
            "entreprise": {
                "raison_sociale": "Biocoop",
                "effectif": {"tranche": "50:250"},
            },
        },
    )
    resp = await client.get("/search?q=bio")
    assert resp.status == 200
    assert json.loads(resp.body) == {
        "data": [
            {
                "declaration": {"noteIndex": 95},
                "id": "12345678-1234-5678-9012-123456789013",
                "informations": {"anneeDeclaration": 2019},
                "informationsEntreprise": {
                    "nomEntreprise": "Bio c Bon",
                    "departement": None,
                    "region": None,
                    "siren": "12345671",
                    "structure": "Entreprise",
                    "entreprisesUES": [],
                    "nomUES": None,
                },
            },
        ],
        "total": 1,
    }
    resp = await client.get("/search?q=bio&limit=1")
    assert resp.status == 200
    assert len(json.loads(resp.body)["data"]) == 1


async def test_invalid_search_query(client):
    resp = await client.get("/search?q=")
    assert resp.status == 400
    resp = await client.get("/search?q= ")
    assert resp.status == 400


async def test_config_endpoint(client):
    resp = await client.get("/config")
    assert resp.status == 200
    assert list(json.loads(resp.body).keys()) == [
        "YEARS",
        "EFFECTIFS",
        "DEPARTEMENTS",
        "REGIONS",
        "REGIONS_TO_DEPARTEMENTS",
        "NAF",
    ]
    assert json.loads(resp.body)["YEARS"] == [2018, 2019, 2020]
    resp = await client.get("/config?key=YEARS&key=REGIONS")
    assert resp.status == 200
    assert list(json.loads(resp.body).keys()) == [
        "YEARS",
        "REGIONS",
    ]


async def test_validate_siren(client):
    resp = await client.get("/validate-siren?siren=1234567")
    assert resp.status == 422
    resp = await client.get("/validate-siren?siren=123456789")
    assert resp.status == 422
    resp = await client.get("/validate-siren?siren=123456782")
    assert resp.status == 204


async def test_me(client):
    resp = await client.get("/me")
    assert resp.status == 200
    assert json.loads(resp.body) == {"email": "foo@bar.org"}


async def test_me_without_token(client):
    client.logout()
    resp = await client.get("/me")
    assert resp.status == 401
