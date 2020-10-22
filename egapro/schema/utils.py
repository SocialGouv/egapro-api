from egapro import constants


def regions():
    return {"type": "string", "enum": constants.REGIONS.keys()}


def departements():
    return {"type": "string", "enum": constants.DEPARTEMENTS.keys()}
