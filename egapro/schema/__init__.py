from collections import namedtuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import ujson as json


def parse_datetime(v):
    return datetime.strptime(v, "%d/%m/%Y %H:%M").isoformat() + "Z"


def parse_date(v):
    return datetime.strptime(v, "%d/%m/%Y").date().isoformat()


def init():
    path = Path(__file__).parent / "raw.yml"
    globals()["SCHEMA"] = Schema(path.read_text()).raw


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
    if definition.startswith("[") and definition.endswith("]"):
        values = definition[1:-1].split(",")
        if len(values) > 1:
            items = [extrapolate(v.strip()) for v in values]
        else:
            items = extrapolate(values[0])
        return {"type": "array", "items": items}
    raise ValueError(f"Unknown type {definition!r}")


def from_legacy(data):
    data["declarant"] = data.pop("informationsDeclarant", {})
    clean_legacy(data["declarant"])

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

    # Un
    un = data["indicateurs"]["rémunérations"]
    un["mode"] = un["autre"] and "autre" or un["coef"] and "coef" or "csp"
    niveaux = []
    # TODO coefficient
    for idx, category in enumerate(un.get("remunerationAnnuelle", [])):
        if "tranchesAges" not in category:
            continue
        niveaux.append(
            {
                "nom": category.get("nom", f"tranche {idx}"),
                "tranches": {
                    "<29": category["tranchesAges"][0].get("ecartTauxRemuneration", 0)
                },
            }
        )
    un["niveaux"] = niveaux
    clean_legacy(un)

    # Deux
    deux = data["indicateurs"]["augmentations"]
    if not deux.get("motifNonCalculable"):
        niveaux = []
        for idx, category in enumerate(deux.get("tauxAugmentation", [])):
            if "tranchesAges" not in category:
                continue
            niveaux.append(
                {
                    "nom": category.get("nom", f"tranche {idx}"),
                    "tranches": {
                        "<29": category["tranchesAges"][0].get(
                            "ecartTauxAugmentation", 0
                        )
                    },
                }
            )
        deux["niveaux"] = niveaux
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
        niveaux = []
        for idx, category in enumerate(trois.get("tauxPromotion", [])):
            if "tranchesAges" not in category:
                continue
            niveaux.append(
                {
                    "nom": category.get("nom", f"tranche {idx}"),
                    "tranches": {
                        "<29": category["tranchesAges"][0].get("ecartTauxPromotion", 0)
                    },
                }
            )
        trois["niveaux"] = niveaux
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
        "resultatFinal": "resultat",
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
        "totalPointCalculable": "total_points_calculable",
        "nombreSalariesTotal": "total",
        "codeNaf": "code_naf",
        "codePostal": "code_postal",
        "nomEntreprise": "raison_sociale",
        "tel": "téléphone",
        "prenom": "prénom",
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
        "nomUES",
    ]
    for k in to_delete:
        try:
            del legacy[k]
        except KeyError:
            pass


def count_indent(s):
    for i, c in enumerate(s):
        if c != " ":
            return i
    return len(s)


class ParsingError(Exception):
    def __init__(self, msg, line):
        super().__init__(f"{line.index}: {msg} in `{line.key}`")


Line = namedtuple("Line", ["index", "indent", "key", "value", "kind", "description"])


@dataclass
class Node:
    index: int
    indent: int
    key: str = None
    definition: str = None
    description: str = None
    required: bool = False
    kind: str = None
    strict: bool = True
    nullable: bool = False

    def __bool__(self):
        return bool(self.key or self.definition)


class Property:
    def __init__(self, line):
        self.line = line


class StopRecursivity(Exception):
    def __init__(self, indent):
        self.indent = indent


class Object(dict):
    def __init__(self, node=None):
        kwargs = {
            "type": "object",
            "properties": {},
            "additionalProperties": node and not node.strict or False,
        }
        super().__init__(**kwargs)

    def add(self, node, definition=None):
        if definition is None:
            definition = extrapolate(node.definition)
        if node.description:
            definition["description"] = node.description
        if node.nullable:
            definition = {"anyOf": [{"type": "null"}, definition]}
        self["properties"][node.key] = definition
        if node.required:
            self.required(node.key)

    def required(self, key):
        if "required" not in self:
            self["required"] = []
        self["required"].append(key)


class Array(dict):
    def __init__(self, node):
        kwargs = {
            "type": "array",
            "items": {},
        }
        super().__init__(**kwargs)

    def add(self, node, definition=None):
        if node.key:
            if not self["items"]:
                self["items"] = Object()
            self["items"].add(node, definition)
        else:
            self["items"] = extrapolate(node.definition)
            if node.description:
                self["items"]["description"] = node.description


class Schema:
    def __init__(self, raw):
        self.raw = json.loads(json.dumps(self.load(raw.splitlines())))

    @staticmethod
    def iter_lines(iterable):
        previous = Node(0, 0)
        current = None
        for index, raw in enumerate(iterable):
            indent = count_indent(raw)
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            node = Node(index, indent)
            if line.startswith("- "):
                line = line[2:]
                node.kind = "array"
                node.indent += 2
            if ":" in line:
                key, definition = line.split(":", maxsplit=1)
                if key.startswith("+"):
                    key = key[1:]
                    node.required = True
                if key.startswith("?"):
                    key = key[1:]
                    node.nullable = True
                if key.startswith("~"):
                    key = key[1:]
                    node.strict = False
                if key.startswith('"') and key.endswith('"'):
                    key = key[1:-1]
                node.key = key.lower()
            else:
                definition = line
            description = None
            if "#" in definition:
                definition, description = definition.split("#")
                node.description = description.strip()
            definition = definition.strip()
            if definition.startswith('"') and definition.endswith('"'):
                definition = definition[1:-1]
            node.definition = definition
            next_ = node
            if current:
                yield (previous, current, next_)
                previous = current
            current = next_
        yield (previous, current, Node(0, 0))

    @classmethod
    def load(cls, lines, parent=None):
        if parent is None:
            parent = Object()
            lines = cls.iter_lines(lines)
        for (prev, curr, next_) in lines:
            if curr.indent % 2 != 0:
                raise ParsingError("Wrong indentation", curr)
            if curr.indent != prev.indent and parent is None:
                raise ParsingError("Wrong indentation", curr)
            if curr.definition:
                parent.add(curr)
            if next_.indent < curr.indent:
                raise StopRecursivity(indent=next_.indent)
                # Move back one step up in recursivity.
            elif next_.indent > curr.indent:  # One more indent
                # Are we an array or an object ?
                if next_.kind == "array":
                    children = Array(curr)
                else:
                    children = Object(curr)
                if curr.key:
                    parent.add(curr, children)
                try:
                    Schema.load(lines, children)
                except StopRecursivity as err:
                    if err.indent < curr.indent:
                        raise
                    continue  # We are on the right level.
        return parent


init()
