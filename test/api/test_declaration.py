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
            "code_naf": "47.25Z",
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
    assert "modified_at" in data
    del data["modified_at"]
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
    assert record["data"]["déclarant"]["email"] == "foo@bar.com"
    assert record["data"]["indicateurs"] == {}


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
        "entreprise.code_naf": "47.25Z",
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
    body["indicateurs"] = {
        "rémunérations": {"mode": "csp", "résultat": 5.28},
        "augmentations_hors_promotions": {"résultat": 5.03},
        "augmentations": {"résultat": 4.73, "résultat_nombre_salariés": 5.5},
        "promotions": {"résultat": 2.03},
        "congés_maternité": {"résultat": 88},
        "hautes_rémunérations": {"résultat": 3},
    }
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    data = (await db.declaration.get("514027945", 2019))["data"]
    assert data["indicateurs"]["rémunérations"]["note"] == 34
    assert data["indicateurs"]["augmentations_hors_promotions"]["note"] == 10
    assert data["indicateurs"]["augmentations"]["note_nombre_salariés"] == 15
    assert data["indicateurs"]["augmentations"]["note_en_pourcentage"] == 25
    assert data["indicateurs"]["augmentations"]["note"] == 25
    assert data["indicateurs"]["promotions"]["note"] == 15
    assert data["indicateurs"]["congés_maternité"]["note"] == 0
    assert data["indicateurs"]["hautes_rémunérations"]["note"] == 5
    assert data["déclaration"]["points"] == 89
    assert data["déclaration"]["points_calculables"] == 135
    assert data["déclaration"]["index"] == 66


async def test_patch_declaration_should_compute_notes(client, declaration):
    await declaration(siren="514027945", year=2018, owner="foo@bar.org")
    resp = await client.patch(
        "/declaration/514027945/2018",
        body={"indicateurs": {"rémunérations": {"mode": "csp", "résultat": 18.75}}},
    )
    assert resp.status == 204
    data = (await db.declaration.get("514027945", 2018))["data"]
    assert data["indicateurs"]["rémunérations"]["note"] == 5
