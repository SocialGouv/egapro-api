from egapro import emails, models


def test_success_email_with_small_company():
    data = models.Data(
        {
            "id": "1234",
            "source": "formulaire",
            "déclaration": {
                "date": "2020-11-04T10:37:06+00:00",
                "année_indicateurs": 2019,
                "fin_période_référence": "2019-12-31",
                "index": 65,
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
                "effectif": {"total": 312, "tranche": "50:250"},
            },
            "indicateurs": {
                "promotions": {},
                "augmentations": {},
                "rémunérations": {
                    "mode": "csp",
                    "note": 38,
                    "résultat": 1.95,
                    "catégories": [
                        {"nom": "tranche 0", "tranches": {}},
                        {
                            "nom": "tranche 1",
                            "tranches": {
                                "50:": -8.6,
                                ":29": 4.6,
                                "30:39": -0.7,
                                "40:49": 5.2,
                            },
                        },
                        {
                            "nom": "tranche 2",
                            "tranches": {
                                "50:": 1.9,
                                ":29": 2.2,
                                "30:39": 1.1,
                                "40:49": 2.2,
                            },
                        },
                        {
                            "nom": "tranche 3",
                            "tranches": {
                                "50:": 22.5,
                                ":29": 7.6,
                                "30:39": 2.9,
                                "40:49": 6.4,
                            },
                        },
                    ],
                    "population_favorable": "hommes",
                },
                "congés_maternité": {"non_calculable": "absrcm"},
                "hautes_rémunérations": {
                    "note": 0,
                    "résultat": 0,
                    "population_favorable": "hommes",
                },
                "augmentations_et_promotions": {
                    "note": 0,
                    "résultat": 34.4888,
                    "note_en_pourcentage": 0,
                    "population_favorable": "hommes",
                    "note_nombre_salariés": 0,
                    "résultat_nombre_salariés": 11.4,
                },
            },
        }
    )
    txt, html = emails.success(url=data.uri, **data)
    # fmt: off
    assert html == """<html>
  <body>
    <p>Madame, Monsieur,</p>
    <p>Vous venez de procéder à la transmission aux services du ministre chargé du travail de vos indicateurs et de votre niveau de résultat en matière d’écart de rémunération entre les femmes et les hommes pour l'année {year} conformément aux dispositions de l’article D.1142-5 du code du travail. L’administration du travail accuse réception par le présent message de votre due transmission. Cet accusé réception ne vaut pas contrôle de conformité de vos déclarations.</p>

    <p>Vous avez déclaré un index global de 65, décliné par indicateurs comme suit :</p>
    <ul>
      <li>Indicateur écart de rémunérations : 38</li>
      <li>Indicateur écart de taux de promotion (pour les entreprises de plus de 250 salariés) : 0</li>
      <li>Indicateur retour de congés maternité : non calculable</li>
      <li>Indicateur hautes rémunérations: 0</li>
    </ul>
    <p>Si vous souhaitez visualiser ou modifier votre déclaration, veuillez cliquer sur le lien suivant : <a href="declaration/?siren=514027945&year=2019">declaration/?siren=514027945&year=2019</a></p>
    <p>Il conviendra de saisir de nouveau votre email ; puis les informations relatives à l’année au titre de laquelle les indicateurs sont calculés (2019) et au numéro Siren de votre entreprise (514027945).</p>
    <p>Pour tout renseignement utile, vous êtes invité à prendre contact avec les services de la DIRECCTE dont le siège de votre entreprise dépend.</p>
    <p>Veuillez agréer, Madame, Monsieur, nos salutations distinguées,</p>
    <p>Les services de l’administration du travail</p>
   </body>
</html>"""
    assert txt == """Madame, Monsieur,

Vous venez de procéder à la transmission aux services du ministre chargé du travail de vos indicateurs et de votre niveau de résultat en matière d’écart de rémunération entre les femmes et les hommes pour l'année 2019 conformément aux dispositions de l’article D.1142-5 du code du travail. L’administration du travail accuse réception par le présent message de votre due transmission. Cet accusé réception ne vaut pas contrôle de conformité de vos déclarations.

Vous avez déclaré un index global de 65, décliné par indicateurs comme suit :

- Indicateur écart de rémunérations : 38
- Indicateur écart de taux de promotion (pour les entreprises de plus de 250 salariés) : 0
- Indicateur retour de congés maternité : non calculable
- Indicateur hautes rémunérations: 0

Si vous souhaitez visualiser ou modifier votre déclaration, veuillez cliquer sur le lien suivant :

declaration/?siren=514027945&year=2019

Il conviendra de saisir de nouveau votre email ; puis les informations relatives à l’année au titre de laquelle les indicateurs sont calculés (2019) et au numéro Siren de votre entreprise (514027945).

Pour tout renseignement utile, vous êtes invité à prendre contact avec les services de la DIRECCTE dont le siège de votre entreprise dépend.

Veuillez agréer, Madame, Monsieur, nos salutations distinguées,
Les services de l’administration du travail."""

    # fmt: on


def test_success_email_with_small_company_non_calculable_index():
    data = models.Data(
        {
            "id": "1234",
            "source": "formulaire",
            "déclaration": {
                "date": "2020-11-04T10:37:06+00:00",
                "année_indicateurs": 2019,
                "fin_période_référence": "2019-12-31",
                "index": None,
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
                "effectif": {"total": 312, "tranche": "50:250"},
            },
            "indicateurs": {
                "promotions": {},
                "augmentations": {},
                "rémunérations": {
                    "mode": "csp",
                    "note": 38,
                    "résultat": 1.95,
                    "catégories": [
                        {"nom": "tranche 0", "tranches": {}},
                        {
                            "nom": "tranche 1",
                            "tranches": {
                                "50:": -8.6,
                                ":29": 4.6,
                                "30:39": -0.7,
                                "40:49": 5.2,
                            },
                        },
                        {
                            "nom": "tranche 2",
                            "tranches": {
                                "50:": 1.9,
                                ":29": 2.2,
                                "30:39": 1.1,
                                "40:49": 2.2,
                            },
                        },
                        {
                            "nom": "tranche 3",
                            "tranches": {
                                "50:": 22.5,
                                ":29": 7.6,
                                "30:39": 2.9,
                                "40:49": 6.4,
                            },
                        },
                    ],
                    "population_favorable": "hommes",
                },
                "congés_maternité": {"non_calculable": "absrcm"},
                "hautes_rémunérations": {
                    "note": 0,
                    "résultat": 0,
                    "population_favorable": "hommes",
                },
                "augmentations_et_promotions": {
                    "note": 0,
                    "résultat": 34.4888,
                    "note_en_pourcentage": 0,
                    "population_favorable": "hommes",
                    "note_nombre_salariés": 0,
                    "résultat_nombre_salariés": 11.4,
                },
            },
        }
    )
    txt, html = emails.success(url=data.uri, **data)
    assert "Vous avez déclaré un index global non calculable," in html
    assert "Vous avez déclaré un index global non calculable," in txt


def test_success_email_with_big_company():
    data = models.Data(
        {
            "id": "1234",
            "source": "formulaire",
            "déclaration": {
                "date": "2020-11-04T10:37:06+00:00",
                "année_indicateurs": 2019,
                "fin_période_référence": "2019-12-31",
                "index": 65,
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
                "effectif": {"total": 312, "tranche": "1000:"},
            },
            "indicateurs": {
                "promotions": {
                    "note": 15,
                    "résultat": 2.83,
                    "catégories": [None, None, -1.41, -1.42],
                    "population_favorable": "femmes",
                },
                "augmentations": {
                    "note": 20,
                    "résultat": 0.66,
                    "catégories": [None, -0.34, 0.77, 0.23],
                    "population_favorable": "hommes",
                },
                "rémunérations": {
                    "mode": "csp",
                    "note": 38,
                    "résultat": 1.95,
                    "catégories": [
                        {"nom": "tranche 0", "tranches": {}},
                        {
                            "nom": "tranche 1",
                            "tranches": {
                                "50:": -8.6,
                                ":29": 4.6,
                                "30:39": -0.7,
                                "40:49": 5.2,
                            },
                        },
                        {
                            "nom": "tranche 2",
                            "tranches": {
                                "50:": 1.9,
                                ":29": 2.2,
                                "30:39": 1.1,
                                "40:49": 2.2,
                            },
                        },
                        {
                            "nom": "tranche 3",
                            "tranches": {
                                "50:": 22.5,
                                ":29": 7.6,
                                "30:39": 2.9,
                                "40:49": 6.4,
                            },
                        },
                    ],
                    "population_favorable": "hommes",
                },
                "congés_maternité": {"note": 15, "résultat": 100.0},
                "hautes_rémunérations": {
                    "note": 0,
                    "résultat": 0,
                    "population_favorable": "hommes",
                },
                "augmentations_et_promotions": {},
            },
        }
    )
    txt, html = emails.success(url=data.uri, **data)
    assert "Indicateur écart de taux d'augmentation : 20" in html
    assert "Indicateur écart de taux de promotion : 15" in html
    assert "(pour les entreprises de plus de 250 salariés)" not in html
    assert "Indicateur écart de taux d'augmentation : 20" in txt
    assert "Indicateur écart de taux de promotion : 15" in txt
    assert "(pour les entreprises de plus de 250 salariés)" not in txt
