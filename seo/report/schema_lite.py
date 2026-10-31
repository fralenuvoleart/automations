"""Draft-07 subset validator — the keywords `references/findings-schema.json` actually uses.

Stdlib only, so the CI gate stays hermetic (`bash seo/check.sh` with any `python3`). Every keyword
is checked against a strict allowlist: if the schema grows `$ref`, `allOf`, `format` or anything else
not implemented here, validation **fails loudly** instead of silently ignoring the rule — which is
what a general validator would do. Errors carry the same attributes as `jsonschema`'s
(`absolute_path`, `relative_schema_path`, `validator`, `validator_value`, `instance`, `schema`,
`message`, `context`) so `validate_report._schema_messages` formats them unchanged.

Equivalence with `jsonschema` (Draft 7) is pinned by `seo/tests/test_schema_equivalence.py`.
"""
from __future__ import annotations

import re

# Keywords that carry no validation logic (annotations) or that this module implements.
ANNOTATIONS = frozenset({"$schema", "title", "description", "x-message", "definitions"})
KEYWORDS = frozenset({"type", "enum", "pattern", "minimum", "minItems", "required", "properties",
                      "additionalProperties", "items", "dependencies", "anyOf", "oneOf"})


class SchemaUnsupported(Exception):
    """The schema uses a keyword this validator does not implement."""


class Failure:
    """One validation failure, shaped like `jsonschema.exceptions.ValidationError`."""

    __slots__ = ("absolute_path", "relative_schema_path", "validator", "validator_value", "instance",
                 "schema", "message", "context")

    def __init__(self, absolute_path, relative_schema_path, validator, validator_value, instance,
                 schema, message, context=()):
        self.absolute_path = tuple(absolute_path)
        self.relative_schema_path = tuple(relative_schema_path)
        self.validator = validator
        self.validator_value = validator_value
        self.instance = instance
        self.schema = schema
        self.message = message
        self.context = list(context)

    def __repr__(self) -> str:
        return f"Failure({self.validator} at {list(self.absolute_path)}: {self.message})"


def typename(v) -> str:
    """JSON type of a Python value (bool before int, int before float)."""
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    if v is None:
        return "null"
    return type(v).__name__


def _is_type(v, t: str) -> bool:
    if t == "integer":
        return isinstance(v, int) and not isinstance(v, bool)
    if t == "number":
        return isinstance(v, (int, float)) and not isinstance(v, bool)
    if t == "boolean":
        return isinstance(v, bool)
    if t == "string":
        return isinstance(v, str)
    if t == "array":
        return isinstance(v, list)
    if t == "object":
        return isinstance(v, dict)
    if t == "null":
        return v is None
    raise SchemaUnsupported(f"type {t!r}")


def _same(a, b) -> bool:
    """JSON equality — True never matches 1."""
    return typename(a) == typename(b) and a == b


TYPES = ("integer", "number", "boolean", "string", "array", "object", "null")


def check_schema(schema, where: str = "$"):
    """Raise SchemaUnsupported for anything this module cannot enforce *exactly* (recursively).

    A schema that is wrong in a way the validator would skip (tuple-form ``items``, an uncompilable
    ``pattern``, a non-numeric ``minimum``) is rejected here rather than silently ignored later.
    """
    if not isinstance(schema, dict):  # draft-07 boolean schemas: nothing to enforce
        return schema
    for k, v in schema.items():
        if k not in ANNOTATIONS and k not in KEYWORDS:
            raise SchemaUnsupported(f"{where}.{k}")
        if k == "properties":
            for pk, pv in v.items():
                check_schema(pv, f"{where}.properties.{pk}")
        elif k == "pattern":
            try:
                re.compile(v)
            except (re.error, TypeError) as e:
                raise SchemaUnsupported(f"{where}.pattern {v!r} does not compile ({e})") from e
        elif k == "enum":
            if not isinstance(v, list) or not v:
                raise SchemaUnsupported(f"{where}.enum must be a non-empty list")
        elif k == "minimum":
            if not _is_type(v, "number"):
                raise SchemaUnsupported(f"{where}.minimum must be a number")
        elif k == "items":
            if not isinstance(v, dict):  # tuple validation ("items": [schema, …]) is not implemented
                raise SchemaUnsupported(f"{where}.items (one schema only, not a tuple of schemas)")
            check_schema(v, f"{where}.items")
        elif k == "additionalProperties":
            if isinstance(v, dict):
                check_schema(v, f"{where}.additionalProperties")
            elif not isinstance(v, bool):
                raise SchemaUnsupported(f"{where}.additionalProperties (true, false or a schema)")
        elif k in ("anyOf", "oneOf"):
            if not isinstance(v, list) or not v:
                raise SchemaUnsupported(f"{where}.{k} must be a non-empty list")
            for i, sub in enumerate(v):
                check_schema(sub, f"{where}.{k}[{i}]")
        elif k == "dependencies":
            for dk, need in v.items():
                if not isinstance(need, list) or not all(isinstance(x, str) for x in need):
                    raise SchemaUnsupported(f"{where}.dependencies.{dk} (property dependencies only)")
        elif k == "required":
            if not isinstance(v, list) or not all(isinstance(x, str) for x in v):
                raise SchemaUnsupported(f"{where}.required must be a list of property names")
        elif k == "minItems":
            if not _is_type(v, "integer"):
                raise SchemaUnsupported(f"{where}.minItems must be an integer")
        elif k == "type":
            for t in (v if isinstance(v, list) else [v]):
                if t not in TYPES:
                    raise SchemaUnsupported(f"{where}.type {t!r}")
    return schema


def iter_errors(instance, schema):
    """Yield every Failure for `instance` under `schema` (annotations ignored)."""
    yield from _walk(instance, schema, (), ())


def _walk(v, s: dict, ap: tuple, rp: tuple):
    if not isinstance(s, dict):
        return
    # literal keywords, in the order jsonschema evaluates them
    if "type" in s:
        want = s["type"] if isinstance(s["type"], list) else [s["type"]]
        if not any(_is_type(v, t) for t in want):
            yield Failure(ap, rp + ("type",), "type", s["type"], v, s,
                          f"{v!r} is not of type {', '.join(repr(t) for t in want)}")
    if "enum" in s and not any(_same(v, o) for o in s["enum"]):
        yield Failure(ap, rp + ("enum",), "enum", s["enum"], v, s, f"{v!r} is not one of {s['enum']!r}")
    if "pattern" in s and isinstance(v, str) and re.search(s["pattern"], v) is None:
        yield Failure(ap, rp + ("pattern",), "pattern", s["pattern"], v, s,
                      f"{v!r} does not match {s['pattern']!r}")
    if "minimum" in s and _is_type(v, "number") and v < s["minimum"]:
        yield Failure(ap, rp + ("minimum",), "minimum", s["minimum"], v, s,
                      f"{v!r} is less than the minimum of {s['minimum']!r}")

    if isinstance(v, dict):
        for r in s.get("required") or []:
            if r not in v:
                yield Failure(ap, rp + ("required",), "required", s["required"], v, s,
                              f"{r!r} is a required property")
        props = s.get("properties") or {}
        for k, sub in props.items():
            if k in v:
                yield from _walk(v[k], sub, ap + (k,), rp + ("properties", k))
        for dk, need in (s.get("dependencies") or {}).items():
            if dk in v:
                for n in need:
                    if n not in v:
                        yield Failure(ap, rp + ("dependencies",), "dependencies", s["dependencies"], v, s,
                                      f"{n!r} is a dependency of {dk!r}")
        extra = s.get("additionalProperties")
        if extra is not None:
            for k, item in v.items():
                if k in props:
                    continue
                if extra is False:
                    yield Failure(ap, rp + ("additionalProperties",), "additionalProperties", extra, v, s,
                                  f"Additional properties are not allowed ({k!r} was unexpected)")
                elif isinstance(extra, dict):
                    yield from _walk(item, extra, ap + (k,), rp + ("additionalProperties",))

    if isinstance(v, list):
        if "minItems" in s and len(v) < s["minItems"]:
            yield Failure(ap, rp + ("minItems",), "minItems", s["minItems"], v, s, f"{v!r} is too short")
        sub = s.get("items")
        if isinstance(sub, dict):
            for i, item in enumerate(v):
                yield from _walk(item, sub, ap + (i,), rp + ("items",))

    for key in ("anyOf", "oneOf"):  # applicators: one error at the parent path, branches in `context`
        if key not in s:
            continue
        subs = s[key]
        found = [list(_walk(v, sub, ap, (i,) + ())) for i, sub in enumerate(subs)]
        ok = [not f for f in found]
        if (key == "anyOf" and not any(ok)) or (key == "oneOf" and sum(ok) != 1):
            yield Failure(ap, rp + (key,), key, subs, v, s,
                          f"{v!r} is not valid under any of the given schemas"
                          if key == "anyOf" else f"{v!r} is valid under {sum(ok)} of the given schemas",
                          context=[e for f in found for e in f])
