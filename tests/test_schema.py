from egapro.schema import load


def test_basic_object():
    raw = """
$schema: http:foo.bar
key1:
    subkey: integer
    subkey2: date-time
"""
    schema = load(raw)
    assert schema == {
        "$schema": "http:foo.bar",
        "type": "object",
        "properties": {
            "key1": {
                "type": "object",
                "properties": {
                    "subkey": {"type": "integer"},
                    "subkey2": {"format": "date-time", "type": "string"},
                },
            }
        },
    }


def test_basic_list():
    raw = "key1: [integer]"
    schema = load(raw)
    assert schema == {
        "type": "object",
        "properties": {
            "key1": {
                "items": {"type": "integer"},
                "type": "array",
            },
        },
    }


def test_required():
    raw = "+key1: integer"
    schema = load(raw)
    assert schema == {
        "type": "object",
        "properties": {
            "key1": {
                "type": "integer",
            },
        },
        "required": ["key1"],
    }


def test_nullable():
    raw = "?key1: integer"
    schema = load(raw)
    assert schema == {
        "type": "object",
        "properties": {
            "key1": {"anyOf": [{"type": "null"}, {"type": "integer"}]},
        },
    }


def test_strict():
    raw = """
=key1:
    subkey: integer
"""
    schema = load(raw)
    assert schema == {
        "type": "object",
        "properties": {
            "key1": {
                "type": "object",
                "properties": {"subkey": {"type": "integer"}},
                "additionalProperties": False,
            },
        },
    }
