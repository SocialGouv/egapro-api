from datetime import date, datetime, timezone

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
            flatten(b[j], prefix + j, delim, val)
    elif flatten_lists and isinstance(b, list):
        get = b
        for j in range(len(get)):
            flatten(get[j], prefix + delim + str(j), delim, val)
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
