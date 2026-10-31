"""Tests for seo/report/schema_lite.py — the Draft-07 subset the findings contract relies on."""
import json
import sys
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO / "report"))
sys.path.insert(0, str(SEO / "tests"))

import schema_lite  # noqa: E402
import validate_report  # noqa: E402
from _runner import main  # noqa: E402

SCHEMA = json.loads((SEO / "references" / "findings-schema.json").read_text())
GOOD = json.loads((SEO / "tests" / "fixtures" / "findings_example.json").read_text())


def _errors(instance, schema=None):
    return list(schema_lite.iter_errors(instance, SCHEMA if schema is None else schema))


def test_integer_excludes_boolean():
    # bool is an int in Python: `{"type": "integer"}` must still reject True
    assert [e.validator for e in _errors(True, {"type": "integer"})] == ["type"]
    assert _errors(3, {"type": "integer"}) == []
    assert _errors(3.0, {"type": "number"}) == []
    assert [e.validator for e in _errors(3.0, {"type": "integer"})] == ["type"]


def test_enum_is_type_aware():
    schema = {"enum": [1, "a"]}
    assert _errors(True, schema), "True must not match 1"
    assert _errors(1, schema) == [] and _errors("a", schema) == []


def test_pattern_is_a_search_not_a_full_match():
    # JSON Schema `pattern` is unanchored: 'b' matches 'abc'
    assert _errors("abc", {"type": "string", "pattern": "b"}) == []
    assert [e.validator for e in _errors("abc", {"pattern": "^b$"})] == ["pattern"]


def test_additional_properties_accepts_a_schema_or_false():
    as_schema = {"type": "object", "properties": {"a": {"type": "string"}},
                 "additionalProperties": {"type": "number"}}
    assert _errors({"a": "x", "b": 1}, as_schema) == []
    assert [e.validator for e in _errors({"b": "not a number"}, as_schema)] == ["type"]
    closed = {"type": "object", "properties": {"a": {"type": "string"}}, "additionalProperties": False}
    assert [e.validator for e in _errors({"a": "x", "z": 1}, closed)] == ["additionalProperties"]


def test_nested_keywords_report_the_full_paths():
    schema = {"type": "object", "properties": {"rows": {"type": "array", "items": {"type": "object",
              "additionalProperties": {"type": "string"}}}}}
    err = _errors({"rows": [{"a": "ok"}, {"a": 1}]}, schema)[0]
    assert list(err.absolute_path) == ["rows", 1, "a"]
    assert list(err.relative_schema_path) == ["properties", "rows", "items", "additionalProperties", "type"]
    assert err.validator == "type" and err.validator_value == "string" and err.instance == 1


def test_allowlist_rejects_keywords_it_cannot_enforce():
    bad = [
        {"$ref": "#/definitions/x"}, {"allOf": []}, {"type": "string", "format": "date"},
        {"if": {}, "then": {}}, {"const": 1}, {"propertyNames": {}},
        {"items": [{"type": "string"}]},                 # tuple validation: not implemented
        {"pattern": "[unclosed"},                        # would raise re.error at validation time
        {"minimum": "0"},                                # would raise TypeError on comparison
        {"enum": "not-a-list"}, {"anyOf": []},
        {"additionalProperties": "yes"}, {"minItems": "1"},
    ]
    for schema in bad:
        try:
            schema_lite.check_schema(schema)
        except schema_lite.SchemaUnsupported:
            continue
        raise AssertionError(f"{schema} should be rejected as unsupported")


def test_the_real_schema_is_fully_implemented():
    schema_lite.check_schema(SCHEMA)  # raises SchemaUnsupported if the schema grows an unimplemented keyword
    assert _errors(GOOD) == []


def test_failures_format_through_the_report_layer():
    """OneOf/anyOf branch errors must reach validate_report's x-message formatter intact."""
    cases = {
        "missing required key: impact": {**GOOD, "actions": [{"action": "x"}]},
        "unknown key 'extra'": {**GOOD, "actions": [{"action": "x", "impact": "high",
                                                     "effort": "low", "extra": 1}]},
        "window needs both compareStartDate and compareEndDate": {
            **GOOD, "window": {**GOOD["window"], "compareStartDate": "2026-09-01"}},
        "table cells must be scalars": {**GOOD, "sections": [{"heading": "H", "body": "b",
                                                             "table": [{"a": {"n": 1}}]}]},
        "missing required key: affects": {**GOOD, "unavailable": [{"source": "x"}]},
    }
    for expect, findings in cases.items():
        issues = validate_report.validate_structure(findings)
        assert any(expect in i for i in issues), (expect, issues)


def test_broken_schema_fails_loudly_in_the_report_layer():
    original = validate_report.SCHEMA_PATH
    tmp = Path(original).with_suffix(".broken.json")
    schema = json.loads(Path(original).read_text())
    schema["properties"]["sections"] = {"$ref": "#/definitions/Section"}
    tmp.write_text(json.dumps(schema))
    validate_report.SCHEMA_PATH = tmp
    try:
        issues = validate_report.validate_structure(GOOD)
    finally:
        validate_report.SCHEMA_PATH = original
        tmp.unlink()
    assert issues and "unsupported keyword" in issues[0] and "$ref" in issues[0], issues


if __name__ == "__main__":
    main(globals())
