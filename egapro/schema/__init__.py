import sys
from collections import namedtuple
from dataclasses import dataclass
from pathlib import Path

import fastjsonschema
import ujson as json
from stdnum.fr.siren import is_valid as siren_is_valid

from egapro import constants
from egapro.utils import import_by_path
from egapro.models import Data

SCHEMA = None
JSON_SCHEMA = None


def init():
    path = Path(__file__).parent / "raw.yml"
    schema = Schema(path.read_text()).raw
    globals()["SCHEMA"] = schema
    try:
        globals()["JSON_SCHEMA"] = fastjsonschema.compile(schema)
    except ValueError as err:
        print(json.dumps(schema))
        sys.exit(err)


def validate(data):
    try:
        JSON_SCHEMA(data)
    except fastjsonschema.JsonSchemaException as err:
        raise ValueError(err)


def cross_validate(data):
    try:
        _cross_validate(data)
    except AssertionError as err:
        raise ValueError(err)


def _cross_validate(data):
    data = Data(data)
    if data.validated:
        # Those keys are only required if the data is validated
        required = [
            "entreprise.région",
            "entreprise.département",
            "entreprise.adresse",
            "entreprise.commune",
            "entreprise.code_postal",
            "entreprise.code_naf",
            "déclarant.prénom",
            "déclarant.nom",
            "déclarant.téléphone",
        ]
        for path in required:
            assert data.path(path), f"{path} must not be empty"
        dep = data.path("entreprise.département")
        region = data.path("entreprise.région")
        cp = data.path("entreprise.code_postal")
        msg = "entreprise.département and entreprise.région do not match"
        assert dep in constants.REGIONS_TO_DEPARTEMENTS[region], msg
        msg = "entreprise.département and entreprise.code_postal do not match"
        assert cp[:2] == dep or (dep in ["2A", "2B"] and cp[:2] == "20"), msg
        index = data.path("déclaration.index") or 0
        mesures_correctives = data.path("déclaration.mesures_correctives")
        if index and index >= 75:
            msg = "déclaration.mesures_correctives must not be set when déclaration.index >= 75"
            assert not mesures_correctives, msg
        elif index:
            msg = "déclaration.mesures_correctives must not be null when déclaration.index < 75"
            assert mesures_correctives, msg
        elif not index:
            msg = "déclaration.mesures_correctives must not be set when déclaration.index is 'non calculable'"
            assert not mesures_correctives, msg
    tranche = data.path("entreprise.effectif.tranche")
    if tranche == "50:250":
        paths = ("indicateurs.promotions", "indicateurs.augmentations")
        for path in paths:
            msg = f"{path} cannot be set if entreprise.effectif.tranche='50:250'"
            assert not data.path(path), msg
    else:
        path = "indicateurs.augmentations_et_promotions"
        msg = f"{path} cannot be set if entreprise.effectif.tranche is not '50:250'"
        assert not data.path(path), msg
    for key in SCHEMA["properties"]["indicateurs"]["properties"].keys():
        path = f"indicateurs.{key}"
        if data.path(f"{path}.non_calculable"):
            msg = f"{path} must not contain other key when set to non_calculable"
            assert list(data.path(path).keys()) == ["non_calculable"], msg
        elif data.path(path) is not None:
            resultat = data.path(f"{path}.résultat")
            msg = f"{path}.résultat must be set when indicateur is calculable"
            assert resultat is not None, msg
    keys = ["rémunérations", "augmentations", "promotions"]
    for key in keys:
        path = f"indicateurs.{key}"
        if data.path(f"{path}.résultat") == 0:
            msg = f"{path}.population_favorable must be empty if résultat=0"
            assert not data.path(f"{path}.population_favorable"), msg

    # Entreprise
    for ues in data.path("entreprise.ues.entreprises") or []:
        msg = f"Invalid siren: {ues['siren']}"
        assert siren_is_valid(ues["siren"]), msg

    # Rémunérations
    base = "indicateurs.rémunérations"
    if not data.path(f"{base}.non_calculable"):
        date_consultation_cse = data.path(f"{base}.date_consultation_cse")
        mode = data.path(f"{base}.mode")
        if mode == "csp":
            msg = f"{base}.date_consultation_cse must be empty if indicateurs.rémunérations.mode='csp'"
            assert not date_consultation_cse, msg
        elif mode in ["niveau_autre", "niveau_branche"]:
            msg = f"{base}.date_consultation_cse must be set if indicateurs.rémunérations.mode!='csp'"
            assert date_consultation_cse, msg

    # Augmentations et promotions
    base = "indicateurs.augmentations_et_promotions"
    if (
        data.path(f"{base}.résultat") == 0
        and data.path(f"{base}.résultat_nombre_salariés") == 0
    ):
        path = f"{base}.population_favorable"
        msg = f"{path} must be empty if résultat=0 and résultat_nombre_salariés=0"
        assert not data.path(path), msg

    # Hautes rémunérations
    base = "indicateurs.hautes_rémunérations"
    if data.path(f"{base}.résultat") == 5:
        msg = f"{base}.population_favorable must be empty if résultat=5"
        assert not data.path(f"{base}.population_favorable"), msg


def extrapolate(definition):
    # TODO: arbitrate between ?key: value and key: ?value
    if definition.startswith("?"):
        return {"oneOf": [{"type": "null"}, extrapolate(definition[1:])]}
    if definition in ("date", "time", "date-time", "uri", "email"):
        return {"type": "string", "format": definition}
    if definition in ("integer", "string", "boolean", "number"):
        return {"type": definition}
    if definition.startswith('r"') and definition.endswith('"'):
        return {"type": "string", "pattern": definition[2:-1]}
    if definition.startswith("python:"):
        path = definition[7:]
        definition = import_by_path(path)
        if callable(definition):
            definition = definition()
        return definition
    if definition.count(":") == 1:
        type_ = float if "." in definition else int
        out = {"type": "number" if type_ is float else "integer"}
        min_ = max_ = None
        minmax = definition.split(":")
        if len(minmax) == 2:
            min_, max_ = minmax
        elif definition.startswith(":"):
            max_ = minmax[0]
        else:
            min_ = minmax[0]
        if min_ is not None:
            out["minimum"] = type_(min_)
        if max_ is not None:
            out["maximum"] = type_(max_)
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
    readonly: bool = False

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
        if node.readonly:
            definition["readOnly"] = True
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
            if ": " in line or line.endswith(":"):
                if line.endswith(":"):
                    key = line[:-1]
                    definition = ""
                else:
                    key, definition = line.split(": ", maxsplit=1)
                if key.startswith("+"):
                    key = key[1:]
                    node.required = True
                if key.startswith("?"):
                    key = key[1:]
                    node.nullable = True
                if key.startswith("="):
                    key = key[1:]
                    node.readonly = True
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
