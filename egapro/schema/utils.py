from egapro import constants
from naf import DB as NAF


def regions():
    return {"type": "string", "enum": constants.REGIONS.keys()}


def departements():
    return {"type": "string", "enum": constants.DEPARTEMENTS.keys()}


def naf():
    return {"type": "string", "enum": NAF.keys()}


def years():
    return {
        "type": "integer",
        "minimum": constants.YEARS[0],
        "maximum": constants.YEARS[-1],
    }


def clean_readonly(data, schema):
    if not data:
        return
    for key, subschema in schema.get("properties", {}).items():
        if subschema.get("readOnly"):
            try:
                del data[key]
            except KeyError:
                pass
            continue
        clean_readonly(data.get(key), subschema)
