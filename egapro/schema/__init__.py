from pathlib import Path

import yaml


def init():
    path = Path(__file__).parent / "raw.yml"
    globals()["SCHEMA"] = load(path.read_text())


def load(s):
    raw = yaml.safe_load(s)
    schema = {}
    walk(raw, schema)
    return schema


def walk(what, schema):
    """Walk through the raw schema and populate the real schema"""
    if isinstance(what, dict):
        print(schema)
        schema["type"] = "object"
        schema["properties"] = {}
        required = []
        for key, definition in what.items():
            if key.startswith("$"):
                schema[key] = definition
                continue
            if key.startswith("+"):
                key = key[1:]
                required.append(key)
            current = {}
            if isinstance(definition, dict):
                walk(definition, current)
            elif isinstance(definition, list):
                print("Found a list", definition)
                current.update({"type": "array", "items": {}})
                walk(definition[0], current["items"])
            else:
                definition = extrapolate(definition)
                print(f"Setting schema for key {key}: {definition}")
                current.update(definition)
            if key.startswith("="):
                key = key[1:]
                current["additionalProperties"] = False
            if key.startswith("?"):
                key = key[1:]
                current = {"anyOf": [{"type": "null"}, current]}
            schema["properties"][key] = current
            if required:
                schema["required"] = required
    elif isinstance(what, list):
        print("What is a list")
        schema.update({"type": "array", "items": {}})
        walk(what[0], schema["items"])
        # definition = extrapolate(what[0])
        # schema.update(definition)
    else:
        schema.update(extrapolate(what))


def extrapolate(definition):
    if definition in ("date", "time", "date-time", "uri", "email"):
        return {"type": "string", "format": definition}
    if definition in ("integer", "string", "boolean", "number"):
        return {"type": definition}
    if definition.count(":") == 1:
        out = {"type": "integer"}
        min_ = max_ = None
        minmax = definition.split(":")
        if len(minmax) == 2:
            min_, max_ = minmax
        elif definition.startswith(":"):
            max_ = minmax[0]
        else:
            min_ = minmax[0]
        if min_ is not None:
            out["minimum"] = int(min_)  # float ?
        if max_ is not None:
            out["maximum"] = int(max_)
        return out
    if "|" in definition:
        enum = definition.split("|")
        return {"type": "string", "enum": enum}
    raise ValueError(f"Unknown type {definition}")


def from_legacy(data):
    data["declarant"] = data.pop("informationsDeclarant", {})
    data["entreprise"] = data.pop("informationsEntreprise", {})
    entreprise = data["entreprise"]
    entreprise["structure"] = (
        "simple" if entreprise["structure"] == "Entreprise" else "ues"
    )
    entreprise["raison_sociale"] = entreprise.pop("nomEntreprise")
    data["indicateurs"] = {
        "un": data.pop("indicateurUn", {}),
        "deux": data.pop("indicateurDeux", {}),
        "deux_trois": data.pop("indicateurDeuxTrois", {}),
        "trois": data.pop("indicateurTrois", {}),
        "quatre": data.pop("indicateurQuatre", {}),
        "cinq": data.pop("indicateurCinq", {}),
    }
    data["declaration"]["annee_indicateurs"] = data["informations"].pop(
        "anneeDeclaration"
    )
    # Un
    un = data["indicateurs"]["un"]
    un["mode"] = un["autre"] and "autre" or un["coef"] and "coef" or "csp"
    remuneration_annuelle = []
    for category in un.pop("remunerationAnnuelle", []):
        remuneration_annuelle.append(
            [t.get("ecartTauxRemuneration", 0) for t in category["tranchesAges"]]
        )
    un["remuneration_annuelle"] = remuneration_annuelle
    from_legacy_indicateur(un)

    # Deux
    deux = data["indicateurs"]["deux"]
    taux_augmentation = []
    for category in deux.pop("tauxAugmentation", []):
        taux_augmentation.append(
            [
                t.get("ecartTauxAugmentation", 0)
                for t in category.get("tranchesAges", [])
            ]
        )
    deux["taux_augmentation"] = taux_augmentation
    from_legacy_indicateur(deux)

    # DeuxTrois
    deux_trois = data["indicateurs"]["deux_trois"]
    from_legacy_indicateur(deux_trois)

    # Trois
    trois = data["indicateurs"]["trois"]
    taux_promotion = []
    for category in trois.pop("tauxPromotion", []):
        taux_promotion.append(
            [
                t.get("ecartTauxPromotion", 0)
                for t in category.get("tranchesAges", [])
            ]
        )
    trois["taux_promotion"] = taux_promotion
    from_legacy_indicateur(trois)

    # Quatre
    quatre = data["indicateurs"]["quatre"]
    from_legacy_indicateur(quatre)

    # Cinq
    cinq = data["indicateurs"]["cinq"]
    from_legacy_indicateur(cinq)
    return data


def from_legacy_indicateur(legacy):
    mapping = {
        "motifNonCalculable": "non_calculable",
        "motifNonCalculablePrecision": "motif_non_calculable",
        "noteFinale": "note",
        "resultatFinal": "resultat",
        "sexeSurRepresente": "en_faveur_de",
        "mesuresCorrection": "mesures_correction",
        "presenceAugmentation": "presence_augmentation",
        "presencePromotion": "presence_promotion",
        # TODO understand and rename those fields
        "nombreSalarieesAugmentees": "salariees_augmentees",
        "nombreSalarieesPeriodeAugmentation": "salariees_augmentees_periode",
        "presenceCongeMat": "presence_conges_mat",
        "nombreSalariesFemmes": "salaries_femmes",
        "nombreSalariesHommes": "salaries_hommes",
        "presenceAugmentationPromotion": "presence_augmentation_promotion",
        "nombreAugmentationPromotionFemmes": "augmentation_femmes",
        "nombreAugmentationPromotionHommes": "augmentation_hommes",
        "periodeDeclaration": "periode_declaration",
        "resultatFinalEcart": "ecart_final",
        "resultatFinalNombreSalaries": "nombre_salaries",
        "noteEcart": "note_ecart",
        "noteNombreSalaries": "note_nombre_salarie",
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
    ]
    for k in to_delete:
        try:
            del legacy[k]
        except KeyError:
            pass


init()
