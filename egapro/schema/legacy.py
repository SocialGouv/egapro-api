from datetime import datetime, timezone

import pytz

from egapro import constants, utils

TRANCHES = {"50 à 250": "50:250", "251 à 999": "251:999", "1000 et plus": "1000:"}
MOTIFS_NON_CALCULABLE = {
    "egvinf40pcet": "egvi40pcet",
    "absretcm": "absrcm",
    "absaugpdtcong": "absaugpdtcm",
}
REVERSED_REGIONS = {v: k for k, v in constants.REGIONS.items()}
REVERSED_REGIONS.update({"Ile-de-France": "11", "Grand Est": "44"})
REVERSED_DEPARTEMENTS = {v: k for k, v in constants.DEPARTEMENTS.items()}
REVERSED_DEPARTEMENTS.update(
    {"Côtes-d'armor": "22", "Val-d'oise": "95", "Côte-d'or": "21"}
)


def parse_datetime(v):
    if not v:
        return None
    paris = pytz.timezone("Europe/Paris")
    dt = datetime.strptime(v, "%d/%m/%Y %H:%M")
    dt = paris.localize(dt)
    return dt.astimezone(timezone.utc).isoformat()


def parse_date(v):
    if not v:
        return None
    return datetime.strptime(v, "%d/%m/%Y").date().isoformat()


def from_legacy(data):
    source = data.get("source", "egapro")
    data["déclarant"] = data.pop("informationsDeclarant", {})
    clean_legacy(data["déclarant"])

    data["entreprise"] = data.pop("informationsEntreprise", {})
    entreprise = data["entreprise"]
    ues = entreprise.get("structure") == "Unité Economique et Sociale (UES)"
    clean_legacy(entreprise)
    if entreprise.get("code_naf"):
        entreprise["code_naf"] = entreprise["code_naf"][:6]
    if "région" in entreprise:
        entreprise["région"] = REVERSED_REGIONS.get(entreprise.get("région"))
    if "département" in entreprise:
        entreprise["département"] = REVERSED_DEPARTEMENTS.get(
            entreprise.get("département")
        )
    nom_ues = entreprise.pop("nomUES", entreprise.get("raison_sociale", ""))
    if "entreprisesUES" in entreprise or ues:
        entreprises = [
                {"raison_sociale": e.get("nom"), "siren": e["siren"]}
                for e in entreprise.pop("entreprisesUES", [])
            ]
        declarante = {
            "raison_sociale": entreprise["raison_sociale"],
            "siren": entreprise["siren"],
        }
        if declarante not in entreprises:
            entreprises.insert(0, declarante)
        entreprise["ues"] = {
            "raison_sociale": nom_ues,
            "entreprises": entreprises,
        }
    if not ues:
        try:
            del entreprise["ues"]
        except KeyError:
            pass

    data["indicateurs"] = {
        "rémunérations": data.pop("indicateurUn", {}),
        "augmentations": data.pop("indicateurDeux", {}),
        "augmentations_et_promotions": data.pop("indicateurDeuxTrois", {}),
        "promotions": data.pop("indicateurTrois", {}),
        "congés_maternité": data.pop("indicateurQuatre", {}),
        "hautes_rémunérations": data.pop("indicateurCinq", {}),
    }
    # Make sure we do not use motifNonCalculable for solen data when data is calculable.
    if data.get("source", "").startswith("solen"):
        for indicateur in data["indicateurs"].values():
            if not indicateur.get("nonCalculable"):
                try:
                    del indicateur["motifNonCalculable"]
                except KeyError:
                    pass
    declaration = data["déclaration"] = data.pop("declaration", {})
    informations = data.pop("informations", {})
    declaration["année_indicateurs"] = informations.pop("anneeDeclaration", None)
    declaration["période_référence"] = [
        parse_date(informations.get("debutPeriodeReference")),
        parse_date(informations.get("finPeriodeReference")),
    ]
    if "mesuresCorrection" in declaration:
        value = declaration.pop("mesuresCorrection")
        if value not in (None, ""):
            declaration["mesures_correctives"] = value
    publication = {}
    if declaration.get("datePublication"):
        publication["date"] = parse_date(declaration["datePublication"])
    modalites = declaration.get("lienPublication")
    if modalites and modalites.lower().startswith(("http", "www")):
        publication["url"] = modalites
    elif modalites:
        publication["modalités"] = modalites
    declaration["publication"] = publication
    clean_legacy(declaration)
    index = declaration.get("index") or 0
    if index >= 75:
        declaration.pop("mesures_correctives", None)
    elif index and not declaration.get("mesures_correctives"):
        # Fallback for declarations from 2019
        declaration["mesures_correctives"] = "me"
    declaration["date"] = parse_datetime(declaration.get("date"))
    if "date_consultation_cse" in declaration:
        declaration["date_consultation_cse"] = parse_date(
            declaration["date_consultation_cse"]
        )

    effectif = data.pop("effectif", {})
    clean_legacy(effectif)
    if "total" not in effectif:
        total = 0
        for category in effectif.pop("nombreSalaries", []):
            for tranche in category["tranchesAges"]:
                total += tranche["nombreSalariesFemmes"]
                total += tranche["nombreSalariesHommes"]
        effectif["total"] = total
    tranche = informations.get("trancheEffectifs")
    if tranche == "Plus de 250":
        if effectif["total"] >= 1000:
            tranche = "1000:"
        else:
            tranche = "251:999"
    else:
        tranche = TRANCHES.get(tranche)
    effectif["tranche"] = tranche
    entreprise["effectif"] = effectif

    # Un
    un = data["indicateurs"]["rémunérations"]
    mode = (
        un.get("autre")
        and "niveau_autre"
        or un.get("coef")
        and "niveau_branche"
        or un.get("csp")
        and "csp"
        or None
    )
    if not mode and "coefficient" in un:
        un["mode"] = "niveau_branche"
    if mode:
        un["mode"] = mode
    categories = []
    key = "remunerationAnnuelle" if un.get("mode") == "csp" else "coefficient"
    for idx, category in enumerate(un.get(key, [])):
        if "tranchesAges" not in category:
            continue
        tranches = {
            ":29": None,
            "30:39": None,
            "40:49": None,
            "50:": None,
        }
        for i, key in enumerate(tranches):
            ta = category["tranchesAges"][i]
            if "ecartTauxRemuneration" in ta:
                tranches[key] = ta["ecartTauxRemuneration"]
                if not source.startswith("solen"):
                    tranches[key] *= 100
            elif (h := ta.get("remunerationAnnuelleBrutHommes")) and (
                f := ta.get("remunerationAnnuelleBrutFemmes")
            ):
                tranches[key] = (1 - f / h) * 100
        tranches = {k: v for k, v in tranches.items() if v is not None}
        categories.append(
            {
                "nom": category.get("nom", f"tranche {idx}"),
                "tranches": tranches,
            }
        )
    un["catégories"] = categories
    clean_legacy(un)
    if un.get("résultat") == 0:
        un.pop("population_favorable", None)

    # Deux
    deux = data["indicateurs"]["augmentations"]
    if not deux.get("nonCalculable"):
        deux["catégories"] = [
            c.get("ecartTauxAugmentation") for c in deux.get("tauxAugmentation", [])
        ]
    clean_legacy(deux)
    if effectif["tranche"] == "50:250":
        deux.clear()
    if deux.get("résultat") == 0:
        deux.pop("population_favorable", None)

    # # DeuxTrois
    deux_trois = data["indicateurs"]["augmentations_et_promotions"]
    clean_legacy(deux_trois)
    if effectif["tranche"] != "50:250":
        deux_trois.clear()
    if (
        deux_trois.get("résultat") == 0
        and deux_trois.get("résultat_nombre_salariés") == 0
    ):
        deux_trois.pop("population_favorable", None)
    # Missing in some Egapro declarations
    if not deux_trois.get("non_calculable"):
        # in percent
        if deux_trois.get("note_en_pourcentage") is None:
            note = utils.compute_note(
                deux_trois.get("résultat"),
                utils.AUGMENTATIONS_PROMOTIONS_THRESHOLDS,
            )
            if note is not None:
                deux_trois["note_en_pourcentage"] = note

        # in absolute
        if deux_trois.get("note_nombre_salariés") is None:
            note = utils.compute_note(
                deux_trois.get("résultat_nombre_salariés"),
                utils.AUGMENTATIONS_PROMOTIONS_THRESHOLDS,
            )
            if note is not None:
                deux_trois["note_nombre_salariés"] = note

    # Trois
    trois = data["indicateurs"]["promotions"]
    if not trois.get("nonCalculable"):
        trois["catégories"] = [
            c.get("ecartTauxPromotion") for c in trois.get("tauxPromotion", [])
        ]
    clean_legacy(trois)
    if effectif["tranche"] == "50:250":
        trois.clear()
    if trois.get("résultat") == 0:
        trois.pop("population_favorable", None)

    # Quatre
    quatre = data["indicateurs"]["congés_maternité"]
    clean_legacy(quatre)

    # Cinq
    cinq = data["indicateurs"]["hautes_rémunérations"]
    clean_legacy(cinq)
    if cinq.get("résultat") == 5:
        cinq.pop("population_favorable", None)
    # if 5 < cinq["résultat"] < 10:
    #     cinq["résultat"] = 10 - cinq["résultat"]
    #     cinq["population_favorable"] = (
    #         "femmes" if cinq["population_favorable"] == "hommes" else "hommes"
    #     )
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
        "noteNombreSalaries": "note_nombre_salariés",
        "noteEcart": "note_en_pourcentage",
        "dateConsultationCSE": "date_consultation_cse",
        "dateDeclaration": "date",
        "totalPoint": "points",
        "totalPointCalculable": "points_calculables",
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
    non_calculable = legacy.get("non_calculable")
    if non_calculable:
        legacy.clear()
        legacy["non_calculable"] = non_calculable
