"""Tests for seo/resolve.py — registry integrity, rendering round-trips, semantic and schema checks."""
import contextlib
import copy
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

SEO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SEO))
sys.path.insert(0, str(SEO / "tests"))

import resolve  # noqa: E402
from _runner import main  # noqa: E402

SAMPLE = """---
name: seo-demo
---
## Data Sources
{{include:datasources}}

## Workflow
{{include:evidence days=28 flags=--compare}}

1. Pull {{cap:gsc.page}} then {{cap:gsc.query}}; profile {{site:priority_pages}}.

## Configuration
{{include:configuration}}
"""


def _quiet(fn, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*a, **k)
    return rc, buf.getvalue()


def test_display_renders_args_and_runtime():
    cap = {"server": "s", "tool": "t", "args": {"a": 1}, "runtime": ["b"]}
    assert resolve.display(cap) == '`s` → `t` {"a": 1} (supply: b)'
    assert resolve.display({"server": "s", "tool": "t"}) == "`s` → `t`"


def test_registry_integrity():
    data, caps, disp, alias = resolve.load()
    assert data["version"] >= 7
    for cid, c in caps.items():
        assert c["server"] in data["servers"], f"{cid}: unknown server {c['server']}"
        assert isinstance(c["tool"], str) and c["tool"]
        assert isinstance(c.get("args", {}), dict) and isinstance(c.get("runtime", []), list)
        assert c.get("desc"), f"{cid}: missing desc (rendered into Data Sources tables)"
    assert len(alias) == len(set(alias))


def test_render_is_idempotent_and_expands_tokens():
    once = resolve.render(SAMPLE, "seo-demo")
    assert "{{cap:" not in once and "{{include:" not in once and "{{site:" not in once
    assert "<!--cap:gsc.page-->`search-console` → `analytics_query`" in once
    assert "| `gsc.page` |" in once and "| `gsc.query` |" in once          # generated table
    assert "--days 28 --compare --out-dir" in once                      # include attrs
    assert resolve.render(once, "seo-demo") == once


def test_registry_change_propagates_on_rerender():
    """H4: editing the registry must update already-rendered skills (no hand edits)."""
    data = resolve.load()[0]
    once = resolve.render(SAMPLE, "seo-demo", data)
    changed = copy.deepcopy(data)
    changed["capabilities"]["gsc.page"]["args"]["rowLimit"] = 1234
    again = resolve.render(once, "seo-demo", changed)
    assert '"rowLimit": 1234' in again and again != once


def test_tool_rename_via_alias_does_not_corrupt():
    """H4: an aliased legacy name becomes a clean block — no doubled server prefix."""
    data = copy.deepcopy(resolve.load()[0])
    data["capabilities"]["gsc.sites_list"].update(tool="sites_list_v2", aliases=["sites_list_legacy"])
    text = resolve.render("Use `sites_list_legacy` and {{cap:gsc.sites_list}}.", "seo-demo", data)
    assert text.count("`search-console` → `sites_list_v2`") == 2
    assert "`search-console` → `search-console`" not in text


def test_check_passes_on_repo_and_detects_stale_blocks():
    rc, out = _quiet(resolve.check)
    assert rc == 0, out
    tmp = Path(tempfile.mkdtemp())
    try:
        skills = tmp / "skills"
        shutil.copytree(SEO.parent / ".agents" / "skills" / "seo-audit", skills / "seo-audit")
        f = skills / "seo-audit" / "SKILL.md"
        f.write_text(f.read_text().replace('"rowLimit": 25000', '"rowLimit": 1000', 1))
        rc, out = _quiet(resolve.check, skills)
        assert rc == 1 and "STALE" in out
    finally:
        shutil.rmtree(tmp)


def test_check_flags_unrendered_tokens():
    tmp = Path(tempfile.mkdtemp())
    try:
        d = tmp / "skills" / "seo-x"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("call {{cap:gsc.page}}\n")
        rc, out = _quiet(resolve.check, tmp / "skills")
        assert rc == 1 and "unrendered" in out
    finally:
        shutil.rmtree(tmp)


def test_semantics_require_rowlimit_engine_and_reject_deprecated_metrics():
    caps = copy.deepcopy(resolve.load()[1])
    assert _quiet(resolve.check_semantics, caps)[0] == 0
    caps["gsc.query"]["args"].pop("rowLimit")
    caps["gsc.page"]["args"].pop("engine")
    caps["ga4.channels"]["args"]["metrics"].append("conversions")
    caps["ga4.referrals"]["args"]["dimension_filter"]["filter"]["string_filter"]["match_type"] = "LIKE"
    n, out = _quiet(resolve.check_semantics, caps)
    assert n == 4, out
    assert "rowLimit" in out and "engine" in out and "conversions" in out and "match_type" in out


def test_validate_args_and_types():
    schema = {"properties": {"a": {"type": "string"}, "b": {"anyOf": [{"type": "integer"}, {"type": "string"}]}},
              "required": ["a"]}
    assert _quiet(resolve._validate_args, "c", {"server": "s", "tool": "t", "args": {}, "runtime": ["a", "b"]}, schema)[0] == 0
    n, out = _quiet(resolve._validate_args, "c", {"server": "s", "tool": "t", "args": {}, "runtime": []}, schema)
    assert n == 1 and "required" in out
    assert _quiet(resolve._check_type, "c", "k", True, {"type": "integer"})[0] == 1  # bool is not a number


def test_validate_cached_passes():
    rc, out = _quiet(resolve.validate_cached)
    assert rc == 0, out


def test_tool_map_matches_registry():
    _, caps, disp, _ = resolve.load()
    text = (SEO / "tool-map.md").read_text()
    for cid in caps:
        assert f"| `{cid}` | {disp[cid]} |" in text, f"tool-map.md stale for {cid}"


def test_every_capability_is_used_by_a_skill():
    _, caps, _, _ = resolve.load()
    used = set()
    for f in resolve.skill_files():
        used |= set(resolve.caps_used(f.read_text()))
    assert set(caps) == used, f"unused: {sorted(set(caps) - used)}"


if __name__ == "__main__":
    main(globals())
