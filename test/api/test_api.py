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


async def test_stats_endpoint(client):
    rows = [
        ("12345671", "1000 et plus"),
        ("12345672", "1000 et plus"),
        ("12345673", "251 à 999"),
        ("12345674", "50 à 250"),
        ("12345675", "50 à 250"),
        ("12345676", "50 à 250"),
    ]
    for siren, tranche in rows:
        await db.declaration.put(
            siren,
            2019,
            "foo@bar.org",
            {"informations": {"trancheEffectifs": tranche}},
        )
    resp = await client.get("/stats")
    assert resp.status == 200
    assert json.loads(resp.body) == {"1000 et plus": 2, "251 à 999": 1, "50 à 250": 3}


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
                "effectif": {"tranche": "251:999"},
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
                "informationsEntreprise": {"nomEntreprise": "Bio c Bon"},
            },
        ],
        "total": 1,
    }
    resp = await client.get("/search?q=bio&limit=1")
    assert resp.status == 200
    assert len(json.loads(resp.body)["data"]) == 1


async def test_config_endpoint(client):
    resp = await client.get("/config")
    assert resp.status == 200
    assert list(json.loads(resp.body).keys()) == [
        "YEARS",
        "EFFECTIFS",
        "DEPARTEMENTS",
        "REGIONS",
        "REGIONS_TO_DEPARTEMENTS",
    ]
    assert json.loads(resp.body)["YEARS"] == [2018, 2019]
    resp = await client.get("/config?key=YEARS&key=REGIONS")
    assert resp.status == 200
    assert list(json.loads(resp.body).keys()) == [
        "YEARS",
        "REGIONS",
    ]
