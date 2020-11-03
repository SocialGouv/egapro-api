from egapro import constants
from naf import DB as NAF


def regions():
    return {"type": "string", "enum": constants.REGIONS.keys()}


def departements():
    return {"type": "string", "enum": constants.DEPARTEMENTS.keys()}


def naf():
    return {"type": "string", "enum": NAF.keys()}
