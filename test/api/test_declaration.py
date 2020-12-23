import json

import pytest

from egapro import db

pytestmark = pytest.mark.asyncio


# Minimal body to send post requests
@pytest.fixture
def body():
    return {
        "id": "1234",
        "source": "formulaire",
        "déclaration": {
            "date": "2020-11-04T10:37:06+00:00",
            "année_indicateurs": 2019,
            "fin_période_référence": "2019-12-31",
        },
        "déclarant": {
            "email": "foo@bar.org",
            "prénom": "Foo",
            "nom": "Bar",
            "téléphone": "+33123456789",
        },
        "entreprise": {
            "raison_sociale": "FooBar",
            "siren": "514027945",
            "code_naf": "47.25Z",
            "code_postal": "12345",
            "région": "76",
            "département": "12",
            "adresse": "12, rue des adresses",
            "commune": "Y",
            "effectif": {"total": 312, "tranche": "251:999"},
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
        "error": "Il est possible de déclarer seulement pour les années 2018, 2019, 2020"
    }


async def test_put_declaration_with_empty_body(client):
    resp = await client.put("/declaration/514027945/2019", body="")
    assert resp.status == 400


async def test_put_declaration_with_invalid_json(client):
    resp = await client.put("/declaration/514027945/2019", body="<foo>bar</foo>")
    assert resp.status == 400


async def test_put_declaration_with_empty_json(client):
    resp = await client.put("/declaration/514027945/2019", body="{}")
    assert resp.status == 422


async def test_basic_declaration_should_save_data(client, body):
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    resp = await client.get("/declaration/514027945/2019")
    assert resp.status == 200
    data = json.loads(resp.body)
    assert "modified_at" in data
    del data["modified_at"]
    assert data["declared_at"]
    del data["declared_at"]
    del data["data"]["déclaration"]["date"]
    del body["déclaration"]["date"]
    assert data == {"data": body, "siren": "514027945", "year": 2019}
    # Just to make sure we have the same result on an existing declaration
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    resp = await client.get("/declaration/514027945/2019")
    assert resp.status == 200
    data = json.loads(resp.body)
    assert "modified_at" in data
    del data["modified_at"]
    assert data["declared_at"]
    del data["declared_at"]
    del data["data"]["déclaration"]["date"]
    assert data == {"data": body, "siren": "514027945", "year": 2019}


async def test_draft_declaration_should_save_data(client, body):
    # Draft
    body["déclaration"]["brouillon"] = True
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    resp = await client.get("/declaration/514027945/2019")
    assert resp.status == 200
    data = json.loads(resp.body)
    assert "modified_at" in data
    del data["modified_at"]
    assert not data.get("declared_at")
    assert "date" not in data["data"]["déclaration"]
    assert data["data"]["déclaration"]["brouillon"] is True
    del body["déclaration"]["date"]
    assert data == {
        "data": body,
        "siren": "514027945",
        "year": 2019,
        "declared_at": None,
    }

    # Real
    del body["déclaration"]["brouillon"]
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    resp = await client.get("/declaration/514027945/2019")
    assert resp.status == 200
    data = json.loads(resp.body)
    assert "modified_at" in data
    del data["modified_at"]
    assert data.get("declared_at")
    del data["declared_at"]
    assert data["data"]["déclaration"]["date"]
    del data["data"]["déclaration"]["date"]
    assert data == {"data": body, "siren": "514027945", "year": 2019}

    # Draft again
    body["déclaration"]["brouillon"] = True
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    resp = await client.get("/declaration/514027945/2019")
    assert resp.status == 200
    data = json.loads(resp.body)
    assert "modified_at" in data
    del data["modified_at"]
    assert data.get("declared_at")
    del data["declared_at"]
    assert data["data"]["déclaration"]["date"]
    del data["data"]["déclaration"]["date"]
    assert data["data"]["déclaration"]["brouillon"] is True
    assert data == {"data": body, "siren": "514027945", "year": 2019}


async def test_basic_declaration_without_declarant_should_be_ok(client, body):
    del body["déclarant"]
    del body["déclaration"]["date"]
    body["déclaration"]["brouillon"] = True
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    resp = await client.get("/declaration/514027945/2019")
    assert resp.status == 200
    data = json.loads(resp.body)
    assert "modified_at" in data
    assert data["data"]["déclarant"] == {"email": "foo@bar.org"}


async def test_owner_email_should_be_lower_cased(client, body):
    client.login("FoO@BAZ.baR")
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    assert await db.declaration.owner("514027945", 2019) == "foo@baz.bar"


async def test_basic_declaration_should_remove_data_namespace_if_present(client, body):
    await client.put("/declaration/514027945/2019", body={"data": body})
    data = await db.declaration.get("514027945", "2019")
    del data["data"]["déclaration"]["date"]
    del body["déclaration"]["date"]
    assert data["data"] == body


async def test_cannot_load_not_owned_declaration(client, monkeypatch):
    async def mock_owner(*args, **kwargs):
        return "foo@bar.baz"

    monkeypatch.setattr("egapro.db.declaration.owner", mock_owner)
    client.login("other@email.com")
    resp = await client.get("/declaration/514027945/2019")
    assert resp.status == 403
    assert json.loads(resp.body) == {
        "error": "Cette déclaration a été créée par un autre utilisateur"
    }


async def test_staff_can_load_not_owned_declaration(client, monkeypatch, declaration):
    async def mock_owner(*args, **kwargs):
        return "foo@bar.baz"

    await declaration(siren="514027945", year=2019)
    monkeypatch.setattr("egapro.config.STAFF", ["staff@email.com"])
    monkeypatch.setattr("egapro.db.declaration.owner", mock_owner)
    client.login("Staff@email.com")
    resp = await client.get("/declaration/514027945/2019")
    assert resp.status == 200


async def test_cannot_put_not_owned_declaration(client, monkeypatch):
    async def mock_owner(*args, **kwargs):
        return "foo@bar.baz"

    monkeypatch.setattr("egapro.db.declaration.owner", mock_owner)
    client.login("other@email.com")
    resp = await client.put("/declaration/514027945/2019")
    assert resp.status == 403
    assert json.loads(resp.body) == {
        "error": "Cette déclaration a déjà été créée par un autre utilisateur"
    }


async def test_owner_check_is_lower_case(client, body):
    client.login("FOo@baR.com")
    await client.put("/declaration/514027945/2019", body=body)
    client.login("FOo@BAR.COM")
    body["entreprise"]["raison_sociale"] = "newnew"
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    record = await db.declaration.get("514027945", 2019)
    assert record["data"]["déclarant"]["email"] == "foo@bar.com"
    assert record["data"]["entreprise"]["raison_sociale"] == "newnew"


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
    company = "FooBar"
    del body["id"]

    def mock_send(to, subject, txt, html):
        print(txt)
        assert to == "foo@bar.org"
        assert "/declaration/?siren=514027945&year=2019" in txt
        assert "/declaration/?siren=514027945&year=2019" in html
        assert company in txt
        assert company in html
        nonlocal calls
        calls += 1

    body["déclaration"]["brouillon"] = True
    monkeypatch.setattr("egapro.emails.send", mock_send)
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    assert not calls
    del body["déclaration"]["brouillon"]
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    assert calls == 1


async def test_confirmed_declaration_should_send_email_for_legacy_call(
    client, monkeypatch, body
):
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

    body["déclaration"]["brouillon"] = True
    monkeypatch.setattr("egapro.emails.send", mock_send)
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    assert not calls
    del body["déclaration"]["brouillon"]
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    assert calls == 1


async def test_confirmed_declaration_should_raise_if_missing_entreprise_data(
    client, monkeypatch, body
):
    del body["entreprise"]["région"]
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    body = json.loads(resp.body)
    assert body == {"error": "entreprise.région must not be empty"}


async def test_with_unknown_siren_or_year(client):
    resp = await client.get("/declaration/514027945/2019")
    assert resp.status == 404


async def test_invalid_declaration_data_should_raise_on_put(client):
    resp = await client.put(
        "/declaration/514027945/2019",
        body={"foo": "bar"},
    )
    assert resp.status == 422
    assert json.loads(resp.body) == {"error": "data.déclaration.date must be string"}


async def test_cannot_set_augmentations_if_tranche_is_not_50_250(client, body):
    body["indicateurs"] = {
        "rémunérations": {"mode": "csp", "résultat": 5.28},
        "augmentations": {"résultat": 5.03},
        "augmentations_et_promotions": {
            "résultat": 4.73,
            "résultat_nombre_salariés": 5.5,
        },
        "promotions": {"résultat": 2.03},
        "congés_maternité": {"résultat": 88},
        "hautes_rémunérations": {"résultat": 3},
    }
    body["déclaration"]["mesures_correctives"] = "mmo"
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    assert (
        json.loads(resp.body)["error"]
        == "indicateurs.augmentations_et_promotions cannot be set if entreprise.effectif.tranche is not '50:250'"
    )


async def test_population_favorable_must_be_empty_if_resultat_is_zero(client, body):
    body["indicateurs"] = {
        "rémunérations": {
            "mode": "csp",
            "résultat": 0,
            "population_favorable": "femmes",
        },
        "augmentations": {"résultat": 5.03},
        "promotions": {"résultat": 2.03},
        "congés_maternité": {"résultat": 88},
        "hautes_rémunérations": {"résultat": 3},
    }
    body["déclaration"]["mesures_correctives"] = "mmo"
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    assert (
        json.loads(resp.body)["error"]
        == "indicateurs.rémunérations.population_favorable must be empty if résultat=0"
    )


async def test_population_favorable_must_be_empty_if_resultat_is_0_on2et3(client, body):
    body["entreprise"]["effectif"]["tranche"] = "50:250"
    body["indicateurs"] = {
        "augmentations_et_promotions": {
            "résultat": 0,
            "résultat_nombre_salariés": 0,
            "population_favorable": "femmes",
        },
    }
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    assert (
        json.loads(resp.body)["error"]
        == "indicateurs.augmentations_et_promotions.population_favorable must be empty if résultat=0 and résultat_nombre_salariés=0"
    )


async def test_population_favorable_must_be_empty_if_resultat_is_five(client, body):
    body["indicateurs"] = {
        "rémunérations": {
            "mode": "csp",
            "résultat": 20,
        },
        "augmentations": {"résultat": 5.03},
        "promotions": {"résultat": 2.03},
        "congés_maternité": {"résultat": 88},
        "hautes_rémunérations": {"résultat": 5, "population_favorable": "femmes"},
    }
    body["déclaration"]["mesures_correctives"] = "mmo"
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    assert (
        json.loads(resp.body)["error"]
        == "indicateurs.hautes_rémunérations.population_favorable must be empty if résultat=5"
    )


async def test_mesures_correctives_must_be_set_if_index_below_75(client, body):
    body["indicateurs"] = {
        "rémunérations": {
            "mode": "csp",
            "résultat": 10,
            "population_favorable": "femmes",
        },
        "augmentations": {"résultat": 15.03},
        "promotions": {"résultat": 15.03},
        "congés_maternité": {"résultat": 88},
        "hautes_rémunérations": {"résultat": 3},
    }
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    assert (
        json.loads(resp.body)["error"]
        == "déclaration.mesures_correctives must not be null when déclaration.index < 75"
    )


async def test_mesures_correctives_must_not_be_set_if_index_above_75(client, body):
    body["indicateurs"] = {
        "rémunérations": {
            "mode": "csp",
            "résultat": 0,
        },
        "augmentations": {"résultat": 1.03},
        "promotions": {"résultat": 2.03},
        "congés_maternité": {"résultat": 88},
        "hautes_rémunérations": {"résultat": 1},
    }
    body["déclaration"]["mesures_correctives"] = "mmo"
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    assert (
        json.loads(resp.body)["error"]
        == "déclaration.mesures_correctives must not be set when déclaration.index >= 75"
    )


async def test_cannot_set_promotions_if_tranche_is_50_250(client, body):
    body["entreprise"]["effectif"]["tranche"] = "50:250"
    body["indicateurs"] = {
        "rémunérations": {"mode": "csp", "résultat": 5.28},
        "promotions": {"résultat": 2.03},
        "augmentations": {"résultat": 5.03},
        "augmentations_et_promotions": {
            "résultat": 4.73,
            "résultat_nombre_salariés": 5.5,
        },
        "congés_maternité": {"résultat": 88},
        "hautes_rémunérations": {"résultat": 3},
    }
    body["déclaration"]["mesures_correctives"] = "mmo"
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    assert (
        json.loads(resp.body)["error"]
        == "indicateurs.promotions cannot be set if entreprise.effectif.tranche='50:250'"
    )


async def test_put_declaration_should_compute_notes(client, body):
    body["indicateurs"] = {
        "rémunérations": {"mode": "csp", "résultat": 5.28},
        "augmentations": {"résultat": 5.03},
        "augmentations_et_promotions": {},
        "promotions": {"résultat": 2.03},
        "congés_maternité": {"résultat": 88},
        "hautes_rémunérations": {"résultat": 3},
    }
    body["déclaration"]["mesures_correctives"] = "mmo"
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    data = (await db.declaration.get("514027945", 2019))["data"]
    assert data["indicateurs"]["rémunérations"]["note"] == 34
    assert data["indicateurs"]["augmentations"]["note"] == 10
    assert data["indicateurs"]["promotions"]["note"] == 15
    assert data["indicateurs"]["congés_maternité"]["note"] == 0
    assert data["indicateurs"]["hautes_rémunérations"]["note"] == 5
    assert data["déclaration"]["points"] == 64
    assert data["déclaration"]["points_calculables"] == 100
    assert data["déclaration"]["index"] == 64


async def test_put_declaration_should_compute_notes_for_50_250(client, body):
    body["entreprise"]["effectif"]["tranche"] = "50:250"
    body["indicateurs"] = {
        "rémunérations": {"mode": "csp", "résultat": 5.28},
        "augmentations": {},
        "augmentations_et_promotions": {
            "résultat": 4.73,
            "résultat_nombre_salariés": 5.5,
        },
        "promotions": {},
        "congés_maternité": {"résultat": 88},
        "hautes_rémunérations": {"résultat": 3},
    }
    body["déclaration"]["mesures_correctives"] = "mmo"
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    data = (await db.declaration.get("514027945", 2019))["data"]
    assert data["indicateurs"]["rémunérations"]["note"] == 34
    assert (
        data["indicateurs"]["augmentations_et_promotions"]["note_nombre_salariés"] == 15
    )
    assert (
        data["indicateurs"]["augmentations_et_promotions"]["note_en_pourcentage"] == 25
    )
    assert data["indicateurs"]["augmentations_et_promotions"]["note"] == 25
    assert data["indicateurs"]["congés_maternité"]["note"] == 0
    assert data["indicateurs"]["hautes_rémunérations"]["note"] == 5
    assert data["déclaration"]["points"] == 64
    assert data["déclaration"]["points_calculables"] == 100
    assert data["déclaration"]["index"] == 64


async def test_date_consultation_cse_must_be_empty_if_mode_is_csp(client, body):
    body["indicateurs"] = {
        "rémunérations": {
            "mode": "csp",
            "date_consultation_cse": "2020-01-18",
            "résultat": 10,
        },
    }
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    assert json.loads(resp.body)["error"] == (
        "indicateurs.rémunérations.date_consultation_cse must be empty "
        "if indicateurs.rémunérations.mode='csp'"
    )


async def test_basic_declaration_with_ues(client, body):
    body["entreprise"]["ues"] = {
        "nom": "Nom UES",
        "entreprises": [{"siren": "123456782", "raison_sociale": "Foobarbaz"}],
    }
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204
    resp = await client.get("/declaration/514027945/2019")
    assert resp.status == 200
    data = json.loads(resp.body)
    assert "modified_at" in data
    del data["modified_at"]
    assert data["declared_at"]
    del data["declared_at"]
    del data["data"]["déclaration"]["date"]
    del body["déclaration"]["date"]
    assert data == {"data": body, "siren": "514027945", "year": 2019}


async def test_basic_declaration_with_ues_and_invalid_siren(client, body):
    body["entreprise"]["ues"] = {
        "nom": "Nom UES",
        "entreprises": [{"siren": "invalid", "raison_sociale": "Foobarbaz"}],
    }
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    assert json.loads(resp.body) == {"error": "Invalid siren: invalid"}


async def test_basic_declaration_with_ues_and_missing_siren(client, body):
    body["entreprise"]["ues"] = {
        "nom": "Nom UES",
        "entreprises": [{"raison_sociale": "Foobarbaz"}],
    }
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    assert json.loads(resp.body) == {
        "error": "data.entreprise.ues.entreprises[0] must contain ['raison_sociale', 'siren'] properties"
    }


async def test_basic_declaration_with_niveau_branche(client, body):
    body["indicateurs"] = {
        "rémunérations": {
            "mode": "niveau_branche",
            "date_consultation_cse": "2020-12-12",
            "résultat": 35,
        }
    }
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 204


async def test_basic_declaration_with_niveau_branche_without_cse(client, body):
    body["indicateurs"] = {"rémunérations": {"mode": "niveau_branche", "résultat": 15}}
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    assert json.loads(resp.body) == {
        "error": "indicateurs.rémunérations.date_consultation_cse must be set if indicateurs.rémunérations.mode!='csp'"
    }


async def test_basic_declaration_without_resultat(client, body):
    body["indicateurs"] = {"augmentations": {"catégories": [1, 2, 3, 4]}}
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    assert json.loads(resp.body) == {
        "error": "indicateurs.augmentations.résultat must be set when indicateur is calculable"
    }


async def test_remunerations_declaration_without_resultat(client, body):
    body["indicateurs"] = {
        "rémunérations": {"mode": "csp", "population_favorable": "femmes"}
    }
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    assert json.loads(resp.body) == {
        "error": "indicateurs.rémunérations.résultat must be set when indicateur is calculable"
    }


async def test_put_declaration_with_invalid_region(client, body):
    body["entreprise"]["région"] = "88"
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422


async def test_put_declaration_with_departement_and_region_mismatch(client, body):
    body["entreprise"]["région"] = "11"
    body["entreprise"]["département"] = "11"
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    assert json.loads(resp.body) == {
        "error": "entreprise.département and entreprise.région do not match"
    }


async def test_put_declaration_with_code_postal_and_region_mismatch(client, body):
    body["entreprise"]["code_postal"] = "54321"
    body["entreprise"]["département"] = "12"
    resp = await client.put("/declaration/514027945/2019", body=body)
    assert resp.status == 422
    assert json.loads(resp.body) == {
        "error": "entreprise.département and entreprise.code_postal do not match"
    }


async def test_declare_with_legacy_schema(client, body):
    legacy = {
        "id": "5e41ad88-5dcc-491d-908a-93d5d2fae344",
        "effectif": {
            "formValidated": "Valid",
            "nombreSalaries": [
                {
                    "tranchesAges": [
                        {
                            "trancheAge": 0,
                            "nombreSalariesFemmes": 0,
                            "nombreSalariesHommes": 0,
                        },
                        {
                            "trancheAge": 1,
                            "nombreSalariesFemmes": 0,
                            "nombreSalariesHommes": 0,
                        },
                        {
                            "trancheAge": 2,
                            "nombreSalariesFemmes": 0,
                            "nombreSalariesHommes": 0,
                        },
                        {
                            "trancheAge": 3,
                            "nombreSalariesFemmes": 0,
                            "nombreSalariesHommes": 0,
                        },
                    ],
                    "categorieSocioPro": 0,
                },
                {
                    "tranchesAges": [
                        {
                            "trancheAge": 0,
                            "nombreSalariesFemmes": 23,
                            "nombreSalariesHommes": 7,
                        },
                        {
                            "trancheAge": 1,
                            "nombreSalariesFemmes": 20,
                            "nombreSalariesHommes": 11,
                        },
                        {
                            "trancheAge": 2,
                            "nombreSalariesFemmes": 25,
                            "nombreSalariesHommes": 13,
                        },
                        {
                            "trancheAge": 3,
                            "nombreSalariesFemmes": 17,
                            "nombreSalariesHommes": 5,
                        },
                    ],
                    "categorieSocioPro": 1,
                },
                {
                    "tranchesAges": [
                        {
                            "trancheAge": 0,
                            "nombreSalariesFemmes": 0,
                            "nombreSalariesHommes": 2,
                        },
                        {
                            "trancheAge": 1,
                            "nombreSalariesFemmes": 3,
                            "nombreSalariesHommes": 3,
                        },
                        {
                            "trancheAge": 2,
                            "nombreSalariesFemmes": 2,
                            "nombreSalariesHommes": 2,
                        },
                        {
                            "trancheAge": 3,
                            "nombreSalariesFemmes": 0,
                            "nombreSalariesHommes": 1,
                        },
                    ],
                    "categorieSocioPro": 2,
                },
                {
                    "tranchesAges": [
                        {
                            "trancheAge": 0,
                            "nombreSalariesFemmes": 0,
                            "nombreSalariesHommes": 0,
                        },
                        {
                            "trancheAge": 1,
                            "nombreSalariesFemmes": 0,
                            "nombreSalariesHommes": 0,
                        },
                        {
                            "trancheAge": 2,
                            "nombreSalariesFemmes": 0,
                            "nombreSalariesHommes": 1,
                        },
                        {
                            "trancheAge": 3,
                            "nombreSalariesFemmes": 0,
                            "nombreSalariesHommes": 0,
                        },
                    ],
                    "categorieSocioPro": 3,
                },
            ],
            "nombreSalariesTotal": 135,
        },
        "declaration": {
            "noteIndex": 94,
            "totalPoint": 94,
            "formValidated": "Valid",
            "dateDeclaration": "14/02/2020 16:02",
            "datePublication": "14/02/2020",
            "lienPublication": "La note globale est portée à la connaissance des collaborateurs sur le panneau d'affichage qui leur est dédié.",
            "mesuresCorrection": "",
            "dateConsultationCSE": "",
            "totalPointCalculable": 100,
        },
        "indicateurUn": {
            "csp": True,
            "coef": False,
            "autre": False,
            "noteFinale": 39,
            "coefficient": [],
            "formValidated": "Valid",
            "resultatFinal": 0.1433,
            "sexeSurRepresente": "hommes",
            "motifNonCalculable": "",
            "remunerationAnnuelle": [
                {
                    "tranchesAges": [
                        {"trancheAge": 0},
                        {"trancheAge": 1},
                        {"trancheAge": 2},
                        {"trancheAge": 3},
                    ],
                    "categorieSocioPro": 0,
                },
                {
                    "tranchesAges": [
                        {
                            "trancheAge": 0,
                            "remunerationAnnuelleBrutFemmes": 21302,
                            "remunerationAnnuelleBrutHommes": 21916,
                        },
                        {
                            "trancheAge": 1,
                            "remunerationAnnuelleBrutFemmes": 21328,
                            "remunerationAnnuelleBrutHommes": 22169,
                        },
                        {
                            "trancheAge": 2,
                            "remunerationAnnuelleBrutFemmes": 21228,
                            "remunerationAnnuelleBrutHommes": 22182,
                        },
                        {
                            "trancheAge": 3,
                            "remunerationAnnuelleBrutFemmes": 21242,
                            "remunerationAnnuelleBrutHommes": 22297,
                        },
                    ],
                    "categorieSocioPro": 1,
                },
                {
                    "tranchesAges": [
                        {"trancheAge": 0},
                        {
                            "trancheAge": 1,
                            "remunerationAnnuelleBrutFemmes": 26466,
                            "remunerationAnnuelleBrutHommes": 28778,
                        },
                        {"trancheAge": 2},
                        {"trancheAge": 3},
                    ],
                    "categorieSocioPro": 2,
                },
                {
                    "tranchesAges": [
                        {"trancheAge": 0},
                        {"trancheAge": 1},
                        {"trancheAge": 2},
                        {"trancheAge": 3},
                    ],
                    "categorieSocioPro": 3,
                },
            ],
            "motifNonCalculablePrecision": "",
            "coefficientGroupFormValidated": "None",
            "coefficientEffectifFormValidated": "None",
        },
        "informations": {
            "formValidated": "Valid",
            "nomEntreprise": "SAS PERDRIX",
            "anneeDeclaration": 2019,
            "trancheEffectifs": "50 à 250",
            "finPeriodeReference": "31/12/2019",
            "debutPeriodeReference": "01/01/2019",
        },
        "indicateurCinq": {
            "noteFinale": 5,
            "formValidated": "Valid",
            "resultatFinal": 3,
            "sexeSurRepresente": "hommes",
            "nombreSalariesFemmes": 3,
            "nombreSalariesHommes": 7,
        },
        "indicateurDeux": {
            "formValidated": "None",
            "tauxAugmentation": [
                {"categorieSocioPro": 0},
                {"categorieSocioPro": 1},
                {"categorieSocioPro": 2},
                {"categorieSocioPro": 3},
            ],
            "mesuresCorrection": False,
            "motifNonCalculable": "",
            "presenceAugmentation": True,
            "motifNonCalculablePrecision": "",
        },
        "indicateurTrois": {
            "formValidated": "None",
            "tauxPromotion": [
                {"categorieSocioPro": 0},
                {"categorieSocioPro": 1},
                {"categorieSocioPro": 2},
                {"categorieSocioPro": 3},
            ],
            "mesuresCorrection": False,
            "presencePromotion": True,
            "motifNonCalculable": "",
            "motifNonCalculablePrecision": "",
        },
        "indicateurQuatre": {
            "noteFinale": 15,
            "formValidated": "Valid",
            "resultatFinal": 100,
            "presenceCongeMat": True,
            "motifNonCalculable": "",
            "nombreSalarieesAugmentees": 1,
            "motifNonCalculablePrecision": "",
            "nombreSalarieesPeriodeAugmentation": 1,
        },
        "indicateurDeuxTrois": {
            "noteFinale": 35,
            "formValidated": "Valid",
            "mesuresCorrection": False,
            "sexeSurRepresente": "hommes",
            "motifNonCalculable": "",
            "periodeDeclaration": "unePeriodeReference",
            "resultatFinalEcart": 2.2222,
            "motifNonCalculablePrecision": "",
            "resultatFinalNombreSalaries": 1,
            "presenceAugmentationPromotion": True,
            "nombreAugmentationPromotionFemmes": 8,
            "nombreAugmentationPromotionHommes": 5,
        },
        "informationsDeclarant": {
            "nom": "FOOBAR",
            "tel": "0238295999",
            "email": "foobar@foobar.fr",
            "prenom": "CAROLINE",
            "formValidated": "Valid",
            "acceptationCGU": True,
        },
        "informationsEntreprise": {
            "siren": "514027945",
            "nomUES": "",
            "region": "Centre-Val de Loire",
            "adresse": "4 RUE DE SAVOIE",
            "codeNaf": "47.11F - Hypermarchés",
            "commune": "SAINTE MERE SUR LOIR",
            "structure": "Entreprise",
            "codePostal": "45100",
            "departement": "Loiret",
            "formValidated": "Valid",
            "nomEntreprise": "SAS PERDRIX",
            "entreprisesUES": [],
        },
    }

    resp = await client.put("/declaration/514027945/2019", body=legacy)
    assert resp.status == 204
    declaration = await db.declaration.get("514027945", 2019)
    expected = {
        "id": "5e41ad88-5dcc-491d-908a-93d5d2fae344",
        "source": "simulateur",
        "déclarant": {
            "nom": "FOOBAR",
            "email": "foo@bar.org",
            "prénom": "CAROLINE",
            "téléphone": "0238295999",
        },
        "entreprise": {
            "siren": "514027945",
            "adresse": "4 RUE DE SAVOIE",
            "commune": "SAINTE MERE SUR LOIR",
            "région": "24",
            "code_naf": "47.11F",
            "effectif": {"total": 135, "tranche": "50:250"},
            "code_postal": "45100",
            "département": "45",
            "raison_sociale": "SAS PERDRIX",
        },
        "indicateurs": {
            "promotions": {},
            "augmentations_et_promotions": {
                "note": 35,
                "résultat": 2.2222,
                "note_en_pourcentage": 25,
                "note_nombre_salariés": 35,
                "population_favorable": "hommes",
                "résultat_nombre_salariés": 1,
            },
            "rémunérations": {
                "mode": "csp",
                "note": 39,
                "résultat": 0.1433,
                "catégories": [
                    {
                        "nom": "tranche 0",
                        "tranches": {},
                    },
                    {
                        "nom": "tranche 1",
                        "tranches": {
                            "50:": 4.7315782392,
                            ":29": 2.8016061325,
                            "30:39": 3.7935856376,
                            "40:49": 4.3007844198,
                        },
                    },
                    {
                        "nom": "tranche 2",
                        "tranches": {
                            "30:39": 8.033914796,
                        },
                    },
                    {
                        "nom": "tranche 3",
                        "tranches": {},
                    },
                ],
                "population_favorable": "hommes",
            },
            "congés_maternité": {"note": 15, "résultat": 100},
            "hautes_rémunérations": {
                "note": 5,
                "résultat": 3,
                "population_favorable": "hommes",
            },
            "augmentations": {},
        },
        "déclaration": {
            "index": 94,
            "points": 94,
            "publication": {
                "date": "2020-02-14",
                "modalités": "La note globale est portée à la connaissance des collaborateurs sur le panneau d'affichage qui leur est dédié.",
            },
            "année_indicateurs": 2019,
            "points_calculables": 100,
            "fin_période_référence": "2019-12-31",
        },
    }
    declared_at = declaration["data"]["déclaration"].pop("date")
    assert declared_at
    assert declaration["data"] == expected

    # Make sure we support {"data": {"data": {}}} and "id" at root level
    id_ = legacy.pop("id")
    resp = await client.put(
        "/declaration/514027945/2019", body={"data": legacy, "id": id_}
    )
    assert resp.status == 204
    declaration = await db.declaration.get("514027945", 2019)
    assert declaration.data["id"] == "5e41ad88-5dcc-491d-908a-93d5d2fae344"
