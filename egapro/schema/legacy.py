from datetime import datetime

TRANCHES = {"50 à 250": "50:250", "251 à 999": "251:999", "1000 et plus": "1000:"}


def parse_datetime(v):
    return datetime.strptime(v, "%d/%m/%Y %H:%M").isoformat() + "Z"


def parse_date(v):
    return datetime.strptime(v, "%d/%m/%Y").date().isoformat()


def from_legacy(data):
    data["déclarant"] = data.pop("informationsDeclarant", {})
    clean_legacy(data["déclarant"])

    data["entreprise"] = data.pop("informationsEntreprise", {})
    entreprise = data["entreprise"]
    entreprise["structure"] = (
        "simple" if entreprise["structure"] == "Entreprise" else "ues"
    )
    clean_legacy(entreprise)
    if "entreprisesUES" in entreprise:
        entreprise["ues"] = {
            "raison_sociale": entreprise.pop("nomUES", ""),
            "entreprises": [
                {"raison_sociale": e.get("nom"), "siren": e["siren"]}
                for e in entreprise.pop("entreprisesUES")
            ],
        }

    data["indicateurs"] = {
        "rémunérations": data.pop("indicateurUn", {}),
        "augmentations": data.pop("indicateurDeux", {}),
        # "deux_trois": data.pop("indicateurDeuxTrois", {}),
        "promotions": data.pop("indicateurTrois", {}),
        "congés_maternité": data.pop("indicateurQuatre", {}),
        "hautes_rémunérations": data.pop("indicateurCinq", {}),
    }
    data["déclaration"] = data.pop("declaration")
    data["déclaration"]["année_indicateurs"] = data["informations"].pop(
        "anneeDeclaration"
    )
    data["déclaration"]["période_référence"] = [
        parse_date(data["informations"]["debutPeriodeReference"]),
        parse_date(data["informations"]["finPeriodeReference"]),
    ]
    if "mesuresCorrection" in data["déclaration"]:
        value = data["déclaration"].pop("mesuresCorrection")
        if value not in (None, ""):
            data["déclaration"]["mesures_correctives"] = value
    clean_legacy(data["déclaration"])
    data["déclaration"]["date_déclaration"] = parse_datetime(
        data["déclaration"]["date_déclaration"]
    )
    if data["déclaration"].get("date_publication"):
        data["déclaration"]["date_publication"] = parse_date(
            data["déclaration"]["date_publication"]
        )

    clean_legacy(data["effectif"])
    if "total" not in data["effectif"]:
        total = 0
        for category in data["effectif"].pop("nombreSalaries", []):
            for tranche in category["tranchesAges"]:
                total += tranche["nombreSalariesFemmes"]
                total += tranche["nombreSalariesHommes"]
        data["effectif"]["total"] = total
    tranche = data["informations"]["trancheEffectifs"]
    if tranche == "Plus de 250":
        if data["effectif"]["total"] >= 1000:
            tranche = "1000:"
        else:
            tranche = "251:999"
    else:
        tranche = TRANCHES[tranche]
    data["effectif"]["tranche"] = tranche

    # Un
    un = data["indicateurs"]["rémunérations"]
    un["mode"] = un["autre"] and "autre" or un["coef"] and "coef" or un["csp"] and "csp"
    if un["mode"] is None:
        un["mode"] = "coef" if "coefficient" in un and un["coefficient"] else "csp"
    niveaux = []
    # TODO coefficient
    key = "remunerationAnnuelle" if un["mode"] == "csp" else "coefficient"
    for idx, category in enumerate(un.get(key, [])):
        if "tranchesAges" not in category:
            continue
        niveaux.append(
            {
                "nom": category.get("nom", f"tranche {idx}"),
                "tranches": {
                    ":29": category["tranchesAges"][0].get(
                        "ecartTauxRemuneration", None
                    ),
                    "30:39": category["tranchesAges"][1].get(
                        "ecartTauxRemuneration", None
                    ),
                    "40:49": category["tranchesAges"][2].get(
                        "ecartTauxRemuneration", None
                    ),
                    "50:": category["tranchesAges"][3].get(
                        "ecartTauxRemuneration", None
                    ),
                },
            }
        )
    un["niveaux"] = niveaux
    clean_legacy(un)

    # Deux
    deux = data["indicateurs"]["augmentations"]
    if not deux.get("motifNonCalculable"):
        deux["niveaux"] = [
            c.get("ecartTauxAugmentation", None)
            for c in deux.get("tauxAugmentation", [])
        ]
    clean_legacy(deux)

    # # DeuxTrois
    # deux_trois = data["indicateurs"]["deux_trois"]
    # clean_legacy(deux_trois)
    # TODO
    try:
        del data["indicateurDeuxTrois"]
    except KeyError:
        pass

    # Trois
    trois = data["indicateurs"]["promotions"]
    if not trois.get("motifNonCalculable"):
        trois["niveaux"] = [
            c.get("ecartTauxPromotion", None) for c in trois.get("tauxPromotion", [])
        ]
    clean_legacy(trois)

    # Quatre
    quatre = data["indicateurs"]["congés_maternité"]
    clean_legacy(quatre)

    # Cinq
    cinq = data["indicateurs"]["hautes_rémunérations"]
    clean_legacy(cinq)
    del data["informations"]
    return data


def clean_legacy(legacy):
    mapping = {
        "motifNonCalculable": "non_calculable",
        "motifNonCalculablePrecision": "motif_non_calculable",
        "noteFinale": "note",
        "noteIndex": "index",
        "resultatFinal": "résultat",
        "sexeSurRepresente": "en_faveur_de",
        # TODO understand and rename those fields
        "nombreSalarieesAugmentees": "salariees_augmentees",
        "nombreSalarieesPeriodeAugmentation": "salariees_augmentees_periode",
        "nombreSalariesFemmes": "salaries_femmes",
        "nombreSalariesHommes": "salaries_hommes",
        "nombreAugmentationPromotionFemmes": "augmentation_femmes",
        "nombreAugmentationPromotionHommes": "augmentation_hommes",
        "periodeDeclaration": "periode_declaration",
        "resultatFinalEcart": "ecart_final",
        "resultatFinalNombreSalaries": "nombre_salaries",
        "noteEcart": "note_ecart",
        "noteNombreSalaries": "note_nombre_salarie",
        "dateConsultationCSE": "date_consultation_cse",
        "dateDeclaration": "date_déclaration",
        "datePublication": "date_publication",
        "lienPublication": "lien_publication",
        "totalPoint": "total_points",
        "totalPointCalculable": "total_points_calculables",
        "nombreSalariesTotal": "total",
        "codeNaf": "code_naf",
        "codePostal": "code_postal",
        "nomEntreprise": "raison_sociale",
        "tel": "téléphone",
        "prenom": "prénom",
        "region": "région",
        "departement": "département",
    }
    for old, new in mapping.items():
        value = legacy.pop(old, None)
        if value not in (None, ""):
            legacy[new] = value
    to_delete = [
        "autre",
        "coef",
        "csp",
        "coefficientEffectifFormValidated",
        "coefficientGroupFormValidated",
        "formValidated",
        "nombreCoefficients",
        "nonCalculable",
        "mesuresCorrection",
        "presenceAugmentation",
        "presencePromotion",
        "presenceAugmentationPromotion",
        "tauxAugmentation",
        "tauxPromotion",
        "remunerationAnnuelle",
        "presenceCongeMat",
        "coefficient",
        "nombreSalaries",
        "nombreEntreprises",
        "acceptationCGU",
    ]
    for k in to_delete:
        try:
            del legacy[k]
        except KeyError:
            pass
