import math
from datetime import date, datetime, timezone
from importlib import import_module

import json


def default_json(v):
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return str(v)


def json_dumps(v):
    return json.dumps(v, default=default_json)


def utcnow():
    return datetime.now(timezone.utc)


def prepare_query(query):
    # TODO deal with edge cases ( | , !…)
    query = query.replace("&", " ")  # Escape &.
    query = " ".join(query.split())  # Remove multiple whitespaces.
    query = query.replace(" ", " & ")
    if not query.endswith("*"):
        # Prefix search on last token, to autocomplete.
        query = query + ":*"
    return query


def flatten(b, prefix="", delim=".", val=None, flatten_lists=False):
    # See https://stackoverflow.com/a/57228641/330911
    if val is None:
        val = {}
    if isinstance(b, dict):
        if prefix:
            prefix = prefix + delim
        for j in b.keys():
            flatten(b[j], prefix + j, delim, val, flatten_lists)
    elif flatten_lists and isinstance(b, list):
        get = b
        for j in range(len(get)):
            flatten(get[j], prefix + delim + str(j), delim, val, flatten_lists)
    else:
        val[prefix] = b
    return val


def unflatten(d, delim="."):
    # From https://stackoverflow.com/a/6037657
    result = dict()
    for key, value in d.items():
        parts = key.split(delim)
        d = result
        for part in parts[:-1]:
            if part not in d:
                d[part] = dict()
            d = d[part]
        d[parts[-1]] = value
    return result


def import_by_path(path):
    """
    Import variables, functions or class by their path. Should be of the form:
    path.to.module.func
    """
    if not isinstance(path, str):
        return path
    module_path, *name = path.rsplit(".", 1)
    func = import_module(module_path)
    if name:
        func = getattr(func, name[0])
    return func


def official_round(i):
    """The threshold is x.05, instead of x.5.

    So for example, 0.01 should be rounded to 0, while 0.1 should be rounded to 1.
    """
    return round(float(i) + 0.5 - 0.049)


REMUNERATIONS_THRESHOLDS = {
    0.00: 40,
    0.05: 39,
    1.05: 38,
    2.05: 37,
    3.05: 36,
    4.05: 35,
    5.05: 34,
    6.05: 33,
    7.05: 31,
    8.05: 29,
    9.05: 27,
    10.05: 25,
    11.05: 23,
    12.05: 21,
    13.05: 19,
    14.05: 17,
    15.05: 14,
    16.05: 11,
    17.05: 8,
    18.05: 5,
    19.05: 2,
    20.05: 0,
}

AUGMENTATIONS_HP_THRESHOLDS = {
    0.00: 20,
    2.05: 10,
    5.05: 5,
    10.05: 0,
}

AUGMENTATIONS_PROMOTIONS_THRESHOLDS = {
    0.00: 35,
    2.05: 25,
    5.05: 15,
    10.05: 0,
}

PROMOTIONS_THRESHOLDS = {
    0.00: 15,
    2.05: 10,
    5.05: 5,
    10.05: 0,
}

CONGES_MATERNITE_THRESHOLDS = {
    0.0: 0,
    100.0: 15,
}

HAUTES_REMUNERATIONS_THRESHOLDS = {
    0: 0,
    2: 5,
    4: 10,
    6: 0,  # Align on old schema for now, any value > 5 means 0
}


def compute_note(resultat, thresholds):
    if resultat is None:
        return None
    try:
        resultat = round(float(resultat), 2)
    except ValueError:
        return None
    previous = 0
    for threshold, note in thresholds.items():
        if resultat >= threshold:
            previous = note
            continue
    return previous


def compute_notes(data):
    if "indicateurs" not in data:
        return
    points = 0
    maximum = 0
    population_favorable = None
    # indicateurs 1
    if not data.path("indicateurs.rémunérations.non_calculable"):
        result = data.path("indicateurs.rémunérations.résultat")
        note = compute_note(result, REMUNERATIONS_THRESHOLDS)
        if note is not None:
            if note != 40:
                # note=40 would mean equality
                population_favorable = data.path(
                    "indicateurs.rémunérations.population_favorable"
                )
            maximum += 40
            data["indicateurs"]["rémunérations"]["note"] = note
            points += note

    # indicateurs 2
    if not data.path("indicateurs.augmentations.non_calculable"):
        note = compute_note(
            data.path("indicateurs.augmentations.résultat"),
            AUGMENTATIONS_HP_THRESHOLDS,
        )
        if note is not None:
            maximum += 20
            indic_favorable = data.path(
                "indicateurs.augmentations.population_favorable"
            )
            if population_favorable and population_favorable != indic_favorable:
                # Cf https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000037964765/ Annexe 5.2
                note = 20
            data["indicateurs"]["augmentations"]["note"] = note
            points += note

    # indicateurs 2et3
    if not data.path("indicateurs.augmentations.non_calculable"):
        # in percent
        percent = compute_note(
            data.path("indicateurs.augmentations_et_promotions.résultat"),
            AUGMENTATIONS_PROMOTIONS_THRESHOLDS,
        )

        if percent is not None:
            data["indicateurs"]["augmentations_et_promotions"][
                "note_en_pourcentage"
            ] = percent
        # in absolute
        absolute = compute_note(
            data.path(
                "indicateurs.augmentations_et_promotions.résultat_nombre_salariés"
            ),
            AUGMENTATIONS_PROMOTIONS_THRESHOLDS,
        )
        if absolute is not None:
            data["indicateurs"]["augmentations_et_promotions"][
                "note_nombre_salariés"
            ] = absolute
        if absolute is not None or percent is not None:
            absolute = absolute or 0
            percent = percent or 0
            note = max(absolute, percent)
            maximum += 35
            indic_favorable = data.path(
                "indicateurs.augmentations_et_promotions.population_favorable"
            )
            if population_favorable and population_favorable != indic_favorable:
                # Cf https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000037964765/ Annexe 5.2
                note = 35
            data["indicateurs"]["augmentations_et_promotions"]["note"] = note
            points += note

    # indicateurs 3
    if not data.path("indicateurs.promotions.non_calculable"):
        note = compute_note(
            data.path("indicateurs.promotions.résultat"), PROMOTIONS_THRESHOLDS
        )
        if note is not None:
            maximum += 15
            indic_favorable = data.path("indicateurs.promotions.population_favorable")
            if population_favorable and population_favorable != indic_favorable:
                # Cf https://www.legifrance.gouv.fr/jorf/id/JORFTEXT000037964765/ Annexe 5.2
                note = 15
            data["indicateurs"]["promotions"]["note"] = note
            points += note

    # indicateurs 4
    if not data.path("indicateurs.congés_maternité.non_calculable"):
        result = data.path("indicateurs.congés_maternité.résultat")
        if result is not None:
            note = 15 if result == 100 else 0
            maximum += 15
            data["indicateurs"]["congés_maternité"]["note"] = note
            points += note

    # indicateurs 5
    note = compute_note(
        data.path("indicateurs.hautes_rémunérations.résultat"),
        HAUTES_REMUNERATIONS_THRESHOLDS,
    )
    if note is not None:
        maximum += 10
        data["indicateurs"]["hautes_rémunérations"]["note"] = note
        points += note

    # Global counts
    data["déclaration"]["points"] = points
    data["déclaration"]["points_calculables"] = maximum
    if maximum >= 75:
        # Make sure to round up halway
        # cf https://stackoverflow.com/a/33019698/
        data["déclaration"]["index"] = math.floor((points / maximum * 100) + 0.5)
