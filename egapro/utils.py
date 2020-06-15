from datetime import datetime, timezone


def utcnow():
    return datetime.now(timezone.utc)


def prepare_query(query):
    # TODO deal with edge cases ( | , !…)
    query = query.replace("  ", " ").replace(" ", " & ")
    if not query.endswith("*"):
        # Prefix search on last token, to autocomplete.
        query = query + ":*"
    return query


def flatten(b, prefix="", delim="/", val=None):
    "See https://stackoverflow.com/a/57228641/330911"
    if val is None:
        val = {}
    if isinstance(b, dict):
        for j in b.keys():
            flatten(b[j], prefix + delim + j, delim, val)
    elif isinstance(b, list):
        get = b
        for j in range(len(get)):
            key = str(j)
            if isinstance(get[j], dict):
                if "key" in get[j]:
                    key = get[j]["key"]
            flatten(get[j], prefix + delim + key, delim, val)
    else:
        val[prefix] = b
    return val
