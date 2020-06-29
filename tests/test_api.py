import json

import pytest

from egapro import db, config

pytestmark = pytest.mark.asyncio


async def test_cannot_put_declaration_without_token(client):
    client.logout()
    resp = await client.put("/declaration/514027945/2020", body={"foo": "bar"})
    assert resp.status == 401


async def test_request_token(client, monkeypatch):
    calls = 0

    def mock_send(to, subject, body):
        assert to == "foo@bar.org"
        assert "/sésame/" in body
        nonlocal calls
        calls += 1

    client.logout()
    monkeypatch.setattr("egapro.emails.send", mock_send)
    resp = await client.post("/token", body={"email": "foo@bar.org"})
    assert resp.status == 204
    assert calls == 1


async def test_declaration_should_contain_declarant_email_if_token_not_active(client):
    config.REQUIRE_TOKEN = False
    resp = await client.put("/declaration/514027945/2020", body={"foo": "bar"})
    assert resp.status == 422
    resp = await client.put(
        "/declaration/514027945/2020",
        body={"data": {"informationsDeclarant": {"email": "foo@bar.org"}}},
    )
    assert resp.status == 204
    assert await db.declaration.owner("514027945", "2020") == "foo@bar.org"
    config.REQUIRE_TOKEN = True


async def test_basic_declaration_should_save_data(client):
    resp = await client.put("/declaration/514027945/2020", body={"foo": "bar"})
    assert resp.status == 204
    resp = await client.get("/declaration/514027945/2020")
    assert resp.status == 200
    data = json.loads(resp.body)
    assert "last_modified" in data
    del data["last_modified"]
    assert data == {
        "data": {"foo": "bar"},
        "siren": "514027945",
        "year": 2020,
    }


async def test_patch_declaration(client, declaration):
    await declaration(
        siren="12345678",
        year=2018,
        owner="foo@bar.org",
        informationsEntreprise={"nomEntreprise": "Roma"},
    )
    resp = await client.patch(
        "/declaration/12345678/2018",
        body={
            "informationsEntreprise": {"nomEntreprise": "Roma"},
            "declaration": {"formValidated": "Invalid"},
        },
    )
    assert resp.status == 204
    declaration = await db.declaration.get("12345678", 2018)
    assert declaration["data"]["informationsEntreprise"]["nomEntreprise"] == "Roma"
    assert declaration["data"]["declaration"] == {"formValidated": "Invalid"}


async def test_basic_declaration_should_remove_data_namespace_if_present(client):
    await client.put("/declaration/514027945/2020", body={"data": {"foo": "bar"}})
    assert (await db.declaration.get("514027945", "2020"))["data"] == {"foo": "bar"}


async def test_cannot_load_not_owned_declaration(client, monkeypatch):
    async def mock_owner(*args, **kwargs):
        return "foo@bar.baz"

    monkeypatch.setattr("egapro.db.declaration.owner", mock_owner)
    client.login("other@email.com")
    resp = await client.get("/declaration/514027945/2020")
    assert resp.status == 403


async def test_cannot_put_not_owned_declaration(client, monkeypatch):
    async def mock_owner(*args, **kwargs):
        return "foo@bar.baz"

    monkeypatch.setattr("egapro.db.declaration.owner", mock_owner)
    client.login("other@email.com")
    resp = await client.put("/declaration/514027945/2020")
    assert resp.status == 403


async def test_declaring_twice_should_not_duplicate(client, app):
    resp = await client.put("/declaration/514027945/2020", body={"foo": "bar"})
    assert resp.status == 204
    resp = await client.put("/declaration/514027945/2020", body={"foo": "baz"})
    assert resp.status == 204
    async with db.declaration.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT data FROM declaration WHERE siren=$1 and year=$2",
            "514027945",
            2020,
        )
    assert len(rows) == 1
    assert rows[0]["data"] == {"foo": "baz"}


async def test_confirmed_declaration_should_send_email(client, monkeypatch):
    calls = 0
    id = "12345678-1234-5678-9012-123456789012"
    company = "TotalRecall"

    def mock_send(to, subject, txt, html):
        assert to == "foo@bar.org"
        assert id in txt
        assert id in html
        assert company in txt
        assert company in html
        nonlocal calls
        calls += 1

    monkeypatch.setattr("egapro.emails.send", mock_send)
    resp = await client.put("/declaration/514027945/2020", body={"foo": False})
    assert resp.status == 204
    assert not calls
    resp = await client.put(
        "/declaration/514027945/2020", body={"declaration": {"formValidated": "None"}}
    )
    assert resp.status == 204
    assert not calls
    resp = await client.put(
        "/declaration/514027945/2020",
        body={
            "id": id,
            "declaration": {"formValidated": "Valid"},
            "informations": {"anneeDeclaration": 2020},
            "informationsEntreprise": {"nomEntreprise": company},
        },
    )
    assert resp.status == 204
    assert calls == 1


async def test_confirmed_declaration_should_raise_if_missing_id(client, monkeypatch):
    calls = 0

    def mock_send(to, subject, txt, html):
        nonlocal calls
        calls += 1

    monkeypatch.setattr("egapro.emails.send", mock_send)
    resp = await client.put(
        "/declaration/514027945/2020",
        body={
            "declaration": {"formValidated": "Valid"},
            "informations": {"anneeDeclaration": 2020},
            "informationsEntreprise": {"nomEntreprise": "NomNom"},
        },
    )
    assert resp.status == 400
    body = json.loads(resp.body)
    assert body == {"error": "Missing id"}
    assert not calls


async def test_with_unknown_siren_or_year(client):
    resp = await client.get("/declaration/514027945/2020")
    assert resp.status == 404


async def test_start_new_simulation(client):
    resp = await client.post("/simulation", body={"foo": "bar"})
    assert resp.status == 200
    data = json.loads(resp.body)
    assert "id" in data
    assert await db.simulation.get(data["id"])


async def test_get_simulation(client):
    uid = await db.simulation.create({"foo": "bar"})
    resp = await client.get(f"/simulation/{uid}")
    assert resp.status == 200
    data = json.loads(resp.body)
    assert "last_modified" in data
    del data["last_modified"]
    assert data == {
        "data": {"foo": "bar"},
        "id": uid,
    }


async def test_basic_simulation_should_save_data(client):
    resp = await client.put(
        "/simulation/12345678-1234-5678-9012-123456789012",
        body={"data": {"foo": "bar"}},
    )
    assert resp.status == 200
    data = json.loads(resp.body)
    assert "last_modified" in data
    del data["last_modified"]
    assert data == {
        "data": {"foo": "bar"},
        "id": "12345678-1234-5678-9012-123456789012",
    }


async def test_start_new_simulation_send_email_if_given(client, monkeypatch):
    calls = 0
    email_body = ""

    def mock_send(to, subject, txt, html=None):
        assert to == "foo@bar.org"
        nonlocal calls
        nonlocal email_body
        email_body = txt
        calls += 1

    monkeypatch.setattr("egapro.emails.send", mock_send)
    resp = await client.post("/simulation", body={"foo": "bar"})
    assert resp.status == 200
    assert not calls
    resp = await client.post(
        "/simulation",
        body={"data": {"informationsDeclarant": {"email": "foo@bar.org"}}},
    )
    assert resp.status == 200
    data = json.loads(resp.body)
    assert data["id"] in email_body


async def test_put_simulation_should_redirect_to_declaration_if_validated(client):
    resp = await client.put(
        "/simulation/12345678-1234-5678-9012-123456789012",
        body={
            "data": {
                "declaration": {"formValidated": "Valid"},
                "informationsEntreprise": {"siren": "12345678"},
                "informations": {"anneeDeclaration": 2020},
            },
        },
    )
    assert resp.status == 307
    assert resp.headers["Location"] == "/declaration/12345678/2020"
    # Simulation should have been saved too
    assert await db.simulation.get("12345678-1234-5678-9012-123456789012")


async def test_get_simulation_should_redirect_to_declaration_if_validated(client):
    uid = await db.simulation.create(
        {
            "declaration": {"formValidated": "Valid"},
            "informationsEntreprise": {"siren": "12345678"},
            "informations": {"anneeDeclaration": 2020},
        }
    )
    resp = await client.get(f"/simulation/{uid}")
    assert resp.status == 302
    assert resp.headers["Location"] == "/declaration/12345678/2020"


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
            siren, 2020, "foo@bar.org", {"informations": {"trancheEffectifs": tranche}},
        )
    resp = await client.get("/stats")
    assert resp.status == 200
    assert json.loads(resp.body) == {"1000 et plus": 2, "251 à 999": 1, "50 à 250": 3}


async def test_send_code_endpoint(client, monkeypatch):
    calls = 0
    email_body = ""
    recipient = None

    def mock_send(to, subject, txt, html=None):
        assert to == "foo@bar.org"
        nonlocal calls
        nonlocal email_body
        nonlocal recipient
        email_body = txt
        recipient = to
        calls += 1

    monkeypatch.setattr("egapro.emails.send", mock_send)

    # Invalid UUID
    resp = await client.post("/simulation/unknown/send-code", body={"foo": "bar"})
    assert resp.status == 400
    assert json.loads(resp.body) == {
        "error": 'Invalid data: invalid input syntax for type uuid: "unknown"'
    }
    assert not calls

    # Not found UUID
    resp = await client.post(
        "/simulation/12345678-1234-5678-9012-123456789012/send-code",
        body={"foo": "bar"},
    )
    assert resp.status == 404
    assert not calls

    # Create simulation
    uid = await db.simulation.create(
        {
            "declaration": {"formValidated": "Valid"},
            "informationsEntreprise": {"siren": "12345678"},
            "informations": {"anneeDeclaration": 2020},
        }
    )

    # Missing email
    resp = await client.post(f"/simulation/{uid}/send-code", body={"foo": "bar"})
    assert resp.status == 400
    assert json.loads(resp.body) == {"error": "Missing `email` key"}
    assert not calls

    # Valid request.
    resp = await client.post(
        f"/simulation/{uid}/send-code", body={"email": "foo@bar.org"}
    )
    assert resp.status == 204
    assert uid in email_body
    assert recipient == "foo@bar.org"


async def test_search_endpoint(client):
    await db.declaration.put(
        "12345671",
        2020,
        "foo@bar.org",
        {
            "declaration": {"noteIndex": 95},
            "id": "12345678-1234-5678-9012-123456789013",
            "informations": {"anneeDeclaration": "2020"},
            "informationsEntreprise": {"nomEntreprise": "Bio c Bon"},
        },
    )
    await db.declaration.put(
        "12345672",
        2020,
        "foo@bar.org",
        {
            "declaration": {"noteIndex": 93},
            "id": "12345678-1234-5678-9012-123456789012",
            "informations": {"anneeDeclaration": "2020"},
            "informationsEntreprise": {"nomEntreprise": "Biocoop"},
        },
    )
    resp = await client.get("/search?q=bio")
    assert resp.status == 200
    assert json.loads(resp.body) == {
        "data": [
            {
                "declaration": {"noteIndex": 95},
                "id": "12345678-1234-5678-9012-123456789013",
                "informations": {"anneeDeclaration": "2020"},
                "informationsEntreprise": {"nomEntreprise": "Bio c Bon"},
            },
            {
                "declaration": {"noteIndex": 93},
                "id": "12345678-1234-5678-9012-123456789012",
                "informations": {"anneeDeclaration": "2020"},
                "informationsEntreprise": {"nomEntreprise": "Biocoop"},
            },
        ],
        "total": 2,
    }
    resp = await client.get("/search?q=bio&limit=1")
    assert resp.status == 200
    assert len(json.loads(resp.body)["data"]) == 1
