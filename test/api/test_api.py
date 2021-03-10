import json

import pytest

from egapro import db

pytestmark = pytest.mark.asyncio


async def test_request_token(client, monkeypatch):
    calls = 0

    def mock_send(to, subject, body):
        assert to == "foo@bar.org"
        assert "/declaration/?token=" in body
        nonlocal calls
        calls += 1

    client.logout()
    monkeypatch.setattr("egapro.emails.send", mock_send)
    resp = await client.post("/token", body={"email": "foo@bar.org"})
    assert resp.status == 204
    assert calls == 1


async def test_request_token_with_allowed_ips(client, monkeypatch):
    calls = 0

    def mock_send(to, subject, body):
        nonlocal calls
        calls += 1

    client.logout()
    monkeypatch.setattr("egapro.emails.send", mock_send)
    monkeypatch.setattr("egapro.config.ALLOWED_IPS", ["1.1.1.1"])
    resp = await client.post(
        "/token", body={"email": "foo@bar.org"}, headers={"X-REAL-IP": "1.1.1.1"}
    )
    assert resp.status == 200
    assert list(json.loads(resp.body).keys()) == ["token"]
    assert calls == 0


async def test_search_endpoint(client):
    await db.declaration.put(
        "12345671",
        2020,
        "foo@bar.org",
        {
            "déclaration": {"index": 95, "année_indicateurs": 2020},
            "id": "12345678-1234-5678-9012-123456789013",
            "entreprise": {
                "raison_sociale": "Bio c Bon",
                "effectif": {"tranche": "1000:"},
            },
        },
    )
    await db.declaration.put(
        "12345672",
        2020,
        "foo@bar.org",
        {
            "déclaration": {"index": 93, "année_indicateurs": 2020},
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
                "entreprise": {
                    "raison_sociale": "Bio c Bon",
                    "département": None,
                    "région": None,
                    "code_naf": None,
                    "effectif": {"tranche": "1000:"},
                    "siren": "12345671",
                    "ues": None,
                },
                "notes": {"2020": 95},
            },
        ],
    }
    resp = await client.get("/search?q=bio&limit=1")
    assert resp.status == 200
    assert len(json.loads(resp.body)["data"]) == 1
    resp = await client.get("/search")
    assert resp.status == 200
    assert len(json.loads(resp.body)["data"]) == 1


async def test_stats_endpoint(client):
    await db.declaration.put(
        "12345671",
        2020,
        "foo@bar.org",
        {
            "déclaration": {"index": 95, "année_indicateurs": 2020},
            "id": "12345678-1234-5678-9012-123456789013",
            "entreprise": {
                "raison_sociale": "Bio c Bon",
                "effectif": {"tranche": "1000:"},
                "département": "12",
            },
        },
    )
    # Small
    await db.declaration.put(
        "12345672",
        2020,
        "foo@bar.org",
        {
            "déclaration": {"index": 93, "année_indicateurs": 2020},
            "id": "12345678-1234-5678-9012-123456789012",
            "entreprise": {
                "raison_sociale": "Biocoop",
                "effectif": {"tranche": "50:250"},
                "département": "11",
            },
        },
    )
    await db.declaration.put(
        "123456782",
        2020,
        "foo@bar.org",
        {
            "déclaration": {"index": 93, "année_indicateurs": 2020},
            "id": "12345678-1234-5678-9012-123456789012",
            "entreprise": {
                "raison_sociale": "RoboCoop",
                "effectif": {"tranche": "251:999"},
                "département": "11",
            },
        },
    )
    resp = await client.get("/stats")
    assert resp.status == 200
    assert json.loads(resp.body) == {
        "count": 2,
        "max": 95,
        "min": 93,
        "avg": 94,
    }
    resp = await client.get("/stats?departement=11")
    assert resp.status == 200
    assert json.loads(resp.body) == {
        "count": 1,
        "max": 93,
        "min": 93,
        "avg": 93,
    }


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
        "SECTIONS_NAF",
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
