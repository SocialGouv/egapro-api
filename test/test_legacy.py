from egapro.schema.legacy import from_legacy


def test_from_legacy_solen():
    legacy = {
        "id": "1162z18z1z906z-1zB82CA6D199",
        "source": "solen-2019",
        "effectif": {"nombreSalariesTotal": 2543.0},
        "declaration": {
            "noteIndex": 100,
            "totalPoint": 100,
            "formValidated": "Valid",
            "dateDeclaration": "20/02/2019 12:47",
            "datePublication": "20/02/2019",
            "lienPublication": "néant",
            "totalPointCalculable": 100,
        },
        "indicateurUn": {
            "csp": True,
            "coef": False,
            "autre": False,
            "noteFinale": 40,
            "nonCalculable": False,
            "resultatFinal": 0.0,
            "sexeSurRepresente": "femmes",
            "remunerationAnnuelle": [
                {
                    "tranchesAges": [
                        {"trancheAge": 0, "ecartTauxRemuneration": 2.8},
                        {"trancheAge": 1, "ecartTauxRemuneration": 0.6},
                        {"trancheAge": 2, "ecartTauxRemuneration": 1.5},
                        {"trancheAge": 3, "ecartTauxRemuneration": 3.7},
                    ],
                    "categorieSocioPro": 0,
                },
                {
                    "tranchesAges": [
                        {"trancheAge": 0, "ecartTauxRemuneration": -10.8},
                        {"trancheAge": 1, "ecartTauxRemuneration": 0.1},
                        {"trancheAge": 2, "ecartTauxRemuneration": -11.3},
                        {"trancheAge": 3, "ecartTauxRemuneration": 11.1},
                    ],
                    "categorieSocioPro": 1,
                },
                {
                    "tranchesAges": [
                        {"trancheAge": 0, "ecartTauxRemuneration": 5.0},
                        {"trancheAge": 1, "ecartTauxRemuneration": 2.3},
                        {"trancheAge": 2, "ecartTauxRemuneration": 2.8},
                        {"trancheAge": 3, "ecartTauxRemuneration": 0.2},
                    ],
                    "categorieSocioPro": 2,
                },
                {
                    "tranchesAges": [
                        {"trancheAge": 0, "ecartTauxRemuneration": 1.1},
                        {"trancheAge": 1, "ecartTauxRemuneration": 5.2},
                        {"trancheAge": 2, "ecartTauxRemuneration": 7.1},
                        {"trancheAge": 3, "ecartTauxRemuneration": 12.2},
                    ],
                    "categorieSocioPro": 3,
                },
            ],
        },
        "informations": {
            "anneeDeclaration": 2018,
            "trancheEffectifs": "1000 et plus",
            "finPeriodeReference": "31/12/2018",
            "debutPeriodeReference": "01/01/2018",
        },
        "indicateurCinq": {
            "noteFinale": 10,
            "resultatFinal": 5,
            "sexeSurRepresente": "femmes",
        },
        "indicateurDeux": {
            "noteFinale": 20,
            "nonCalculable": False,
            "resultatFinal": 0.1,
            "tauxAugmentation": [
                {"categorieSocioPro": 0, "ecartTauxAugmentation": 0.94},
                {"categorieSocioPro": 1, "ecartTauxAugmentation": 0.08},
                {"categorieSocioPro": 2, "ecartTauxAugmentation": -0.79},
                {"categorieSocioPro": 3, "ecartTauxAugmentation": -0.16},
            ],
            "sexeSurRepresente": "hommes",
            "presenceAugmentation": True,
        },
        "indicateurTrois": {
            "noteFinale": 15,
            "nonCalculable": False,
            "resultatFinal": 0.4,
            "tauxPromotion": [
                {"categorieSocioPro": 0, "ecartTauxPromotion": 0.94},
                {"categorieSocioPro": 1, "ecartTauxPromotion": 0.08},
                {"categorieSocioPro": 2, "ecartTauxPromotion": -0.64},
                {"categorieSocioPro": 3, "ecartTauxPromotion": 0.0},
            ],
            "presencePromotion": True,
            "sexeSurRepresente": "hommes",
        },
        "indicateurQuatre": {
            "noteFinale": 15,
            "nonCalculable": False,
            "resultatFinal": 100.0,
            "presenceCongeMat": True,
        },
        "informationsDeclarant": {
            "nom": "FOOBAR",
            "tel": "616534899",
            "email": "kikoobar@kookoo.com",
            "prenom": "CLAIRE",
        },
        "informationsEntreprise": {
            "siren": "841600323",
            "region": "Nouvelle-Aquitaine",
            "codeNaf": "49.31Z - Transports urbains et suburbains de voyageurs",
            "structure": "Entreprise",
            "departement": "Gironde",
            "nomEntreprise": "KIKOOLIS",
        },
    }
    assert from_legacy(legacy) == {
        "déclarant": {
            "email": "kikoobar@kookoo.com",
            "nom": "FOOBAR",
            "prénom": "CLAIRE",
            "téléphone": "616534899",
        },
        "déclaration": {
            "année_indicateurs": 2018,
            "date": "2019-02-20T11:47:00+00:00",
            "index": 100,
            "points": 100,
            "points_calculables": 100,
            "publication": {"date": "2019-02-20", "modalités": "néant"},
            "période_référence": ["2018-01-01", "2018-12-31"],
        },
        "entreprise": {
            "code_naf": "49.31Z",
            "département": "33",
            "effectif": {"total": 2543.0, "tranche": "1000:"},
            "raison_sociale": "KIKOOLIS",
            "région": "75",
            "siren": "841600323",
        },
        "id": "1162z18z1z906z-1zB82CA6D199",
        "indicateurs": {
            "augmentations_et_promotions": {},
            "augmentations": {
                "catégories": [0.94, 0.08, -0.79, -0.16],
                "note": 20,
                "population_favorable": "hommes",
                "résultat": 0.1,
            },
            "congés_maternité": {"note": 15, "résultat": 100.0},
            "hautes_rémunérations": {
                "note": 10,
                "résultat": 5,
            },
            "promotions": {
                "catégories": [0.94, 0.08, -0.64, 0.0],
                "note": 15,
                "population_favorable": "hommes",
                "résultat": 0.4,
            },
            "rémunérations": {
                "catégories": [
                    {
                        "nom": "tranche 0",
                        "tranches": {
                            "30:39": 0.6,
                            "40:49": 1.5,
                            "50:": 3.7,
                            ":29": 2.8,
                        },
                    },
                    {
                        "nom": "tranche 1",
                        "tranches": {
                            "30:39": 0.1,
                            "40:49": -11.3,
                            "50:": 11.1,
                            ":29": -10.8,
                        },
                    },
                    {
                        "nom": "tranche 2",
                        "tranches": {
                            "30:39": 2.3,
                            "40:49": 2.8,
                            "50:": 0.2,
                            ":29": 5.0,
                        },
                    },
                    {
                        "nom": "tranche 3",
                        "tranches": {
                            "30:39": 5.2,
                            "40:49": 7.1,
                            "50:": 12.2,
                            ":29": 1.1,
                        },
                    },
                ],
                "mode": "csp",
                "note": 40,
                "résultat": 0.0,
            },
        },
        "source": "solen-2019",
    }
