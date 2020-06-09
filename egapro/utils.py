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
