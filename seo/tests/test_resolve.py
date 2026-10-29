"""Tests for seo/resolve.py — registry integrity, arg validation, and drift guards.

Run:  python3 -m pytest seo/tests -q
"""
import contextlib
import io
import json
import sys
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))

import resolve  # noqa: E402


def test_display_renders_args_and_runtime():
    cap = {"server": "s", "tool": "t", "args": {"a": 1}, "runtime": ["b"]}
    assert resolve.display(cap) == '`s` → `t` {"a": 1} (supply: b)'


def test_display_without_args_or_runtime():
    assert resolve.display({"server": "s", "tool": "t"}) == "`s` → `t`"


def test_check_type_accepts_and_rejects():
    assert resolve._check_type("c", "k", "x", {"type": "string"}) == 0
    assert resolve._check_type("c", "k", True, {"type": "boolean"}) == 0
    assert resolve._check_type("c", "k", ["a"], {"type": "array"}) == 0

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert resolve._check_type("c", "k", 5, {"type": "string"}) == 1
        assert resolve._check_type("c", "k", "z", {"type": "string", "enum": ["x"]}) == 1
    assert "ERROR" in buf.getvalue()


def test_bool_is_not_number():
    # bool is a subclass of int; the validator must reject it for numeric types.
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert resolve._check_type("c", "k", True, {"type": "integer"}) == 1


def test_validate_args_required_coverage():
    schema = {"properties": {"a": {"type": "string"}}, "required": ["a"]}
    assert resolve._validate_args("c", {"server": "s", "tool": "t", "args": {}, "runtime": ["a"]}, schema) == 0

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        n = resolve._validate_args("c", {"server": "s", "tool": "t", "args": {}, "runtime": []}, schema)
    assert n == 1 and "required" in buf.getvalue()


def test_balanced_json_handles_nesting_and_strings():
    text = 'x `t` {"a": {"b": 1}, "c": "}"} tail'
    start = text.index("{")
    assert resolve._balanced_json(text, start) == '{"a": {"b": 1}, "c": "}"}'


def test_registry_integrity():
    data, caps, disp, alias = resolve.load()
    assert caps, "registry has no capabilities"
    for cid, c in caps.items():
        assert c["server"] in data["servers"], f"{cid}: unknown server {c['server']}"
        assert isinstance(c["tool"], str) and c["tool"], f"{cid}: bad tool"
        assert isinstance(c.get("args", {}), dict), f"{cid}: args must be an object"
        assert isinstance(c.get("runtime", []), list), f"{cid}: runtime must be a list"
        assert isinstance(c.get("aliases", []), list), f"{cid}: aliases must be a list"
        assert cid in disp


def test_aliases_are_unique():
    _, _, _, alias = resolve.load()
    seen = {}
    for a in alias:
        assert a not in seen, f"alias {a} mapped twice"
        seen[a] = True


def test_no_camelcase_filter_keys():
    """GA4 Data API MCP serializes protobuf -> snake_case keys (guards H-1)."""
    _, caps, _, _ = resolve.load()
    forbidden = {"fieldName", "inListFilter", "stringFilter", "numericFilter", "betweenFilter", "emptyFilter"}

    def walk(o, cid):
        if isinstance(o, dict):
            for k, v in o.items():
                assert k not in forbidden, f"{cid}: camelCase key {k!r} in args"
                walk(v, cid)
        elif isinstance(o, list):
            for v in o:
                walk(v, cid)

    for cid, c in caps.items():
        walk(c.get("args", {}), cid)


def test_expanded_specs_match_registry():
    """Guards H-2: every `tool` {json} in a skill must equal a registry capability."""
    assert resolve.check_expanded() == 0


def test_tool_map_matches_registry():
    """tool-map.md must be a faithful render of the registry."""
    _, caps, disp, _ = resolve.load()
    map_text = (SEO / "tool-map.md").read_text()
    for cid in caps:
        assert f"| `{cid}` | {disp[cid]} |" in map_text, f"tool-map.md stale for {cid}"


def _run_all() -> int:
    """Run every test_* function without requiring pytest."""
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"{len(fns) - failed}/{len(fns)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
