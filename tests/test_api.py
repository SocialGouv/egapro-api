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
    assert db.declaration.owner("514027945", "2020") == "foo@bar.org"
    config.REQUIRE_TOKEN = True


async def test_basic_declaration_should_save_data(client):
    resp = await client.put("/declaration/514027945/2020", body={"foo": "bar"})
    assert resp.status == 204
    resp = await client.get("/declaration/514027945/2020")
    assert resp.status == 200
    assert json.loads(resp.body) == {"foo": "bar"}


async def test_cannot_load_not_owned_declaration(client, monkeypatch):
    monkeypatch.setattr(
        "egapro.db.declaration.owner", lambda *args, **kwargs: "foo@bar.baz"
    )
    client.login("other@email.com")
    resp = await client.get("/declaration/514027945/2020")
    assert resp.status == 403


async def test_cannot_put_not_owned_declaration(client, monkeypatch):
    monkeypatch.setattr(
        "egapro.db.declaration.owner", lambda *args, **kwargs: "foo@bar.baz"
    )
    client.login("other@email.com")
    resp = await client.put("/declaration/514027945/2020")
    assert resp.status == 403


async def test_declaring_twice_should_not_duplicate(client, app):
    resp = await client.put("/declaration/514027945/2020", body={"foo": "bar"})
    assert resp.status == 204
    resp = await client.put("/declaration/514027945/2020", body={"foo": "baz"})
    assert resp.status == 204
    with db.declaration.conn as conn:
        curs = conn.execute(
            "SELECT data FROM declaration WHERE siren=? and year=?",
            ("514027945", "2020"),
        )
        data = curs.fetchall()
    assert len(data) == 1
    assert json.loads(data[0][0]) == {"foo": "baz"}


async def test_confirmed_declaration_should_send_email(client, monkeypatch):
    calls = 0

    def mock_send(to, subject, body):
        assert to == "foo@bar.org"
        assert "Votre déclaration est maintenant confirmée" in body
        nonlocal calls
        calls += 1

    monkeypatch.setattr("egapro.emails.send", mock_send)
    resp = await client.put("/declaration/514027945/2020", body={"foo": False})
    assert resp.status == 200
    assert not calls
    resp = await client.put("/declaration/514027945/2020", body={"confirm": False})
    assert resp.status == 200
    assert not calls
    resp = await client.put("/declaration/514027945/2020", body={"confirm": True})
    assert resp.status == 200
    assert calls == 1


async def test_with_unknown_siren_or_year(client):
    resp = await client.get("/declaration/514027945/2020")
    assert resp.status == 404
