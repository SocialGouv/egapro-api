from datetime import datetime, timezone

from egapro import constants

TRANCHES = {"50 à 250": "50:250", "251 à 999": "251:999", "1000 et plus": "1000:"}
MOTIFS_NON_CALCULABLE = {
    "egvinf40pcet": "egvi40pcet",
    "absretcm": "absrcm",
    "absaugpdtcong": "absaugpdtcm",
}
REVERSED_REGIONS = {v: k for k, v in constants.REGIONS.items()}
REVERSED_REGIONS.update({"Ile-de-France": "11", "Grand Est": "44"})


def parse_datetime(v):
    return datetime.strptime(v, "%d/%m/%Y %H:%M").replace(tzinfo=timezone.utc)


def parse_date(v):
    return datetime.strptime(v, "%d/%m/%Y").date()


def from_legacy(data):
    data["déclarant"] = data.pop("informationsDeclarant", {})
    clean_legacy(data["déclarant"])

    data["entreprise"] = data.pop("informationsEntreprise", {})
    entreprise = data["entreprise"]
    clean_legacy(entreprise)
    if "région" in entreprise:
        entreprise["région"] = REVERSED_REGIONS.get(entreprise.get("région"))
    nom_ues = entreprise.pop("nomUES", entreprise.get("raison_sociale", ""))
    if "entreprisesUES" in entreprise:
        entreprise["ues"] = {
            "raison_sociale": nom_ues,
            "entreprises": [
                {"raison_sociale": e.get("nom"), "siren": e["siren"]}
                for e in entreprise.pop("entreprisesUES")
            ],
        }

    data["indicateurs"] = {
        "rémunérations": data.pop("indicateurUn", {}),
        "augmentations_hors_promotions": data.pop("indicateurDeux", {}),
        "augmentations": data.pop("indicateurDeuxTrois", {}),
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
    publication = {}
    if data["déclaration"].get("datePublication"):
        publication["date"] = parse_date(data["déclaration"]["datePublication"])
    modalites = data["déclaration"].get("lienPublication")
    if modalites and modalites.lower().startswith(("http", "www")):
        publication["url"] = modalites
    elif modalites:
        publication["modalités"] = modalites
    data["déclaration"]["publication"] = publication
    clean_legacy(data["déclaration"])
    data["déclaration"]["date"] = parse_datetime(data["déclaration"]["date"])

    effectif = data["effectif"]
    clean_legacy(effectif)
    if "total" not in effectif:
        total = 0
        for category in effectif.pop("nombreSalaries", []):
            for tranche in category["tranchesAges"]:
                total += tranche["nombreSalariesFemmes"]
                total += tranche["nombreSalariesHommes"]
        effectif["total"] = total
    tranche = data["informations"]["trancheEffectifs"]
    if tranche == "Plus de 250":
        if effectif["total"] >= 1000:
            tranche = "1000:"
        else:
            tranche = "251:999"
    else:
        tranche = TRANCHES[tranche]
    effectif["tranche"] = tranche
    entreprise["effectif"] = effectif
    del data["effectif"]

    # Un
    un = data["indicateurs"]["rémunérations"]
    un["mode"] = (
        un["autre"] and "autre" or un["coef"] and "coef" or un["csp"] and "csp" or None
    )
    if un["mode"] is None:
        un["mode"] = "coef" if "coefficient" in un and un["coefficient"] else "csp"
    categories = []
    # TODO coefficient
    key = "remunerationAnnuelle" if un["mode"] == "csp" else "coefficient"
    for idx, category in enumerate(un.get(key, [])):
        if "tranchesAges" not in category:
            continue
        categories.append(
            {
                "nom": category.get("nom", f"tranche {idx}"),
                "tranches": {
                    ":29": category["tranchesAges"][0].get("ecartTauxRemuneration", 0),
                    "30:39": category["tranchesAges"][1].get(
                        "ecartTauxRemuneration", 0
                    ),
                    "40:49": category["tranchesAges"][2].get(
                        "ecartTauxRemuneration", 0
                    ),
                    "50:": category["tranchesAges"][3].get("ecartTauxRemuneration", 0),
                },
            }
        )
    un["catégories"] = categories
    clean_legacy(un)

    # Deux
    deux = data["indicateurs"]["augmentations_hors_promotions"]
    if not deux.get("motifNonCalculable"):
        deux["catégories"] = [
            c.get("ecartTauxAugmentation", 0) for c in deux.get("tauxAugmentation", [])
        ]
    clean_legacy(deux)

    # # DeuxTrois
    deux_trois = data["indicateurs"]["augmentations"]
    clean_legacy(deux_trois)

    # Trois
    trois = data["indicateurs"]["promotions"]
    if not trois.get("motifNonCalculable"):
        trois["catégories"] = [
            c.get("ecartTauxPromotion", 0) for c in trois.get("tauxPromotion", [])
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
        "noteFinale": "note",
        "noteIndex": "index",
        "resultatFinal": "résultat",
        "sexeSurRepresente": "population_favorable",
        "resultatFinalEcart": "résultat",
        "resultatFinalNombreSalaries": "résultat_nombre_salariés",
        "noteNombreSalaries": "note",
        "noteEcart": "points_en_pourcentage",
        "dateConsultationCSE": "date_consultation_cse",
        "dateDeclaration": "date",
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
        if new == "non_calculable":
            value = MOTIFS_NON_CALCULABLE.get(value, value)
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
        "datePublication",
        "lienPublication",
        "structure",
        "motifNonCalculablePrecision",
        "nombreAugmentationPromotionFemmes",
        "nombreAugmentationPromotionHommes",
        "periodeDeclaration",
        "nombreSalarieesAugmentees",
        "nombreSalarieesPeriodeAugmentation",
        "nombreSalariesFemmes",
        "nombreSalariesHommes",
    ]
    for k in to_delete:
        try:
            del legacy[k]
        except KeyError:
            pass
