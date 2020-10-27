import json

import pytest

from egapro import db

pytestmark = pytest.mark.asyncio


# Minimal body to send post requests
@pytest.fixture
def body():
    return {
        "id": "1234",
        "status": "valid",
        "déclaration": {
            "année_indicateurs": 2019,
            "période_référence": ["2019-01-01", "2019-12-31"],
        },
        "déclarant": {"email": "foo@bar.org", "prénom": "Foo", "nom": "Bar"},
        "entreprise": {
            "raison_sociale": "FooBar",
            "siren": "514027945",
            "région": "76",
            "département": "12",
            "adresse": "12, rue des adresses",
            "commune": "Y",
        },
    }


async def test_cannot_put_declaration_without_token(client, body):
    client.logout()
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 401


async def test_cannot_get_declaration_without_token(client):
    client.logout()
    resp = await client.get("/declaration/514027945/2019")
    assert resp.status == 401


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


async def test_invalid_siren_should_raise(client, body):
    resp = await client.put("/declaration/111111111/2019", body=body)
    assert resp.status == 422
    assert json.loads(resp.body) == {"error": "Numéro SIREN invalide: 111111111"}


async def test_invalid_year_should_raise(client, body):
    resp = await client.put("/declaration/514027945/2017", body=body)
    assert resp.status == 422
    assert json.loads(resp.body) == {
        "error": "Il est possible de déclarer seulement pour les années 2018, 2019"
    }


async def test_basic_declaration_should_save_data(client, body):
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    resp = await client.get("/declaration/514027945/2019")
    assert resp.status == 200
    data = json.loads(resp.body)
    assert "last_modified" in data
    del data["last_modified"]
    assert data == {"data": body, "siren": "514027945", "year": 2019}


async def test_owner_email_should_be_lower_cased(client, body):
    client.login("FoO@BAZ.baR")
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    assert await db.declaration.owner("514027945", 2019) == "foo@baz.bar"


async def test_patch_declaration(client, declaration):
    data = await declaration(
        siren="12345678",
        year=2018,
        owner="foo@bar.org",
        entreprise={"raison_sociale": "Milano"},
    )
    modified = data["entreprise"]
    modified["raison_sociale"] = "Roma"
    resp = await client.patch(
        "/declaration/12345678/2018",
        body={
            "entreprise": modified,
            "status": "pending",
        },
    )
    assert resp.status == 204
    declaration = await db.declaration.get("12345678", 2018)
    assert declaration["data"]["entreprise"]["raison_sociale"] == "Roma"
    assert declaration["data"]["status"] == "pending"


async def test_basic_declaration_should_remove_data_namespace_if_present(client, body):
    await client.put("/declaration/514027945/2019", body={"data": body})
    assert (await db.declaration.get("514027945", "2019"))["data"] == body


@pytest.mark.xfail
async def test_cannot_load_not_owned_declaration(client, monkeypatch):
    async def mock_owner(*args, **kwargs):
        return "foo@bar.baz"

    monkeypatch.setattr("egapro.db.declaration.owner", mock_owner)
    client.login("other@email.com")
    resp = await client.get("/declaration/514027945/2019")
    assert resp.status == 403


async def test_cannot_put_not_owned_declaration(client, monkeypatch):
    async def mock_owner(*args, **kwargs):
        return "foo@bar.baz"

    monkeypatch.setattr("egapro.db.declaration.owner", mock_owner)
    client.login("other@email.com")
    resp = await client.put("/declaration/514027945/2019")
    assert resp.status == 403


async def test_owner_check_is_lower_case(client, body):
    client.login("FOo@baR.com")
    await client.put("/declaration/514027945/2019", body=body)
    client.login("FOo@BAR.COM")
    resp = await client.patch("/declaration/514027945/2019", {"indicateurs": {}})
    assert resp.status == 204
    record = await db.declaration.get("514027945", 2019)
    body["déclarant"]["email"] = "foo@bar.com"
    body["indicateurs"] = {}
    assert record["data"] == body


async def test_declaring_twice_should_not_duplicate(client, app, body):
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    body["indicateurs"] = {}
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    async with db.declaration.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT data FROM declaration WHERE siren=$1 and year=$2",
            "514027945",
            2019,
        )
    assert len(rows) == 1
    assert rows[0]["data"] == body


async def test_confirmed_declaration_should_send_email(client, monkeypatch, body):
    calls = 0
    id = "1234"
    company = "FooBar"

    def mock_send(to, subject, txt, html):
        assert to == "foo@bar.org"
        assert id in txt
        assert id in html
        assert company in txt
        assert company in html
        nonlocal calls
        calls += 1

    del body["status"]
    monkeypatch.setattr("egapro.emails.send", mock_send)
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    assert not calls
    body["status"] = "pending"
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    assert not calls
    body["status"] = "valid"
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    assert calls == 1


async def test_confirmed_declaration_should_raise_if_missing_id(
    client, monkeypatch, body
):
    calls = 0

    def mock_send(to, subject, txt, html):
        nonlocal calls
        calls += 1

    del body["id"]
    monkeypatch.setattr("egapro.emails.send", mock_send)
    resp = await client.put(
        "/declaration/514027945/2019",
        body=body,
    )
    assert resp.status == 400
    body = json.loads(resp.body)
    assert body == {"error": "Missing id"}
    assert not calls


async def test_with_unknown_siren_or_year(client):
    resp = await client.get("/declaration/514027945/2019")
    assert resp.status == 404


async def test_start_new_simulation(client, body):
    resp = await client.post("/simulation", body=body)
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
        body={"data": {"déclarant": {"email": "foo@bar.org"}}},
    )
    assert resp.status == 200
    data = json.loads(resp.body)
    assert data["id"] in email_body


async def test_put_simulation_should_redirect_to_declaration_if_validated(client):
    resp = await client.put(
        "/simulation/12345678-1234-5678-9012-123456789012",
        body={
            "data": {
                "déclarant": {"email": "foo@bar.org"},
                "status": "valid",
                "entreprise": {"siren": "12345678"},
                "déclaration": {"année_indicateurs": 2019},
            },
        },
    )
    assert resp.status == 307
    assert resp.headers["Location"] == "/declaration/12345678/2019"
    # Simulation should have been saved too
    assert await db.simulation.get("12345678-1234-5678-9012-123456789012")


async def test_get_simulation_should_redirect_to_declaration_if_validated(client):
    uid = await db.simulation.create(
        {
            "déclarant": {"email": "foo@bar.org"},
            "status": "valid",
            "entreprise": {"siren": "12345678"},
            "déclaration": {"année_indicateurs": 2019},
        }
    )
    resp = await client.get(f"/simulation/{uid}")
    assert resp.status == 307
    assert resp.headers["Location"] == "/declaration/12345678/2019"
    assert "api-key" in resp.cookies


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


async def test_send_code_endpoint(client, monkeypatch, body):
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
    resp = await client.post("/simulation/unknown/send-code", body=body)
    assert resp.status == 400
    assert json.loads(resp.body) == {
        "error": 'Invalid data: invalid input syntax for type uuid: "unknown"'
    }
    assert not calls

    # Not found UUID
    resp = await client.post(
        "/simulation/12345678-1234-5678-9012-123456789012/send-code",
        body=body,
    )
    assert resp.status == 404
    assert not calls

    # Create simulation
    uid = await db.simulation.create(
        {
            "déclaration": {"formValidated": "Valid"},
            "entreprise": {"siren": "12345678"},
            "informations": {"année_indicateurs": 2019},
        }
    )

    # Missing email
    resp = await client.post(f"/simulation/{uid}/send-code", body=body)
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
    # Only public data should be returned: https://github.com/SocialGouv/egapro-api/pull/14
    await db.declaration.put(
        "12345673",
        2019,
        "foo@bar.org",
        {
            "déclaration": {"index": 95, "année_indicateurs": 2019},
            "id": "12345678-1234-5678-9012-123456789015",
            "entreprise": {
                "raison_sociale": "Bio c Bon moins de 1000",
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


async def test_declare_with_flat_data(client, body):
    flat_body = {
        "id": "1234",
        "status": "valid",
        "déclaration.année_indicateurs": 2019,
        "déclaration.période_référence": ["2019-01-01", "2019-12-31"],
        "déclarant.email": "foo@bar.org",
        "déclarant.prénom": "Foo",
        "déclarant.nom": "Bar",
        "entreprise.raison_sociale": "FooBar",
        "entreprise.siren": "514027945",
        "entreprise.région": "76",
        "entreprise.département": "12",
        "entreprise.adresse": "12, rue des adresses",
        "entreprise.commune": "Y",
    }
    resp = await client.put(
        "/declaration/514027945/2019",
        body=flat_body,
        headers={"Accept": "application/vnd.egapro.v1.flat+json"},
    )
    assert resp.status == 204
    declaration = await db.declaration.get("514027945", 2019)
    assert declaration["data"] == body
    resp = await client.get(
        "/declaration/514027945/2019",
        headers={"Accept": "application/vnd.egapro.v1.flat+json"},
    )
    assert resp.status == 200
    data = json.loads(resp.body)
    assert data["data"] == flat_body


async def test_invalid_declaration_data_should_raise_on_put(client):
    resp = await client.put(
        "/declaration/514027945/2019",
        body={"foo": "bar"},
    )
    assert resp.status == 422
    assert json.loads(resp.body) == {"error": "False schema does not allow '\"foo\"'"}


async def test_invalid_declaration_data_should_raise_on_patch(client, body):
    await client.put("/declaration/514027945/2019", body=body)
    resp = await client.patch(
        "/declaration/514027945/2019",
        body={"foo": "bar"},
    )
    assert resp.status == 422
    assert json.loads(resp.body) == {"error": "False schema does not allow '\"foo\"'"}


async def test_put_declaration_should_compute_notes(client, body):
    body["indicateurs"] = {"rémunérations": {"mode": "csp", "résultat": 5.28}}
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    declaration = await db.declaration.get("514027945", 2019)
    assert declaration["data"]["indicateurs"]["rémunérations"]["note"] == 34


async def test_patch_declaration_should_compute_notes(client, declaration):
    await declaration(siren="514027945", year=2018, owner="foo@bar.org")
    resp = await client.patch(
        "/declaration/514027945/2018",
        body={"indicateurs": {"rémunérations": {"mode": "csp", "résultat": 18.75}}},
    )
    assert resp.status == 204
    data = (await db.declaration.get("514027945", 2018))["data"]
    assert data["indicateurs"]["rémunérations"]["note"] == 5
