import json

import pytest
from egapro import db

pytestmark = pytest.mark.asyncio


# Minimal simulation body
@pytest.fixture
def body():
    return {
        "id": "1234",
    }


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
    assert "modified_at" in data
    del data["modified_at"]
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
    assert "modified_at" in data
    del data["modified_at"]
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
                "entreprise": {"siren": "12345678"},
                "déclaration": {"année_indicateurs": 2019, "date": "2020-11-04"},
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
            "entreprise": {"siren": "12345678"},
            "déclaration": {"année_indicateurs": 2019, "date": "2020-11-04"},
        }
    )
    resp = await client.get(f"/simulation/{uid}")
    assert resp.status == 307
    assert resp.headers["Location"] == "/declaration/12345678/2019"
    assert "api-key" in resp.cookies


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
